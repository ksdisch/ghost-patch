"""test_m3.py — pre-committed M3 logic, TDD'd before any paid call (docs/M3-BRIEF.md).

Covers the pure core: T2-damaged entry subsets + start-state provenance, the
per-pass seed convention, trajectory classification (escaped/deepened/held/improved),
loop outcomes with the three-cause INVALID taxonomy, escape-curve math,
REPORTED/UNDERPOWERED labels, the generation floor, wave estimates, the frozen
M3 prompt template, and the synthetic dry-run fixtures.
"""
from __future__ import annotations

from m3 import (
    CAUSE_ANCHOR,
    CAUSE_PARSE,
    CAUSE_REJECTED,
    DRAFT_EST,
    REPAIR_EST,
    damaged_subset,
    gen_floor_ok,
    m3_outcomes,
    mean_failed_by_pass,
    model_verdict_m3,
    pass_seed,
    start_index,
    trajectory,
    wave_estimate_m3,
    _synthetic,
)
from prompts import m2_repair_prompt, m3_repair_prompt

DS = "deepseek/deepseek-chat-v3.1"
QW = "qwen/qwen3-coder-30b-a3b-instruct"


def _t2(model, pid, damaged, **kw):
    return {"model": model, "problem_id": pid, "arm": "T2", "repair_success": False,
            "damaged": damaged, "patch": f"code-{pid}",
            "graded": {"passed": 2, "failed": 4}, **kw}


# ---------- entry subsets (frozen rule: graded, valid, damaged T2; bank order) ----------

def test_damaged_subset_filters_and_orders_by_bank():
    bank_order = ["p1", "p2", "p3", "p4", "p5", "p6"]
    recs = [
        _t2(DS, "p4", True),
        _t2(DS, "p1", False),                                          # undamaged
        _t2(DS, "p2", True),
        _t2(QW, "p3", True),                                           # other model
        {"model": DS, "problem_id": "p5", "arm": "T3", "repair_success": False,
         "damaged": True},                                             # wrong arm
        {"model": DS, "problem_id": "p6", "arm": "T2", "invalid": "no parse"},
    ]
    assert damaged_subset(recs, DS, bank_order) == ["p2", "p4"]


def test_damaged_subset_later_record_wins_and_ungraded_never_enter():
    recs = [_t2(DS, "p1", True), _t2(DS, "p1", False),
            {"model": DS, "problem_id": "p2", "arm": "T2", "patch": "x"}]
    assert damaged_subset(recs, DS, ["p1", "p2"]) == []


def test_start_index_labels_provenance_and_carries_grade_and_patch():
    m1 = [_t2(DS, "p1", True)]
    ext = [_t2(DS, "p9", True, graded={"passed": 1, "failed": 7})]
    idx = start_index(m1, ext, DS)
    assert idx["p1"] == {"source": "m1", "start_failed": 4, "patch": "code-p1"}
    assert idx["p9"] == {"source": "extension", "start_failed": 7, "patch": "code-p9"}


def test_start_index_ignores_undamaged_and_other_models():
    idx = start_index([_t2(DS, "p1", False), _t2(QW, "p2", True)], [], DS)
    assert idx == {}


# ---------- per-pass seeding ----------

def test_pass_seed_convention():
    assert pass_seed("p03001", 4) == "p03001#p4"


# ---------- trajectory classification ----------

def test_trajectory_classes():
    assert trajectory(start_failed=4, final_failed=0, escaped=True) == "escaped"
    assert trajectory(4, 6, False) == "deepened"
    assert trajectory(4, 4, False) == "held"
    assert trajectory(4, 2, False) == "improved"


# ---------- loop outcomes + INVALID taxonomy ----------

def _grade0(model, pid, start_failed, source="m1"):
    return {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
            "baseline_ok": True, "start_source": source, "start_failed": start_failed,
            "graded": {"passed": 6 - start_failed, "failed": start_failed},
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                        "stdout": "0"}]}


