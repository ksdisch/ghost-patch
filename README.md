# ghost-patch

Hobby-scale, pre-committed reproduction of **"Obey, Diverge, Collapse"** (arXiv 2607.04537): the claim that code LLMs recognize a wrong-location repair instruction as incorrect, follow it anyway, compound ghost errors across iterative repair passes, and land in a corrupted state that self-guided repair cannot recover — not even back to the original buggy baseline. Fourth in a lineage of reproduce-and-measure projects (forge-gap → decay-pin → lossy-wall); the target paper is days old, unreplicated, and its promised code appendix is absent from v1, so every prompt, filter, and gate here is independently built and disclosed.

**Status: v1 COMPLETE — the chain is closed end-to-end (M4 closed 2026-07-11).** Measured on two cheap models — deepseek-chat-v3.1 and qwen3-coder-30b-a3b-instruct — over a frozen 186-problem RunBugRun bank, with every verdict rendered by a script written and dry-run **before** the paid data existed. Lifetime spend: **$1.4244** against a $5.00 guard.

## The chain verdict

| Link | Paper claim | Our verdict | Key measured numbers |
|---|---|---|---|
| Precondition (M0) | aware-but-obedient | **NULL (tier-level)** | 0/6 models clear the probe gate ×2 wordings; Kimi ~25% vs paper's 63% |
| Obey (M1) | wrong-location drop | **NULL ×2** | +4.0 pts [−2.2, +10.3]; +3.6 pts [−3.4, +10.6]; comply 129/150, 127/146 |
| Recover (M2) | recovery ceiling | **REPORTED ×2** | 78.3% [58.1, 90.3]; 52.6% [37.3, 67.5]; pass-1 front-loaded |
| Compound (M3) | ghost-error compounding | **REPORTED (qwen) · UNDERPOWERED (deepseek)** | escape 30.4% [15.6, 50.9], pass-1-only; final-below-baseline 65.2% vs base 31.6% (descriptive) |
| Collapse (M4) | irrecoverability | **UNDERPOWERED ×2 (pre-declared) + descriptive IDR** | IDR 6/12 = 50% [25.4, 74.6]; M2−M4 +28.3 [−17.0, +70.6] / +19.3 [−12.3, +43.9] |

The two headline results are **nulls, reported as headlines**: the awareness precondition does not reproduce at the cheap tier (blindness, not blind obedience — including on the paper's own Kimi K2.5), and one wrong instruction produces no net single-pass repair drop. The chain's back half is visible where powered: under five passes of mechanically verified sabotage, qwen escapes only at pass 1 (curve [7,7,7,7,7]), and once the saboteur stops, half its corrupted states (6/12) never re-cross the buggy baseline in five feedback passes — damage stops compounding (deepened 0/12) but doesn't heal.

## Read the results

- **Paper:** [docs/paper/ghost-patch-paper.md](docs/paper/ghost-patch-paper.md) — the full writeup; every number lifted verbatim from the repo's committed records.
- **Presenter pack:** [docs/paper/ghost-patch-presenter-pack.md](docs/paper/ghost-patch-presenter-pack.md) — the 60-second story, a claim-by-claim provenance map, and anticipated Q&A.
- **Milestone briefs (source of truth):** [docs/M0-BRIEF.md](docs/M0-BRIEF.md) … [docs/M4-BRIEF.md](docs/M4-BRIEF.md) — pre-committed decisions, triggers, and appended RESULTS.
- **Machine results:** `data/m1_results.json` … `data/m4_results.json` (+ `data/pilot_results.json`), with per-trial artifacts and cost ledgers under `data/m1/`–`data/m4/`.

## How it was measured (honesty contract)

Reproduce and measure, never invent. Deterministic, judge-free grading in a network-less Docker sandbox (frozen S-exact semantics; the container never sees expected outputs). Every wrong instruction is a manufactured fault that must pass a per-trial mechanical verifier — anchor matches the code, target provably disjoint from the diff-computed true-fix region, no fix content leaked — and unverifiable drafts are INVALID: excluded from every denominator, counted, reported. Verdict gates were frozen as code before any paid run; all rates carry Wilson intervals and contrasts carry Newcombe intervals; any gated cell under 20 clean trials auto-reports UNDERPOWERED, no rescue. Direction + structure, never point estimates. Full contract: [docs/KICKOFF.md](docs/KICKOFF.md).

## Repo map

| Path | What it is |
|---|---|
| `m0.py` … `m4.py` | per-milestone verdict scripts — gates and triggers as code, subcommands per milestone |
| `pilot.py`, `prompts.py`, `client.py` | M0 pilot runner, prompt templates, metered OpenRouter client (check-before-call, $5 lifetime guard) |
| `sandbox.py`, `grading.py` | Docker sandbox execution + deterministic S-exact grading |
| `filter_bank.py`, `regions.py`, `stats.py` | pre-committed bank filter; fix-region math; Wilson/Newcombe (no external stats deps) |
| `fetch_runbugrun.py` | checksum-pinned fetch of RunBugRun + PIE4Perf statements into `data/raw/` (gitignored) |
| `test_*.py` | pytest suite — 256 tests green at M4 close |
| `data/bank.json`, `data/pool.json` | the frozen 186-problem bank; the seed-2607 pool (frozen-prefix discipline) |
| `docs/` | KICKOFF brief, M0–M4 briefs, spot-read samples of accepted wrong instructions, the paper |

## Reproduce / audit

Raw data is gitignored but refetchable via `fetch_runbugrun.py`; everything derived (pool, bank, smoke/run logs, trial artifacts, results JSON) is committed. Run `pytest` for the test suite. The natural next arm — a gated "cure" experiment (does putting failing-test evidence or a refusal license into the wrong instruction collapse obedience?) — is parked; see the paper's conclusion.

## Spend

M0 $0.3269 · M1 $0.5840 · M2 $0.1874 · M3 $0.2549 · M4 $0.0711 — **lifetime $1.4244**, all inside pre-committed caps.
