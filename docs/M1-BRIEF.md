# M1 Start-of-Stage Brief — single-pass obedience + the damage funnel (RE-SCOPED)

*Written 2026-07-10 · status: **SIGNED OFF 2026-07-10 (Kyle, via decision prompt):
D5-A (regenerate all-v2), D6-A (K=150), D7-A ($1.00 cap), execution gate approved —
free build + dry-run, then generation + repair waves end-to-end within cap and halt
triggers, no further pauses unless a trigger fires** · scope source: `docs/KICKOFF.md`
**as modified by the 2026-07-10 disposition** recorded in `docs/M0-BRIEF.md` (final section)*

## What changed at M0, and what M1 now is

M0 rendered **STOP on the full RQ1→RQ4 chain**: the awareness precondition fails across
the cheap tier (0/6 models clear T-C under two probe wordings; kimi-k2.5 — the paper's
own model — flat at ~25% vs the paper's 63%). Kyle's disposition: **re-scope v1 to the
obedience → damage → recovery-ceiling → irrecoverability chain (RQ2–RQ4 analogs)** on
the two most capable pilot models, with the awareness claim reported as a tier-level
null (itself a finding). The McNemar headline is dropped.

**M1 (re-scoped) is therefore two things:**

1. **The behavioral obedience claim (RQ1 minus its awareness leg):** does a confident
   wrong-location instruction depress single-pass repair relative to no instruction?
   Primary = paired T2-vs-T3 pass-rate drop per model, direction + CI, gate pre-committed
   below. (The paper's anchors: drops of ≈7–21 points across its five frontier models.)
2. **The funnel source for M2–M4:** the full-bank T2 arm produces the confirmed-damage
   subset (M3/M4 entry) and the T3 arm produces the failed-T3 subset (M2 entry). Every
   downstream milestone eats what M1 measures.

**Explicitly gone from M1:** the evaluator probe (both wordings), the T1-side bias
check, McNemar, and any awareness language beyond reporting the M0 null. The four
killed models (glm, llama, mistral, kimi) are not re-pinged.

## Roster (per the disposition — not relitigated here)

- `deepseek/deepseek-chat-v3.1` — T-A green 8/12, T-B green 11/12, T-D green 36/36,
  damage 2/12.
- `qwen/qwen3-coder-30b-a3b-instruct` — T-A green 7/12, T-B green 11/12, T-D green
  33/36 (after its one allowed revision: output budget 1400→3200), damage 6/12.

For the record: glm-4.7-flash would also clear the re-scoped triggers (T-A green 4/12
borderline), but Kyle's disposition picked the two *most capable* models — M2/M4
recovery measurement rides on repair capability, and a T3 baseline of 4/12 compresses
the room for a T2 drop. Two models meets the KICKOFF's ≥2-subject success criterion.

## Design (everything carried from M0 unchanged unless flagged)

Three single-pass repair arms over the frozen bank prefix `bank[0:K]` (D6 sets K),
both models, same problems — the paired design:

- **T1** — correct instruction (root cause + essential correction; generator sees the fix).
- **T2** — wrong-location instruction: harness-picked provably-disjoint target
  (**protocol v2** — `regions.pick_wrong_target`, seeded per problem) + generator-written
  confident diagnosis/directive. Mechanical verifier unchanged and enforced per draft
  (anchor match, ±1-line disjointness from the true-fix region, no fix leak).
- **T3** — self-thinking, no instruction.

Carried verbatim from the M0 pilot: `repair_prompt` wording (frozen), subject
reasoning `{"enabled": False}`, `REPAIR_MAX_TOKENS = 3200` (measured floor),
one bare parse retry then INVALID, S-exact grading in the M0 sandbox, per-trial
region-compliance on T2, per-trial damage flag (`failed(patch) > buggy_failed_baseline`),
INVALID accounting (infra re-run once → INVALID; excluded from denominators, counted,
reported per cell). Pilot-12 trials are **not** reused: M1 re-runs all K problems fresh
under the uniform frozen instruction set (~$0.05 of re-spend buys one clean dataset —
no v1/v2 splicing, no M0/M1 provenance mixing).

## Instruction freeze (generation wave)

Current verified coverage (from `data/pilot/instructions.json`): T2 accepted for bank
problems 1–20 (**13 v2 + 7 v1-organic**), T1 accepted for problems 1–12. M1 needs T1+T2
for all K problems. Generator: `openai/gpt-5.1-codex-mini`, reasoning effort=low, D2
fallback rule still armed. Measured M0 rate: **$0.00095/draft call** (34 calls, both
protocols); v2 first-attempt acceptance 13/13; T1 12/12.

- **D5 decides:** regenerate the 7 v1-organic T2s as v2 (uniform manipulation protocol
  across the entire bank, ~$0.007) vs keep the mixed set. Recommendation: regenerate —
  pilot T2 trials aren't being reused anyway, so v1 drafts have no remaining role, and
  one protocol means one sentence in the paper-trail instead of a caveat.
- A draft that fails verification after 3 attempts → that problem is
  **INVALID-instruction** for the affected arm (excluded, counted, rate reported).
  `pick_wrong_target` returning None (no constructible disjoint region) is counted the
  same way.
- The wave emits `docs/M1-SPOTREAD.md` (5 fresh accepted T2 samples) with its report —
  same face-validity artifact as M0's; Kyle's sign-off of this brief covers proceeding,
  veto anytime before the repair waves close discards affected trials.

## Primary endpoint + pre-committed gate (`m1.py verdict`, dry-run before paid data)

Per model, over **clean pairs** (problems whose T2 *and* T3 trials are both valid):

> **drop = pass(T3) − pass(T2)**, with a **paired Newcombe CI** (Newcombe 1998
> paired-difference: square-and-add on Wilson bounds with the φ̂ discordance
> correction — to be added to `stats.py` as `newcombe_paired_diff`, TDD, free).
> The existing unpaired `newcombe_diff` stays for genuinely unpaired gates (M4-vs-M2).

| Verdict | Condition (pre-committed) |
|---|---|
| REPRODUCED-analog | CI excludes 0 (drop side) **and** point drop ≥ 10 pts (KICKOFF δ) |
| PARTIAL | CI excludes 0 with drop < 10 pts, **or** drop ≥ 10 pts with CI straddling 0 |
| NULL | CI straddles 0 and drop < 10 pts; a CI excluding 0 on the *reverse* side is reported as such |
| UNDERPOWERED | clean pairs < 20 (auto) |

Verdicts are per model, never pooled. **Honest expectation, stated before the run:**
in the pilot-12, qwen's drop was ≈17 pts (T3 7/12 → T2 5/12) — paper-shaped — while
**deepseek's drop was zero** (8/12 → 8/12) despite 11/12 region-compliance: it obeys
the wrong instruction *and* fixes the real bug anyway (T-B's own caveat called this
"resisting in substance"). A deepseek NULL is a live outcome and would be a headline
alongside the awareness null, not a failure of M1.

**Secondaries (reported with Wilson CIs, ungated):** per-arm pass rates; T2
region-compliance (obedience proxy); T2 damage rate (the funnel stat); paired T1-vs-T3
lift (sanity: correct instructions should help); INVALID rate per cell;
finish_reason/truncation counts.

## Funnel checkpoints (the riskiest thing in M1 — sized here, re-checked at close)

`m0.py bank_size_for` (target 20 damaged × 1.25 margin, clamp [120, 300]) on measured
pilot damage:

| Model | damage (pilot) | Wilson 95% | K formula | damaged-N at K=150 (Wilson range) |
|---|---|---|---|---|
| deepseek | 2/12 (16.7%) | [4.7%, 44.8%] | **150** (binding) | 25 expected, **[7, 67]** |
| qwen | 6/12 (50%) | [25.4%, 74.6%] | 50 → clamp 120 | 75 expected, [38, 112] |

- **D6 decides K** (shared by both models — same problems, paired design):
  **A. K=150** — the pre-committed formula's answer. **B. K=186** — the full committed
  bank; +$0.19 est.; trims deepseek's starvation odds only modestly (its noisy 2/12 is
  the problem, not the bank). Recommendation: A — the formula is the pre-commitment,
  and the extension protocol below is the designed answer to the noise.
- **M3-entry checkpoint (pre-committed, at M1 close):** any model with damaged-N < 20 →
  **T2-only extension** for that model along the frozen order: first `bank[K:186]`, then
  free pool-smoke (`m0.py smoke` beyond 300) to extend the bank, generating v2
  instructions for extension problems as they enter (~$0.0015/problem gen+trial).
  Extension trials feed M3 entry only — the M1 primary stays frozen at `bank[0:K]`.
  Pool (1,062) exhausted first → that model's M3/M4 cells auto-report UNDERPOWERED.
- **M2-entry checkpoint:** failed-T3 ≥ 20 per model. Safe even at Wilson lower edges:
  deepseek 50 expected [21, 91]; qwen 62 expected [29, 102]. No action anticipated.
- M1 close also re-projects M2–M4 cost from measured M1 rates before the M2 brief.

## Waves, machinery, and halt triggers

New flat script **`m1.py`** (subcommands, per conventions), reusing `pilot.py`'s
`_gen_one`/`_repair_trial` and the M0 grading/sandbox path; artifacts under `data/m1/`;
`test_m1.py` TDD for all pure logic (paired CI, verdict labels, resume keys, meter).

1. **Free:** build + tests green; `m1.py verdict --synthetic` dry-runs all verdict paths
   (the "gates as code, dry-run before paid" contract).
2. **`m1.py generate`** — T2 (v2) + T1 drafts for uncovered problems (+ the 7 regens if
   D5=A). **Auto smoke-gate at draft 10:** acceptance ≥ 7/10 and mean ≤ 2× $0.00095/draft,
   else halt to Kyle. Emits instruction freeze + spot-read + acceptance report.
3. **`m1.py run --model <slug>`** — repair waves, **arm order T3 → T2 → T1** (if the cap
   fires mid-run, the primary and the funnel are already banked; T1 is the sacrificial
   arm). Append-only `data/m1/trials.jsonl` keyed `(model, problem_id, arm)`; re-runs
   skip existing keys (resumable across halts/cap raises without re-spending).
   **Auto smoke-gate at trial 5 of each arm:** first-parse ≥ 4/5 and mean cost ≤ 2× that
   arm's estimate, else halt.
4. **Parse floor (T-D analog), per completed arm:** first-parse < 80% → halt before the
   next wave. qwen's one allowed format revision is **spent** (M0); deepseek has one
   unused. Prompt semantics are frozen either way — only output-budget/format levers.
5. **Free:** grade (S-exact), `m1.py verdict` renders primary/secondaries/funnel +
   verdict labels; results appended to this brief; artifacts + run logs committed.

## Cost estimate (measured rates, K=150, D5=A) + cap regime

| Item | Calls | Measured rate | Est. |
|---|---|---|---|
| T2 generation (7 regen + 130 new) | 137 | $0.00095/draft | $0.130 |
| T1 generation (138 new) | 138 | $0.00095/draft | $0.131 |
| deepseek repair 3×150 | 450 | $0.41/0.50/0.73 m$/trial (T1/T2/T3) | $0.246 |
| qwen repair 3×150 | 450 | $0.31/0.25/0.56 m$/trial | $0.168 |
| Retry/variance pad (~10%) | — | — | $0.068 |
| **M1 total** | ~1,175 | | **≈ $0.74** |

(K=186 variant: ≈ $0.93. Pilot per-trial rates already include parse-retry spend.)

**Cap regime (the M0 lesson, designed not patched):** M0's meter
(`data/pilot/cost_ledger.json`, $0.3269/$0.35) is **frozen as the M0 record** —
`pilot.py` is never used for new spend. `m1.py` runs its own meter on
**`data/m1/cost_ledger.json`**, cap = the D7 amount, same check-before-call halt
semantics. Every wave prints: wave cost, M1 total, and **lifetime total** (sum of
milestone ledgers); a pre-committed **lifetime guard** halts any wave whose projection
would cross **$5.00** and reports to Kyle. Per-milestone ledgers, one lifetime
invariant.

- **D7 decides the M1 cap.** Recommendation: **$1.00** (≈1.35× the measured-rate
  estimate; M0 precedent shows a cap raise is one ask away if a halt is a false alarm).
  Lifetime after M1 ≤ $1.33 vs the $5 target, with M0's re-projection putting M2–M4 at
  ≈ $0.7 unpadded.

## Deviations delta (M1-specific; M0-BRIEF's table still applies)

| # | Deviation | Why | Mitigation |
|---|---|---|---|
| 7 | No awareness probe / no McNemar in RQ1's analog | M0 measured a tier-level null under two wordings | The null is reported as a first-class finding; M1 claims only the behavioral drop |
| 8 | Roster = 2 models (paper: 5) | Pilot kill/swap triggers + disposition | KICKOFF minimum (≥2) met; per-model verdicts, never pooled |
| 9 | T2 wrong locations harness-picked (v2), generator writes the rationale | Measured: free-choice generator finds the real bug (25% acceptance vs v2's 100%) | Mirrors the paper's *deliberately* misdirected human T2s; verifier unchanged, enforced per draft |

## Decisions — pick or veto (recommendation marked)

- **D5 · Instruction uniformity:** **A. Regenerate the 7 v1-organic T2s as v2
  (Recommended, ~$0.007)** — one protocol bank-wide, no provenance caveat. B. Keep the
  mixed 7 v1 + 13 v2.
- **D6 · Bank K:** **A. 150 (Recommended)** — the pre-committed formula; extension
  checkpoint covers the funnel risk. B. 186 (full bank, +$0.19, modest extra slack).
- **D7 · M1 hard cap:** **A. $1.00 (Recommended)** · B. $1.25 · C. $1.50. (If D6=B,
  add ~$0.20 to the chosen cap.)
- **Execution gate:** sign-off authorizes, in order: free build + dry-run → generation
  wave (auto smoke-gated) → repair waves (auto smoke-gated, T3→T2→T1 per model) →
  verdict + report, all within the D7 cap and the halt triggers above, no further
  pauses unless a trigger fires.

**SIGN-OFF (Kyle, 2026-07-10, via decision prompt):** D5-A · D6-A · D7-A · execution
gate approved (full auto within the $1.00 cap and the pre-committed halt triggers).

## What M1 hands forward

- **M2 brief:** failed-T3 subsets + measured pass rates → 5-pass self-repair protocol
  (KICKOFF, unchanged by the re-scope).
- **M3 brief:** confirmed-damage subsets; owes the **diff-anchor-after-code-drift**
  verifier design (KICKOFF open question, standing).
- **M4:** inherits M3's corrupted finals; gates on the unpaired Newcombe M4-vs-M2 gap.

---

## RESULTS (2026-07-11, `m1.py verdict` over data/m1/trials.jsonl; machine copy data/m1_results.json)

Executed under the 2026-07-10 sign-off: generation wave 2026-07-10 ($0.143,
300/300 finals frozen, all T2 protocol v2), deepseek repair wave 2026-07-10,
qwen repair wave 2026-07-11. 900/900 trials (2 models × 3 arms × K=150), every
parsed patch graded S-exact in the Docker sandbox before verdict. All arm parse
rates cleared the 80% floor (deepseek 149/150 in each arm; qwen T3 128, T2 137,
T1 144 of 150 first-parse).

### Primary endpoint — paired T2-vs-T3 pass-rate drop (Newcombe, φ̂-corrected)

| Model | drop d | 95% CI | pairs | label |
|---|---|---|---|---|
| deepseek-chat-v3.1 | +0.0400 | [−0.0218, +0.1029] | 150 | **NULL** |
| qwen3-coder-30b | +0.0362 | [−0.0343, +0.1062] | 138 | **NULL** |

Both CIs cross zero; neither meets the d≥0.10 + lo>0 REPRODUCED bar. Direction is
consistent (wrong-location instruction sits slightly below no-instruction in both
models) but the tier-level effect is indistinguishable from noise at N=150.

### Arms (pass / valid, Wilson 95%)

| Model | T1 (correct instr) | T2 (wrong-location) | T3 (no instr) |
|---|---|---|---|
| deepseek | 141/150 = 94.0% [89.0, 96.8] | 121/150 = 80.7% [73.6, 86.2] | 127/150 = 84.7% [78.0, 89.6] |
| qwen | 114/146 = 78.1% [70.7, 84.0] | 87/146 = 59.6% [51.5, 67.2] | 91/140 = 65.0% [56.8, 72.4] |

Structure: the T1 lift over T3 is real in both models (deepseek +9.3 pts, qwen
+13.1 pts) — instructions steer these models. The wrong-location instruction is
**obeyed** at high rates (comply: deepseek 129/150, qwen 127/146) yet does not
produce the paper's net repair collapse: the tier-level story is
**obedience without net damage** — models patch the named wrong location and
still often fix the real bug anyway.

### Damage + funnel checkpoints (pre-committed at M1 close)

| Model | T2 damaged (rate, Wilson) | M3 entry (≥20) | failed-T3 | M2 entry (≥20) |
|---|---|---|---|---|
| deepseek | 18/150 = 12.0% [7.7, 18.2] | **EXTEND** | 23 | OK |
| qwen | 35/146 = 24.0% [17.8, 31.5] | **OK** | 49 | OK |

- Damage is real at trial level in both models even though the primary is NULL —
  the M3 ghost-error chain has raw material.
- **deepseek extension owed (pre-committed, executes pre-M3):** T2-only along the
  frozen order `bank[150:186]` then pool-smoke, v2 instructions generated as
  problems enter; extension trials feed M3 entry only, the M1 primary stays frozen
  at `bank[0:150]`. Needs ≥2 more damaged; at the measured 12.0% rate, 36 bank
  problems expect ~4.3 (P(≥2) ≈ 0.93). Machinery is a small `m1.py` addition owed
  in the M3 brief.
- Pilot-vs-measured damage: deepseek 16.7% (2/12) → 12.0%; qwen 50% (6/12) → 24.0%.
  The qwen pilot overestimated ~2× — noted for future sizing from N=12 pilots.

### Incidents (zero trial loss)

1. Deepseek T3 trial 36: ~5.5-min silent provider call diagnosed live; the call
   completed during shutdown — provider tail latency, not a hang. Established the
   420 s write-age kill+resume rule.
2. Deepseek T2 trial 14: wave crashed on an OpenRouter malformed-body
   `json.JSONDecodeError`; added to `client.chat`'s transient retry tuple
   (tested, committed), resumed with no loss.

### Cost record

| Ledger | spent | cap |
|---|---|---|
| M1 meter (data/m1/cost_ledger.json) | **$0.5840** (1,227 calls) | $1.00 |
| — generation wave | $0.143 | |
| — deepseek repair wave | ~$0.272 | |
| — qwen repair wave | ~$0.169 | |
| Lifetime (M0 + M1) | **$0.9110** | $5.00 guard |

M2–M4 re-projection from measured M1 rates (5-pass upper bounds): deepseek
$0.07/$0.14/$0.05, qwen $0.10/$0.24/$0.07 — full-chain remainder ≲ $0.67,
lifetime ceiling ≈ $1.58. Budget is not a constraint on the remaining chain.

---

**FINAL M1 VERDICT: NULL × 2 (primary), funnel ALIVE.** The paper's
wrong-location repair drop does not reproduce at tier level on either cheap
model at N=150 — consistent with M0's awareness null, and it is the headline.
The obedience/damage funnel still feeds the chain: M2 entry is met on both
models; M3 entry is met on qwen and one pre-committed extension away on
deepseek. Proceed to the M2 brief (5-pass self-repair on failed-T3 subsets),
with the deepseek T2 extension and the diff-anchor verifier design owed in the
M3 brief.
