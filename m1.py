"""m1.py — Milestone 1 (RE-SCOPED): three-arm full-bank repair + the damage funnel.

Signed off 2026-07-10 (docs/M1-BRIEF.md): D5-A (all-v2 T2 instructions), D6-A
(K=150), D7-A ($1.00 cap on data/m1/cost_ledger.json — M0's pilot ledger is frozen
as the M0 record and never resumed). No probes, no McNemar; awareness is reported
as the M0 tier-level null.

Subcommands:
  generate — paid. T2 (protocol v2) + T1 drafts for every bank[0:K] problem not
             carried from M0 (carry rule: T2 iff accepted AND v2; T1 iff accepted).
             Auto smoke-gate at draft job 10; D2 generator-fallback rule armed.
  run      — paid. --model <slug>: repair waves in arm order T3 -> T2 -> T1 (a
             cap-fire protects the primary and the funnel). Each trial is appended
             to data/m1/trials.jsonl (with patch — M3 needs damaged T2 states)
             the moment it returns; re-runs skip existing (model, problem, arm)
             keys, so waves are resumable without re-spending.
  grade    — free, idempotent. Grades ungraded patches in the sandbox (S-exact),
             sets repair_success/damaged/comply, rewrites trials.jsonl atomically.
  verdict  — free. Paired T2-vs-T3 primary (newcombe_paired_diff, delta >= 10 pts),
             secondaries with Wilson CIs, M2/M3 funnel checkpoints, M2-M4 cost
             re-projection. `--synthetic` dry-runs every verdict label path on
             fixture records, per the "dry-run before paid data" contract.

Every threshold here is pre-committed in docs/M1-BRIEF.md and unit-tested in
test_m1.py BEFORE any paid call.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from client import BudgetExceeded, CostMeter, GENERATOR, GENERATOR_FALLBACK
from pilot import _gen_one, _grade, _repair_trial
from regions import region_compliance
from stats import newcombe_paired_diff, wilson

DATA = Path(__file__).parent / "data"
M1_DIR = DATA / "m1"
BANK_PATH = DATA / "bank.json"
TRIALS_PATH = M1_DIR / "trials.jsonl"
INSTR_PATH = M1_DIR / "instructions.json"
RESULTS_PATH = DATA / "m1_results.json"
M0_LEDGER = DATA / "pilot" / "cost_ledger.json"
SPOTREAD = Path(__file__).parent / "docs" / "M1-SPOTREAD.md"

# Signed constants (docs/M1-BRIEF.md, 2026-07-10)
K = 150                    # D6-A: the formula's answer (binding on deepseek 2/12)
M1_CAP = 1.00              # D7-A
LIFETIME_CAP = 5.00        # KICKOFF budget target, enforced as a wave-start guard
MIN_PAIRS = 20             # N>=20 clean per gated cell, else UNDERPOWERED (auto)
DELTA_GATE = 0.10          # KICKOFF delta: drop >= 10 points
FUNNEL_TARGET = 20         # damaged-N needed per model for M3 entry
EST_DRAFT_COST = 0.00095   # measured M0 rate over all 34 draft calls
GEN_SMOKE_N = 10
ARM_SMOKE_N = 5
ARM_ORDER = ("T3", "T2", "T1")  # cap-fire sacrifices T1, never the primary
MODELS = [
    "deepseek/deepseek-chat-v3.1",
    "qwen/qwen3-coder-30b-a3b-instruct",
]
ARM_EST = {  # measured pilot per-trial cost (incl. parse-retry spend), $/trial
    "deepseek/deepseek-chat-v3.1": {"T1": 0.00041, "T2": 0.00050, "T3": 0.00073},
    "qwen/qwen3-coder-30b-a3b-instruct": {"T1": 0.00031, "T2": 0.00025, "T3": 0.00056},
}


# ---------- pre-committed pure logic (unit-tested before any paid call) ----------

def verdict_label(d: float, lo: float, hi: float, n_pairs: int) -> tuple[str, bool]:
    """M1 primary verdict per model. Returns (label, reverse_direction).

    REPRODUCED-analog: CI excludes 0 on the drop side AND point drop >= DELTA_GATE.
    PARTIAL: real-but-small, or big-but-straddling. NULL otherwise (a CI fully on
    the reverse side is flagged). UNDERPOWERED overrides everything at n < 20.
    """
    if n_pairs < MIN_PAIRS:
        return ("UNDERPOWERED", False)
    if lo > 0.0:
        return ("REPRODUCED", False) if d >= DELTA_GATE else ("PARTIAL", False)
    if hi < 0.0:
        return ("NULL", True)
    return ("PARTIAL", False) if d >= DELTA_GATE else ("NULL", False)


def pairs_table(records: list[dict], model: str) -> dict:
    """2x2 discordance table over problems valid in BOTH T3 (mech) and T2 (base).

    A trial is valid iff it was graded (`repair_success` present) and not INVALID.
    Later records win on key collisions (defensive; resume skips should prevent them).
    """
    succ: dict[tuple[str, str], bool] = {}
    for r in records:
        if r.get("model") != model or r.get("arm") not in ("T3", "T2"):
            continue
        if "repair_success" in r and "invalid" not in r:
            succ[(r["problem_id"], r["arm"])] = bool(r["repair_success"])
    e = f = g = h = 0
    for pid in {pid for pid, _ in succ}:
        if (pid, "T3") in succ and (pid, "T2") in succ:
            t3, t2 = succ[(pid, "T3")], succ[(pid, "T2")]
            e += t3 and t2
            f += t3 and not t2
            g += (not t3) and t2
            h += (not t3) and (not t2)
    return {"both": e, "mech_only": f, "base_only": g, "neither": h,
            "n_pairs": e + f + g + h}


def gen_jobs(bank: list[dict], prior: list[dict], k: int) -> tuple[list, list]:
    """Plan the generation wave under D5-A. Returns (jobs, carried).

    Carry rule: a T2 record carries iff accepted AND protocol v2 (v1-organic
    drafts regenerate — one manipulation protocol bank-wide); a T1 record carries
    iff accepted. T2 jobs come first so the draft-10 smoke gate reads the
    informative kind. Later prior records win on key collisions (M1 partial
    results overlay the M0 set, making a halted generate wave resumable).
    """
    prior_by: dict[tuple[str, str], dict] = {}
    for r in prior:
        prior_by[(r["kind"], r["problem_id"])] = r
    carried, t2_jobs, t1_jobs = [], [], []
    for e in bank[:k]:
        pid = e["problem_id"]
        t2 = prior_by.get(("T2", pid))
        if t2 and t2.get("final") and t2.get("protocol") == "v2":
            carried.append(t2)
        else:
            t2_jobs.append(("T2", e))
        t1 = prior_by.get(("T1", pid))
        if t1 and t1.get("final"):
            carried.append(t1)
        else:
            t1_jobs.append(("T1", e))
    return t2_jobs + t1_jobs, carried


def existing_keys(lines) -> set[tuple[str, str, str]]:
    """Resume keys from trials.jsonl lines; blank/partial lines are skipped."""
    keys = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if all(k in r for k in ("model", "problem_id", "arm")):
            keys.add((r["model"], r["problem_id"], r["arm"]))
    return keys


def gen_gate(accepted: int, mean_cost: float) -> bool:
    """Draft-10 smoke gate: first-attempt acceptance >= 7/10, cost in band."""
    return accepted >= 7 and mean_cost <= 2 * EST_DRAFT_COST


def arm_gate(parse_ok: int, mean_cost: float, arm_est: float) -> bool:
    """Trial-5 smoke gate per arm: first-parse >= 4/5, cost <= 2x the arm estimate."""
    return parse_ok >= 4 and mean_cost <= 2 * arm_est


def parse_floor_ok(parse_ok: int, total: int) -> bool:
    """T-D analog per completed arm: first-parse rate >= 80% (vacuously ok at 0)."""
    return total == 0 or parse_ok / total >= 0.80


def lifetime_ok(prior_total: float, wave_est: float) -> bool:
    """The $5 lifetime guard: no wave starts if its projection crosses the cap."""
    return prior_total + wave_est <= LIFETIME_CAP + 1e-9


# ---------- meter + ledger (per-milestone regime; M0's ledger is frozen) ----------

def _meter() -> CostMeter:
    m = CostMeter(M1_CAP)
    ledger = M1_DIR / "cost_ledger.json"
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        m.total, m.calls = prior["total"], prior["calls"]
    return m


def _save_meter(m: CostMeter):
    (M1_DIR / "cost_ledger.json").write_text(
        json.dumps({"total": round(m.total, 6), "calls": m.calls, "cap": m.cap}))


def _lifetime(m1_total: float) -> float:
    m0 = json.loads(M0_LEDGER.read_text())["total"] if M0_LEDGER.exists() else 0.0
    return m0 + m1_total


def _bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text())["bank"]


def _read_trials() -> list[dict]:
    if not TRIALS_PATH.exists():
        return []
    return [json.loads(x) for x in TRIALS_PATH.read_text().splitlines() if x.strip()]


def _append_trial(rec: dict):
    with open(TRIALS_PATH, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


# ---------- wave 1: generate (paid) ----------

def cmd_generate() -> int:
    M1_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank = _bank()
    prior = json.loads((DATA / "pilot" / "instructions.json").read_text())["results"]
    if INSTR_PATH.exists():  # resume: M1 partials overlay the M0 set
        prior = prior + json.loads(INSTR_PATH.read_text())["results"]
    jobs, carried = gen_jobs(bank, prior, K)
    est = len(jobs) * EST_DRAFT_COST * 1.3
    print(f"generate: {len(jobs)} jobs ({sum(1 for k, _ in jobs if k == 'T2')} T2, "
          f"rest T1), {len(carried)} carried · est ${est:.3f}")
    if not lifetime_ok(_lifetime(m.total), est):
        print(f"HALT: lifetime guard — ${_lifetime(m.total):.2f} + ${est:.2f} > $5.00")
        return 4

    gen_model = GENERATOR
    fallback_note = None
    results: list[dict] = []

    def _save(note: str | None = None):
        merged: dict[tuple[str, str], dict] = {}
        for r in carried:
            merged[(r["kind"], r["problem_id"])] = {**r, "carried_from_m0": True}
        for r in results:
            merged[(r["kind"], r["problem_id"])] = r
        out = list(merged.values())
        t2_new = [r for r in results if r["kind"] == "T2"]
        acc_first = sum(1 for r in t2_new if r["attempts"] and r["attempts"][0]["accepted"])
        calls = [a["cost"] for r in results for a in r["attempts"]]
        report = {
            "protocol": "v2 (T2); T1 has no protocol split",
            "generator_used": gen_model,
            "fallback_note": note,
            "jobs_run": len(results),
            "t2_drafts_new": len(t2_new),
            "t2_first_attempt_accepted": acc_first,
            "unconstructable": sum(1 for r in results if r.get("unconstructable")),
            "coverage_T2": sum(1 for r in out if r["kind"] == "T2" and r["final"]),
            "coverage_T1": sum(1 for r in out if r["kind"] == "T1" and r["final"]),
            "k": K,
            "mean_draft_cost": round(sum(calls) / len(calls), 6) if calls else None,
            "wave_cost": round(m.total, 4),
            "lifetime": round(_lifetime(m.total), 4),
        }
        INSTR_PATH.write_text(json.dumps({"report": report, "results": out}, indent=1))
        return report

    try:
        for i, (kind, entry) in enumerate(jobs):
            results.append(_gen_one(kind, entry, gen_model, m,
                                    protocol="v2" if kind == "T2" else "v1"))
            _save_meter(m)
            if i % 10 == 9:  # partial save: a crash mid-wave orphans no paid draft
                _save(fallback_note)
            if i == GEN_SMOKE_N - 1:
                first10 = results[:GEN_SMOKE_N]
                acc = sum(1 for r in first10 if r["attempts"] and r["attempts"][0]["accepted"])
                calls = [a["cost"] for r in first10 for a in r["attempts"]]
                mean = sum(calls) / len(calls)
                print(f"smoke gate @10: accepted {acc}/10, mean ${mean:.5f}/draft")
                if acc < 7:
                    _save("HALTED at smoke gate: acceptance")
                    print("HALT: generation acceptance below 7/10 — to Kyle")
                    return 2
                if mean > 2 * EST_DRAFT_COST:  # D2 fallback rule, pre-committed
                    gen_model = GENERATOR_FALLBACK
                    fallback_note = f"D2 fallback fired at ${mean:.5f}/draft"
                    print(fallback_note)
    except BudgetExceeded as e:
        _save_meter(m)
        _save(f"HALTED: {e}")
        print(f"HALT: {e}")
        return 3

    _save_meter(m)
    report = _save(fallback_note)
    _write_spotread([r for r in results if r["kind"] == "T2" and r["final"]][:5], bank)
    print(json.dumps(report, indent=2))
    print(f"meter: ${m.total:.4f} of ${m.cap:.2f} · lifetime ${_lifetime(m.total):.4f}")
    return 0


def _write_spotread(samples: list[dict], bank: list[dict]) -> None:
    by_pid = {e["problem_id"]: e for e in bank}
    lines = [
        "# M1 spot-read — 5 accepted T2 (wrong-location) instructions from the freeze",
        "",
        "*Kyle: face-validity record (same artifact as M0's). Wrongness is already*",
        "*mechanically proven per draft. Veto before the repair waves close discards*",
        "*affected trials (M1-BRIEF).*",
        "",
    ]
    for i, s in enumerate(samples, 1):
        e = by_pid[s["problem_id"]]
        lines += [f"## Sample {i} — problem {s['problem_id']}", "",
                  "```python", e["buggy_code"].rstrip(), "```", "",
                  f"> {s['render']}", ""]
    SPOTREAD.write_text("\n".join(lines))


# ---------- wave 2: run (paid, per model, resumable) ----------

def cmd_run(model: str) -> int:
    if model not in MODELS:
        print(f"unknown model {model}; roster: {MODELS}")
        return 1
    M1_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank = _bank()[:K]
    instr = json.loads(INSTR_PATH.read_text())["results"]
    renders = {(r["kind"], r["problem_id"]): r["render"] for r in instr if r["final"]}
    done = existing_keys(TRIALS_PATH.read_text().splitlines()) if TRIALS_PATH.exists() else set()

    for arm in ARM_ORDER:
        todo = [e for e in bank if (model, e["problem_id"], arm) not in done]
        est = len(todo) * ARM_EST[model][arm]
        print(f"— {model} {arm}: {len(todo)} to run · est ${est:.3f}", flush=True)
        if not lifetime_ok(_lifetime(m.total), est):
            print(f"HALT: lifetime guard — ${_lifetime(m.total):.2f} + ${est:.2f} > $5.00")
            return 4
        paid: list[dict] = []
        try:
            for e in todo:
                pid = e["problem_id"]
                if arm != "T3" and (arm, pid) not in renders:
                    _append_trial({"model": model, "problem_id": pid, "arm": arm,
                                   "invalid": "no verified instruction"})
                    continue
                rec = _repair_trial(model, e, arm, renders.get((arm, pid)), m)
                _append_trial(rec)
                _save_meter(m)
                paid.append(rec)
                if len(paid) == ARM_SMOKE_N:
                    parse = sum(1 for r in paid if r["first_parse"])
                    mean = sum(r["cost"] for r in paid) / len(paid)
                    print(f"  smoke gate @5: parse {parse}/5, mean ${mean:.5f}/trial")
                    if not arm_gate(parse, mean, ARM_EST[model][arm]):
                        print("HALT: arm smoke gate — to Kyle")
                        return 2
        except BudgetExceeded as e:
            _save_meter(m)
            print(f"HALT: {e} (resumable — re-run after a cap decision)")
            return 3
        _grade_all()  # free; also refreshes damaged/comply for the wave report
        arm_recs = [r for r in _read_trials()
                    if r.get("model") == model and r.get("arm") == arm
                    and "invalid" not in r]
        parse_ok = sum(1 for r in arm_recs if r.get("first_parse"))
        if not parse_floor_ok(parse_ok, len(arm_recs)):
            print(f"HALT: parse floor — {parse_ok}/{len(arm_recs)} < 80% on {arm}; "
                  "no format revisions left for qwen (M0), one for deepseek — to Kyle")
            return 5
        print(f"  {arm} complete: parse {parse_ok}/{len(arm_recs)}, "
              f"meter ${m.total:.4f}, lifetime ${_lifetime(m.total):.4f}")
    print(f"{model}: all arms complete")
    return 0


# ---------- grade (free, idempotent) ----------

def _grade_all() -> int:
    records = _read_trials()
    if not records:
        print("no trials to grade")
        return 0
    bank_by = {e["problem_id"]: e for e in _bank()}
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    instr = json.loads(INSTR_PATH.read_text())["results"] if INSTR_PATH.exists() else []
    targets = {r["problem_id"]: (r["final"]["target_start_line"], r["final"]["target_end_line"])
               for r in instr if r["kind"] == "T2" and r["final"]}
    todo = [r for r in records if r.get("patch") and "graded" not in r]
    if todo:
        print(f"grading {len(todo)} patches …", flush=True)
        with ThreadPoolExecutor(max_workers=4) as ex:
            graded = list(ex.map(
                lambda r: _grade(bank_by[r["problem_id"]], r["patch"], semantics), todo))
        for r, g in zip(todo, graded):
            e = bank_by[r["problem_id"]]
            r["graded"] = g
            r["repair_success"] = g["failed"] == 0
            r["damaged"] = g["failed"] > e["buggy_failed_baseline"]
            if r["arm"] == "T2" and r["problem_id"] in targets:
                r["comply"] = region_compliance(e["buggy_code"], r["patch"],
                                                *targets[r["problem_id"]])
        tmp = TRIALS_PATH.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in records))
        tmp.replace(TRIALS_PATH)
    return 0


# ---------- verdict (free) ----------

def _arm_stats(records: list[dict], model: str, arm: str) -> dict:
    recs = [r for r in records if r.get("model") == model and r.get("arm") == arm]
    valid = [r for r in recs if "repair_success" in r and "invalid" not in r]
    k = sum(1 for r in valid if r["repair_success"])
    lo, hi = wilson(k, len(valid))
    return {"n": len(recs), "valid": len(valid), "pass": k,
            "rate": round(k / len(valid), 4) if valid else None,
            "wilson": [round(lo, 4), round(hi, 4)],
            "invalid": len(recs) - len(valid),
            "cost": round(sum(r.get("cost", 0) for r in recs), 4)}


def cmd_verdict(synthetic: bool) -> int:
    if synthetic:
        records = _synthetic_records()
        models = sorted({r["model"] for r in records})
        print("=== DRY RUN on synthetic records (no paid data) ===\n")
    else:
        records = _read_trials()
        ungraded = sum(1 for r in records if r.get("patch") and "graded" not in r)
        if ungraded:
            print(f"{ungraded} trials ungraded — run: uv run python m1.py grade")
            return 1
        models = MODELS

    out: dict = {"models": {}}
    for model in models:
        t = pairs_table(records, model)
        d, lo, hi = newcombe_paired_diff(t["both"], t["mech_only"],
                                         t["base_only"], t["neither"])
        label, reverse = verdict_label(d, lo, hi, t["n_pairs"])
        arms = {arm: _arm_stats(records, model, arm) for arm in ("T1", "T2", "T3")}
        t2 = [r for r in records if r.get("model") == model and r.get("arm") == "T2"
              and "repair_success" in r and "invalid" not in r]
        damaged = sum(1 for r in t2 if r.get("damaged"))
        comply = sum(1 for r in t2 if r.get("comply"))
        failed_t3 = arms["T3"]["valid"] - arms["T3"]["pass"]
        rev = "  (REVERSE: T2 above T3)" if reverse else ""
        print(f"{model}  →  {label}{rev}")
        print(f"  primary: drop d={d:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]  "
              f"pairs={t['n_pairs']} (e={t['both']} f={t['mech_only']} "
              f"g={t['base_only']} h={t['neither']})")
        for arm in ("T3", "T2", "T1"):
            a = arms[arm]
            print(f"  {arm}: pass {a['pass']}/{a['valid']} "
                  f"wilson {a['wilson']}  invalid {a['invalid']}")
        dmg_lo, dmg_hi = wilson(damaged, len(t2)) if t2 else (0.0, 1.0)
        print(f"  T2 comply {comply}/{len(t2)} · damaged {damaged}/{len(t2)} "
              f"wilson [{dmg_lo:.3f}, {dmg_hi:.3f}]")
        m3 = "OK" if damaged >= FUNNEL_TARGET else "EXTEND (T2-only, frozen order, pre-M3)"
        m2 = "OK" if failed_t3 >= FUNNEL_TARGET else "STARVED"
        print(f"  funnel: M3 entry damaged-N={damaged} → {m3} · "
              f"M2 entry failed-T3={failed_t3} → {m2}")
        out["models"][model] = {
            "label": label, "reverse": reverse,
            "drop": round(d, 4), "ci": [round(lo, 4), round(hi, 4)],
            "pairs": t, "arms": arms,
            "t2_comply": comply, "t2_damaged": damaged, "failed_t3": failed_t3,
        }

    if not synthetic:
        m1_total = _meter().total
        cost_line = {"m1_total": round(m1_total, 4),
                     "lifetime": round(_lifetime(m1_total), 4)}
        # measured-rate re-projection for the M2 brief (5-pass upper bounds)
        proj = {}
        for model in models:
            a = out["models"][model]["arms"]
            paid = sum(x["cost"] for x in a.values())
            n_valid = sum(x["valid"] for x in a.values())
            mean = paid / n_valid if n_valid else 0.0
            proj[model] = {
                "m2_max": round(out["models"][model]["failed_t3"] * 5 * mean, 3),
                "m3_max": round(out["models"][model]["t2_damaged"] * 5
                                * (mean + EST_DRAFT_COST), 3),
                "m4_max": round(out["models"][model]["t2_damaged"] * 5 * mean, 3),
            }
        out["cost"] = cost_line
        out["projection_upper_bounds"] = proj
        RESULTS_PATH.write_text(json.dumps(out, indent=1))
        print(f"\ncost: {json.dumps(cost_line)}")
        print(f"M2–M4 re-projection (5-pass upper bounds): {json.dumps(proj)}")
    return 0


# ---------- synthetic fixture (dry-run) ----------

def _pairs_to_records(model: str, e: int, f: int, g: int, h: int) -> list[dict]:
    recs, i = [], 0
    for t3, t2, count in ((True, True, e), (True, False, f),
                          (False, True, g), (False, False, h)):
        for _ in range(count):
            pid = f"syn{i:03d}"
            recs.append({"model": model, "problem_id": pid, "arm": "T3",
                         "repair_success": t3, "cost": 0.0007})
            recs.append({"model": model, "problem_id": pid, "arm": "T2",
                         "repair_success": t2, "cost": 0.0005, "comply": True,
                         "damaged": not t2 and i % 2 == 0})
            recs.append({"model": model, "problem_id": pid, "arm": "T1",
                         "repair_success": t3 or t2, "cost": 0.0004})
            i += 1
    recs.append({"model": model, "problem_id": "syn-bad", "arm": "T2",
                 "invalid": "no verified instruction"})
    return recs


def _synthetic_records() -> list[dict]:
    return (
        _pairs_to_records("demo/reproduced", e=20, f=25, g=2, h=13)
        + _pairs_to_records("demo/partial-straddle", e=6, f=6, g=3, h=9)
        + _pairs_to_records("demo/null", e=16, f=4, g=4, h=16)
        + _pairs_to_records("demo/underpowered", e=5, f=4, g=2, h=4)
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate", help="T1+T2 instruction wave (paid, smoke-gated)")
    r = sub.add_parser("run", help="repair waves T3→T2→T1 (paid, resumable)")
    r.add_argument("--model", required=True)
    sub.add_parser("grade", help="grade ungraded patches (free, idempotent)")
    v = sub.add_parser("verdict", help="paired primary + funnel checkpoints")
    v.add_argument("--synthetic", action="store_true", help="dry-run on fixtures")
    args = ap.parse_args()
    if args.cmd == "generate":
        raise SystemExit(cmd_generate())
    if args.cmd == "run":
        raise SystemExit(cmd_run(args.model))
    if args.cmd == "grade":
        raise SystemExit(_grade_all())
    raise SystemExit(cmd_verdict(args.synthetic))
