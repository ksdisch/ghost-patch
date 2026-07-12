"""test_m4.py — pre-committed M4 logic, TDD'd before any paid call (docs/M4-BRIEF.md).

Covers the pure core: entry extraction from M3 finals (exhausted-only, escape/
INVALID excluded) with the D12 class split (damaged vs at-or-below-baseline),
re-cross math (transient counts, pass-0 pair re-crossed by definition), the IDR
block (damaged-16 primary denominator + all-N sensitivity + curve + durable
secondary), loop outcomes on M4 records, verdict assembly with the pre-declared
UNDERPOWERED labels, per-loop table rows, wave estimates, and the synthetic
dry-run fixtures.
"""
from __future__ import annotations

from m4 import (
    CLASS_ATBELOW,
    CLASS_DAMAGED,
    EXPECTED_DAMAGED,
    EXPECTED_ENTRY,
    PASS_EST,
    entry_class,
    idr_block,
    m4_entry,
    m4_outcomes,
    model_verdict_m4,
    per_loop_rows,
    recross_at,
    wave_estimate_m4,
    _synthetic,
)

DS = "deepseek/deepseek-chat-v3.1"
QW = "qwen/qwen3-coder-30b-a3b-instruct"


# ---------- M3-shaped record builders ----------

def _m3_pass0(model, pid, start):
    return {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
            "baseline_ok": True, "start_source": "m1", "start_failed": start,
            "graded": {"passed": 6 - start, "failed": start},
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                        "stdout": "0"}]}


def _m3_pass(model, pid, k, failed, patch=None):
    return {"model": model, "problem_id": pid, "pass": k, "first_parse": True,
            "patch": patch or f"code-{pid}-p{k}", "cost": 0.001,
            "recovered": failed == 0,
            "graded": {"passed": 6 - failed, "failed": failed},
            "detail": [{"i": 0, "rc": 0, "timed_out": False,
                        "passed": failed == 0, "stdout": "1"}]}


def _m3_exhausted(model, pid, start, faileds):
    assert len(faileds) == 5 and all(f > 0 for f in faileds)
    recs = [_m3_pass0(model, pid, start)]
    recs += [_m3_pass(model, pid, k, f) for k, f in enumerate(faileds, 1)]
    return recs


def _m3_escaped(model, pid, start, at):
    recs = [_m3_pass0(model, pid, start)]
    recs += [_m3_pass(model, pid, k, 3) for k in range(1, at)]
    recs.append(_m3_pass(model, pid, at, 0))
    return recs


# ---------- entry class (the D12 split) ----------

def test_entry_class_damaged_strictly_above_baseline():
    assert entry_class(16, 1) == CLASS_DAMAGED
    assert entry_class(2, 1) == CLASS_DAMAGED


def test_entry_class_at_or_below_baseline():
    assert entry_class(1, 1) == CLASS_ATBELOW    # p03069: final == baseline
    assert entry_class(1, 3) == CLASS_ATBELOW    # p03593: final < baseline


# ---------- entry extraction (clean non-escaped M3 finals only) ----------

def test_m4_entry_keeps_exhausted_classifies_and_freezes_final_patch():
    recs = (_m3_exhausted(DS, "p1", 11, [12, 14, 16, 16, 16])       # damaged
            + _m3_exhausted(DS, "p2", 4, [4, 3, 2, 1, 1]))          # ends at base
    baselines = {"p1": 1, "p2": 1}
    entry = m4_entry(recs, DS, ["p1", "p2"], baselines)
    assert list(entry) == ["p1", "p2"]
    assert entry["p1"] == {"start_patch": "code-p1-p5", "start_failed": 16,
                           "baseline": 1, "class": CLASS_DAMAGED}
    assert entry["p2"] == {"start_patch": "code-p2-p5", "start_failed": 1,
                           "baseline": 1, "class": CLASS_ATBELOW}


