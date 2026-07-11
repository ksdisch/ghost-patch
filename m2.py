"""m2.py — Milestone 2: the recovery ceiling (RQ2 analog).

Signed off 2026-07-11 (docs/M2-BRIEF.md): D8-A (full failing-test report), D9-A
($0.45 cap on data/m2/cost_ledger.json). Per model, every problem it failed
feedback-free in M1 (failed-T3) gets a self-guided repair loop: stateless
single-turn passes, current code + first-failing-test feedback, max 5 passes,
early stop on all-tests-pass, start state = the ORIGINAL buggy program (KICKOFF
verbatim; reconciliation in the brief).

Subcommands:
  subset  — free. Derives the per-model failed-T3 subsets from data/m1/trials.jsonl,
            asserts the frozen counts (deepseek 23, qwen 49), writes
            data/m2/subsets.json in frozen bank order.
  run     — paid. --model <slug>: loop wave, resumable via (model, problem_id, pass)
            keys in data/m2/trials.jsonl; grade-0 integrity halt; smoke gate at the
            first 5 paid pass-calls; 80% parse floor per completed wave.
  verdict — free. Ceiling + recovery curve + secondaries + FLOOR flag per model,
            M3/M4 cost re-projection. `--synthetic` dry-runs every label path on
            fixtures, per the "gates as code, dry-run before paid" contract.

Every threshold is pre-committed in docs/M2-BRIEF.md and unit-tested in test_m2.py
BEFORE any paid call.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from client import BudgetExceeded, CostMeter, SUBJECT_REASONING, chat
from grading import compare_outputs
from m1 import EST_DRAFT_COST, arm_gate, lifetime_ok, parse_floor_ok
from pilot import REPAIR_MAX_TOKENS, _compiles
from prompts import extract_patch, m2_repair_prompt
from sandbox import TEST_TIMEOUT_S, run_tests
from stats import wilson

DATA = Path(__file__).parent / "data"
M2_DIR = DATA / "m2"
TRIALS_PATH = M2_DIR / "trials.jsonl"
SUBSETS_PATH = M2_DIR / "subsets.json"
RESULTS_PATH = DATA / "m2_results.json"
M1_TRIALS_PATH = DATA / "m1" / "trials.jsonl"
BANK_PATH = DATA / "bank.json"
M0_LEDGER = DATA / "pilot" / "cost_ledger.json"
M1_LEDGER = DATA / "m1" / "cost_ledger.json"

# Signed constants (docs/M2-BRIEF.md, 2026-07-11)
M2_CAP = 0.45              # D9-A
MAX_PASSES = 5             # paper protocol verbatim (KICKOFF)
MIN_N = 20                 # clean loops per cell, else UNDERPOWERED (auto)
FLOOR_LO = 0.05            # ceiling Wilson lower bound below this → FLOOR flag
FIELD_CAP = 1000           # chars per feedback field before the truncation marker
SMOKE_N = 5                # paid pass-calls before the smoke gate fires
MODELS = [
    "deepseek/deepseek-chat-v3.1",
    "qwen/qwen3-coder-30b-a3b-instruct",
]
EXPECTED_SUBSET = {MODELS[0]: 23, MODELS[1]: 49}   # frozen from M1 RESULTS
PASS_EST = {MODELS[0]: 0.00135, MODELS[1]: 0.00068}  # $/pass, measured basis


# ---------- pre-committed pure logic (unit-tested before any paid call) ----------

def failed_t3_subset(m1_records: list[dict], model: str,
                     bank_order: list[str]) -> list[str]:
    """Entry rule: problems whose M1 T3 trial was graded AND failed, bank order.

    INVALID trials never enter (an unparseable response never demonstrated
    incorrect code). Later records win on duplicate keys (same defensive rule
    as m1.pairs_table).
    """
    success: dict[str, bool] = {}
    for r in m1_records:
        if r.get("model") != model or r.get("arm") != "T3":
            continue
        if "repair_success" in r and "invalid" not in r:
            success[r["problem_id"]] = bool(r["repair_success"])
    failed = {pid for pid, ok in success.items() if not ok}
    return [pid for pid in bank_order if pid in failed]


def truncate_field(s: str, cap: int = FIELD_CAP) -> str:
    """Feedback-field truncation: cap chars, then the pre-committed marker."""
    return s if len(s) <= cap else s[:cap] + "… [truncated]"


def actual_output(run: dict) -> str:
    """The 'actual output' a failing test shows: stdout + a status marker.

    The sandbox captures rc/stdout/timed_out only (stderr is discarded by
    design), so abnormal terminations are reported as markers, never invented.
    """
    marker = None
    if run["timed_out"]:
        marker = f"[process timed out after {TEST_TIMEOUT_S:g}s]"
    elif run["rc"] != 0:
        marker = f"[process exited with code {run['rc']}]"
    stdout = run["stdout"]
    if marker is None:
        return stdout
    if not stdout:
        return marker
    sep = "" if stdout.endswith("\n") else "\n"
    return stdout + sep + marker


def first_failing(detail: list[dict]) -> int | None:
    """Lowest-index failing test in the frozen per-problem order, or None."""
    for row in detail:
        if not row["passed"]:
            return row["i"]
    return None


def detail_from_runs(runs, tests: list[dict], semantics: str) -> tuple[dict, list[dict]]:
    """Reduce sandbox runs to (counts, per-test detail rows).

    Stored stdout is pre-truncated to FIELD_CAP — exactly what any later
    feedback render could show — so resume rebuilds identical prompts.
    """
    detail = []
    for i, (r, t) in enumerate(zip(runs, tests)):
        passed = r.rc == 0 and not r.timed_out and compare_outputs(t["output"], r.stdout, semantics)
        detail.append({"i": i, "rc": r.rc, "timed_out": r.timed_out,
                       "passed": passed, "stdout": truncate_field(r.stdout)})
    n_pass = sum(1 for d in detail if d["passed"])
    return {"passed": n_pass, "failed": len(detail) - n_pass}, detail


def feedback_fields(entry: dict, detail: list[dict]) -> dict:
    """D8-A full report for the first failing test of the current state."""
    i = first_failing(detail)
    t = entry["tests"][i]
    return {"test_index": i,
            "input": truncate_field(t["input"]),
            "expected": truncate_field(t["output"]),
            "actual": actual_output(detail[i])}


def m2_keys(lines) -> set[tuple[str, str, int]]:
    """Resume keys (model, problem_id, pass); blank/partial lines are skipped."""
    keys = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if all(k in r for k in ("model", "problem_id", "pass")):
            keys.add((r["model"], r["problem_id"], r["pass"]))
    return keys


def loop_state(records: list[dict]) -> dict:
    """Reconstruct one problem's loop from its pass records (resume-safe).

    Terminal: recovered / invalid / exhausted (MAX_PASSES unrecovered).
    Otherwise run_pass carries the next pass number and the current code
    (None after grade-0 → the caller substitutes the bank's buggy_code —
    the pass-1 start state is never stored, only verified).
    """
    if not records:
        return {"status": "need_grade0"}
    recs = sorted(records, key=lambda r: r["pass"])
    for r in recs:
        if "invalid" in r:
            return {"status": "invalid", "at": r["pass"]}
        if r.get("recovered"):
            return {"status": "recovered", "at": r["pass"]}
    last = recs[-1]
    if last["pass"] >= MAX_PASSES:
        return {"status": "exhausted"}
    return {"status": "run_pass", "next": last["pass"] + 1,
            "code": last.get("patch"), "detail": last["detail"]}


def loop_outcomes(records: list[dict], model: str, subset: list[str],
                  baselines: dict[str, int]) -> dict[str, dict]:
    """Classify every subset loop: todo/active/recovered/exhausted/invalid.

    ever_below / damaged_final read against the frozen buggy baseline — the
    no-instruction self-damage secondaries (context for M3's damage claim).
    """
    by_pid: dict[str, list[dict]] = {pid: [] for pid in subset}
    for r in records:
        if r.get("model") == model and r.get("problem_id") in by_pid:
            by_pid[r["problem_id"]].append(r)
    out = {}
    for pid in subset:
        recs = sorted(by_pid[pid], key=lambda r: r["pass"])
        state = loop_state(recs)
        status = {"need_grade0": "todo", "run_pass": "active"}.get(
            state["status"], state["status"])
        base = baselines[pid]
        graded_paid = [r for r in recs if r["pass"] >= 1 and "graded" in r]
        final_failed = graded_paid[-1]["graded"]["failed"] if graded_paid else None
        out[pid] = {
            "status": status,
            "recovered_at": state.get("at") if state["status"] == "recovered" else None,
            "passes_used": max((r["pass"] for r in recs), default=0),
            "final_failed": final_failed,
            "ever_below": any(r["graded"]["failed"] > base for r in graded_paid),
            "damaged_final": status == "exhausted" and final_failed is not None
                             and final_failed > base,
        }
    return out


def recovery_curve(clean: dict[str, dict]) -> list[int]:
    """Cumulative recovered count by pass k = 1..MAX_PASSES over clean loops."""
    return [sum(1 for o in clean.values()
                if o["recovered_at"] is not None and o["recovered_at"] <= k)
            for k in range(1, MAX_PASSES + 1)]


def m2_label(clean_n: int) -> str:
    """M2 has no REPRODUCED/NULL gate of its own (the KICKOFF gates M4-vs-M2)."""
    return "REPORTED" if clean_n >= MIN_N else "UNDERPOWERED"


def floor_flag(recovered: int, clean_n: int) -> bool:
    """FLOOR: ceiling Wilson lower bound < FLOOR_LO → the M4 directional gate is
    pre-declared unresolvable for this model (docs/M2-BRIEF.md)."""
    lo, _ = wilson(recovered, clean_n)
    return lo < FLOOR_LO


def model_verdict(outcomes: dict[str, dict]) -> dict:
    """Assemble one model's verdict block from its loop outcomes (pure)."""
    clean = {p: o for p, o in outcomes.items()
             if o["status"] in ("recovered", "exhausted")}
    clean_n = len(clean)
    recovered = sum(1 for o in clean.values() if o["status"] == "recovered")
    lo, hi = wilson(recovered, clean_n)
    return {
        "clean_n": clean_n,
        "recovered": recovered,
        "rate": round(recovered / clean_n, 4) if clean_n else None,
        "wilson": [round(lo, 4), round(hi, 4)],
        "label": m2_label(clean_n),
        "floor": floor_flag(recovered, clean_n),
        "curve": recovery_curve(clean),
        "pass1_recovered": sum(1 for o in clean.values() if o["recovered_at"] == 1),
        "mean_passes": round(sum(o["passes_used"] for o in clean.values()) / clean_n, 4)
                       if clean_n else None,
        "damaged_final": sum(1 for o in clean.values() if o["damaged_final"]),
        "ever_below": sum(1 for o in clean.values() if o["ever_below"]),
        "invalid": sum(1 for o in outcomes.values() if o["status"] == "invalid"),
        "unfinished": sum(1 for o in outcomes.values() if o["status"] in ("todo", "active")),
    }


def wave_estimate(outcomes: dict[str, dict], model: str) -> float:
    """Upper-bound cost of finishing this model's wave: remaining passes × rate."""
    remaining = 0
    for o in outcomes.values():
        if o["status"] == "todo":
            remaining += MAX_PASSES
        elif o["status"] == "active":
            remaining += MAX_PASSES - o["passes_used"]
    return round(remaining * PASS_EST[model], 6)


# ---------- synthetic fixture (dry-run) ----------

def _syn_loop(model: str, pid: str, *, recovered_at: int | None = None,
              invalid_at: int | None = None, baseline: int = 2) -> list[dict]:
    """One synthetic loop: grade-0 + paid passes to a terminal state."""
    recs = [{"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
             "baseline_ok": True, "graded": {"passed": 3, "failed": baseline},
             "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                         "stdout": "0"}]}]
    last = invalid_at or recovered_at or MAX_PASSES
    for k in range(1, last + 1):
        if k == invalid_at:
            recs.append({"model": model, "problem_id": pid, "pass": k,
                         "invalid": "parse failure", "first_parse": False, "cost": 0.001})
            break
        failed = 0 if k == recovered_at else (baseline + 1 if k % 2 else 1)
        recs.append({"model": model, "problem_id": pid, "pass": k, "first_parse": True,
                     "patch": "x = 1", "cost": 0.001, "finish_reason": "stop",
                     "feedback": {"test_index": 0}, "recovered": failed == 0,
                     "graded": {"passed": 5 - failed, "failed": failed},
                     "detail": [{"i": 0, "rc": 0, "timed_out": False,
                                 "passed": failed == 0, "stdout": "1"}]})
        if failed == 0:
            break
    return recs


def _synthetic() -> tuple[list[dict], dict[str, list[str]], dict[str, dict[str, int]]]:
    """Fixture models covering every label path: REPORTED, UNDERPOWERED, FLOOR."""
    records, subsets, baselines = [], {}, {}
    # REPORTED, no floor: 24 loops, 1 invalid, 10/23 recovered across passes
    m = "demo/reported"
    plan = [1] * 4 + [2] * 3 + [3] * 2 + [5] + [None] * 13
    subsets[m] = [f"r{i:02d}" for i in range(24)]
    for i, pid in enumerate(subsets[m]):
        if i == 23:
            records += _syn_loop(m, pid, invalid_at=2)
        else:
            records += _syn_loop(m, pid, recovered_at=plan[i])
    baselines[m] = {pid: 2 for pid in subsets[m]}
    # UNDERPOWERED: 12 loops, none recovered
    m = "demo/underpowered"
    subsets[m] = [f"u{i:02d}" for i in range(12)]
    for pid in subsets[m]:
        records += _syn_loop(m, pid)
    baselines[m] = {pid: 2 for pid in subsets[m]}
    # FLOOR: 49 clean loops, 2 recovered (wilson lo ≈ .011 < .05)
    m = "demo/floor"
    subsets[m] = [f"f{i:02d}" for i in range(49)]
    for i, pid in enumerate(subsets[m]):
        records += _syn_loop(m, pid, recovered_at=2 if i < 2 else None)
    baselines[m] = {pid: 2 for pid in subsets[m]}
    return records, subsets, baselines


# ---------- meter + ledger (per-milestone regime; M0/M1 ledgers are frozen) ----------

def _meter() -> CostMeter:
    m = CostMeter(M2_CAP)
    ledger = M2_DIR / "cost_ledger.json"
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        m.total, m.calls = prior["total"], prior["calls"]
    return m


def _save_meter(m: CostMeter):
    (M2_DIR / "cost_ledger.json").write_text(
        json.dumps({"total": round(m.total, 6), "calls": m.calls, "cap": m.cap}))


def _lifetime(m2_total: float) -> float:
    prior = 0.0
    for ledger in (M0_LEDGER, M1_LEDGER):
        if ledger.exists():
            prior += json.loads(ledger.read_text())["total"]
    return prior + m2_total


def _bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text())["bank"]


def _read_trials() -> list[dict]:
    if not TRIALS_PATH.exists():
        return []
    return [json.loads(x) for x in TRIALS_PATH.read_text().splitlines() if x.strip()]


def _append_trial(rec: dict):
    with open(TRIALS_PATH, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def _load_subsets() -> dict[str, list[str]]:
    return json.loads(SUBSETS_PATH.read_text())["subsets"]


def grade_detail(entry: dict, code: str, semantics: str) -> tuple[dict, list[dict]]:
    """Grade `code` on the problem's full frozen test set (free, local sandbox)."""
    runs = run_tests(code, [t["input"] for t in entry["tests"]])
    return detail_from_runs(runs, entry["tests"], semantics)


# ---------- subset (free) ----------

def cmd_subset() -> int:
    M2_DIR.mkdir(parents=True, exist_ok=True)
    bank_order = [e["problem_id"] for e in _bank()]
    m1_records = [json.loads(x) for x in M1_TRIALS_PATH.read_text().splitlines() if x.strip()]
    subsets = {}
    for model in MODELS:
        subset = failed_t3_subset(m1_records, model, bank_order)
        if len(subset) != EXPECTED_SUBSET[model]:
            print(f"HALT: {model} subset {len(subset)} != frozen {EXPECTED_SUBSET[model]}")
            return 1
        subsets[model] = subset
        print(f"{model}: {len(subset)} failed-T3 problems (frozen)")
    SUBSETS_PATH.write_text(json.dumps({
        "derived_from": "data/m1/trials.jsonl",
        "rule": "arm==T3, graded, repair_success==false; INVALID excluded; bank order",
        "subsets": subsets}, indent=1))
    print(f"wrote {SUBSETS_PATH}")
    return 0


# ---------- run (paid, per model, resumable) ----------

def _pass_call(model: str, prompt: str, m: CostMeter) -> dict:
    """One repair pass: same call/parse/retry contract as M0/M1 (_repair_trial)."""
    r = chat(model, prompt, max_tokens=REPAIR_MAX_TOKENS,
             reasoning=SUBJECT_REASONING, meter=m)
    patch = extract_patch(r["text"])
    first_parse = patch is not None and _compiles(patch)
    if not first_parse:  # one bare retry, per the brief
        r2 = chat(model, prompt, max_tokens=REPAIR_MAX_TOKENS,
                  reasoning=SUBJECT_REASONING, meter=m)
        patch = extract_patch(r2["text"])
        if patch is not None and not _compiles(patch):
            patch = None
        r["cost"] += r2["cost"]
    elif patch is not None and not _compiles(patch):
        patch = None
    return {"patch": patch, "first_parse": first_parse, "cost": r["cost"],
            "response_chars": len(r["text"]), "finish_reason": r["finish_reason"]}


def cmd_run(model: str) -> int:
    if model not in MODELS:
        print(f"unknown model {model}; roster: {MODELS}")
        return 1
    M2_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank_by = {e["problem_id"]: e for e in _bank()}
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    subset = _load_subsets()[model]
    baselines = {pid: bank_by[pid]["buggy_failed_baseline"] for pid in subset}
    records = _read_trials()
    outcomes = loop_outcomes(records, model, subset, baselines)
    est = wave_estimate(outcomes, model)
    todo = sum(1 for o in outcomes.values() if o["status"] in ("todo", "active"))
    print(f"— {model}: {todo} loops to run/resume · est ${est:.3f} (upper bound)",
          flush=True)
    if not lifetime_ok(_lifetime(m.total), est):
        print(f"HALT: lifetime guard — ${_lifetime(m.total):.2f} + ${est:.2f} > $5.00")
        return 4
    by_pid: dict[str, list[dict]] = {pid: [] for pid in subset}
    for r in records:
        if r.get("model") == model and r.get("problem_id") in by_pid:
            by_pid[r["problem_id"]].append(r)
    paid: list[tuple[bool, float]] = []  # (first_parse, cost) per paid pass-call

    def _smoke_check() -> bool:
        if len(paid) != SMOKE_N:
            return True
        parse = sum(1 for fp, _ in paid if fp)
        mean = sum(c for _, c in paid) / len(paid)
        print(f"  smoke gate @{SMOKE_N}: parse {parse}/{SMOKE_N}, mean ${mean:.5f}/pass")
        if not arm_gate(parse, mean, PASS_EST[model]):
            print("HALT: smoke gate — to Kyle")
            return False
        return True

    try:
        for pid in subset:
            entry = bank_by[pid]
            state = loop_state(by_pid[pid])
            if state["status"] in ("recovered", "invalid", "exhausted"):
                continue
            if state["status"] == "need_grade0":
                counts, detail = grade_detail(entry, entry["buggy_code"], semantics)
                if counts["failed"] != entry["buggy_failed_baseline"]:
                    print(f"HALT: grade-0 integrity — {pid} failed {counts['failed']} "
                          f"!= frozen baseline {entry['buggy_failed_baseline']} "
                          "(harness drift; investigate before resuming)")
                    return 6
                rec = {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
                       "baseline_ok": True, "graded": counts, "detail": detail}
                _append_trial(rec)
                state = {"status": "run_pass", "next": 1, "code": None, "detail": detail}
            while state["status"] == "run_pass":
                k = state["next"]
                code = state["code"] or entry["buggy_code"]
                fb = feedback_fields(entry, state["detail"])
                prompt = m2_repair_prompt(entry["description"], code, fb)
                call = _pass_call(model, prompt, m)
                paid.append((call["first_parse"], call["cost"]))
                if call["patch"] is None:
                    _append_trial({"model": model, "problem_id": pid, "pass": k,
                                   "invalid": "parse failure", "first_parse": False,
                                   "cost": call["cost"], "feedback": fb,
                                   "finish_reason": call["finish_reason"]})
                    _save_meter(m)
                    if not _smoke_check():
                        return 2
                    break  # loop INVALID — terminal
                counts, detail = grade_detail(entry, call["patch"], semantics)
                recovered = counts["failed"] == 0
                _append_trial({"model": model, "problem_id": pid, "pass": k,
                               "first_parse": call["first_parse"], "patch": call["patch"],
                               "cost": call["cost"], "finish_reason": call["finish_reason"],
                               "response_chars": call["response_chars"], "feedback": fb,
                               "graded": counts, "detail": detail, "recovered": recovered})
                _save_meter(m)
                if not _smoke_check():
                    return 2
                if recovered or k >= MAX_PASSES:
                    break
                state = {"status": "run_pass", "next": k + 1,
                         "code": call["patch"], "detail": detail}
    except BudgetExceeded as e:
        _save_meter(m)
        print(f"HALT: {e} (resumable — re-run after a cap decision)")
        return 3
    _save_meter(m)
    model_rows = [r for r in _read_trials()
                  if r.get("model") == model and r.get("pass", 0) >= 1
                  and "first_parse" in r]
    parse_ok = sum(1 for r in model_rows if r["first_parse"])
    if not parse_floor_ok(parse_ok, len(model_rows)):
        print(f"HALT: parse floor — {parse_ok}/{len(model_rows)} < 80%; "
              "one format revision left for deepseek, none for qwen — to Kyle")
        return 5
    outcomes = loop_outcomes(_read_trials(), model, subset, baselines)
    rec_n = sum(1 for o in outcomes.values() if o["status"] == "recovered")
    print(f"{model}: wave complete — recovered {rec_n}/{len(subset)} · "
          f"parse {parse_ok}/{len(model_rows)} · meter ${m.total:.4f} · "
          f"lifetime ${_lifetime(m.total):.4f}")
    return 0


# ---------- verdict (free) ----------

def cmd_verdict(synthetic: bool) -> int:
    if synthetic:
        records, subsets, baselines_by = _synthetic()
        models = sorted(subsets)
        print("=== DRY RUN on synthetic records (no paid data) ===\n")
    else:
        records = _read_trials()
        subsets = _load_subsets()
        bank_by = {e["problem_id"]: e for e in _bank()}
        baselines_by = {mo: {pid: bank_by[pid]["buggy_failed_baseline"] for pid in ss}
                        for mo, ss in subsets.items()}
        models = MODELS

    out: dict = {"models": {}}
    for model in models:
        o = loop_outcomes(records, model, subsets[model], baselines_by[model])
        v = model_verdict(o)
        if not synthetic and v["unfinished"]:
            print(f"{model}: {v['unfinished']} loops unfinished — finish the wave first")
            return 1
        floor = "  FLOOR (M4 directional gate pre-declared unresolvable)" if v["floor"] else ""
        print(f"{model}  →  {v['label']}{floor}")
        print(f"  ceiling: {v['recovered']}/{v['clean_n']} recovered "
              f"(rate {v['rate']})  wilson {v['wilson']}")
        print(f"  curve (cum by pass): {v['curve']}  ·  pass-1 {v['pass1_recovered']} "
              f"·  mean passes {v['mean_passes']}")
        print(f"  self-damage: final {v['damaged_final']}/{v['clean_n']} "
              f"·  ever-below {v['ever_below']}/{v['clean_n']} "
              f"·  invalid loops {v['invalid']}")
        rows = [r for r in records if r.get("model") == model
                and r.get("pass", 0) >= 1 and "first_parse" in r]
        cost = sum(r.get("cost", 0) for r in rows)
        v["pass_calls"] = len(rows)
        v["first_parse"] = sum(1 for r in rows if r["first_parse"])
        v["cost"] = round(cost, 4)
        print(f"  pass-calls {v['pass_calls']} · first-parse {v['first_parse']} "
              f"· cost ${v['cost']}")
        out["models"][model] = v

    if not synthetic:
        m2_total = _meter().total
        out["cost"] = {"m2_total": round(m2_total, 4),
                       "lifetime": round(_lifetime(m2_total), 4)}
        m1_res = json.loads((DATA / "m1_results.json").read_text())["models"]
        proj = {}
        for model in models:
            v = out["models"][model]
            mean = v["cost"] / v["pass_calls"] if v["pass_calls"] else 0.0
            damaged = m1_res[model]["t2_damaged"]
            proj[model] = {
                "m3_max": round(damaged * MAX_PASSES * (mean + EST_DRAFT_COST), 3),
                "m4_max": round(damaged * MAX_PASSES * mean, 3),
            }
        out["projection_upper_bounds"] = proj
        RESULTS_PATH.write_text(json.dumps(out, indent=1))
        print(f"\ncost: {json.dumps(out['cost'])}")
        print(f"M3–M4 re-projection (5-pass upper bounds): {json.dumps(proj)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("subset", help="freeze per-model failed-T3 subsets (free)")
    r = sub.add_parser("run", help="loop wave (paid, resumable)")
    r.add_argument("--model", required=True)
    v = sub.add_parser("verdict", help="ceiling + curve + FLOOR checkpoints")
    v.add_argument("--synthetic", action="store_true", help="dry-run on fixtures")
    args = ap.parse_args()
    if args.cmd == "subset":
        raise SystemExit(cmd_subset())
    if args.cmd == "run":
        raise SystemExit(cmd_run(args.model))
    raise SystemExit(cmd_verdict(args.synthetic))
