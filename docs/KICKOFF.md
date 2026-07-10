# Kickoff Brief — ghost-patch
*Created 2026-07-10 · status: scoped (approved 2026-07-10) · repo: github.com/ksdisch/ghost-patch (public)*

## One-liner
Reproduce and measure, on cheap models at hobby scale, the "Obey, Diverge, Collapse" failure chain (arXiv 2607.04537): code LLMs correctly flag a wrong-location repair instruction as incorrect, follow it anyway, compound Ghost Errors across iterative passes, and land in a corrupted state that self-guided repair cannot recover even to the original buggy baseline.

## Why now / the problem
Fourth rung of the reproduce-and-measure lineage (forge-gap → decay-pin → lossy-wall). Chosen at `/seed-hunt` as the **new-surface** option: code repair + a sandboxed code-execution/test-grading harness is a genuinely new muscle, while the transferable discipline (Wilson/Newcombe, pre-committed gates, mechanical verification) carries over. The paper is days old (v1 2026-07-05), unreplicated, and its promised code appendix is **missing from v1** — an honest independent reproduction has real standalone value. The paper is also a pure failure mode with no cure, which tees up the gated post-v1 arm.

## Who it's for
Kyle — portfolio of honest reproductions + the learning arc. The recruiter-legible artifact is the repo + verdicts; the new skill is sandboxed execution of untrusted (model-generated) code against deterministic test suites.