def test_m4_entry_excludes_escaped_invalid_unfinished_and_other_models():
    recs = (_m3_escaped(DS, "p1", 4, at=2)                          # escaped
            + [_m3_pass0(DS, "p2", 5),
               {"model": DS, "problem_id": "p2", "pass": 1,
                "invalid": "parse failure", "cost": 0.001}]         # INVALID
            + [_m3_pass0(DS, "p3", 5)]                              # unfinished
            + _m3_exhausted(QW, "p4", 5, [6, 6, 6, 6, 6])           # other model
            + _m3_exhausted(DS, "p5", 5, [6, 6, 6, 6, 6]))          # enters
    baselines = {p: 2 for p in ("p1", "p2", "p3", "p4", "p5")}
    entry = m4_entry(recs, DS, ["p1", "p2", "p3", "p4", "p5"], baselines)
    assert list(entry) == ["p5"]


def test_m4_entry_follows_m3_subset_order():
    recs = (_m3_exhausted(DS, "pB", 5, [6] * 5)
            + _m3_exhausted(DS, "pA", 5, [6] * 5))
    entry = m4_entry(recs, DS, ["pA", "pB"], {"pA": 2, "pB": 2})
    assert list(entry) == ["pA", "pB"]


# ---------- re-cross math (KICKOFF verbatim: within 5 passes, transient counts) ----------

def test_recross_at_damaged_start_never_counts_pass_zero():
    assert recross_at(16, 1, [(1, 5), (2, 1), (3, 4)]) == 2   # earliest k
    assert recross_at(16, 1, [(1, 0)]) == 1                   # full fix re-crosses
    assert recross_at(16, 1, [(k, 9) for k in range(1, 6)]) is None


def test_recross_at_transient_recross_still_counts():
    # dips to baseline at pass 2, climbs back above — "within 5 passes" is met
    assert recross_at(8, 3, [(1, 6), (2, 3), (3, 7), (4, 7), (5, 7)]) == 2


def test_recross_at_at_or_below_start_recrosses_at_pass_zero():
    assert recross_at(1, 1, [(1, 5), (2, 5)]) == 0
    assert recross_at(1, 3, []) == 0


# ---------- M4 record builders (loop outcomes) ----------

