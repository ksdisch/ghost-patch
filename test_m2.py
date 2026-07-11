"""test_m2.py — pre-committed M2 logic, TDD'd before any paid call (docs/M2-BRIEF.md).

Covers the pure core: entry-subset extraction, feedback-block building (D8-A full
report: truncation, status markers, first-failing pick), loop-state reconstruction
for resume, recovery/INVALID classification, curve math, REPORTED/UNDERPOWERED
labels + the FLOOR flag, and the synthetic dry-run fixtures.
"""
from __future__ import annotations

import json

from sandbox import TestRun as SandboxRun  # alias: pytest must not collect it

from m2 import (
    FIELD_CAP,
    actual_output,
    detail_from_runs,
    failed_t3_subset,
    feedback_fields,
    first_failing,
    truncate_field,
)

DS = "deepseek/deepseek-chat-v3.1"
QW = "qwen/qwen3-coder-30b-a3b-instruct"


def _t3(model, pid, success):
    return {"model": model, "problem_id": pid, "arm": "T3", "repair_success": success}


# ---------- entry subset (frozen rule: graded-and-failed T3, bank order) ----------

def test_failed_t3_subset_filters_and_orders_by_bank():
    bank_order = ["p1", "p2", "p3", "p4", "p5"]
    recs = [
        _t3(DS, "p4", False),
        _t3(DS, "p1", True),
        _t3(DS, "p2", False),
        _t3(QW, "p3", False),                                      # other model
        {"model": DS, "problem_id": "p5", "arm": "T2", "repair_success": False},  # wrong arm
        {"model": DS, "problem_id": "p3", "arm": "T3", "invalid": "no parse"},    # INVALID excluded
    ]
    assert failed_t3_subset(recs, DS, bank_order) == ["p2", "p4"]


def test_failed_t3_subset_later_record_wins_on_duplicate_key():
    bank_order = ["p1"]
    recs = [_t3(DS, "p1", False), _t3(DS, "p1", True)]
    assert failed_t3_subset(recs, DS, bank_order) == []


def test_failed_t3_subset_ungraded_rows_never_enter():
    recs = [{"model": DS, "problem_id": "p1", "arm": "T3", "patch": "x = 1"}]
    assert failed_t3_subset(recs, DS, ["p1"]) == []


# ---------- feedback fields (D8-A) ----------

def test_truncate_field_short_passthrough_and_exact_cap():
    assert truncate_field("abc") == "abc"
    s = "x" * FIELD_CAP
    assert truncate_field(s) == s  # boundary: exactly cap, no marker


def test_truncate_field_over_cap_appends_marker():
    s = "x" * (FIELD_CAP + 5)
    out = truncate_field(s)
    assert out.startswith("x" * FIELD_CAP)
    assert out.endswith("… [truncated]")
    assert len(out) == FIELD_CAP + len("… [truncated]")


def test_actual_output_clean_run_is_stdout_only():
    assert actual_output({"rc": 0, "timed_out": False, "stdout": "42\n"}) == "42\n"


def test_actual_output_timeout_marker():
    out = actual_output({"rc": -9, "timed_out": True, "stdout": ""})
    assert out == "[process timed out after 5s]"


def test_actual_output_nonzero_exit_marker_after_stdout():
    out = actual_output({"rc": 1, "timed_out": False, "stdout": "partial"})
    assert out == "partial\n[process exited with code 1]"


def test_actual_output_exit_marker_no_double_newline():
    out = actual_output({"rc": 2, "timed_out": False, "stdout": "a\n"})
    assert out == "a\n[process exited with code 2]"


def test_first_failing_picks_lowest_index_and_none_when_all_pass():
    detail = [{"i": 0, "passed": True}, {"i": 1, "passed": False}, {"i": 2, "passed": False}]
    assert first_failing(detail) == 1
    assert first_failing([{"i": 0, "passed": True}]) is None


def test_detail_from_runs_grades_and_caps_stdout():
    runs = [
        SandboxRun(rc=0, stdout="42\n", timed_out=False),     # pass
        SandboxRun(rc=0, stdout="7\n", timed_out=False),      # wrong output
        SandboxRun(rc=1, stdout="", timed_out=False),         # exception
        SandboxRun(rc=-9, stdout="y" * (FIELD_CAP + 50), timed_out=True),  # timeout, big stdout
    ]
    tests = [{"input": "", "output": "42"}, {"input": "", "output": "8"},
             {"input": "", "output": "1"}, {"input": "", "output": "z"}]
    counts, detail = detail_from_runs(runs, tests, "exact")
    assert counts == {"passed": 1, "failed": 3}
    assert [d["passed"] for d in detail] == [True, False, False, False]
    assert detail[3]["stdout"].endswith("… [truncated]")
    assert detail[3]["timed_out"] is True
    assert detail[1]["rc"] == 0 and detail[1]["stdout"] == "7\n"


