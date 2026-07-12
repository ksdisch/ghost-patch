"""m3.py — Milestone 3: ghost-error compounding (RQ3 analog).

Signed off 2026-07-11 (docs/M3-BRIEF.md): D10-A ($1.00 cap on
data/m3/cost_ledger.json). Per model, every problem its M1 T2 trial confirmed
damaged gets up to 5 more repair passes, each carrying a fresh live-generated,
mechanically-verified wrong-location instruction (protocol v2 on the drifted
current code via regions.map_fix_region) alongside the most recent failing
test. Start state = the damaged T2 patch. Early stop on escape
(all-tests-pass). Escape curve is descriptive; labels are REPORTED /
UNDERPOWERED only — the chain gate lives at M4-vs-M2.

Subcommands:
  extend  — paid. The pre-committed deepseek T2-only extension over
            bank[150:186]: v2 instruction + one M1-protocol repair trial per
            problem, all 36, metered here (M1's ledger and primary stay
            frozen). Artifacts: data/m3/extension_{instructions.json,
            trials.jsonl}.
  subset  — free. Freezes per-model entry subsets (M1 T2-damaged + extension
            damaged for deepseek) with start-state provenance to
            data/m3/subsets.json; asserts qwen 35, deepseek 18+E.
  run     — paid. --model <slug>: loop wave, resumable via
            (model, problem_id, pass) keys in data/m3/trials.jsonl; grade-0
            integrity halt; gen + repair smoke gates; 60% generation floor;
            80% parse floor per completed wave.
  verdict — free. Escape curves + damage trajectory + secondaries + M4
            re-projection. `--synthetic` dry-runs every label and INVALID-cause
            path on fixtures, per the "gates as code, dry-run before paid"
            contract.

Every threshold is pre-committed in docs/M3-BRIEF.md and unit-tested in
test_m3.py BEFORE any paid call.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from client import (
    BudgetExceeded, CostMeter, GENERATOR, GENERATOR_FALLBACK,
    GENERATOR_REASONING, chat,
)
from m1 import (
    ARM_EST, ARM_SMOKE_N, EST_DRAFT_COST, GEN_SMOKE_N, MODELS,
    arm_gate, gen_gate, lifetime_ok, parse_floor_ok,
)
from m2 import (
    MAX_PASSES, MIN_N, _pass_call, feedback_fields, grade_detail, loop_state,
    m2_label,
)
from pilot import GEN_ATTEMPTS, GEN_MAX_TOKENS, _gen_one, _repair_trial
from prompts import m3_repair_prompt, parse_draft, render_instruction, \
    t2_generator_prompt_v2, verify_draft
from regions import (
    drift_ratio, fix_added_lines, map_fix_region, pick_wrong_target,
    region_compliance, true_fix_region,
)
from stats import wilson

DATA = Path(__file__).parent / "data"
M3_DIR = DATA / "m3"
TRIALS_PATH = M3_DIR / "trials.jsonl"
SUBSETS_PATH = M3_DIR / "subsets.json"
EXT_INSTR_PATH = M3_DIR / "extension_instructions.json"
EXT_TRIALS_PATH = M3_DIR / "extension_trials.jsonl"
RESULTS_PATH = DATA / "m3_results.json"
M1_TRIALS_PATH = DATA / "m1" / "trials.jsonl"
BANK_PATH = DATA / "bank.json"
M0_LEDGER = DATA / "pilot" / "cost_ledger.json"
M1_LEDGER = DATA / "m1" / "cost_ledger.json"
M2_LEDGER = DATA / "m2" / "cost_ledger.json"
SPOTREAD = Path(__file__).parent / "docs" / "M3-SPOTREAD.md"

# Signed constants (docs/M3-BRIEF.md, 2026-07-11)
M3_CAP = 1.00                  # D10-A
EXT_LO, EXT_HI = 150, 186      # the pre-committed extension slice
EXT_MIN_NEW_DAMAGED = 2        # below this the pool-smoke fallback fires
M1_DS_DAMAGED = 18             # frozen from M1 RESULTS
EXPECTED_QWEN = 35             # frozen from M1 RESULTS
GEN_FLOOR = 0.60               # cumulative first-attempt acceptance floor
GEN_FLOOR_MIN = 20             # ... evaluated only after this many draft passes
DRAFT_PAD = 1.3                # retry pad on the measured draft rate
DRAFT_EST = EST_DRAFT_COST * DRAFT_PAD
REPAIR_EST = {                 # $/repair-pass, M2-measured + instruction bump
    MODELS[0]: 0.00160,
    MODELS[1]: 0.00082,
}
CAUSE_PARSE = "parse failure"          # subject parse fail after bare retry (m2 string)
CAUSE_REJECTED = "draft rejected"      # 3 generator attempts, none verified
CAUSE_ANCHOR = "anchor unresolvable"   # no constructible disjoint target after drift


# ---------- pre-committed pure logic (unit-tested before any paid call) ----------

def damaged_subset(records: list[dict], model: str, bank_order: list[str]) -> list[str]:
    """Entry rule: problems whose T2 trial was graded, valid, and damaged
    (failed > buggy baseline — the paper's confirmed-damage condition), bank
    order. INVALID and ungraded rows never enter; later records win on
    duplicate keys (same defensive rule as m1.pairs_table)."""
    damaged: dict[str, bool] = {}
    for r in records:
        if r.get("model") != model or r.get("arm") != "T2":
            continue
        if "repair_success" in r and "invalid" not in r:
            damaged[r["problem_id"]] = bool(r.get("damaged"))
    keep = {pid for pid, d in damaged.items() if d}
    return [pid for pid in bank_order if pid in keep]


def start_index(m1_records: list[dict], ext_records: list[dict],
                model: str) -> dict[str, dict]:
    """Start-state provenance: pid -> {source, start_failed, patch} over the
    model's damaged T2 trials (M1 first, extension overlays)."""
    idx: dict[str, dict] = {}
    for recs, source in ((m1_records, "m1"), (ext_records, "extension")):
        for r in recs:
            if r.get("model") != model or r.get("arm") != "T2":
                continue
            if "repair_success" not in r or "invalid" in r or not r.get("damaged"):
                continue
            idx[r["problem_id"]] = {"source": source,
                                    "start_failed": r["graded"]["failed"],
                                    "patch": r["patch"]}
    return idx


def pass_seed(problem_id: str, k: int) -> str:
    """Per-pass target seed: a fresh deterministic review each pass."""
    return f"{problem_id}#p{k}"


def trajectory(start_failed: int, final_failed: int, escaped: bool) -> str:
    """Ghost-error read per clean loop, against its own damaged start."""
    if escaped:
        return "escaped"
    if final_failed > start_failed:
        return "deepened"
    if final_failed == start_failed:
        return "held"
    return "improved"


def gen_floor_ok(accepted_first: int, n_draft_passes: int) -> bool:
    """Generation floor: cumulative first-attempt acceptance >= 60%, evaluated
    only once >= 20 draft-bearing passes exist (docs/M3-BRIEF.md)."""
    return n_draft_passes < GEN_FLOOR_MIN or accepted_first / n_draft_passes >= GEN_FLOOR


def m3_outcomes(records: list[dict], model: str, subset: list[str],
                baselines: dict[str, int]) -> dict[str, dict]:
    """Classify every subset loop; m2.loop_state supplies the terminal logic,
    the vocabulary here is M3's (escaped, trajectory, invalid cause)."""
    by_pid: dict[str, list[dict]] = {pid: [] for pid in subset}
    for r in records:
        if r.get("model") == model and r.get("problem_id") in by_pid:
            by_pid[r["problem_id"]].append(r)
    out = {}
    for pid in subset:
        recs = sorted(by_pid[pid], key=lambda r: r["pass"])
        state = loop_state(recs)
        status = {"need_grade0": "todo", "run_pass": "active",
                  "recovered": "escaped"}.get(state["status"], state["status"])
        base = baselines[pid]
        grade0 = next((r for r in recs if r["pass"] == 0), None)
        start_failed = grade0["start_failed"] if grade0 else None
        graded_paid = [r for r in recs if r["pass"] >= 1 and "graded" in r]
        final_failed = graded_paid[-1]["graded"]["failed"] if graded_paid else None
        o = {
            "status": status,
            "escaped_at": state.get("at") if status == "escaped" else None,
            "passes_used": max((r["pass"] for r in recs), default=0),
            "start_failed": start_failed,
            "final_failed": final_failed,
            "ever_below": any(r["graded"]["failed"] > base for r in graded_paid),
            "final_below": status == "exhausted" and final_failed is not None
                           and final_failed > base,
            "trajectory": None,
            "invalid_cause": None,
        }
        if status in ("escaped", "exhausted"):
            o["trajectory"] = trajectory(start_failed, final_failed,
                                         escaped=status == "escaped")
        if status == "invalid":
            o["invalid_cause"] = next(r["invalid"] for r in recs if "invalid" in r)
        out[pid] = o
    return out


def model_verdict_m3(outcomes: dict[str, dict]) -> dict:
    """Assemble one model's verdict block from its loop outcomes (pure)."""
    clean = {p: o for p, o in outcomes.items()
             if o["status"] in ("escaped", "exhausted")}
    clean_n = len(clean)
    escaped = sum(1 for o in clean.values() if o["status"] == "escaped")
    lo, hi = wilson(escaped, clean_n)
    causes = {c: 0 for c in (CAUSE_PARSE, CAUSE_REJECTED, CAUSE_ANCHOR)}
    for o in outcomes.values():
        if o["status"] == "invalid" and o["invalid_cause"] in causes:
            causes[o["invalid_cause"]] += 1
    return {
        "clean_n": clean_n,
        "escaped": escaped,
        "rate": round(escaped / clean_n, 4) if clean_n else None,
        "wilson": [round(lo, 4), round(hi, 4)],
        "label": m2_label(clean_n),
        "curve": [sum(1 for o in clean.values()
                      if o["escaped_at"] is not None and o["escaped_at"] <= k)
                  for k in range(1, MAX_PASSES + 1)],
        "pass1_escaped": sum(1 for o in clean.values() if o["escaped_at"] == 1),
        "mean_passes": round(sum(o["passes_used"] for o in clean.values()) / clean_n, 4)
                       if clean_n else None,
        "deepened": sum(1 for o in clean.values() if o["trajectory"] == "deepened"),
        "held": sum(1 for o in clean.values() if o["trajectory"] == "held"),
        "improved": sum(1 for o in clean.values() if o["trajectory"] == "improved"),
        "final_below": sum(1 for o in clean.values() if o["final_below"]),
        "ever_below": sum(1 for o in clean.values() if o["ever_below"]),
        "invalid": sum(1 for o in outcomes.values() if o["status"] == "invalid"),
        "invalid_by_cause": causes,
        "unfinished": sum(1 for o in outcomes.values()
                          if o["status"] in ("todo", "active")),
    }


def mean_failed_by_pass(records: list[dict], model: str,
                        pids: list[str]) -> list[float | None]:
    """Descriptive damage curve: mean failed count over loops still active at
    pass k (i.e., that produced a graded pass-k state)."""
    pidset = set(pids)
    means: list[float | None] = []
    for k in range(1, MAX_PASSES + 1):
        vals = [r["graded"]["failed"] for r in records
                if r.get("model") == model and r.get("problem_id") in pidset
                and r.get("pass") == k and "graded" in r]
        means.append(round(sum(vals) / len(vals), 4) if vals else None)
    return means


def wave_estimate_m3(outcomes: dict[str, dict], model: str) -> float:
    """Upper-bound cost of finishing this model's wave (repair + padded drafts)."""
    remaining = 0
    for o in outcomes.values():
        if o["status"] == "todo":
            remaining += MAX_PASSES
        elif o["status"] == "active":
            remaining += MAX_PASSES - o["passes_used"]
    return remaining * (REPAIR_EST[model] + DRAFT_EST)


# ---------- synthetic fixture (dry-run) ----------

def _syn_gen(accepted_first: bool = True) -> dict:
    return {"target": [1, 1], "fprime": [3], "first_attempt_accepted": accepted_first,
            "attempts": [{"accepted": accepted_first, "reason": "ok", "cost": 0.001}],
            "render": "The bug is in line 1.", "cost": 0.001, "drift_ratio": 0.9}


def _syn_loop(model: str, pid: str, *, escaped_at: int | None = None,
              final: int | None = None, invalid_at: int | None = None,
              cause: str = CAUSE_PARSE, start: int = 4, baseline: int = 2) -> list[dict]:
    recs = [{"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
             "baseline_ok": True, "start_source": "m1", "start_failed": start,
             "graded": {"passed": 6 - start, "failed": start},
             "detail": [{"i": 0, "rc": 0, "timed_out": False, "passed": False,
                         "stdout": "0"}]}]
    last = invalid_at or escaped_at or MAX_PASSES
    for k in range(1, last + 1):
        if k == invalid_at:
            rec = {"model": model, "problem_id": pid, "pass": k, "invalid": cause,
                   "cost": 0.001, "gen": _syn_gen(cause == CAUSE_PARSE)}
            if cause == CAUSE_PARSE:
                rec["first_parse"] = False
            recs.append(rec)
            break
        failed = 0 if k == escaped_at else (final if final is not None else start)
        recs.append({"model": model, "problem_id": pid, "pass": k, "first_parse": True,
                     "patch": "x = 1", "cost": 0.0015, "finish_reason": "stop",
                     "gen": _syn_gen(), "feedback": {"test_index": 0},
                     "recovered": failed == 0, "comply": True,
                     "graded": {"passed": 6 - failed, "failed": failed},
                     "detail": [{"i": 0, "rc": 0, "timed_out": False,
                                 "passed": failed == 0, "stdout": "1"}]})
        if failed == 0:
            break
    return recs


def _synthetic() -> tuple[list[dict], dict[str, list[str]], dict[str, dict[str, int]]]:
    """Fixture models covering REPORTED + UNDERPOWERED and all INVALID causes."""
    records, subsets, baselines = [], {}, {}
    # REPORTED: 24 loops — 14 escapes, 9 exhausted (4 deepened, 3 held, 2 improved),
    # 1 invalid (parse) -> clean 23 >= 20
    m = "demo/reported"
    subsets[m] = [f"r{i:02d}" for i in range(24)]
    plan: list[dict] = ([{"escaped_at": 1}] * 8 + [{"escaped_at": 2}] * 4
                        + [{"escaped_at": 3}] * 2
                        + [{"final": 6}] * 4 + [{"final": 4}] * 3 + [{"final": 1}] * 2
                        + [{"invalid_at": 2, "cause": CAUSE_PARSE}])
    for pid, kw in zip(subsets[m], plan):
        records += _syn_loop(m, pid, **kw)
    baselines[m] = {pid: 2 for pid in subsets[m]}
    # UNDERPOWERED: 8 loops — 5 clean, 3 invalid (one per remaining cause + parse)
    m = "demo/underpowered"
    subsets[m] = [f"u{i:02d}" for i in range(8)]
    plan = ([{"escaped_at": 1}] * 2 + [{"final": 6}] * 3
            + [{"invalid_at": 1, "cause": CAUSE_REJECTED}]
            + [{"invalid_at": 1, "cause": CAUSE_ANCHOR}]
            + [{"invalid_at": 2, "cause": CAUSE_PARSE}])
    for pid, kw in zip(subsets[m], plan):
        records += _syn_loop(m, pid, **kw)
    baselines[m] = {pid: 2 for pid in subsets[m]}
    return records, subsets, baselines


# ---------- meter + ledger (per-milestone regime; M0/M1/M2 ledgers are frozen) ----------

def _meter() -> CostMeter:
    m = CostMeter(M3_CAP)
    ledger = M3_DIR / "cost_ledger.json"
    if ledger.exists():
        prior = json.loads(ledger.read_text())
        m.total, m.calls = prior["total"], prior["calls"]
    return m


def _save_meter(m: CostMeter):
    (M3_DIR / "cost_ledger.json").write_text(
        json.dumps({"total": round(m.total, 6), "calls": m.calls, "cap": m.cap}))


def _lifetime(m3_total: float) -> float:
    prior = 0.0
    for ledger in (M0_LEDGER, M1_LEDGER, M2_LEDGER):
        if ledger.exists():
            prior += json.loads(ledger.read_text())["total"]
    return prior + m3_total


def _bank() -> list[dict]:
    return json.loads(BANK_PATH.read_text())["bank"]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def _append_jsonl(path: Path, rec: dict):
    with open(path, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def _load_subsets() -> dict:
    return json.loads(SUBSETS_PATH.read_text())


def _append_spotread(title: str, samples: list[tuple[str, str, str, str]]):
    """Face-validity record (M1 semantics: veto before RESULTS close discards
    affected loops). samples = (problem_id, context, code, render)."""
    lines = []
    if not SPOTREAD.exists():
        lines += ["# M3 spot-read — accepted wrong-location instructions", "",
                  "*Kyle: face-validity record. Wrongness is mechanically proven per*",
                  "*draft (anchor match in the current code, disjoint from the mapped*",
                  "*fix region F', no fix leak). Veto before M3 RESULTS close discards*",
                  "*affected loops (docs/M3-BRIEF.md).*", ""]
    lines += [f"## {title}", ""]
    for i, (pid, ctx, code, render) in enumerate(samples, 1):
        lines += [f"### Sample {i} — problem {pid} ({ctx})", "",
                  "```python", code.rstrip(), "```", "", f"> {render}", ""]
    with open(SPOTREAD, "a") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------- the per-pass generator stage (paid) ----------

def _gen_pass(entry: dict, current: str, k: int, gen_model: str, m: CostMeter) -> dict:
    """Draft + mechanically verify one per-pass wrong instruction on the drifted
    current code. Mirrors pilot._gen_one's v2 protocol with the M3 diff-anchor:
    F' = map_fix_region, target seeded per (problem, pass)."""
    buggy, fixed = entry["buggy_code"], entry["fixed_code"]
    fprime = map_fix_region(buggy, current, true_fix_region(buggy, fixed))
    gen: dict = {"drift_ratio": round(drift_ratio(buggy, current), 4),
                 "fprime": sorted(fprime), "cost": 0.0, "attempts": []}
    target = (pick_wrong_target(current, fprime, pass_seed(entry["problem_id"], k))
              if fprime else None)
    if target is None:
        gen["invalid_cause"] = CAUSE_ANCHOR
        return gen
    gen["target"] = list(target)
    added = fix_added_lines(buggy, fixed)
    lines = current.splitlines()
    prompt = t2_generator_prompt_v2(current, *target)
    for _ in range(GEN_ATTEMPTS):
        r = chat(gen_model, prompt, max_tokens=GEN_MAX_TOKENS,
                 reasoning=GENERATOR_REASONING, meter=m)
        gen["cost"] = round(gen["cost"] + r["cost"], 6)
        d = parse_draft(r["text"])
        if d is None:
            ok, reason = False, "unparseable JSON"
        else:
            d = {"target_start_line": target[0], "target_end_line": target[1],
                 "anchor_excerpt": lines[target[0] - 1].strip(), **d}
            ok, reason = verify_draft(d, current, fprime, added, kind="T2")
        gen["attempts"].append({"accepted": ok, "reason": reason,
                                "cost": round(r["cost"], 6)})
        if ok:
            gen["final"] = d
            gen["render"] = render_instruction(d)
            break
    gen["first_attempt_accepted"] = gen["attempts"][0]["accepted"]
    if "final" not in gen:
        gen["invalid_cause"] = CAUSE_REJECTED
    return gen


# ---------- extend (paid: the pre-committed deepseek T2-only extension) ----------

def cmd_extend() -> int:
    M3_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank = _bank()
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    ext_entries = bank[EXT_LO:EXT_HI]
    model = MODELS[0]  # deepseek — the only model owed an extension (M1 RESULTS)

    prior = json.loads(EXT_INSTR_PATH.read_text())["results"] if EXT_INSTR_PATH.exists() else []
    prior_by = {r["problem_id"]: r for r in prior}
    jobs = [e for e in ext_entries if not prior_by.get(e["problem_id"], {}).get("final")]
    done = {(r["model"], r["problem_id"], r["arm"])
            for r in _read_jsonl(EXT_TRIALS_PATH)}
    trials_todo = sum(1 for e in ext_entries
                      if (model, e["problem_id"], "T2") not in done)
    est = len(jobs) * EST_DRAFT_COST * DRAFT_PAD + trials_todo * ARM_EST[model]["T2"]
    print(f"extend: {len(jobs)} draft jobs + {trials_todo} {model} T2 trials "
          f"over bank[{EXT_LO}:{EXT_HI}] · est ${est:.3f}", flush=True)
    if not lifetime_ok(_lifetime(m.total), est):
        print(f"HALT: lifetime guard — ${_lifetime(m.total):.2f} + ${est:.2f} > $5.00")
        return 4

    gen_model = GENERATOR
    results: list[dict] = []

    def _save_instr():
        merged = dict(prior_by)
        for r in results:
            merged[r["problem_id"]] = r
        out = [merged[e["problem_id"]] for e in ext_entries
               if e["problem_id"] in merged]
        acc_first = sum(1 for r in results
                        if r["attempts"] and r["attempts"][0]["accepted"])
        report = {"protocol": "v2", "generator_used": gen_model,
                  "slice": [EXT_LO, EXT_HI], "jobs_run": len(results),
                  "first_attempt_accepted": acc_first,
                  "coverage": sum(1 for r in out if r["final"]),
                  "wave_cost": round(m.total, 4)}
        EXT_INSTR_PATH.write_text(json.dumps({"report": report, "results": out}, indent=1))

    try:
        for i, e in enumerate(jobs):
            results.append(_gen_one("T2", e, gen_model, m, protocol="v2"))
            _save_meter(m)
            if i % 10 == 9:
                _save_instr()
            if i == GEN_SMOKE_N - 1:
                first10 = results[:GEN_SMOKE_N]
                acc = sum(1 for r in first10
                          if r["attempts"] and r["attempts"][0]["accepted"])
                calls = [a["cost"] for r in first10 for a in r["attempts"]]
                mean = sum(calls) / len(calls) if calls else 0.0
                print(f"  gen smoke @10: accepted {acc}/10, mean ${mean:.5f}/draft")
                if acc < 7:
                    _save_instr()
                    print("HALT: extension generation acceptance below 7/10 — to Kyle")
                    return 2
                if mean > 2 * EST_DRAFT_COST:  # D2 fallback rule, pre-committed
                    gen_model = GENERATOR_FALLBACK
                    print(f"D2 fallback fired at ${mean:.5f}/draft → {gen_model}")
        _save_instr()

        renders = {r["problem_id"]: r["render"]
                   for r in json.loads(EXT_INSTR_PATH.read_text())["results"] if r["final"]}
        paid: list[dict] = []
        for e in ext_entries:
            pid = e["problem_id"]
            if (model, pid, "T2") in done:
                continue
            if pid not in renders:
                _append_jsonl(EXT_TRIALS_PATH, {"model": model, "problem_id": pid,
                                                "arm": "T2",
                                                "invalid": "no verified instruction"})
                continue
            rec = _repair_trial(model, e, "T2", renders[pid], m)
            _append_jsonl(EXT_TRIALS_PATH, rec)
            _save_meter(m)
            paid.append(rec)
            if len(paid) == ARM_SMOKE_N:
                parse = sum(1 for r in paid if r["first_parse"])
                mean = sum(r["cost"] for r in paid) / len(paid)
                print(f"  trial smoke @5: parse {parse}/5, mean ${mean:.5f}/trial")
                if not arm_gate(parse, mean, ARM_EST[model]["T2"]):
                    print("HALT: extension trial smoke gate — to Kyle")
                    return 2
    except BudgetExceeded as e:
        _save_meter(m)
        _save_instr()
        print(f"HALT: {e} (resumable — re-run after a cap decision)")
        return 3

    _save_meter(m)
    _grade_ext(semantics)
    recs = [r for r in _read_jsonl(EXT_TRIALS_PATH) if "invalid" not in r]
    parse_ok = sum(1 for r in recs if r.get("first_parse"))
    if not parse_floor_ok(parse_ok, len(recs)):
        print(f"HALT: extension parse floor — {parse_ok}/{len(recs)} < 80% — to Kyle")
        return 5
    damaged = [r for r in _read_jsonl(EXT_TRIALS_PATH) if r.get("damaged")]
    finals = [r for r in json.loads(EXT_INSTR_PATH.read_text())["results"] if r["final"]]
    by_pid = {e["problem_id"]: e for e in _bank()}
    _append_spotread(
        f"Extension wave ({model}, bank[{EXT_LO}:{EXT_HI}])",
        [(s["problem_id"], "extension, M1 protocol", by_pid[s["problem_id"]]["buggy_code"],
          s["render"]) for s in finals[:5]])
    entry = M1_DS_DAMAGED + len(damaged)
    print(f"extension complete: instructions {len(finals)}/{len(ext_entries)} · "
          f"trials {len(recs)} (parse {parse_ok}) · new damaged E={len(damaged)} · "
          f"deepseek M3 entry {M1_DS_DAMAGED}+{len(damaged)}={entry} · "
          f"meter ${m.total:.4f} · lifetime ${_lifetime(m.total):.4f}")
    if len(damaged) < EXT_MIN_NEW_DAMAGED:
        print(f"FALLBACK (pre-committed): E={len(damaged)} < {EXT_MIN_NEW_DAMAGED} — "
              "extend the bank via m0.py smoke deeper into the frozen pool "
              "(max 3 rounds of ~36), then re-run extend; pool exhausted → "
              "deepseek M3/M4 auto-UNDERPOWERED (docs/M3-BRIEF.md)")
        return 7
    return 0


def _grade_ext(semantics: str) -> None:
    """Grade ungraded extension patches (free, local); sets
    repair_success/damaged/comply — mirrors m1's grade over M3's files."""
    from concurrent.futures import ThreadPoolExecutor

    from pilot import _grade

    records = _read_jsonl(EXT_TRIALS_PATH)
    bank_by = {e["problem_id"]: e for e in _bank()}
    instr = json.loads(EXT_INSTR_PATH.read_text())["results"] if EXT_INSTR_PATH.exists() else []
    targets = {r["problem_id"]: (r["final"]["target_start_line"],
                                 r["final"]["target_end_line"])
               for r in instr if r["final"]}
    todo = [r for r in records if r.get("patch") and "graded" not in r]
    if not todo:
        return
    print(f"grading {len(todo)} extension patches …", flush=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        graded = list(ex.map(
            lambda r: _grade(bank_by[r["problem_id"]], r["patch"], semantics), todo))
    for r, g in zip(todo, graded):
        e = bank_by[r["problem_id"]]
        r["graded"] = g
        r["repair_success"] = g["failed"] == 0
        r["damaged"] = g["failed"] > e["buggy_failed_baseline"]
        if r["problem_id"] in targets:
            r["comply"] = region_compliance(e["buggy_code"], r["patch"],
                                            *targets[r["problem_id"]])
    tmp = EXT_TRIALS_PATH.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in records))
    tmp.replace(EXT_TRIALS_PATH)


# ---------- subset (free) ----------

def cmd_subset() -> int:
    M3_DIR.mkdir(parents=True, exist_ok=True)
    bank_order = [e["problem_id"] for e in _bank()]
    m1_records = _read_jsonl(M1_TRIALS_PATH)
    ext_records = _read_jsonl(EXT_TRIALS_PATH)
    ds, qw = MODELS
    ds_m1 = damaged_subset(m1_records, ds, bank_order)
    if len(ds_m1) != M1_DS_DAMAGED:
        print(f"HALT: {ds} M1 damaged {len(ds_m1)} != frozen {M1_DS_DAMAGED}")
        return 1
    subsets = {ds: damaged_subset(m1_records + ext_records, ds, bank_order),
               qw: damaged_subset(m1_records, qw, bank_order)}
    if len(subsets[qw]) != EXPECTED_QWEN:
        print(f"HALT: {qw} subset {len(subsets[qw])} != frozen {EXPECTED_QWEN}")
        return 1
    provenance, underpowered = {}, {}
    for model in MODELS:
        idx = start_index(m1_records, ext_records, model)
        missing = [pid for pid in subsets[model] if pid not in idx]
        if missing:
            print(f"HALT: {model} start states missing for {missing}")
            return 1
        provenance[model] = {pid: {"source": idx[pid]["source"],
                                   "start_failed": idx[pid]["start_failed"]}
                             for pid in subsets[model]}
        underpowered[model] = len(subsets[model]) < MIN_N
        ext_n = sum(1 for p in provenance[model].values() if p["source"] == "extension")
        print(f"{model}: {len(subsets[model])} T2-damaged entry problems "
              f"({ext_n} from extension){' — UNDERPOWERED at entry' if underpowered[model] else ''}")
    SUBSETS_PATH.write_text(json.dumps({
        "derived_from": ["data/m1/trials.jsonl", "data/m3/extension_trials.jsonl"],
        "rule": "arm==T2, graded, valid, damaged (failed > buggy baseline); bank order",
        "subsets": subsets, "provenance": provenance,
        "underpowered_entry": underpowered}, indent=1))
    print(f"wrote {SUBSETS_PATH}")
    return 0


# ---------- run (paid, per model, resumable) ----------

def cmd_run(model: str) -> int:
    if model not in MODELS:
        print(f"unknown model {model}; roster: {MODELS}")
        return 1
    M3_DIR.mkdir(parents=True, exist_ok=True)
    m = _meter()
    bank_by = {e["problem_id"]: e for e in _bank()}
    semantics = json.loads(BANK_PATH.read_text())["semantics"]
    doc = _load_subsets()
    subset = doc["subsets"][model]
    baselines = {pid: bank_by[pid]["buggy_failed_baseline"] for pid in subset}
    starts = start_index(_read_jsonl(M1_TRIALS_PATH), _read_jsonl(EXT_TRIALS_PATH), model)
    missing = [pid for pid in subset if pid not in starts]
    if missing:
        print(f"HALT: start states missing for {missing}")
        return 1
    records = _read_jsonl(TRIALS_PATH)
    outcomes = m3_outcomes(records, model, subset, baselines)
    est = wave_estimate_m3(outcomes, model)
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

    gen_model = GENERATOR
    paid_repairs: list[tuple[bool, float]] = []
    gsmoke: list[tuple[bool, float, int]] = []  # (first_ok, gen_cost, n_attempts)
    gfloor_acc = gfloor_n = 0
    spot: list[tuple[str, str, str, str]] = []

    def _gen_checks(gen: dict) -> str | None:
        """Returns 'halt' on a fired gate, else None (may switch gen_model)."""
        nonlocal gen_model, gfloor_acc, gfloor_n
        if not gen["attempts"]:
            return None  # anchor-unresolvable: no drafts ran
        first_ok = gen["first_attempt_accepted"]
        gsmoke.append((first_ok, gen["cost"], len(gen["attempts"])))
        gfloor_acc += first_ok
        gfloor_n += 1
        if len(gsmoke) == GEN_SMOKE_N:
            acc = sum(1 for ok, _, _ in gsmoke if ok)
            mean = sum(c for _, c, _ in gsmoke) / max(1, sum(n for _, _, n in gsmoke))
            print(f"  gen smoke @{GEN_SMOKE_N}: first-attempt {acc}/{GEN_SMOKE_N}, "
                  f"mean ${mean:.5f}/draft")
            if not gen_gate(acc, mean):
                if acc < 7:
                    print("HALT: gen smoke gate (acceptance on drifted code) — to Kyle")
                    return "halt"
                gen_model = GENERATOR_FALLBACK  # D2 fallback rule, pre-committed
                print(f"D2 fallback fired at ${mean:.5f}/draft → {gen_model}")
        if not gen_floor_ok(gfloor_acc, gfloor_n):
            print(f"HALT: generation floor — first-attempt acceptance "
                  f"{gfloor_acc}/{gfloor_n} < 60% — to Kyle")
            return "halt"
        return None

    def _repair_smoke() -> bool:
        if len(paid_repairs) != ARM_SMOKE_N:
            return True
        parse = sum(1 for fp, _ in paid_repairs if fp)
        mean = sum(c for _, c in paid_repairs) / len(paid_repairs)
        print(f"  repair smoke @{ARM_SMOKE_N}: parse {parse}/{ARM_SMOKE_N}, "
              f"mean ${mean:.5f}/pass")
        if not arm_gate(parse, mean, REPAIR_EST[model]):
            print("HALT: repair smoke gate — to Kyle")
            return False
        return True

    try:
        for pid in subset:
            entry = bank_by[pid]
            state = loop_state(by_pid[pid])
            if state["status"] in ("recovered", "invalid", "exhausted"):
                continue
            if state["status"] == "need_grade0":
                sp = starts[pid]
                counts, detail = grade_detail(entry, sp["patch"], semantics)
                if counts["failed"] != sp["start_failed"]:
                    print(f"HALT: grade-0 integrity — {pid} failed {counts['failed']} "
                          f"!= recorded start {sp['start_failed']} "
                          "(harness drift; investigate before resuming)")
                    return 6
                if counts["failed"] <= entry["buggy_failed_baseline"]:
                    print(f"HALT: entry violation — {pid} start failed "
                          f"{counts['failed']} <= baseline "
                          f"{entry['buggy_failed_baseline']} (not damaged)")
                    return 8
                rec = {"model": model, "problem_id": pid, "pass": 0, "cost": 0.0,
                       "baseline_ok": True, "start_source": sp["source"],
                       "start_failed": counts["failed"], "graded": counts,
                       "detail": detail}
                _append_jsonl(TRIALS_PATH, rec)
                state = {"status": "run_pass", "next": 1, "code": None,
                         "detail": detail}
            while state["status"] == "run_pass":
                k = state["next"]
                code = state["code"] or starts[pid]["patch"]
                gen = _gen_pass(entry, code, k, gen_model, m)
                _save_meter(m)
                if _gen_checks(gen) == "halt":
                    return 2
                if gen.get("invalid_cause"):
                    _append_jsonl(TRIALS_PATH, {
                        "model": model, "problem_id": pid, "pass": k,
                        "invalid": gen["invalid_cause"], "cost": 0.0,
                        "gen": {kk: v for kk, v in gen.items() if kk != "final"}})
                    break  # loop INVALID — terminal
                fb = feedback_fields(entry, state["detail"])
                prompt = m3_repair_prompt(entry["description"], code, fb, gen["render"])
                call = _pass_call(model, prompt, m)
                paid_repairs.append((call["first_parse"], call["cost"]))
                gen_slim = {kk: v for kk, v in gen.items() if kk != "final"}
                if call["patch"] is None:
                    _append_jsonl(TRIALS_PATH, {
                        "model": model, "problem_id": pid, "pass": k,
                        "invalid": CAUSE_PARSE, "first_parse": False,
                        "cost": call["cost"], "gen": gen_slim, "feedback": fb,
                        "finish_reason": call["finish_reason"]})
                    _save_meter(m)
                    if not _repair_smoke():
                        return 2
                    break  # loop INVALID — terminal
                counts, detail = grade_detail(entry, call["patch"], semantics)
                escaped = counts["failed"] == 0
                _append_jsonl(TRIALS_PATH, {
                    "model": model, "problem_id": pid, "pass": k,
                    "first_parse": call["first_parse"], "patch": call["patch"],
                    "cost": call["cost"], "finish_reason": call["finish_reason"],
                    "response_chars": call["response_chars"], "gen": gen_slim,
                    "feedback": fb, "graded": counts, "detail": detail,
                    "recovered": escaped,
                    "comply": region_compliance(code, call["patch"], *gen["target"])})
                _save_meter(m)
                if len(spot) < 5 and all(pid != s[0] for s in spot):
                    spot.append((pid, f"pass {k}, drift {gen['drift_ratio']}",
                                 code, gen["render"]))
                if not _repair_smoke():
                    return 2
                if escaped or k >= MAX_PASSES:
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
    if spot:
        _append_spotread(f"M3 loop wave ({model})", spot)
    outcomes = m3_outcomes(_read_jsonl(TRIALS_PATH), model, subset, baselines)
    esc = sum(1 for o in outcomes.values() if o["status"] == "escaped")
    inv = sum(1 for o in outcomes.values() if o["status"] == "invalid")
    print(f"{model}: wave complete — escaped {esc}/{len(subset)} · invalid {inv} · "
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
        records = _read_jsonl(TRIALS_PATH)
        doc = _load_subsets()
        subsets = doc["subsets"]
        bank_by = {e["problem_id"]: e for e in _bank()}
        baselines_by = {mo: {pid: bank_by[pid]["buggy_failed_baseline"] for pid in ss}
                        for mo, ss in subsets.items()}
        models = MODELS

    out: dict = {"models": {}}
    for model in models:
        o = m3_outcomes(records, model, subsets[model], baselines_by[model])
        v = model_verdict_m3(o)
        if not synthetic and v["unfinished"]:
            print(f"{model}: {v['unfinished']} loops unfinished — finish the wave first")
            return 1
        print(f"{model}  →  {v['label']}")
        print(f"  escape: {v['escaped']}/{v['clean_n']} (rate {v['rate']})  "
              f"wilson {v['wilson']}")
        print(f"  curve (cum by pass): {v['curve']}  ·  pass-1 {v['pass1_escaped']} "
              f"·  mean passes {v['mean_passes']}")
        print(f"  trajectory: deepened {v['deepened']} · held {v['held']} · "
              f"improved {v['improved']} · escaped {v['escaped']}  (of clean)")
        print(f"  vs baseline: final-below {v['final_below']}/{v['clean_n']} "
              f"·  ever-below {v['ever_below']}/{v['clean_n']}  "
              "(M2 no-instruction base rates: see docs/M2-BRIEF.md RESULTS)")
        print(f"  invalid loops {v['invalid']}: {v['invalid_by_cause']}")
        mf = mean_failed_by_pass(records, model, subsets[model])
        print(f"  mean failed by pass (active loops): {mf}")
        rows = [r for r in records if r.get("model") == model
                and r.get("pass", 0) >= 1 and "first_parse" in r]
        gens = [r["gen"] for r in records if r.get("model") == model
                and r.get("pass", 0) >= 1 and r.get("gen", {}).get("attempts")]
        v["pass_calls"] = len(rows)
        v["first_parse"] = sum(1 for r in rows if r["first_parse"])
        v["repair_cost"] = round(sum(r.get("cost", 0) for r in rows), 4)
        v["draft_calls"] = sum(len(g["attempts"]) for g in gens)
        v["draft_first_accept"] = sum(1 for g in gens if g["first_attempt_accepted"])
        v["gen_cost"] = round(sum(g["cost"] for g in gens), 4)
        v["mean_failed_by_pass"] = mf
        drifts = [g["drift_ratio"] for g in gens]
        v["mean_drift"] = round(sum(drifts) / len(drifts), 4) if drifts else None
        print(f"  pass-calls {v['pass_calls']} · first-parse {v['first_parse']} · "
              f"drafts {v['draft_calls']} (first-attempt ok {v['draft_first_accept']}"
              f"/{len(gens)}) · mean drift {v['mean_drift']}")
        print(f"  cost: repair ${v['repair_cost']} + gen ${v['gen_cost']}")
        out["models"][model] = v

    if not synthetic:
        ext = _read_jsonl(EXT_TRIALS_PATH)
        ext_valid = [r for r in ext if "repair_success" in r and "invalid" not in r]
        out["extension"] = {
            "trials": len(ext_valid),
            "damaged": sum(1 for r in ext_valid if r.get("damaged")),
            "comply": sum(1 for r in ext_valid if r.get("comply")),
        }
        m3_total = _meter().total
        out["cost"] = {"m3_total": round(m3_total, 4),
                       "lifetime": round(_lifetime(m3_total), 4)}
        proj = {}
        for model in models:
            v = out["models"][model]
            mean = v["repair_cost"] / v["pass_calls"] if v["pass_calls"] else 0.0
            m4_entry = v["clean_n"] - v["escaped"]  # corrupted finals
            proj[model] = {"m4_entry": m4_entry,
                           "m4_max": round(m4_entry * MAX_PASSES * mean, 3)}
        out["projection_upper_bounds"] = proj
        RESULTS_PATH.write_text(json.dumps(out, indent=1))
        print(f"\nextension: {json.dumps(out['extension'])}")
        print(f"cost: {json.dumps(out['cost'])}")
        print(f"M4 re-projection (5-pass upper bounds): {json.dumps(proj)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extend", help="deepseek T2-only extension over bank[150:186] (paid)")
    sub.add_parser("subset", help="freeze per-model T2-damaged entry subsets (free)")
    r = sub.add_parser("run", help="wrong-instruction loop wave (paid, resumable)")
    r.add_argument("--model", required=True)
    v = sub.add_parser("verdict", help="escape curves + trajectory + M4 re-projection")
    v.add_argument("--synthetic", action="store_true", help="dry-run on fixtures")
    args = ap.parse_args()
    if args.cmd == "extend":
        raise SystemExit(cmd_extend())
    if args.cmd == "subset":
        raise SystemExit(cmd_subset())
    if args.cmd == "run":
        raise SystemExit(cmd_run(args.model))
    raise SystemExit(cmd_verdict(args.synthetic))
