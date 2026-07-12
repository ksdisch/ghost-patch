"""m4.py — Milestone 4: irrecoverability (RQ4 analog).

Signed off 2026-07-11 (docs/M4-BRIEF.md): D11-A (run descriptively), D12-A
(all 18 clean non-escaped M3 finals run; IDR primary over the damaged-at-entry
16), D13-A ($0.10 cap on data/m4/cost_ledger.json). The loop is M2's verbatim
— problem statement + current code + most recent failing test (D8-A),
self-diagnosis, max 5 stateless passes, early stop on all-tests-pass — with
pass-1 current code = the byte-frozen M3 final corrupted patch. Primary:
Irrecoverable Damage Rate, paper verbatim (fails to re-cross the buggy-patch
baseline within 5 passes; transient re-cross counts, durable recovery reported
as the stricter secondary). The KICKOFF chain gate (M4-vs-M2, Newcombe) and
every cell label arrive pre-declared UNDERPOWERED (entry 2/16 < 20) — the run
is descriptive paper-trail by sign-off.

Subcommands:
  subset  — free. Extracts per-model entry (M3 status `exhausted`) from
            data/m3/trials.jsonl, classifies per D12 (damaged vs
            at-or-below-baseline), asserts the frozen counts (2/16, damaged
            1/15), byte-freezes start patches to data/m4/subsets.json.
  run     — paid. --model <slug>: loop wave, resumable via
            (model, problem_id, pass) keys in data/m4/trials.jsonl; grade-0
            integrity + entry-class halt; smoke gate at the first 5 paid
            pass-calls; 80% parse floor per completed wave.
  verdict — free. IDR + re-cross curve + chain-gate contrast (Newcombe vs the
            M2 ceiling, UNDERPOWERED as pre-declared) + secondaries + the
            per-loop table. `--synthetic` dry-runs every label, class, and
            INVALID path on fixtures ("gates as code, dry-run before paid").

Every threshold is pre-committed in docs/M4-BRIEF.md and unit-tested in
test_m4.py BEFORE any paid call.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from client import BudgetExceeded, CostMeter
from m1 import ARM_SMOKE_N, MODELS, arm_gate, lifetime_ok, parse_floor_ok
from m2 import (
    MAX_PASSES, _pass_call, feedback_fields, grade_detail, loop_state,
    m2_label, recovery_curve,
)
from m3 import _append_jsonl, _read_jsonl, trajectory
from prompts import m2_repair_prompt
from regions import drift_ratio
from stats import newcombe_diff, wilson

DATA = Path(__file__).parent / "data"
M4_DIR = DATA / "m4"
TRIALS_PATH = M4_DIR / "trials.jsonl"
SUBSETS_PATH = M4_DIR / "subsets.json"
RESULTS_PATH = DATA / "m4_results.json"
M3_TRIALS_PATH = DATA / "m3" / "trials.jsonl"
M3_SUBSETS_PATH = DATA / "m3" / "subsets.json"
M2_RESULTS_PATH = DATA / "m2_results.json"
BANK_PATH = DATA / "bank.json"
PRIOR_LEDGERS = [DATA / "pilot" / "cost_ledger.json",
                 DATA / "m1" / "cost_ledger.json",
                 DATA / "m2" / "cost_ledger.json",
                 DATA / "m3" / "cost_ledger.json"]

# Signed constants (docs/M4-BRIEF.md, 2026-07-11)
M4_CAP = 0.10                    # D13-A
CLASS_DAMAGED = "damaged"        # start failed > buggy baseline (IDR denominator)
CLASS_ATBELOW = "at-or-below-baseline"   # re-crossed at pass 0 by definition (D12-A)
EXPECTED_ENTRY = {MODELS[0]: 2, MODELS[1]: 16}     # frozen from M3 RESULTS
EXPECTED_DAMAGED = {MODELS[0]: 1, MODELS[1]: 15}   # measured in the brief
PASS_EST = {                     # $/pass: per-model max of M2/M3 measured actuals
    MODELS[0]: 0.00161,
    MODELS[1]: 0.00078,
}


# ---------- pre-committed pure logic (unit-tested before any paid call) ----------

def entry_class(start_failed: int, baseline: int) -> str:
    """D12 split: damaged (net damage exists) vs at-or-below-baseline (the
    pass-0 pair — no net damage; outside the IDR primary denominator)."""
    return CLASS_DAMAGED if start_failed > baseline else CLASS_ATBELOW


def m4_entry(m3_records: list[dict], model: str, m3_subset: list[str],
             baselines: dict[str, int]) -> dict[str, dict]:
    """Entry rule (D12-A): clean non-escaped M3 loops (status `exhausted`) in
    M3 subset (bank) order. Start state = the loop's stored pass-5 patch,
    byte-frozen; start grade = that pass's recorded grade."""
    by_pid: dict[str, list[dict]] = {pid: [] for pid in m3_subset}
    for r in m3_records:
        if r.get("model") == model and r.get("problem_id") in by_pid:
            by_pid[r["problem_id"]].append(r)
    entry: dict[str, dict] = {}
    for pid in m3_subset:
        recs = sorted(by_pid[pid], key=lambda r: r["pass"])
        if loop_state(recs)["status"] != "exhausted":
            continue
        final = [r for r in recs if r["pass"] >= 1 and "graded" in r][-1]
        entry[pid] = {"start_patch": final["patch"],
                      "start_failed": final["graded"]["failed"],
                      "baseline": baselines[pid],
                      "class": entry_class(final["graded"]["failed"],
                                           baselines[pid])}
    return entry


