# M2 Start-of-Stage Brief — the recovery ceiling (RQ2 analog)

*Written 2026-07-11 · status: **SIGNED OFF 2026-07-11 (Kyle, via decision prompt):
D8-A (full failing-test report), D9-A ($0.45 cap), execution gate approved — free
build + dry-run, then loop waves deepseek → qwen end-to-end within cap and halt
triggers, no further pauses unless a trigger fires** · scope source:
`docs/KICKOFF.md` M2, unchanged by the 2026-07-10 re-scope, plus the paper-protocol
notes in `docs/M0-BRIEF.md` ("What the paper settles", item 4) · entry data:
`docs/M1-BRIEF.md` RESULTS*

## What M2 is, in plain terms

KICKOFF, verbatim: *"recovery ceiling — self-guided iterative repair from the original
buggy patch on the failed-T3 subset; paper's protocol verbatim (max 5 passes, early
stop on all-tests-pass)."* Per problem each model failed feedback-free single-pass
(M1's failed-T3 subset), the model now gets what T1–T3 deliberately withheld — test
feedback — and up to 5 self-guided attempts. The output is the **recovery curve** and
its endpoint, the **ceiling**: the best self-repair does under clean conditions. That
ceiling is the comparison anchor M4 measures irrecoverability against.

**What M2 is not:** it has no manipulation — no instructions, no generator, no
verifier; the wrong-location machinery is idle this milestone. It renders **no
REPRODUCED/PARTIAL/NULL verdict of its own** — the KICKOFF gates M4-vs-M2, not M2
alone; M2's labels are **REPORTED** or **UNDERPOWERED** (auto at clean-N < 20), plus a
pre-committed **FLOOR** flag (below). And it does not touch the deepseek M3-entry
extension — that stays owed pre-M3 with its machinery specified in the M3 brief
(standing commitment, `docs/M1-BRIEF.md`).

## Entry subsets (frozen from M1 data before any paid call)

Rule: a problem enters model M's subset iff its M1 T3 trial was **graded and failed**
(`arm == "T3"`, `repair_success == false` in `data/m1/trials.jsonl`). INVALID T3
trials are excluded by construction — an unparseable response never demonstrated
"incorrect code" (qwen has 10 such problems; deepseek 0).

| Model | failed-T3 | of valid T3 | already-damaged in that failed attempt |
|---|---|---|---|
| deepseek-chat-v3.1 | **23** | 150 | 12/23 |
| qwen3-coder-30b | **49** | 140 | 26/49 |

`m2.py subset` (free) derives the lists, asserts the counts (23/49), and freezes them
to **`data/m2/subsets.json`** in frozen bank order — committed before the run.

**N-check:** both cells clear the ≥20 floor, but deepseek has **3 problems of slack**:
any ≥4 INVALID loops → auto-UNDERPOWERED (the rule stands; no rescue). Measured M1
parse behavior (deepseek 149–150/150 first-parse, 150/150 after the bare retry) makes
that unlikely but it is the pre-committed outcome if it happens. This near-starvation
is the M1 T-A high-side flag materializing mildly: deepseek's strong T3 (84.7%) left
few failures.

## Protocol — the loop (paper's RQ2, M0-BRIEF item 4)

Paper protocol: *"each pass the model sees the problem statement, current code, and
the most recent failing test, generates its own diagnosis, repairs; max 5 passes,
early stop when all tests pass."* Each pass is one **stateless single-turn call** — no
chat history; the loop's only memory is the current code and its most recent grade.

**Pass-1 start state — pinned here: the original buggy program, not the failed T3
patch.** The KICKOFF says it verbatim ("from the original buggy patch"); the failed-T3
subset is the paper's *selection filter* ("restricted to failed-T3 instances"), not a
start state. Three reasons this is the right reading and not a wasted re-run:

1. **M4 symmetry.** M4 is "same repair protocol as M2, starting from M3's corrupted
   final states" — the protocol is parameterized on start state, and the M2 anchor
   must start clean (at the buggy baseline, damage = 0) so the M2→M4 contrast
   isolates corruption. Starting from failed-T3 patches would contaminate the anchor:
   12/23 (deepseek) and 26/49 (qwen) of those patches are already *damaged* — worse
   than baseline — which is M4's condition, not M2's.
2. **Pass 1 is not T3 again.** The T1–T3 prompts carried **no test feedback** (pinned
   in `prompts.py` since M0: "test feedback enters at M2+"). Pass 1 = the T3 task
   plus a concrete failing test — a genuinely new trial.
3. Every bank problem has `1 ≤ buggy_failed_baseline ≤ 19` (D3 damage headroom), so a
   failing test **always exists** at pass 1 — no entry-time INVALID analog.

**Per-pass mechanics (k = 1..5):**

- **Grade-0 (free, before pass 1):** the buggy original is graded in the sandbox.
  Pre-committed integrity halt: its failed count must equal the bank's
  `buggy_failed_baseline` **exactly**, else the wave halts (harness drift, not a
  trial-level INVALID) and the disposition is recorded before anything resumes.
- **Feedback:** the prompt shows the **first failing test in the frozen per-problem
  test order**, taken from the grade of the current state (grade-0 for pass 1, the
  pass-(k−1) grade after). Fields per D8; every field truncated at 1,000 chars with a
  `… [truncated]` marker. The sandbox captures rc/stdout/timed_out only (stderr is
  discarded by design), so "actual" = captured stdout plus a status marker
  (`[process exited with code N]` / `[process timed out after 5s]`) when applicable.
  The rendered block is stored **verbatim** in the pass record, and render-time
  asserts the shown test is failing per the recorded grade (feedback-consistency
  check).
- **Repair call:** carried verbatim from M0/M1 — reasoning `{"enabled": False}`,
  `REPAIR_MAX_TOKENS = 3200` (measured floor), provider default sampling, the same
  parse rules (last fenced block, `compile()`-clean, one bare retry then INVALID),
  `client.chat`'s transient-retry tuple incl. OpenRouter's malformed-body
  `JSONDecodeError`.
- **Grade (free, local, synchronous):** full selected test set (≤20 tests), S-exact.
  `failed == 0` → **recovered at pass k**, loop stops. Else current code := the
  parsed patch, next pass.
- **INVALID:** a pass whose parse fails after the bare retry (or an infra error after
  one re-run) makes the **whole loop INVALID** — excluded from every denominator,
  counted, reported. Scoring a format failure as "not recovered" would fake
  divergence; the honesty contract forbids it.
- A patch byte-identical to the current code is a valid pass (it burns a pass and
  regrades the same); no special-casing.

**Prompt template** (frozen in `prompts.py` at build, tested; `# Actual output` block
present under D8-A, absent under D8-B; task/output lines verbatim from the frozen M1
repair template so the parse machinery is untouched):

````
# Problem
{description}

# Current program (it has a bug)
```python
{code}
```

# Most recent failing test
Input:
```
{test_input}
```
Expected output:
```
{expected_output}
```
Actual output:
```
{actual_output}
```

# Task
Diagnose the bug on your own and fix it.

Reply with the complete corrected program in a single ```python code block.
The program must read from stdin and write to stdout exactly as the problem requires.
````

**Per-trial mechanical checks** (M2's analog of manipulation verification): pass-1
current code byte-equals the bank's `buggy_code`; grade-0 reproduces the frozen
baseline; every rendered feedback block cites a test the recorded grade says is
failing; every loop's problem is in the frozen subset. All asserted in code, not
eyeballed.

## Endpoints (all Wilson 95%; per model, never pooled)

- **Primary (descriptive): the recovery ceiling** — recovered loops / clean loops,
  where recovered = all tests pass within ≤5 passes. Labels: REPORTED (clean-N ≥ 20)
  / UNDERPOWERED (auto below).
- **The recovery curve:** cumulative recovery by pass k, k = 1..5 — the KICKOFF's
  named deliverable, and the shape M4 mirrors.
- **Pre-committed FLOOR flag (M4-contrast room):** if a model's ceiling has Wilson
  lower bound < 0.05 (concretely: ≤3/23 recoveries for deepseek, ≤5/49 for qwen), the
  M2 anchor is flagged **FLOOR** — M4's directional gate (M4 < M2) is pre-declared
  unresolvable for that model, both milestones report descriptively, and the combined
  self-repair floor becomes the headline. Declared now so the M4 brief inherits a
  rule, not a rationalization.
- **Secondaries (ungated):** pass-1 recovery (what feedback alone buys); mean passes
  used; **self-inflicted damage** — final state failing more tests than the buggy
  baseline — and **ever-below-baseline** — any pass state worse than baseline. These
  two are the no-instruction damage base rate: M3's wrong-instruction damage claim
  reads against them. Plus INVALID counts, per-pass first-parse rates, finish_reason
  counts.
- **M3/M4 cost re-projection** from measured M2 per-pass rates (M4 runs this exact
  loop; M3 adds the generator), for the M3 brief.

**Honest expectation, stated before the run:** these are the problems each model
*couldn't* fix feedback-free, so the ceiling is not predictable from M1's pass rates.
deepseek's 23 skew hard (it cleared everything easy); qwen's 49 include more ordinary
misses. Half the subsets' failed attempts were already self-damaging (12/23, 26/49) —
if that recurs across passes, divergence beats convergence and the ceiling lands low.
A low ceiling is a reportable finding (nulls are headlines), with its M4 consequence
pre-committed in the FLOOR rule.

## Waves, machinery, and halt triggers

New flat script **`m2.py`** (subcommands, per conventions), artifacts under
`data/m2/`, run logs committed; `test_m2.py` TDD for all pure logic (subset
extraction, resume-state reconstruction, recovery/early-stop classification, curve
math, feedback-block builder incl. truncation + failing-test pick + status markers,
INVALID rules, meter, labels + FLOOR rule) — tests green before any paid call.

1. **Free:** `m2.py subset` freezes `data/m2/subsets.json` (asserts 23/49);
   `m2.py verdict --synthetic` dry-runs REPORTED / UNDERPOWERED / FLOOR paths on
   fixtures ("gates as code, dry-run before paid").
2. **`m2.py run --model <slug>`** — deepseek then qwen (M1's order). Loops in frozen
   subset order; grade-0 integrity halt; ≤5 passes, live-graded, early stop.
   Append-only **`data/m2/trials.jsonl`**, one record per pass keyed
   `(model, problem_id, pass)` (pass 0 = the free grade-0 record; patch + verbatim
   feedback block stored per pass). Resume reconstructs loop state from existing
   records and skips finished loops — halts/cap raises never re-spend.
   **Auto smoke-gate at the first 5 paid pass-calls per model:** first-parse ≥ 4/5
   and mean ≤ 2× that model's per-pass estimate ($0.00135 deepseek / $0.00068 qwen),
   else halt to Kyle.
3. **Parse floor per completed model wave:** first-parse ≥ 80% over its pass-calls,
   else halt — deepseek has one unused format revision, qwen has none (spent in M0);
   prompt semantics are frozen either way.
4. **Free:** `m2.py verdict` renders ceiling + curve + secondaries + checkpoints +
   re-projection; RESULTS appended to this brief; artifacts + logs committed.

Ops rules carried from M1: 420 s trials.jsonl write-age → kill + resume; an
ESTABLISHED provider connection means a call is in flight (don't kill early).

## Cost estimate (measured rates) + cap regime

| Item | Pass-calls (max) | $/pass (measured basis) | 5-pass upper |
|---|---|---|---|
| deepseek 23 loops × ≤5 | 115 | 0.00119 (failed-T3 subset mean) + 0.00016 feedback-input bump → **0.00135** | $0.155 |
| qwen 49 loops × ≤5 | 245 | 0.000626 + 0.00005 → **0.00068** | $0.167 |
| Variance pad ~10% | — | — | $0.032 |
| **M2 upper bound (no early stop)** | ≤360 | | **≈ $0.35** |

Re-basing note: `data/m1_results.json`'s m2_max ($0.07/$0.096) used the all-arms mean
$/trial; this estimate re-bases on the **failed-T3 subset means** — failed trials run
~40% dearer on deepseek (longer responses) — plus the feedback block (~750 tokens of
input). Rates embed M1's parse-retry spend. Early stop only lowers real spend; the
cap is set off the no-early-stop bound. Grading is free/local; there is no generator
wave.

**Cap regime (per-milestone ledgers, one lifetime invariant):** M1's meter is frozen
at $0.5840 as the M1 record; `m2.py` runs its own meter on
**`data/m2/cost_ledger.json`**, cap = D9, same check-before-call halt semantics.
Every wave prints wave cost, M2 total, and lifetime; the pre-committed **$5.00
lifetime guard** halts any wave whose projection would cross it. Lifetime worst case
after M2 at the recommended cap: $0.911 + $0.45 = **$1.36**.

## Deviations delta (M2-specific; M0 rows 1–6 and M1 rows 7–9 still apply)

| # | Deviation | Why | Mitigation |
|---|---|---|---|
| 10 | Failing-test feedback rendering is ours — fields (D8), first-failing-in-frozen-order pick, 1,000-char truncation, stdout-only "actual" with status markers (no stderr — the sandbox discards it by design) | Paper says the model "sees the most recent failing test" but publishes no format | D8 pins the fields; template frozen in code + tested before any paid call; the rendered block is stored verbatim per pass for audit |

## Decisions — pick or veto (recommendation marked)

- **D8 · Feedback content:** **A. Full failing-test report — input + expected +
  actual output (Recommended).** *Merit:* what a real test harness shows; diagnosis
  needs the discrepancy, and M2 is the *ceiling* anchor — under-informing deflates it
  artificially and biases the M4 contrast toward "no gap". *Trade-off:* strictly more
  help than the most literal reading of "sees the failing test".
  **B. Test-only — input + expected, no actual output.** *Merit:* the most literal
  minimal reading; a more conservative ceiling. *Trade-off:* the model can't see what
  its program did; a depressed anchor weakens M4's headline comparison.
- **D9 · M2 hard cap:** **A. $0.45 (Recommended)** — ≈1.3× the no-early-stop upper
  bound, M1's cap ratio. · B. $0.60 — extra slack, one fewer potential halt-and-ask.
  · C. $0.35 — equals the upper bound; can fire on pure variance.
- **Execution gate:** sign-off authorizes, in order: free build + tests green +
  synthetic dry-run + frozen subsets committed → deepseek loop wave (smoke-gated) →
  qwen loop wave (smoke-gated) → verdict + RESULTS + commit — all within the D9 cap
  and the halt triggers above (smoke gates, parse floor, grade-0 integrity halt,
  lifetime guard), no further pauses unless a trigger fires. Sign-off also covers the
  pass-1 start-state pinning (original buggy program, §Protocol).

**SIGN-OFF (Kyle, 2026-07-11, via decision prompt):** D8-A · D9-A · execution gate
approved (full auto within the $0.45 cap and the pre-committed halt triggers,
including the pass-1 start-state pinning).

## What M2 hands forward

- **M4:** the per-model ceiling + curve (its comparison anchor), the FLOOR flag state,
  and the loop machinery itself — written start-state-parameterized so M4 swaps in
  M3's corrupted finals without protocol drift.
- **M3 brief (unchanged, still owed):** the deepseek T2-only extension along
  `bank[150:186]` + pool-smoke (machinery specified there), and the
  diff-anchor-after-code-drift verifier design (KICKOFF open question).
- **M2 RESULTS** will also hand the M3 brief re-projected M3/M4 costs from measured
  per-pass rates.