def _m4_pass0(model, pid, start):
    return {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
            "baseline_ok": True, "start_source": "m3", "start_failed": start,
            "graded": {"passed": 20 - start, "failed": start},
            "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                        "stdout": "0"}]}


def _m4_loop(model, pid, start, faileds, invalid_at=None):
    recs = [_m4_pass0(model, pid, start)]
    for k, f in enumerate(faileds, 1):
        if k == invalid_at:
            recs.append({"model": model, "problem_id": pid, "pass": k,
                         "invalid": "parse failure", "first_parse": False,
                         "cost": 0.001})
            break
        recs.append(_m3_pass(model, pid, k, f))
        if f == 0:
            break
    return recs


def _meta(start, baseline):
    return {"start_patch": "frozen", "start_failed": start, "baseline": baseline,
            "class": entry_class(start, baseline)}


def test_m4_outcomes_recovered_recrossed_durable_and_trajectory():
    entry = {"p1": _meta(16, 1)}
    recs = _m4_loop(DS, "p1", 16, [5, 0])
    o = m4_outcomes(recs, DS, entry)["p1"]
    assert o["status"] == "recovered" and o["recovered_at"] == 2
    assert o["recross_at"] == 2 and o["durable"] is True
    assert o["trajectory"] == "recovered"
    assert o["final_failed"] == 0 and o["best_failed"] == 0


def test_m4_outcomes_transient_recross_is_not_durable():
    entry = {"p1": _meta(8, 3)}
    recs = _m4_loop(DS, "p1", 8, [6, 3, 7, 7, 7])
    o = m4_outcomes(recs, DS, entry)["p1"]
    assert o["status"] == "exhausted" and o["recovered_at"] is None
    assert o["recross_at"] == 2 and o["durable"] is False
    assert o["trajectory"] == "improved"          # final 7 < start 8
    assert o["best_failed"] == 3


def test_m4_outcomes_never_recrossed_deepened_and_held():
    entry = {"p1": _meta(10, 6), "p2": _meta(10, 6)}
    recs = (_m4_loop(DS, "p1", 10, [12, 13, 13, 13, 13])
            + _m4_loop(DS, "p2", 10, [10, 10, 10, 10, 10]))
    out = m4_outcomes(recs, DS, entry)
    assert out["p1"]["recross_at"] is None and out["p1"]["trajectory"] == "deepened"
    assert out["p2"]["recross_at"] is None and out["p2"]["trajectory"] == "held"
    assert out["p1"]["durable"] is False


def test_m4_outcomes_pass0_class_recrosses_immediately_and_can_stay_durable():
    entry = {"p1": _meta(1, 3)}
    recs = _m4_loop(DS, "p1", 1, [1, 1, 1, 1, 1])
    o = m4_outcomes(recs, DS, entry)["p1"]
    assert o["recross_at"] == 0 and o["durable"] is True and o["cls"] == CLASS_ATBELOW


def test_m4_outcomes_invalid_todo_active():
    entry = {"p1": _meta(9, 2), "p2": _meta(9, 2), "p3": _meta(9, 2)}
    recs = (_m4_loop(DS, "p1", 9, [5, 5], invalid_at=2)
            + [_m4_pass0(DS, "p3", 9), _m3_pass(DS, "p3", 1, 7)])
    out = m4_outcomes(recs, DS, entry)
    assert out["p1"]["status"] == "invalid"
    assert out["p2"]["status"] == "todo"
    assert out["p3"]["status"] == "active"


# ---------- the IDR block (D12-A: primary over damaged; every view reported) ----------

def _idr_fixture():
    entry = {
        "d1": _meta(16, 1),   # recovers fully at pass 1
        "d2": _meta(8, 3),    # transient re-cross at 2
        "d3": _meta(10, 6),   # never re-crosses
        "d4": _meta(10, 6),   # never re-crosses
        "d5": _meta(9, 2),    # INVALID at pass 2
        "a1": _meta(1, 3),    # pass-0 class, exhausted at 1 failed
    }
    recs = (_m4_loop(DS, "d1", 16, [0])
            + _m4_loop(DS, "d2", 8, [6, 3, 7, 7, 7])
            + _m4_loop(DS, "d3", 10, [12, 13, 13, 13, 13])
            + _m4_loop(DS, "d4", 10, [10, 10, 10, 10, 10])
            + _m4_loop(DS, "d5", 9, [5, 5], invalid_at=2)
            + _m4_loop(DS, "a1", 1, [1, 1, 1, 1, 1]))
    return m4_outcomes(recs, DS, entry)


def test_idr_primary_denominator_is_damaged_clean_only():
    b = idr_block(_idr_fixture())
    assert b["idr_n"] == 4                     # d1, d2, d3, d4 (d5 INVALID, a1 pass-0 class)
    assert b["irrecoverable"] == 2             # d3, d4
    assert b["idr"] == 0.5


def test_idr_recross_curve_is_cumulative_over_damaged_clean():
    b = idr_block(_idr_fixture())
    assert b["recross_curve"] == [1, 2, 2, 2, 2]


def test_idr_pass0_pair_reported_not_counted_in_primary():
    b = idr_block(_idr_fixture())
    assert b["pass0_pids"] == ["a1"]
    # sensitivity view: all 5 clean loops, a1 re-crossed at pass 0
    assert b["sens_n"] == 5 and b["sens_irrecoverable"] == 2
    assert b["sens_idr"] == 0.4


def test_idr_durable_counts_transient_excluded():
    b = idr_block(_idr_fixture())
    assert b["durable_damaged"] == 1           # d1 only (d2 transient)
    assert b["durable_all"] == 2               # d1 + a1


# ---------- verdict assembly ----------

def test_model_verdict_m4_labels_and_curves():
    out = _idr_fixture()
    v = model_verdict_m4(out)
    assert v["label"] == "UNDERPOWERED"        # clean 5 < 20
    assert v["clean_n"] == 5 and v["recovered"] == 1
    assert v["curve"] == [1, 1, 1, 1, 1]       # full-fix recovery curve
    assert v["pass1_recovered"] == 1
    assert v["invalid"] == 1 and v["unfinished"] == 0
    assert v["trajectory"] == {"recovered": 1, "improved": 1, "held": 2, "deepened": 1}
    assert v["idr_n"] == 4 and v["irrecoverable"] == 2


def test_model_verdict_m4_reported_at_twenty_clean():
    entry = {f"p{i:02d}": _meta(10, 2) for i in range(20)}
    recs = []
    for i, pid in enumerate(entry):
        recs += _m4_loop(DS, pid, 10, [0] if i < 3 else [11, 11, 11, 11, 11])
    v = model_verdict_m4(m4_outcomes(recs, DS, entry))
    assert v["label"] == "REPORTED" and v["clean_n"] == 20
    assert v["irrecoverable"] == 17 and v["idr_n"] == 20


# ---------- per-loop table (N=18: the honest presentation is the loops) ----------

def test_per_loop_rows_order_and_fields():
    out = _idr_fixture()
    rows = per_loop_rows(out, ["d1", "d2", "d3", "d4", "d5", "a1"])
    assert [r["problem_id"] for r in rows] == ["d1", "d2", "d3", "d4", "d5", "a1"]
    assert rows[0]["recovered_at"] == 1 and rows[0]["recross_at"] == 1
    assert rows[1] == {"problem_id": "d2", "class": CLASS_DAMAGED, "baseline": 3,
                       "start_failed": 8, "best_failed": 3, "final_failed": 7,
                       "recross_at": 2, "recovered_at": None, "status": "exhausted"}
    # INVALID keeps the last graded state (m2/m3 convention) but never a recross
    assert rows[4]["status"] == "invalid" and rows[4]["final_failed"] == 5
    assert rows[4]["recross_at"] is None


# ---------- wave estimate ----------

def test_wave_estimate_m4_counts_remaining_passes():
    entry = {"p1": _meta(9, 2), "p2": _meta(9, 2), "p3": _meta(9, 2)}
    recs = (_m4_loop(DS, "p1", 9, [0])                       # recovered: 0 left
            + [_m4_pass0(DS, "p2", 9), _m3_pass(DS, "p2", 1, 7)])  # active: 4 left
    out = m4_outcomes(recs, DS, entry)                       # p3 todo: 5 left
    assert wave_estimate_m4(out, DS) == round(9 * PASS_EST[DS], 6)


# ---------- signed constants + synthetic fixture ----------

def test_signed_entry_constants_match_the_brief():
    assert EXPECTED_ENTRY == {DS: 2, QW: 16}
    assert EXPECTED_DAMAGED == {DS: 1, QW: 15}


def test_synthetic_covers_every_label_and_class_path():
    records, subsets, entry_by = _synthetic()
    reported, underpowered = "demo/reported", "demo/underpowered"
    for model, want in ((reported, "REPORTED"), (underpowered, "UNDERPOWERED")):
        out = m4_outcomes(records, model, entry_by[model])
        v = model_verdict_m4(out)
        assert v["label"] == want and v["unfinished"] == 0
        assert v["invalid"] >= 1
        assert any(o["cls"] == CLASS_ATBELOW for o in out.values())
        assert any(o["recross_at"] is None for o in out.values())          # irrecoverable
        assert any(o["recross_at"] not in (None, 0) and not o["durable"]
                   for o in out.values())                                  # transient