def recross_at(start_failed: int, baseline: int,
               pass_faileds: list[tuple[int, int]]) -> int | None:
    """Earliest pass k with failed <= baseline (KICKOFF verbatim: re-crossing
    the buggy-patch baseline; transient counts). Pass 0 counts only for the
    at-or-below entry class — a damaged start is > baseline by construction."""
    if start_failed <= baseline:
        return 0
    for k, failed in sorted(pass_faileds):
        if failed <= baseline:
            return k
    return None


def m4_outcomes(records: list[dict], model: str,
                entry: dict[str, dict]) -> dict[str, dict]:
    """Classify every entry loop; m2.loop_state supplies the terminal logic,
    the vocabulary here is M4's (recovered, re-crossed, durable, trajectory)."""
    by_pid: dict[str, list[dict]] = {pid: [] for pid in entry}
    for r in records:
        if r.get("model") == model and r.get("problem_id") in by_pid:
            by_pid[r["problem_id"]].append(r)
    out = {}
    for pid, meta in entry.items():
        recs = sorted(by_pid[pid], key=lambda r: r["pass"])
        state = loop_state(recs)
        status = {"need_grade0": "todo", "run_pass": "active"}.get(
            state["status"], state["status"])
        graded_paid = [r for r in recs if r["pass"] >= 1 and "graded" in r]
        faileds = [(r["pass"], r["graded"]["failed"]) for r in graded_paid]
        final_failed = faileds[-1][1] if faileds else None
        clean = status in ("recovered", "exhausted")
        o = {
            "status": status,
            "cls": meta["class"],
            "recovered_at": state.get("at") if status == "recovered" else None,
            "passes_used": max((r["pass"] for r in recs), default=0),
            "start_failed": meta["start_failed"],
            "baseline": meta["baseline"],
            "final_failed": final_failed,
            "best_failed": min((f for _, f in faileds), default=None),
            "recross_at": recross_at(meta["start_failed"], meta["baseline"],
                                     faileds) if clean else None,
            "durable": clean and final_failed is not None
                       and final_failed <= meta["baseline"],
            "trajectory": None,
        }
        if clean:
            t = trajectory(meta["start_failed"], final_failed,
                           escaped=status == "recovered")
            o["trajectory"] = "recovered" if t == "escaped" else t
        out[pid] = o
    return out