def test_m2_repair_prompt_structure_and_frozen_tail():
    from prompts import m2_repair_prompt, repair_prompt

    fb = {"test_index": 1, "input": "9 9", "expected": "18", "actual": "17\n"}
    p = m2_repair_prompt("Sum the numbers.", "print(1)", fb)
    # blocks in paper order: statement, current code, failing test, task
    assert p.index("# Problem") < p.index("# Current program") \
        < p.index("# Most recent failing test") < p.index("# Task")
    assert "Sum the numbers." in p and "print(1)" in p
    assert p.index("Input:") < p.index("Expected output:") < p.index("Actual output:")
    assert "9 9" in p and "18" in p and "17" in p
    assert "Diagnose the bug on your own and fix it." in p
    # frozen-tail invariance: identical last two lines as the M1/M0 repair prompt,
    # so extract_patch/compile parse machinery carries over untouched
    tail = lambda s: [ln for ln in s.strip().splitlines() if ln.strip()][-2:]
    assert tail(p) == tail(repair_prompt("d", "c", None))


def test_feedback_fields_renders_first_failing_test():
    entry = {"tests": [{"input": "1 2", "output": "3"}, {"input": "9 9", "output": "18"}]}
    detail = [{"i": 0, "rc": 0, "timed_out": False, "stdout": "3\n", "passed": True},
              {"i": 1, "rc": 0, "timed_out": False, "stdout": "17\n", "passed": False}]
    fb = feedback_fields(entry, detail)
    assert fb["test_index"] == 1
    assert fb["input"] == "9 9"
    assert fb["expected"] == "18"
    assert fb["actual"] == "17\n"


# ---------- resume keys + loop-state reconstruction ----------

def _p0(pid="p1", failed=2):
    return {"model": DS, "problem_id": pid, "pass": 0, "cost": 0.0, "baseline_ok": True,
            "graded": {"passed": 3, "failed": failed},
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False, "stdout": "0"}]}


def _pk(k, pid="p1", failed=1, patch="x = 1", recovered=None):
    rec = recovered if recovered is not None else failed == 0
    return {"model": DS, "problem_id": pid, "pass": k, "first_parse": True, "patch": patch,
            "cost": 0.001, "finish_reason": "stop", "feedback": {"test_index": 0},
            "graded": {"passed": 5 - failed, "failed": failed}, "recovered": rec,
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": failed == 0,
                        "stdout": "1"}]}


def test_m2_keys_skips_blank_and_partial_lines():
    from m2 import m2_keys
    lines = [json.dumps(_p0()), "", json.dumps(_pk(1)), json.dumps({"model": DS}), "  "]
    assert m2_keys(lines) == {(DS, "p1", 0), (DS, "p1", 1)}


def test_loop_state_empty_needs_grade0():
    from m2 import loop_state
    assert loop_state([])["status"] == "need_grade0"


def test_loop_state_after_grade0_runs_pass1_from_bank_code():
    from m2 import loop_state
    s = loop_state([_p0()])
    assert s["status"] == "run_pass"
    assert s["next"] == 1
    assert s["code"] is None  # None → caller substitutes the bank's buggy_code
    assert s["detail"][0]["stdout"] == "0"


def test_loop_state_mid_loop_resumes_from_last_patch_even_unsorted():
    from m2 import loop_state
    s = loop_state([_pk(2, patch="x = 2"), _p0(), _pk(1, patch="x = 1")])
    assert s["status"] == "run_pass"
    assert s["next"] == 3
    assert s["code"] == "x = 2"


def test_loop_state_recovered_is_terminal():
    from m2 import loop_state
    s = loop_state([_p0(), _pk(1, failed=0)])
    assert s == {"status": "recovered", "at": 1}


def test_loop_state_invalid_is_terminal():
    from m2 import loop_state
    recs = [_p0(), _pk(1),
            {"model": DS, "problem_id": "p1", "pass": 2, "invalid": "parse failure",
             "first_parse": False, "cost": 0.001}]
    assert loop_state(recs)["status"] == "invalid"


def test_loop_state_five_unrecovered_passes_is_exhausted():
    from m2 import loop_state
    recs = [_p0()] + [_pk(k) for k in range(1, 6)]
    assert loop_state(recs)["status"] == "exhausted"


# ---------- outcomes, curve, labels, FLOOR (the pre-committed verdict core) ----------

