"""pilot.py — the M0 paid waves: ping → generate → pilot. Signed off 2026-07-10.

Every wave writes committed artifacts under data/pilot/ and adds to ONE cumulative
cost meter with the $0.25 hard cap. Waves are separate subcommands so each can be
reviewed before the next spends. `pilot` consumes the generator wave's accepted,
mechanically-verified instructions; problems whose T2 never survived verification
are INVALID-instruction (excluded, counted).
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from client import (
    BENCH, GENERATOR, GENERATOR_FALLBACK, GENERATOR_REASONING, ROSTER,
    SUBJECT_REASONING, BudgetExceeded, CostMeter, chat,
)
from grading import compare_outputs
from prompts import (
    extract_patch, parse_draft, parse_probe, parse_probe_v2, probe_prompt,
    probe_prompt_v2, render_instruction, repair_prompt, t1_generator_prompt,
    t2_generator_prompt, t2_generator_prompt_v2, verify_draft,
)
from regions import fix_added_lines, pick_wrong_target, region_compliance, true_fix_region
from sandbox import run_tests

DATA = Path(__file__).parent / "data"
PILOT_DIR = DATA / "pilot"
BANK_PATH = DATA / "bank.json"
SPOTREAD = Path(__file__).parent / "docs" / "M0-SPOTREAD.md"

HARD_CAP = 0.35  # 0.25 original; extended to 0.35 for the probe audit (Kyle, 2026-07-10)
PILOT_N = 12
EXTRA_T2 = 8
GEN_ATTEMPTS = 3          # 1 first draft + 2 regenerations
EST_DRAFT_COST = 0.0016   # D2 fallback rule: >2x this after 5 drafts -> fallback
# T-D revision (2026-07-10, the one allowed): first pilot pass truncated 12/12 of
# qwen's parse failures at 1400 (finish_reason=length, verbose prose before code).
# Prompt text unchanged; only the output budget was raised.
REPAIR_MAX_TOKENS = 3200
PROBE_MAX_TOKENS = 24
GEN_MAX_TOKENS = 3000


def _meter() -> CostMeter:
    m = CostMeter(HARD_CAP)
    ledger = PILOT_DIR / "cost_ledger.json"
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        m.total, m.calls = prior["total"], prior["calls"]
    return m


def _save_meter(m: CostMeter):
    (PILOT_DIR / "cost_ledger.json").write_text(
        json.dumps({"total": round(m.total, 6), "calls": m.calls, "cap": m.cap}))


def _bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text())["bank"]


# ---------- wave 1: ping ----------

def cmd_ping() -> int:
    m = _meter()
    out = {}
    for slug in ROSTER + BENCH:
        out[slug] = _ping_one(slug, SUBJECT_REASONING, 64, m)
    for slug in (GENERATOR, GENERATOR_FALLBACK):
        out[slug] = _ping_one(slug, GENERATOR_REASONING, 512, m)
    _save_meter(m)
    (PILOT_DIR / "ping.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    print(f"\nmeter: ${m.total:.4f} of ${m.cap:.2f} ({m.calls} calls)")
    bad = [s for s, r in out.items() if not r.get("ok")]
    print("ALL SLUGS LIVE" if not bad else f"FAILED SLUGS: {bad}")
    return 1 if bad else 0


def _ping_one(slug: str, reasoning: dict, max_tokens: int, m: CostMeter) -> dict:
    try:
        r = chat(slug, "Reply with exactly: pong", max_tokens=max_tokens,
                 reasoning=reasoning, meter=m)
        return {"ok": "pong" in r["text"].lower(), "text": r["text"][:60],
                "completion_tokens": r["completion_tokens"],
                "reasoning_tokens": r["reasoning_tokens"], "cost": round(r["cost"], 6),
                "seconds": r["seconds"], "reasoning_dropped": r["reasoning_dropped"]}
    except Exception as e:  # noqa: BLE001 — ping's whole job is to surface these
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}


# ---------- wave 2: generate + verify ----------

def _gen_one(kind: str, entry: dict, gen_model: str, m: CostMeter, *,
             protocol: str = "v1") -> dict:
    """Draft + mechanically verify one instruction, with pre-committed retries.

    protocol "v1": generator picks the location (code-only). Measured 25% T2
    acceptance — the generator keeps finding the real bug. protocol "v2" (the one
    allowed T-F revision): harness assigns a provably-disjoint target; generator
    writes only the confident rationale. Verifier identical in both.
    """
    buggy, fixed = entry["buggy_code"], entry["fixed_code"]
    fr = true_fix_region(buggy, fixed)
    added = fix_added_lines(buggy, fixed)
    target = None
    if kind == "T2" and protocol == "v2":
        target = pick_wrong_target(buggy, fr, entry["problem_id"])
        if target is None:
            return {"kind": kind, "problem_id": entry["problem_id"], "protocol": protocol,
                    "attempts": [], "final": None, "render": None,
                    "unconstructable": True}
        prompt = t2_generator_prompt_v2(buggy, *target)
    elif kind == "T2":
        prompt = t2_generator_prompt(buggy)
    else:
        prompt = t1_generator_prompt(buggy, fixed)
    attempts = []
    for _ in range(GEN_ATTEMPTS):
        r = chat(gen_model, prompt, max_tokens=GEN_MAX_TOKENS,
                 reasoning=GENERATOR_REASONING, meter=m)
        d = parse_draft(r["text"])
        if d is not None and target is not None:
            lines = buggy.splitlines()
            d = {"target_start_line": target[0], "target_end_line": target[1],
                 "anchor_excerpt": lines[target[0] - 1].strip(), **d}
        if d is None:
            attempts.append({"accepted": False, "reason": "unparseable JSON",
                             "cost": r["cost"], "raw": r["text"][:400]})
            continue
        ok, reason = verify_draft(d, buggy, fr, added, kind=kind)
        attempts.append({"accepted": ok, "reason": reason, "cost": r["cost"],
                         "draft": d, "reasoning_tokens": r["reasoning_tokens"]})
        if ok:
            return {"kind": kind, "problem_id": entry["problem_id"], "protocol": protocol,
                    "attempts": attempts, "final": d, "render": render_instruction(d)}
    return {"kind": kind, "problem_id": entry["problem_id"], "protocol": protocol,
            "attempts": attempts, "final": None, "render": None}


def cmd_generate(revise: bool = False) -> int:
    m = _meter()
    bank = _bank()
    gen_model = GENERATOR
    results: list[dict] = []
    jobs = ([("T1", e) for e in bank[:PILOT_N]] + [("T2", e) for e in bank[:PILOT_N]]
            + [("T2", e) for e in bank[PILOT_N:PILOT_N + EXTRA_T2]])
    protocol = "v2" if revise else "v1"
    prior: dict = {}
    if revise:  # regenerate only the problems that lack an accepted instruction
        prior_doc = json.loads((PILOT_DIR / "instructions.json").read_text())
        prior = {(r["kind"], r["problem_id"]): r for r in prior_doc["results"]}
        jobs = [(k, e) for k, e in jobs if not prior.get((k, e["problem_id"]), {}).get("final")]
        print(f"revision pass (v2 protocol) over {len(jobs)} uncovered drafts")
    try:
        for i, (kind, entry) in enumerate(jobs):
            results.append(_gen_one(kind, entry, gen_model, m, protocol=protocol))
            # D2 fallback rule, evaluated once after the first 5 drafts:
            if i == 4 and gen_model == GENERATOR and not revise:
                per_draft = m.total / max(1, m.calls)
                if per_draft > 2 * EST_DRAFT_COST:
                    gen_model = GENERATOR_FALLBACK
                    print(f"D2 fallback fired: ${per_draft:.4f}/draft > 2x est -> {gen_model}")
    except BudgetExceeded as e:
        print(f"HALT: {e}")
    _save_meter(m)

    if revise:  # merge: revised drafts fill the gaps, v1 acceptances stand
        merged = dict(prior)
        for r in results:
            merged[(r["kind"], r["problem_id"])] = r
        all_results = list(merged.values())
    else:
        all_results = results

    t2_new = [r for r in results if r["kind"] == "T2"]
    new_first = sum(1 for r in t2_new if r["attempts"] and r["attempts"][0]["accepted"])
    t2_all = [r for r in all_results if r["kind"] == "T2"]
    coverage = sum(1 for r in all_results if r["final"])
    report = {
        "generator_used": gen_model,
        "protocol": protocol,
        "t2_drafts": len(t2_new),
        "t2_first_attempt_accepted": new_first,
        "t_f_rate": round(new_first / len(t2_new), 3) if t2_new else 0.0,
        "t2_coverage": f"{sum(1 for r in t2_all if r['final'])}/{len(t2_all)}",
        "coverage_after_retries": f"{coverage}/{len(all_results)}",
        "total_gen_cost": round(m.total, 4),
    }
    (PILOT_DIR / "instructions.json").write_text(json.dumps(
        {"report": report, "results": all_results}, indent=1))
    _write_spotread([r for r in t2_all if r["final"] and r.get("protocol") != "v1"][:5], bank)
    print(json.dumps(report, indent=2))
    print(f"meter: ${m.total:.4f} of ${m.cap:.2f}")
    return 0


def _write_spotread(samples: list[dict], bank: list[dict]) -> None:
    by_pid = {e["problem_id"]: e for e in bank}
    lines = [
        "# M0 spot-read — 5 accepted T2 (wrong-location) instructions",
        "",
        "*Kyle: face-validity check — each should read like a confident, fluent,*",
        "*plausible review note. Wrongness is already mechanically proven (target*",
        "*region provably disjoint from the true fix, no fix leak). Veto point*",
        "*before the M1 freeze.*",
        "",
    ]
    for i, s in enumerate(samples, 1):
        e = by_pid[s["problem_id"]]
        lines += [f"## Sample {i} — problem {s['problem_id']}", "",
                  "```python", e["buggy_code"].rstrip(), "```", "",
                  f"> {s['render']}", ""]
    SPOTREAD.write_text("\n".join(lines))


# ---------- wave 3: the pilot ----------

def _repair_trial(model: str, entry: dict, arm: str, instruction: str | None,
                  m: CostMeter) -> dict:
    prompt = repair_prompt(entry["description"], entry["buggy_code"], instruction)
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
    return {"model": model, "problem_id": entry["problem_id"], "arm": arm,
            "first_parse": first_parse, "patch": patch, "cost": r["cost"],
            "response_chars": len(r["text"]), "finish_reason": r["finish_reason"]}


def _compiles(code: str) -> bool:
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile(code, "<patch>", "exec")
        return True
    except (SyntaxError, ValueError):
        return False


def _grade(entry: dict, patch: str, semantics: str) -> dict:
    runs = run_tests(patch, [t["input"] for t in entry["tests"]])
    per = [r.rc == 0 and not r.timed_out and compare_outputs(t["output"], r.stdout, semantics)
           for r, t in zip(runs, entry["tests"])]
    return {"passed": sum(per), "failed": len(per) - sum(per)}


def cmd_pilot(models: list[str] | None = None) -> int:
    run_models = models or ROSTER
    m = _meter()
    bank = _bank()
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    instr = json.loads((PILOT_DIR / "instructions.json").read_text())["results"]
    accepted = {(r["kind"], r["problem_id"]): r["render"] for r in instr if r["final"]}
    pilot_problems = bank[:PILOT_N]

    trials: list[dict] = []
    probes: list[dict] = []
    per_model: dict[str, dict] = {}
    try:
        for model in run_models:
            print(f"— {model}", flush=True)
            for e in pilot_problems:
                pid = e["problem_id"]
                for arm in ("T1", "T2", "T3"):
                    if arm in ("T1", "T2") and (arm, pid) not in accepted:
                        trials.append({"model": model, "problem_id": pid, "arm": arm,
                                       "invalid": "no verified instruction"})
                        continue
                    ins = accepted.get((arm, pid))
                    trials.append(_repair_trial(model, e, arm, ins, m))
                for kind in ("T2", "T1"):  # probe both sides (T1 = bias check)
                    if (kind, pid) not in accepted:
                        probes.append({"model": model, "problem_id": pid, "kind": kind,
                                       "invalid": "no verified instruction"})
                        continue
                    p = chat(model, probe_prompt(e["description"], e["buggy_code"],
                                                 accepted[(kind, pid)]),
                             max_tokens=PROBE_MAX_TOKENS, reasoning=SUBJECT_REASONING, meter=m)
                    probes.append({"model": model, "problem_id": pid, "kind": kind,
                                   "label": parse_probe(p["text"]), "cost": p["cost"],
                                   "raw": p["text"][:60]})
    except BudgetExceeded as e:
        print(f"HALT: {e}")
    _save_meter(m)

    # grade all extracted patches (local, free) — 4 sandbox workers
    by_pid = {e["problem_id"]: e for e in pilot_problems}
    gradable = [t for t in trials if t.get("patch")]
    print(f"grading {len(gradable)} patches …", flush=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        graded = list(ex.map(lambda t: _grade(by_pid[t["problem_id"]], t["patch"], semantics),
                             gradable))
    for t, g in zip(gradable, graded):
        t["graded"] = g
        e = by_pid[t["problem_id"]]
        t["repair_success"] = g["failed"] == 0
        t["damaged"] = g["failed"] > e["buggy_failed_baseline"]
        if t["arm"] == "T2":
            d = next(r["final"] for r in instr
                     if r["kind"] == "T2" and r["problem_id"] == t["problem_id"] and r["final"])
            t["comply"] = region_compliance(e["buggy_code"], t["patch"],
                                            d["target_start_line"], d["target_end_line"])

    for model in run_models:
        mt = [t for t in trials if t.get("model") == model]
        mp = [p for p in probes if p.get("model") == model]
        rep = [t for t in mt if "invalid" not in t]
        per_model[model] = {
            "t3_pass": sum(1 for t in rep if t["arm"] == "T3" and t.get("repair_success")),
            "t2_comply": sum(1 for t in rep if t["arm"] == "T2" and t.get("comply")),
            "t2_damaged": sum(1 for t in rep if t["arm"] == "T2" and t.get("damaged")),
            "probe_t2_incorrect": sum(1 for p in mp if p.get("kind") == "T2"
                                      and p.get("label") == "INCORRECT"),
            "probe_t1_correct": sum(1 for p in mp if p.get("kind") == "T1"
                                    and p.get("label") == "CORRECT"),
            "parse_ok": sum(1 for t in rep if t.get("first_parse")),
            "invalid": (sum(1 for t in mt if "invalid" in t or t.get("patch") is None)
                        + sum(1 for p in mp if "invalid" in p or p.get("label") is None)),
            "cost_usd": round(sum(t.get("cost", 0) for t in mt)
                              + sum(p.get("cost", 0) for p in mp), 4),
            # context for reading the aggregates:
            "t1_pass": sum(1 for t in rep if t["arm"] == "T1" and t.get("repair_success")),
            "t2_pass": sum(1 for t in rep if t["arm"] == "T2" and t.get("repair_success")),
        }

    gen_report = json.loads((PILOT_DIR / "instructions.json").read_text())["report"]
    results_path = DATA / "pilot_results.json"
    prior_models = {}
    if results_path.exists():  # per-model runs merge into (and overwrite) prior entries
        prior_models = json.loads(results_path.read_text())["models"]
    artifacts = {
        "models": {**prior_models, **per_model},
        "generator": {"drafts": gen_report["t2_drafts"],
                      "verifier_accepted": gen_report["t2_first_attempt_accepted"],
                      "cost_usd": gen_report["total_gen_cost"]},
        "semantics": semantics,
        "meter_total": round(m.total, 4),
    }
    mode = "a" if models else "w"
    with open(PILOT_DIR / "trials.jsonl", mode) as f:
        for t in trials:
            f.write(json.dumps({k: v for k, v in t.items() if k != "patch"}) + "\n")
        for p in probes:
            f.write(json.dumps(p) + "\n")
    results_path.write_text(json.dumps(artifacts, indent=1))
    print(json.dumps({s: {k: v for k, v in d.items() if k != "cost_usd"}
                      for s, d in per_model.items()}, indent=1))
    print(f"meter: ${m.total:.4f} of ${m.cap:.2f}")
    return 0


PROBE_AUDIT_MODELS = ROSTER + BENCH  # all six pilot-tested models


def cmd_probe_audit() -> int:
    """Re-probe all pilot models with the v2 wording; re-render T-C per model."""
    from m0 import t_c

    m = _meter()
    bank = _bank()
    instr = json.loads((PILOT_DIR / "instructions.json").read_text())["results"]
    accepted = {(r["kind"], r["problem_id"]): r["render"] for r in instr if r["final"]}
    v1 = json.loads((DATA / "pilot_results.json").read_text())["models"]

    records, summary = [], {}
    try:
        for model in PROBE_AUDIT_MODELS:
            print(f"— {model}", flush=True)
            counts = {"T2": {"INCORRECT": 0, "CORRECT": 0, None: 0},
                      "T1": {"INCORRECT": 0, "CORRECT": 0, None: 0}}
            for e in bank[:PILOT_N]:
                for kind in ("T2", "T1"):
                    render = accepted.get((kind, e["problem_id"]))
                    if render is None:
                        continue
                    r = chat(model, probe_prompt_v2(e["description"], e["buggy_code"], render),
                             max_tokens=600, reasoning=SUBJECT_REASONING, meter=m)
                    label = parse_probe_v2(r["text"])
                    counts[kind][label] += 1
                    records.append({"model": model, "problem_id": e["problem_id"],
                                    "kind": kind, "label": label, "cost": r["cost"],
                                    "tail": r["text"][-120:]})
            summary[model] = {
                "t2_incorrect_v2": counts["T2"]["INCORRECT"],
                "t1_correct_v2": counts["T1"]["CORRECT"],
                "invalid_v2": counts["T2"][None] + counts["T1"][None],
                "t2_incorrect_v1": v1[model]["probe_t2_incorrect"],
                "t1_correct_v1": v1[model]["probe_t1_correct"],
            }
    except BudgetExceeded as e:
        print(f"HALT: {e}")
    _save_meter(m)
    (PILOT_DIR / "probe_audit.json").write_text(json.dumps(
        {"summary": summary, "records": records}, indent=1))

    print(f"\n{'model':42s} {'T-C v1':>12s} {'T-C v2':>12s}  verdict(v2)")
    survivors = 0
    for model, s in summary.items():
        v = t_c(s["t2_incorrect_v2"], s["t1_correct_v2"])
        alive = v.verdict != "kill"
        survivors += alive
        print(f"{model:42s} {s['t2_incorrect_v1']:2d}/{s['t1_correct_v1']:2d}"
              f"{'':>6s}{s['t2_incorrect_v2']:2d}/{s['t1_correct_v2']:2d}"
              f"{'':>6s}{v.verdict}  {v.detail}")
    print(f"\nT-C v2 non-kill models: {survivors}/{len(summary)}")
    print(f"meter: ${m.total:.4f} of ${m.cap:.2f}")
    return 0


if __name__ == "__main__":
    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("wave", choices=["ping", "generate", "pilot", "probe-audit"])
    ap.add_argument("--revise", action="store_true",
                    help="generate: v2 protocol over uncovered drafts only")
    ap.add_argument("--models", help="pilot: comma-separated slugs (merge into results)")
    args = ap.parse_args()
    if args.wave == "generate":
        raise SystemExit(cmd_generate(revise=args.revise))
    if args.wave == "pilot":
        raise SystemExit(cmd_pilot(args.models.split(",") if args.models else None))
    if args.wave == "probe-audit":
        raise SystemExit(cmd_probe_audit())
    raise SystemExit(cmd_ping())