def idr_block(outcomes: dict[str, dict]) -> dict:
    """The D12-A reporting block: IDR primary over damaged clean loops, the
    pass-0 pair as its own line, the all-N sensitivity, the re-cross curve,
    and the durable (final <= baseline) stricter secondary."""
    clean = {p: o for p, o in outcomes.items()
             if o["status"] in ("recovered", "exhausted")}
    damaged = {p: o for p, o in clean.items() if o["cls"] == CLASS_DAMAGED}
    irrec = sum(1 for o in damaged.values() if o["recross_at"] is None)
    sens_irrec = sum(1 for o in clean.values() if o["recross_at"] is None)
    lo, hi = wilson(irrec, len(damaged))
    return {
        "idr_n": len(damaged),
        "irrecoverable": irrec,
        "idr": round(irrec / len(damaged), 4) if damaged else None,
        "idr_wilson": [round(lo, 4), round(hi, 4)],
        "recross_curve": [sum(1 for o in damaged.values()
                              if o["recross_at"] is not None
                              and o["recross_at"] <= k)
                          for k in range(1, MAX_PASSES + 1)],
        "pass0_pids": sorted(p for p, o in clean.items()
                             if o["cls"] == CLASS_ATBELOW),
        "sens_n": len(clean),
        "sens_irrecoverable": sens_irrec,
        "sens_idr": round(sens_irrec / len(clean), 4) if clean else None,
        "durable_damaged": sum(1 for o in damaged.values() if o["durable"]),
        "durable_all": sum(1 for o in clean.values() if o["durable"]),
    }


def model_verdict_m4(outcomes: dict[str, dict]) -> dict:
    """Assemble one model's verdict block from its loop outcomes (pure)."""
    clean = {p: o for p, o in outcomes.items()
             if o["status"] in ("recovered", "exhausted")}
    clean_n = len(clean)
    recovered = sum(1 for o in clean.values() if o["status"] == "recovered")
    lo, hi = wilson(recovered, clean_n)
    v = {
        "clean_n": clean_n,
        "recovered": recovered,
        "rate": round(recovered / clean_n, 4) if clean_n else None,
        "wilson": [round(lo, 4), round(hi, 4)],
        "label": m2_label(clean_n),
        "curve": recovery_curve(clean),
        "pass1_recovered": sum(1 for o in clean.values() if o["recovered_at"] == 1),
        "mean_passes": round(sum(o["passes_used"] for o in clean.values()) / clean_n, 4)
                       if clean_n else None,
        "trajectory": {t: sum(1 for o in clean.values() if o["trajectory"] == t)
                       for t in ("recovered", "improved", "held", "deepened")},
        "invalid": sum(1 for o in outcomes.values() if o["status"] == "invalid"),
        "unfinished": sum(1 for o in outcomes.values()
                          if o["status"] in ("todo", "active")),
    }
    v.update(idr_block(outcomes))
    return v


def per_loop_rows(outcomes: dict[str, dict], order: list[str]) -> list[dict]:
    """The RESULTS table: at N = 18 the honest presentation is the loops."""
    return [{"problem_id": pid, "class": o["cls"], "baseline": o["baseline"],
             "start_failed": o["start_failed"], "best_failed": o["best_failed"],
             "final_failed": o["final_failed"], "recross_at": o["recross_at"],
             "recovered_at": o["recovered_at"], "status": o["status"]}
            for pid in order for o in [outcomes[pid]]]


def wave_estimate_m4(outcomes: dict[str, dict], model: str) -> float:
    """Upper-bound cost of finishing this model's wave: remaining passes × rate."""
    remaining = 0
    for o in outcomes.values():
        if o["status"] == "todo":
            remaining += MAX_PASSES
        elif o["status"] == "active":
            remaining += MAX_PASSES - o["passes_used"]
    return round(remaining * PASS_EST[model], 6)


# ---------- synthetic fixture (dry-run) ----------