def _pass(model, pid, k, failed, *, gen_cost=0.001):
    return {"model": model, "problem_id": pid, "pass": k, "first_parse": True,
            "patch": f"p{k}", "cost": 0.0015, "finish_reason": "stop",
            "gen": {"target": [1, 1], "attempts": 1, "first_attempt_accepted": True,
                    "cost": gen_cost, "drift_ratio": 0.9},
            "feedback": {"test_index": 0}, "recovered": failed == 0, "comply": True,
            "graded": {"passed": 6 - failed, "failed": failed},
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": failed == 0,
                        "stdout": "1"}]}


def _invalid(model, pid, k, cause):
    return {"model": model, "problem_id": pid, "pass": k, "invalid": cause,
            "cost": 0.0, "gen": {"cost": 0.001}}


BASE = {"a": 2, "b": 2, "c": 2, "d": 2, "e": 2}


def _fixture_records():
    recs = []
    # a: escapes at pass 2 (pass 1 dips below baseline: ever_below)
    recs += [_grade0(DS, "a", 4), _pass(DS, "a", 1, 5), _pass(DS, "a", 2, 0)]
    # b: exhausted, deepened (start 3 -> final 6), always below baseline
    recs += [_grade0(DS, "b", 3)] + [_pass(DS, "b", k, 6) for k in range(1, 6)]
    # c: invalid parse at pass 2
    recs += [_grade0(DS, "c", 4), _pass(DS, "c", 1, 4),
             {"model": DS, "problem_id": "c", "pass": 2, "invalid": CAUSE_PARSE,
              "first_parse": False, "cost": 0.001, "gen": {"cost": 0.001}}]
    # d: invalid anchor at pass 1
    recs += [_grade0(DS, "d", 5), _invalid(DS, "d", 1, CAUSE_ANCHOR)]
    # e: exhausted, improved (start 4 -> final 1, above baseline-relative floor)
    recs += [_grade0(DS, "e", 4)] + [_pass(DS, "e", k, 1) for k in range(1, 6)]
    return recs


def test_m3_outcomes_statuses_and_trajectories():
    out = m3_outcomes(_fixture_records(), DS, list(BASE), BASE)
    assert out["a"]["status"] == "escaped" and out["a"]["escaped_at"] == 2
    assert out["a"]["trajectory"] == "escaped" and out["a"]["ever_below"] is True
    assert out["b"]["status"] == "exhausted" and out["b"]["trajectory"] == "deepened"
    assert out["b"]["final_below"] is True and out["b"]["final_failed"] == 6
    assert out["c"]["status"] == "invalid" and out["c"]["invalid_cause"] == CAUSE_PARSE
    assert out["d"]["invalid_cause"] == CAUSE_ANCHOR
    assert out["e"]["trajectory"] == "improved" and out["e"]["final_below"] is False
    assert out["e"]["ever_below"] is False


def test_m3_outcomes_unfinished_states():
    recs = [_grade0(DS, "a", 4)]  # graded but no passes yet
    out = m3_outcomes(recs, DS, ["a", "b"], {"a": 2, "b": 2})
    assert out["a"]["status"] == "active"
    assert out["b"]["status"] == "todo"


def test_m3_outcomes_start_failed_carried():
    out = m3_outcomes(_fixture_records(), DS, list(BASE), BASE)
    assert out["b"]["start_failed"] == 3 and out["d"]["start_failed"] == 5


# ---------- verdict block ----------

def test_model_verdict_reported_with_curve_and_causes():
    out = m3_outcomes(_fixture_records(), DS, list(BASE), BASE)
    v = model_verdict_m3(out)
    assert v["clean_n"] == 3 and v["escaped"] == 1
    assert v["curve"] == [0, 1, 1, 1, 1]          # cumulative escapes by pass
    assert v["label"] == "UNDERPOWERED"           # clean 3 < 20
    assert v["invalid"] == 2
    assert v["invalid_by_cause"] == {CAUSE_PARSE: 1, CAUSE_REJECTED: 0, CAUSE_ANCHOR: 1}
    assert v["deepened"] == 1 and v["improved"] == 1 and v["held"] == 0
    assert v["final_below"] == 1 and v["ever_below"] == 2
    assert v["unfinished"] == 0