## What success looks like
- **v1 done means:** all four chained claims have pre-committed verdict scripts (m1–m4.py pattern) that ran on real data and rendered REPRODUCED / PARTIAL / NULL / UNDERPOWERED per claim, on ≥2 pilot-surviving cheap models, with Wilson/Newcombe CIs; every scored T2 trial's manipulation mechanically verified; a null is a reportable headline.
- **Would be amazing:** a clean irrecoverability floor (M4 recovery ≈ 0 at N≥20) with CI-separated M2-vs-M4 recovery gap on 2+ models, plus significant awareness≠resistance McNemar on 2+ models — then a post-v1 cure arm showing a one-line intervention rescues it.
- **Explicitly NOT trying to:** invent mechanisms; run frontier/big models as subjects; reasoning-level ablations (paper's T3*); LLM-judged anything; real-world multi-file repair; match the paper's point estimates (direction + structure only).

## Scope
**In (v1):**
- RunBugRun Python subset → pre-committed filtered bank (deterministic tests, small-diff bugs, short programs, English descriptions). Target 100–150 problems, **expandable to ~300 if M0's measured funnel rates demand it** (see risk 5).
- **M1 (RQ1 analog):** single-pass repair under T1 correct / T2 wrong-location / T3 no instruction, plus the evaluator-role awareness probe (CORRECT/INCORRECT label, neutral key). Primary: awareness≠resistance (McNemar) + paired T2-vs-T3 pass-rate drop.
- **M2 (RQ2):** recovery ceiling — self-guided iterative repair from the original buggy patch on the failed-T3 subset; paper's protocol verbatim (max 5 passes, early stop on all-tests-pass).
- **M3 (RQ3):** iterative wrong instructions on the confirmed-damage subset (T2-damaged: failed-test count exceeds buggy baseline); live generator+verifier per pass; escape-rate flatness descriptive.
- **M4 (RQ4):** same repair protocol as M2, starting from M3's corrupted final states. Primary: **Irrecoverable Damage Rate** (paper's definition verbatim: fails to re-cross the buggy-patch baseline within 5 passes) vs the M2 ceiling.
- Roster: 3 cheap OpenRouter models, pilot-gated with kill/swap triggers. Proposed: `qwen3-coder-30b-a3b` (cheap kin of a paper model), `deepseek-chat-v3`, `llama-3.1-8b-instruct`; bench: `qwen2.5-coder-7b`, `mistral-small`. M0 decides.
- The manipulation: **LLM-drafted (fixed non-roster generator model), mechanically verified, frozen bank** for M1; same generator+verifier live per-pass in M3. Generator outputs structured fields (target function/lines, diagnosis, directive) rendered through a light template — the checkable part is structured, the surface form stays fluent/confident. Verifier: target region provably disjoint from the buggy↔fixed diff **and** no fix-content leak (no normalized overlap with the fix diff's added lines). Unverifiable trial = INVALID, excluded, rate reported.

**Out / deferred / never:**
- Cure/intervention arm (show the failing test, license refusal) — **the flagship post-v1 arm, gated**.
- Reasoning ablation; >3 subject models; non-Python; the paper's harness in our code (reference-only if a v2 ships it — then an optional $-bounded cross-check rider); LLM judges (never).

## Shape
CLI pipeline, lineage pattern: Python + JSON per-trial artifacts + per-milestone verdict scripts, run logs committed. New piece: a local sandboxed runner (Docker `python:3.12-slim`, `--network=none`, CPU/mem/time caps) executing candidate programs against stdin/stdout test pairs.

## Inputs & data
RunBugRun (`giganticode/run_bug_run`) — **verified fetchable 2026-07-10**: JSONL releases per language (`giganticode/run_bug_run_data`, e.g. `python_test0.jsonl.gz` ~1.2 MB, `tests_all.jsonl.gz` ~20 MB) + SQLite dump; schemas confirmed to include `problems.text` (English descriptions), `tests` (input/expected-output), `bugs` (buggy_code, fixed_code, change_count, splits). Note: the paper's exact 538-problem filter is unpublished → our bank is our own pre-committed filter (fine — direction + structure, not point estimates).

## Integrations & dependencies
OpenRouter (existing key), Docker Desktop (present), GitHub via `gh` (authed as ksdisch). No paper code exists to depend on.

## Constraints
Hobby budget (<$5 target; lineage precedent ≈ $2 total); statistics is the binding constraint (N≥20 clean trials per gated cell, else the gate auto-reports UNDERPOWERED); macOS, no GPU; measured-rate cost estimates before every paid wave; N≈5 smoke before every paid arm.

## Riskiest assumptions & unknowns
1. **The precondition (bar 10) — cheap models must exhibit blind obedience.** Three distinct failure directions, per-model: (a) too skeptical → resists T2 (competence ceiling); (b) too weak → T1/T3 repair ≈ 0, so the T2 delta has no room to exist (capability cliff — the bank's difficulty filter is the knob); (c) can't classify the instruction in the evaluator role → the "aware" leg collapses and it's blindness, not blind *obedience*. — *cheap test:* M0 pilot, N≈12 problems × 3 models × {T1,T2,T3,probe}, per-model kill/swap triggers pre-committed.
2. **Harness fidelity** — RunBugRun tests must run locally with clean semantics (whitespace/float tolerance, timeouts). — *cheap test:* M0 smoke: fixed reference passes all tests and buggy fails ≥1 on ≥90% of sampled problems, else tighten filter or kill.
3. **Generator+verifier viability** — drafts must read confident/plausible and survive the mechanical verifier at a workable rate. — *cheap test:* M0 generates ~20 instructions, measures rejection rate, Kyle spot-reads 5.
4. **Patch extraction** — models must return parseable full-program patches; unparseable = INVALID. — *cheap test:* counted in M0; >20% on a model = prompt fix or swap.
5. **The funnel is the N risk.** M3 entry = T2-damaged subset (paper: 5–22% of 538 depending on model); M4 inherits M3. At bank 120 a weak-funnel model can land <20. — *mitigation:* M0's measured obedience rates size the bank (computed, not guessed) so projected M3 entry ≥20/model; bank growth is pennies.
6. "Irrecoverable" pre-committed **verbatim from the paper** before any paid run: 5 passes, early stop, recovery = re-crossing the buggy-patch test-pass baseline.

## Open questions
- Does a v2 with the appendix/code appear? (Watch; reference-only either way.)
- M3 verifier after code drift: anchor the original diff region in mutated code by identifier/line matching; unresolvable anchor = INVALID trial. Detail signed in the M3 stage brief.

## Phased plan
### Milestone 0 — Fit-pilot: the precondition + the new muscle
- Fetch RunBugRun, pre-commit the bank filter, build the sandboxed runner, smoke-test grading fidelity (risk 2).
- Pilot the roster on ~12 problems: awareness rate, obedience signal, T1/T3 baseline repair rate, patch-parse rate (risks 1, 4). Kill/swap triggers **written before the pilot runs**.
- Pilot the instruction generator+verifier (risk 3). Measured per-trial cost → bank sizing (risk 5).
### Milestone 1 — Single-pass obedience (RQ1)
- Freeze the verified T2 bank; run T1/T2/T3 + probe across roster; `m1.py` pre-committed + dry-run (McNemar exact; paired Newcombe T2-vs-T3, gate δ: drop ≥10 pts with CI excluding 0).
### Milestone 2 — Recovery ceiling (RQ2)
- Failed-T3 subset → 5-pass self-repair; recovery curve; establishes the comparison anchor for M4.
### Milestone 3 — Ghost-error compounding (RQ3)
- Confirmed-damage subset → 5 passes of live-generated, per-pass-verified wrong instructions; escape-rate curve (descriptive); hands corrupted states to M4.
### Milestone 4 — Irrecoverability (RQ4)
- M2's protocol from M3's corrupted states; Irrecoverable Damage Rate; gate: M4-vs-M2 recovery difference, Newcombe CI excluding 0 (direction M4 < M2); floor headline if M4 ≈ 0.
### Post-v1 (gated) — The cure arm
- Cheapest intervention the paper never tests: put the failing-test evidence or an explicit refusal license into the T2 prompt — does obedience/irrecoverability collapse?

## Tech stack
Python 3.12 + uv; `openai` SDK → OpenRouter; Docker sandbox for execution; hand-rolled Wilson/Newcombe (port the *pattern* from lossy-wall's stats.py — our own code); no external stats deps. Rationale: identical to the proven lineage stack, plus Docker as the one new component.

## Honesty contract (inherited, non-negotiable)
Reproduce-and-measure, never invent. Judge-free deterministic scoring only. Per-trial mechanical verification of the manipulation. Pre-committed gates as code, dry-run before paid data; nulls are headlines. Direction + structure, never point estimates. Fit-pilot with kill/swap triggers before any grid. Paper harness (if ever released): reference-only.