def _records_fixture():
    """pA recovered@1 · pB recovered@3 · pC exhausted+damaged · pD invalid@2 · pE active."""
    recs = []
    recs += [_p0("pA"), _pk(1, "pA", failed=0)]
    recs += [_p0("pB"), _pk(1, "pB", failed=3), _pk(2, "pB", failed=1), _pk(3, "pB", failed=0)]
    recs += [_p0("pC")] + [_pk(k, "pC", failed=4) for k in range(1, 6)]   # 4 > baseline 2
    recs += [_p0("pD"), _pk(1, "pD"),
             {"model": DS, "problem_id": "pD", "pass": 2, "invalid": "parse failure",
              "first_parse": False, "cost": 0.001}]
    recs += [_p0("pE"), _pk(1, "pE"), _pk(2, "pE")]
    return recs


BASELINES = {p: 2 for p in ("pA", "pB", "pC", "pD", "pE")}


def test_loop_outcomes_classifies_every_loop():
    from m2 import loop_outcomes
    out = loop_outcomes(_records_fixture(), DS, ["pA", "pB", "pC", "pD", "pE"], BASELINES)
    assert out["pA"] == {"status": "recovered", "recovered_at": 1, "passes_used": 1,
                         "final_failed": 0, "ever_below": False, "damaged_final": False}
    assert out["pB"]["recovered_at"] == 3 and out["pB"]["ever_below"] is True
    assert out["pC"] == {"status": "exhausted", "recovered_at": None, "passes_used": 5,
                         "final_failed": 4, "ever_below": True, "damaged_final": True}
    assert out["pD"]["status"] == "invalid"
    assert out["pE"]["status"] == "active"


def test_loop_outcomes_missing_loop_is_todo():
    from m2 import loop_outcomes
    out = loop_outcomes([], DS, ["pA"], BASELINES)
    assert out["pA"]["status"] == "todo"


def test_recovery_curve_cumulative_over_clean_loops():
    from m2 import loop_outcomes, recovery_curve
    out = loop_outcomes(_records_fixture(), DS, ["pA", "pB", "pC", "pD"], BASELINES)
    clean = {p: o for p, o in out.items() if o["status"] in ("recovered", "exhausted")}
    assert recovery_curve(clean) == [1, 1, 2, 2, 2]


def test_m2_label_underpowered_below_20_clean():
    from m2 import m2_label
    assert m2_label(20) == "REPORTED"
    assert m2_label(19) == "UNDERPOWERED"


def test_floor_flag_thresholds_match_brief():
    from m2 import floor_flag
    assert floor_flag(3, 23) is True    # wilson lo ≈ .045 < .05 → FLOOR
    assert floor_flag(4, 23) is False   # lo ≈ .070
    assert floor_flag(5, 49) is True    # lo ≈ .044
    assert floor_flag(6, 49) is False   # lo ≈ .057
    assert floor_flag(0, 0) is True     # no data: lo = 0


# ---------- synthetic dry-run fixtures + wave estimator ----------

def test_synthetic_fixture_exercises_all_label_paths():
    from m2 import _synthetic, loop_outcomes, model_verdict
    records, subsets, baselines = _synthetic()
    v = {m: model_verdict(loop_outcomes(records, m, subsets[m], baselines[m]))
         for m in subsets}
    rep = v["demo/reported"]
    assert rep["label"] == "REPORTED" and rep["floor"] is False
    assert rep["invalid"] == 1
    assert rep["curve"][-1] == rep["recovered"]
    assert v["demo/underpowered"]["label"] == "UNDERPOWERED"
    assert v["demo/floor"]["label"] == "REPORTED" and v["demo/floor"]["floor"] is True
    assert all(x["unfinished"] == 0 for x in v.values())


def test_wave_estimate_counts_only_remaining_passes():
    from m2 import PASS_EST, loop_outcomes, wave_estimate
    out = loop_outcomes(_records_fixture(), DS, ["pA", "pB", "pC", "pD", "pE", "pF"],
                        {**BASELINES, "pF": 2})
    # pA/pB/pC/pD terminal → 0; pE active with 2 used → 3; pF todo → 5
    assert wave_estimate(out, DS) == round(8 * PASS_EST[DS], 6)


def test_model_verdict_assembles_ceiling_and_secondaries():
    from m2 import loop_outcomes, model_verdict
    out = loop_outcomes(_records_fixture(), DS, ["pA", "pB", "pC", "pD"], BASELINES)
    v = model_verdict(out)
    assert v["clean_n"] == 3 and v["recovered"] == 2
    assert v["label"] == "UNDERPOWERED" and v["floor"] is False
    assert v["curve"] == [1, 1, 2, 2, 2]
    assert v["pass1_recovered"] == 1
    assert v["invalid"] == 1
    assert v["damaged_final"] == 1 and v["ever_below"] == 2  # pB dipped, pC ended below
    assert v["mean_passes"] == 3.0  # (1 + 3 + 5) / 3
    assert v["wilson"][0] < 2 / 3 < v["wilson"][1]