def test_model_verdict_reported_label_at_20_clean():
    recs = []
    pids, bases = [], {}
    for i in range(20):
        pid = f"r{i:02d}"
        pids.append(pid); bases[pid] = 2
        recs += [_grade0(DS, pid, 4), _pass(DS, pid, 1, 0)]
    v = model_verdict_m3(m3_outcomes(recs, DS, pids, bases))
    assert v["label"] == "REPORTED" and v["escaped"] == 20 and v["pass1_escaped"] == 20


# ---------- mean failed by pass (descriptive damage curve) ----------

def test_mean_failed_by_pass_over_active_loops():
    recs = _fixture_records()
    means = mean_failed_by_pass(recs, DS, ["a", "b", "e"])
    # pass 1: a=5, b=6, e=1 -> 4.0 ; pass 2: a=0, b=6, e=1 -> 7/3
    assert means[0] == 4.0
    assert abs(means[1] - 7 / 3) < 1e-4  # stats are stored rounded to 4dp
    # passes 3-5: only b and e remain -> 3.5
    assert means[2] == means[3] == means[4] == 3.5


# ---------- generation floor + wave estimate ----------

def test_gen_floor_only_fires_at_20_plus_passes():
    assert gen_floor_ok(5, 19) is True         # below min N: never fires
    assert gen_floor_ok(12, 20) is True        # 60% exactly
    assert gen_floor_ok(11, 20) is False


def test_wave_estimate_counts_remaining_passes_at_full_rate():
    recs = [_grade0(DS, "a", 4), _pass(DS, "a", 1, 3)]   # active: 4 passes left
    out = m3_outcomes(recs, DS, ["a", "b"], {"a": 2, "b": 2})   # b: todo, 5 left
    est = wave_estimate_m3(out, DS)
    assert abs(est - 9 * (REPAIR_EST[DS] + DRAFT_EST)) < 1e-9


# ---------- the frozen M3 prompt ----------

FB = {"test_index": 0, "input": "1 2", "expected": "3", "actual": "4"}


def test_m3_prompt_is_m2_prompt_with_instruction_block():
    m2p = m2_repair_prompt("desc", "x = 1", FB)
    m3p = m3_repair_prompt("desc", "x = 1", FB, "The bug is in line 9 (`x`). Fix it.")
    assert m3p == m2p.replace(
        "# Task\nDiagnose the bug on your own and fix it.",
        "# Reviewer diagnosis\nThe bug is in line 9 (`x`). Fix it.")


def test_m3_prompt_block_order_is_papers():
    p = m3_repair_prompt("DESC", "CODE = 1", FB, "INSTR")
    order = [p.index("# Problem"), p.index("# Current program"),
             p.index("# Most recent failing test"), p.index("# Reviewer diagnosis"),
             p.index("Reply with the complete corrected program")]
    assert order == sorted(order)
    assert "Diagnose the bug on your own" not in p


# ---------- synthetic dry-run fixtures ----------

def test_synthetic_covers_labels_and_all_invalid_causes():
    records, subsets, baselines = _synthetic()
    labels, causes = set(), set()
    for model, subset in subsets.items():
        v = model_verdict_m3(m3_outcomes(records, model, subset, baselines[model]))
        labels.add(v["label"])
        causes.update(c for c, n in v["invalid_by_cause"].items() if n)
        assert v["unfinished"] == 0
    assert labels == {"REPORTED", "UNDERPOWERED"}
    assert causes == {CAUSE_PARSE, CAUSE_REJECTED, CAUSE_ANCHOR}