def _syn_loop(model: str, pid: str, start: int, baseline: int,
              faileds: list[int], invalid_at: int | None = None) -> list[dict]:
    recs = [{"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
             "baseline_ok": True, "start_source": "m3",
             "start_class": entry_class(start, baseline), "start_failed": start,
             "graded": {"passed": 20 - start, "failed": start},
             "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                         "stdout": "0"}]}]
    for k, f in enumerate(faileds, 1):
        if k == invalid_at:
            recs.append({"model": model, "problem_id": pid, "pass": k,
                         "invalid": "parse failure", "first_parse": False,
                         "cost": 0.001})
            break
        recs.append({"model": model, "problem_id": pid, "pass": k,
                     "first_parse": True, "patch": "x = 1", "cost": 0.001,
                     "finish_reason": "stop", "feedback": {"test_index": 0},
                     "recovered": f == 0,
                     "graded": {"passed": 20 - f, "failed": f},
                     "detail": [{"i": 0, "rc": 0, "timed_out": False,
                                 "passed": f == 0, "stdout": "1"}]})
        if f == 0:
            break
    return recs


def _synthetic() -> tuple[list[dict], dict[str, list[str]], dict[str, dict[str, dict]]]:
    """Fixture models covering REPORTED + UNDERPOWERED, both D12 classes,
    INVALID, transient re-cross, durable re-cross, and never-re-crossed."""
    records, subsets, entry_by = [], {}, {}

    def _add(model: str, plan: list[tuple[int, int, list[int], int | None]]):
        subsets[model] = [f"{model[-1]}{i:02d}" for i in range(len(plan))]
        entry_by[model] = {}
        for pid, (start, base, faileds, inv) in zip(subsets[model], plan):
            entry_by[model][pid] = {"start_patch": f"frozen-{pid}",
                                    "start_failed": start, "baseline": base,
                                    "class": entry_class(start, base)}
            records.extend(_syn_loop(model, pid, start, base, faileds, inv))

    # REPORTED: 24 loops, 1 invalid -> clean 23 >= 20
    _add("demo/reported",
         [(16, 1, [0], None)] * 5                       # recovered at pass 1
         + [(16, 1, [5, 0], None)] * 2                  # recovered at pass 2
         + [(8, 3, [6, 3, 7, 7, 7], None)] * 3          # transient re-cross
         + [(8, 3, [6, 2, 2, 2, 2], None)] * 2          # durable re-cross, no full fix
         + [(10, 6, [12, 13, 13, 13, 13], None)] * 5    # deepened, never re-crossed
         + [(10, 6, [10, 10, 10, 10, 10], None)] * 4    # held, never re-crossed
         + [(1, 3, [1, 1, 1, 1, 1], None)] * 2          # pass-0 class, durable
         + [(9, 2, [5, 5, 5, 5, 5], 2)])                # INVALID at pass 2
    # UNDERPOWERED: 6 loops, 1 invalid -> clean 5 < 20
    _add("demo/underpowered",
         [(16, 1, [0], None),
          (8, 3, [6, 3, 7, 7, 7], None),
          (10, 6, [12, 13, 13, 13, 13], None),
          (10, 6, [10, 10, 10, 10, 10], None),
          (1, 1, [1, 1, 1, 1, 1], None),
          (9, 2, [5, 5, 5, 5, 5], 2)])
    return records, subsets, entry_by


# ---------- meter + ledger (per-milestone regime; M0–M3 ledgers are frozen) ----------

def _meter() -> CostMeter:
    m = CostMeter(M4_CAP)
    ledger = M4_DIR / "cost_ledger.json"
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        m.total, m.calls = prior["total"], prior["calls"]
    return m


def _save_meter(m: CostMeter):
    (M4_DIR / "cost_ledger.json").write_text(
        json.dumps({"total": round(m.total, 6), "calls": m.calls, "cap": m.cap}))


def _lifetime(m4_total: float) -> float:
    prior = 0.0
    for ledger in PRIOR_LEDGERS:
        if ledger.exists():
            prior += json.loads(ledger.read_text())["total"]
    return prior + m4_total


def _bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text())["bank"]


def _live_entry(model: str) -> dict[str, dict]:
    """Entry extracted fresh from the M3 record (the byte-identity reference)."""
    bank_by = {e["problem_id"]: e for e in _bank()}
    m3_subset = json.loads(M3_SUBSETS_PATH.read_text())["subsets"][model]
    baselines = {pid: bank_by[pid]["buggy_failed_baseline"] for pid in m3_subset}
    return m4_entry(_read_jsonl(M3_TRIALS_PATH), model, m3_subset, baselines)


def _load_subsets() -> dict:
    return json.loads(SUBSETS_PATH.read_text())


# ---------- subset (free) ----------

def cmd_subset() -> int:
    M4_DIR.mkdir(parents=True, exist_ok=True)
    subsets, entries = {}, {}
    for model in MODELS:
        entry = _live_entry(model)
        if len(entry) != EXPECTED_ENTRY[model]:
            print(f"HALT: {model} entry {len(entry)} != frozen {EXPECTED_ENTRY[model]}")
            return 1
        n_dam = sum(1 for e in entry.values() if e["class"] == CLASS_DAMAGED)
        if n_dam != EXPECTED_DAMAGED[model]:
            print(f"HALT: {model} damaged {n_dam} != frozen {EXPECTED_DAMAGED[model]}")
            return 1
        subsets[model] = list(entry)
        entries[model] = entry
        print(f"{model}: {len(entry)} corrupted finals enter "
              f"({n_dam} damaged, {len(entry) - n_dam} at-or-below-baseline) "
              "— UNDERPOWERED at entry, pre-declared")
    SUBSETS_PATH.write_text(json.dumps({
        "derived_from": ["data/m3/trials.jsonl", "data/m3/subsets.json"],
        "rule": "M3 status exhausted (clean non-escaped); start = pass-5 patch "
                "byte-frozen; D12-A classes vs buggy baseline",
        "subsets": subsets, "entry": entries}, indent=1))
    print(f"wrote {SUBSETS_PATH}")
    return 0


# ---------- run (paid, per model, resumable) ----------

def cmd_run(model: str) -> int:
    if model not in MODELS:
        print(f"unknown model {model}; roster: {MODELS}")
        return 1
    M4_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank_by = {e["problem_id"]: e for e in _bank()}
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    doc = _load_subsets()
    subset, entry = doc["subsets"][model], doc["entry"][model]
    live = _live_entry(model)
    drifted = [pid for pid in subset
               if live.get(pid, {}).get("start_patch") != entry[pid]["start_patch"]]
    if drifted:
        print(f"HALT: frozen start patches no longer byte-match the M3 record: {drifted}")
        return 7
    records = _read_jsonl(TRIALS_PATH)
    outcomes = m4_outcomes(records, model, entry)
    est = wave_estimate_m4(outcomes, model)
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
        if len(paid) != ARM_SMOKE_N:
            return True
        parse = sum(1 for fp, _ in paid if fp)
        mean = sum(c for _, c in paid) / len(paid)
        print(f"  smoke gate @{ARM_SMOKE_N}: parse {parse}/{ARM_SMOKE_N}, "
              f"mean ${mean:.5f}/pass")
        if not arm_gate(parse, mean, PASS_EST[model]):
            print("HALT: smoke gate — to Kyle")
            return False
        return True

    try:
        for pid in subset:
            bank_entry = bank_by[pid]
            meta = entry[pid]
            state = loop_state(by_pid[pid])
            if state["status"] in ("recovered", "invalid", "exhausted"):
                continue
            if state["status"] == "need_grade0":
                counts, detail = grade_detail(bank_entry, meta["start_patch"], semantics)
                if counts["failed"] != meta["start_failed"]:
                    print(f"HALT: grade-0 integrity — {pid} failed {counts['failed']} "
                          f"!= recorded M3 final {meta['start_failed']} "
                          "(harness drift; investigate before resuming)")
                    return 6
                base = meta["baseline"]
                ok = (counts["failed"] > base if meta["class"] == CLASS_DAMAGED
                      else 1 <= counts["failed"] <= base)
                if not ok:
                    print(f"HALT: entry-class violation — {pid} failed "
                          f"{counts['failed']} vs baseline {base} does not match "
                          f"frozen class {meta['class']}")
                    return 8
                rec = {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
                       "baseline_ok": True, "start_source": "m3",
                       "start_class": meta["class"], "start_failed": counts["failed"],
                       "drift_from_buggy": round(
                           drift_ratio(bank_entry["buggy_code"], meta["start_patch"]), 4),
                       "graded": counts, "detail": detail}
                _append_jsonl(TRIALS_PATH, rec)
                state = {"status": "run_pass", "next": 1, "code": None, "detail": detail}
            while state["status"] == "run_pass":
                k = state["next"]
                code = state["code"] or meta["start_patch"]
                fb = feedback_fields(bank_entry, state["detail"])
                prompt = m2_repair_prompt(bank_entry["description"], code, fb)
                call = _pass_call(model, prompt, m)
                paid.append((call["first_parse"], call["cost"]))
                if call["patch"] is None:
                    _append_jsonl(TRIALS_PATH, {"model": model, "problem_id": pid,
                                                "pass": k, "invalid": "parse failure",
                                                "first_parse": False,
                                                "cost": call["cost"], "feedback": fb,
                                                "finish_reason": call["finish_reason"]})
                    _save_meter(m)
                    if not _smoke_check():
                        return 2
                    break  # loop INVALID — terminal
                counts, detail = grade_detail(bank_entry, call["patch"], semantics)
                recovered = counts["failed"] == 0
                _append_jsonl(TRIALS_PATH, {
                    "model": model, "problem_id": pid, "pass": k,
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
    model_rows = [r for r in _read_jsonl(TRIALS_PATH)
                  if r.get("model") == model and r.get("pass", 0) >= 1
                  and "first_parse" in r]
    parse_ok = sum(1 for r in model_rows if r["first_parse"])
    if not parse_floor_ok(parse_ok, len(model_rows)):
        print(f"HALT: parse floor — {parse_ok}/{len(model_rows)} < 80%; "
              "one format revision left for deepseek, none for qwen — to Kyle")
        return 5
    outcomes = m4_outcomes(_read_jsonl(TRIALS_PATH), model, entry)
    rec_n = sum(1 for o in outcomes.values() if o["status"] == "recovered")
    rx = sum(1 for o in outcomes.values()
             if o["status"] in ("recovered", "exhausted")
             and o["recross_at"] not in (None, 0))
    print(f"{model}: wave complete — recovered {rec_n}/{len(subset)} · "
          f"re-crossed (pass ≥1) {rx} · parse {parse_ok}/{len(model_rows)} · "
          f"meter ${m.total:.4f} · lifetime ${_lifetime(m.total):.4f}")
    return 0


# ---------- verdict (free) ----------

def cmd_verdict(synthetic: bool) -> int:
    if synthetic:
        records, subsets, entry_by = _synthetic()
        models = sorted(subsets)
        print("=== DRY RUN on synthetic records (no paid data) ===\n")
    else:
        records = _read_jsonl(TRIALS_PATH)
        doc = _load_subsets()
        subsets, entry_by = doc["subsets"], doc["entry"]
        models = MODELS

    out: dict = {"models": {}, "per_loop": {}}
    for model in models:
        o = m4_outcomes(records, model, entry_by[model])
        v = model_verdict_m4(o)
        if not synthetic and v["unfinished"]:
            print(f"{model}: {v['unfinished']} loops unfinished — finish the wave first")
            return 1
        print(f"{model}  →  {v['label']} (pre-declared; clean {v['clean_n']} < 20)"
              if v["label"] == "UNDERPOWERED" else f"{model}  →  {v['label']}")
        print(f"  IDR (damaged {v['idr_n']}): {v['irrecoverable']}/{v['idr_n']} "
              f"irrecoverable (rate {v['idr']})  wilson {v['idr_wilson']}")
        print(f"  re-cross curve (cum by pass, damaged): {v['recross_curve']}  ·  "
              f"pass-0 pair: {v['pass0_pids']} (re-crossed at pass 0 by definition)")
        print(f"  sensitivity (all {v['sens_n']} clean): "
              f"{v['sens_irrecoverable']}/{v['sens_n']} (rate {v['sens_idr']})")
        print(f"  durable (final ≤ baseline): damaged {v['durable_damaged']}"
              f"/{v['idr_n']} · all {v['durable_all']}/{v['clean_n']}")
        print(f"  full-fix recovery: {v['recovered']}/{v['clean_n']} "
              f"(rate {v['rate']})  wilson {v['wilson']}  curve {v['curve']}  "
              f"pass-1 {v['pass1_recovered']}  mean passes {v['mean_passes']}")
        print(f"  trajectory vs M4 start: {v['trajectory']}  ·  "
              f"invalid loops {v['invalid']}")
        rows = [r for r in records if r.get("model") == model
                and r.get("pass", 0) >= 1 and "first_parse" in r]
        v["pass_calls"] = len(rows)
        v["first_parse"] = sum(1 for r in rows if r["first_parse"])
        v["cost"] = round(sum(r.get("cost", 0) for r in rows), 4)
        drifts = [r["drift_from_buggy"] for r in records
                  if r.get("model") == model and r.get("pass") == 0
                  and "drift_from_buggy" in r]
        v["mean_drift_from_buggy"] = (round(sum(drifts) / len(drifts), 4)
                                      if drifts else None)
        print(f"  pass-calls {v['pass_calls']} · first-parse {v['first_parse']} · "
              f"cost ${v['cost']} · mean start drift {v['mean_drift_from_buggy']}")
        table = per_loop_rows(o, subsets[model])
        out["per_loop"][model] = table
        print("  per-loop: pid · class · base · start → best/final · "
              "recross@ · recovered@ · status")
        for r in table:
            print(f"    {r['problem_id']} · {r['class'][:7]} · {r['baseline']} · "
                  f"{r['start_failed']} → {r['best_failed']}/{r['final_failed']} · "
                  f"{r['recross_at']} · {r['recovered_at']} · {r['status']}")
        out["models"][model] = v

    if not synthetic:
        m2_res = json.loads(M2_RESULTS_PATH.read_text())["models"]
        gate = {}
        for model in models:
            v = out["models"][model]
            m2v = m2_res[model]
            d, lo, hi = newcombe_diff(v["recovered"], v["clean_n"],
                                      m2v["recovered"], m2v["clean_n"])
            gate[model] = {
                "m4_recovered": [v["recovered"], v["clean_n"]],
                "m2_recovered": [m2v["recovered"], m2v["clean_n"]],
                "newcombe_m2_minus_m4": [round(d, 4), round(lo, 4), round(hi, 4)],
                "label": "UNDERPOWERED",  # pre-declared at M3 close (both < 20)
            }
            print(f"\nchain gate {model}: M2 {m2v['recovered']}/{m2v['clean_n']} "
                  f"vs M4 {v['recovered']}/{v['clean_n']} — Newcombe M2−M4 "
                  f"{d:+.1%} [{lo:+.1%}, {hi:+.1%}] → UNDERPOWERED (pre-declared)")
        out["chain_gate"] = gate
        m4_total = _meter().total
        out["cost"] = {"m4_total": round(m4_total, 4),
                       "lifetime": round(_lifetime(m4_total), 4)}
        RESULTS_PATH.write_text(json.dumps(out, indent=1))
        print(f"\ncost: {json.dumps(out['cost'])}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("subset", help="freeze per-model corrupted-final entry (free)")
    r = sub.add_parser("run", help="self-repair loop wave from M3 finals (paid, resumable)")
    r.add_argument("--model", required=True)
    v = sub.add_parser("verdict", help="IDR + re-cross curves + chain-gate contrast")
    v.add_argument("--synthetic", action="store_true", help="dry-run on fixtures")
    args = ap.parse_args()
    if args.cmd == "subset":
        raise SystemExit(cmd_subset())
    if args.cmd == "run":
        raise SystemExit(cmd_run(args.model))
    raise SystemExit(cmd_verdict(args.synthetic))
