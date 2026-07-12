# M3 Start-of-Stage Brief — ghost-error compounding (RQ3 analog)

*Written 2026-07-11 · status: **SIGNED OFF 2026-07-11 (Kyle, via decision prompt):
D10-A ($1.00 cap), execution gate approved — free build + dry-run, then extension →
entry freeze → deepseek → qwen loop waves end-to-end within cap and halt triggers,
no further pauses unless a trigger fires** · scope source: `docs/KICKOFF.md` M3 ("confirmed-damage
subset → 5 passes of live-generated, per-pass-verified wrong instructions; escape-rate
curve (descriptive); hands corrupted states to M4") + the paper-protocol notes in
`docs/M0-BRIEF.md` ("What the paper settles", item 5) · entry data: `docs/M1-BRIEF.md`
RESULTS (T2-damaged funnel + the standing extension pre-commitment) · base rates +
loop machinery: `docs/M2-BRIEF.md` RESULTS*

## What M3 is, in plain terms

M2 measured what self-repair achieves when the only voice in the room is a failing
test. M3 adds the saboteur back: per problem the model already damaged under a single
wrong instruction (M1's T2-damaged subset), it now runs up to **5 more repair passes,
each carrying a fresh, live-generated, mechanically-verified wrong-location
instruction** — while still seeing the most recent failing test. Paper protocol
(M0-BRIEF item 5): per pass, an LLM generator drafts the incorrect instruction from
**only the current code state — no tests, no problem statement** (a reviewer who reads
structure but can't execute); the subject sees **problem statement + current code +
most recent failing test + the instruction**. The named deliverable is the
**escape-rate curve** — how often the model passes all tests *despite* the sabotage —
plus the damage trajectory, and the final corrupted states hand M4 its start line.

**What M3 is not:** it renders **no REPRODUCED/PARTIAL/NULL verdict of its own** — the
KICKOFF's chain gate is M4-vs-M2; M3's labels are **REPORTED** or **UNDERPOWERED**
(auto at clean-N < 20), and its curve is descriptive by pre-commitment ("escape-rate
flatness descriptive"). It is also not a re-run of M1: M1's T2 was single-pass and
feedback-free; M3 is iterative and the wrong instruction must fight a visible failing
test every pass — the configuration M2 proved potent (feedback recovers 78%/53%
front-loaded at pass 1).

## Owed item 1 — the deepseek T2-only extension (pre-committed at M1 close, runs first)

M1 froze the rule; this brief supplies the machinery. deepseek's M3 entry is 18 < 20
damaged, so **before any M3 loop**, a T2-only extension runs along the frozen order
`bank[150:186]` (36 problems; the bank is already frozen at 186 with tests + baselines,
so no new smoke is needed):

- **Per problem, in frozen order:** generate a protocol-v2 T2 instruction
  (`pilot._gen_one` verbatim: harness-picked disjoint target seeded `2607:{pid}`,
  gpt-5.1-codex-mini writes the rationale, 3-attempt verifier rule; unconstructable /
  thrice-rejected → INVALID-instruction, skipped, counted) → run **one** deepseek T2
  repair trial (`pilot._repair_trial` verbatim — M1's exact prompt, budget, parse
  rules; **no feedback**, it's an M1-protocol trial) → grade S-exact, set
  damaged/comply.
- **All 36 run** (no stop-at-target): ~$0.02 buys a cleaner extension damage-rate
  report, maximum entry-N, and no stopping-rule caveat.
- **Bookkeeping:** results go to `data/m3/extension_instructions.json` +
  `data/m3/extension_trials.jsonl` (same record schema as M1), metered on **M3's
  ledger**. M1's files, meter, and primary stay frozen at `bank[0:150]` — extension
  trials feed **M3 entry only**, and the extension damage rate is reported separately,
  never pooled into M1's 12.0%. (The M1 brief guessed "a small `m1.py` addition"; the
  machinery lands in `m3.py extend` instead because the spend, artifacts, and purpose
  are all M3's — it still imports M1's paths verbatim, so the protocol cannot drift.)
- **Gates:** gen smoke @10 drafts (`gen_gate`: first-attempt acceptance ≥ 7/10, mean ≤
  2× $0.00095) · repair smoke @5 trials (`arm_gate` vs the measured deepseek-T2
  $0.00050) · parse floor ≥ 80% on the completed extension arm.
- **Yield math (M1-BRIEF, unchanged):** needs ≥2 more damaged; at the measured 12.0%
  rate, 36 problems expect ~4.3, P(≥2) ≈ 0.93. **Fallback (pre-committed):** if the
  extension lands <2 new damaged, extend the bank itself — re-run the free stage-2
  smoke (`m0.py smoke`) deeper into the frozen pool (deterministic filter: the
  186-prefix reproduces, survivors append; prefix discipline holds) in rounds of ~36
  bank problems, gen+trial each round, **max 3 rounds**; still <20 total (or pool
  exhausted) → deepseek's M3/M4 cells **auto-report UNDERPOWERED** (M0's standing
  rule), the wave still runs on what exists, and no rescue is attempted.

## Owed item 2 — the diff-anchor-after-code-drift verifier (KICKOFF open question, resolved here)

The M1 verifier's "wrong location" guarantee is *target region ±1 provably disjoint
from the true-fix region F*, where F lives in **original buggy-code line coordinates**.
By M3 pass k the current code has drifted (it starts damaged and mutates every pass),
so F must be re-anchored before disjointness means anything. Design, in
`regions.map_fix_region(buggy, current, fix_region) -> set[int]` (pure, TDD):

- Diff `buggy → current` with the **same mechanics as `true_fix_region`**
  (`difflib.SequenceMatcher` over rstrip-normalized lines, autojunk off) and map F
  through the opcodes, **conservatively over-approximating** the image F′:
  - `equal` blocks: F-lines map by offset (line matching — the KICKOFF's sketch);
  - `replace` blocks touching F: the **entire** replacement span joins F′;
  - `delete` blocks touching F: the adjacent current-line pair joins F′ (mirrors
    `true_fix_region`'s insertion convention);
  - `insert` blocks adjacent to an F-line: the inserted span joins F′.
- **Why over-approximation is the honest direction:** a target disjoint from a
  too-big F′ is *a fortiori* disjoint from every surviving trace of the true-fix
  region — the wrongness guarantee never weakens; the only cost is more INVALIDs,
  which are counted and reported. Heavy drift degrades gracefully: a wholesale rewrite
  becomes one giant `replace`, F′ swallows the file, no eligible target survives.
- **Per pass k:** F′ = `map_fix_region(buggy, current)`; target =
  `pick_wrong_target(current, F′, seed "2607:{pid}#p{k}")` (per-pass seed suffix — a
  fresh review each pass, not a stuck record; deterministic, so resume rebuilds
  identical prompts); draft via `t2_generator_prompt_v2(current, *target)`; verified by
  `verify_draft(d, current, F′, fix_added_lines(buggy, fixed), kind="T2")` — anchor
  must match the **current** code, disjointness reads against **F′**, and the no-leak
  needles stay the **original** fix's added lines (the fix doesn't drift).
- **Unresolvable anchor = INVALID (KICKOFF verbatim):** `pick_wrong_target → None`
  (no eligible line outside F′±1, or F′ mapped empty) ends the loop as INVALID at
  pass k, cause `anchor-unresolvable`, excluded from every denominator, counted.
- **Honest limit, stated up front:** the verifier proves the instruction points away
  from (and never quotes) the *original* fix region as mapped forward. It cannot prove
  disjointness from *ghost errors introduced mid-loop* — no oracle knows where those
  live; the paper's free generator has the same exposure, unverified. Our claim is
  scoped accordingly.

## Entry subsets (frozen before any M3 loop; the extension feeds one of them)

Rule: a problem enters model M's subset iff its M1 T2 trial was **graded, valid, and
damaged** (`failed(patch) > buggy_failed_baseline` — the paper's confirmed-damage
condition), plus, for deepseek, extension trials under the identical rule. Frozen to
`data/m3/subsets.json` in bank order with start-state provenance
(`m1` / `extension`), asserted counts, committed before the first loop.

| Model | M3 entry | source | N ≥ 20? |
|---|---|---|---|
| deepseek-chat-v3.1 | **18 + E** (E = extension damaged, expect ~4) | M1 T2-damaged + extension | at E≥2 |
| qwen3-coder-30b | **35** | M1 T2-damaged | yes, slack 15 |

**INVALID-slack arithmetic, pre-declared:** clean-N < 20 → auto-UNDERPOWERED, no
rescue. qwen's slack of 15 absorbs up to 42.9% loop-INVALID — M2 measured 22.4%
(11/49) on this model's loops with **no format revisions left**, and M3 adds two new
INVALID causes (draft-rejected, anchor-unresolvable), so the slack is real but not
extravagant; expect ~8–10 consumed. deepseek at E=2 has **zero slack** (any INVALID
loop → UNDERPOWERED); at the expected E≈4, slack 2. M2 precedent says deepseek runs
clean (0 INVALID loops, parse 91.7%), but the rule stands whatever happens.

## Protocol — the loop (paper's RQ3, M0-BRIEF item 5)

**Start state (pass-1 current code) = the model's own damaged T2 patch** (from M1, or
from the extension for deepseek's E problems) — *not* the buggy original. That is the
paper's RQ3 entry ("T2 trials where the model produced incorrect code and failed-test
count exceeded the buggy baseline"); M3 continues the corruption story from where T2
left it. The loop is `m2.py`'s, start-state-parameterized as designed, plus the
generator stage:

- **Grade-0 (free, before pass 1):** the start-state patch is re-graded in the
  sandbox. Pre-committed integrity halt: its failed count must equal the M1/extension
  trial's recorded `graded.failed` **exactly** (harness drift), **and** must exceed
  the bank baseline (entry condition mechanically re-verified). `start_failed` is
  recorded — the damage trajectory reads against it.
- **Per pass k = 1..5:**
  1. **Generate (paid, gpt-5.1-codex-mini):** F′ → target → draft → verify, per Owed
     item 2; up to 3 attempts (M1 rule). All rejected → loop INVALID
     (`draft-rejected`), terminal. The generator sees only the numbered current code
     + its assigned target lines — v2 template verbatim, no statement, no tests
     (paper-faithful; pinned since M0 in `prompts.py`).
  2. **Repair (paid, subject):** prompt = **M3_REPAIR_TEMPLATE** (below). Call/parse
     contract verbatim from M0/M1/M2: reasoning off, `REPAIR_MAX_TOKENS = 3200`, last
     fenced block, `compile()`-clean, one bare retry then the loop is INVALID
     (`parse-failure`), terminal — scoring a format failure as "still corrupted"
     would fake compounding; the honesty contract forbids it.
  3. **Grade (free, local):** full frozen test set, S-exact. `failed == 0` →
     **escaped at pass k** (early stop — an all-tests-passing program has nothing
     left to corrupt; stored in the shared `recovered` field, reported as escape).
     Else current code := the patch, next pass.
- **Feedback block:** D8-A carried verbatim from M2 (first failing test in frozen
  order from the current state's grade, input + expected + actual with status
  markers, 1,000-char truncation, render-time failing-consistency assert, stored
  verbatim per pass). M4 will run M2's loop on M3's finals, so the chain keeps one
  feedback rendering throughout.
- **Per-pass extras recorded:** the accepted draft + render + target + F′ + gen cost
  + attempts; `comply` = `region_compliance(current, patch, target)` (obedience under
  drift, computed live); `drift_ratio` = SequenceMatcher ratio buggy→current (free,
  the anchor-health curve); finish_reason, response_chars, first_parse.
- **Per-trial mechanical checks (M3's manipulation verification):** every pass's
  instruction re-verifies against the stored current code (anchor match, F′
  disjointness, no-leak) at write time; grade-0 reproduces the recorded entry state;
  every loop's problem is in the frozen subset. Asserted in code, not eyeballed.
- Records append-only to `data/m3/trials.jsonl` keyed `(model, problem_id, pass)`,
  pass 0 = grade-0; resume reconstructs loop state (`m2.loop_state` reused — the
  caller substitutes the frozen start patch where M2 substituted `buggy_code`) and
  never re-spends.

**M3_REPAIR_TEMPLATE** (to be frozen in `prompts.py` at build, tested): the M2
template with its `# Task / Diagnose the bug on your own and fix it.` block replaced
by M1's instruction block — paper's stated order (statement, code, failing test,
instruction), every retained line verbatim so the parse machinery is untouched:

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

# Reviewer diagnosis
{instruction}

Reply with the complete corrected program in a single ```python code block.
The program must read from stdin and write to stdout exactly as the problem requires.
````

## Endpoints (per model, never pooled; all CIs Wilson 95% unless noted)

- **Primary (descriptive, the KICKOFF's named deliverable): the escape-rate curve** —
  cumulative escaped / clean loops by pass k = 1..5, plus the final escape rate.
  Labels: REPORTED (clean-N ≥ 20) / UNDERPOWERED (auto). Flat-and-low = the paper's
  compounding story; front-loaded-and-high = the anti-story, M1's null propagating.
- **Damage trajectory (the ghost-error read):** per clean loop, `final_failed` vs
  `start_failed` → counts **deepened / held / improved / escaped**; mean failed per
  pass over loops still active at that pass. Compounding = deepened dominating and
  the mean rising.
- **Context vs M2's no-instruction base rates (per the M2 handoff):** M3
  final-below-baseline and ever-below-baseline rates reported side-by-side with M2's
  17.4%/31.6% and 30.4%/47.4% (Newcombe unpaired diff as a descriptive delta).
  **Confound stated up front:** M2 loops started *at* baseline on failed-T3 problems;
  M3 loops start *below* baseline on T2-damaged problems — the delta bundles start
  state with instruction pressure and is context, not a gate.
- **Obedience under iteration (ungated):** per-pass comply rate — does wrong-location
  obedience persist when a failing test contradicts the instruction every pass?
- **Generator/anchor health (ungated):** per-pass first-attempt draft acceptance;
  INVALID loops by cause (parse-failure / draft-rejected / anchor-unresolvable);
  drift_ratio curve; extension damage rate (deepseek).
- **Ops secondaries:** per-pass first-parse, finish_reason counts, meter totals, and
  the **M4 cost re-projection** from measured M3 pass rates.

**Honest expectation, stated before the run:** the deck is stacked *against*
compounding here — M1 measured obedience without net damage on these models, and M2
measured feedback recovering 78%/53% front-loaded at pass 1. If that pattern holds
against live sabotage, escapes come early and high, "deepened" stays near the M2
self-damage base rates, and the compounding claim reads NULL-shaped (descriptively) —
with a real side effect: **every early escape shrinks M4's entry** (M4 starts from
corrupted finals; escaped loops leave none). deepseek's M4 entry could starve outright
(~20 entering, M2-precedent escape ~78%), making **M4-deepseek UNDERPOWERED a live,
pre-declared outcome — and the M3 escape curve itself the chain's headline** in that
branch. qwen (35 entering, weaker recovery, higher INVALID risk) is the likelier
carrier of a usable M4 cell. Neither outcome is a failure of M3: nulls are headlines.

## Waves, machinery, and halt triggers

New flat script **`m3.py`** (subcommands, per conventions), artifacts under
`data/m3/`, run logs committed; imports carried machinery instead of duplicating it
(`pilot._gen_one/_repair_trial/_grade`, `m1.arm_gate/gen_gate/parse_floor_ok/
lifetime_ok/EST_DRAFT_COST`, `m2.loop_state/feedback_fields/detail_from_runs/
truncate_field/actual_output`); `test_m3.py` TDD for all new pure logic
(`map_fix_region` incl. every opcode case + over-approximation properties, per-pass
seeding, entry rules + provenance, INVALID taxonomy, trajectory classification,
escape curve, meter, labels) — tests green + synthetic dry-run **before any paid
call**.

1. **Free:** build + tests green; `m3.py verdict --synthetic` dry-runs REPORTED /
   UNDERPOWERED and every INVALID-cause path on fixtures ("gates as code, dry-run
   before paid").
2. **`m3.py extend`** — the deepseek extension wave (Owed item 1; smoke-gated, its
   own spot-read appended to `docs/M3-SPOTREAD.md`).
3. **Free:** `m3.py subset` freezes `data/m3/subsets.json` (asserts qwen 35, deepseek
   18+E, start-state provenance + grades recorded).
4. **`m3.py run --model <slug>`** — deepseek then qwen (the standing order). Loops in
   frozen subset order; grade-0 integrity halt; ≤5 passes, gen→repair→grade per pass,
   early stop on escape. Resumable via `(model, problem_id, pass)` keys.
   **Smoke gates per model wave:** first 10 draft calls (`gen_gate` ≥7/10 accepted,
   mean ≤ 2× $0.00095 — acceptance on *drifted* code is the new unknown; M1's 100%
   was on pristine code) and first 5 repair calls (`arm_gate` ≥4/5 first-parse, mean
   ≤ 2× the model's M2-measured pass rate). **Generation floor (new, pre-committed):**
   cumulative first-attempt draft acceptance < 60% after ≥20 draft-bearing passes →
   halt to Kyle (3-attempt retries balloon cost ~3× and INVALIDs threaten N; 60% sits
   between T-F's green 70% and kill 40%).
5. **Parse floor per completed model wave:** subject first-parse ≥ 80% over the
   wave's repair calls, else halt — deepseek has one unused format revision, qwen has
   none; prompt semantics are frozen either way.
6. Each model wave appends 5 accepted pass-drafts (varied problems/passes) to
   `docs/M3-SPOTREAD.md` — M1's face-validity semantics: sign-off covers proceeding,
   Kyle's veto before M3 RESULTS close discards affected loops (reported).
7. **Free:** `m3.py verdict` renders curves + trajectory + secondaries + checkpoints
   + M4 re-projection; RESULTS appended here; artifacts + logs committed.

Ops rules carried forward: waves strictly sequential (shared trials.jsonl); Docker up
before wave 2 (grade-0 precedes the first paid loop call); 420 s write-age watchdog
reads row-advance + an ESTABLISHED provider connection before any kill (slow provider
≠ stall; escalate ~900 s), kill+resume never re-spends.

## Cost estimate (measured rates) + cap regime

| Item | Calls (max) | Measured basis | Upper |
|---|---|---|---|
| Extension: 36 drafts + 36 deepseek T2 trials | ~76 | $0.00095/draft ×1.3 retry pad · $0.00050/trial | $0.063 |
| deepseek loops: (18+E→plan 25) × ≤5 passes | ≤125×2 | repair $0.00160/pass (M2 $0.00155 + instr-input bump) + drafts $0.00124 (×1.3 pad) | $0.355 |
| qwen loops: 35 × ≤5 passes | ≤175×2 | repair $0.00082/pass + drafts $0.00124 | $0.361 |
| **M3 upper bound (no early escape, E at Wilson-high)** | | | **≈ $0.78** |

Early escapes only lower real spend (M2 landed at 54% of its bound); the cap is set
off the no-escape bound. Grading is free/local. Per-loop worst case ≈ $0.0142
(deepseek) / $0.0103 (qwen).

**Cap regime (per-milestone ledgers, one lifetime invariant):** M2's meter is frozen
at $0.1874 as the M2 record; `m3.py` runs its own meter on
**`data/m3/cost_ledger.json`** (the extension meters here too — it's M3 spend), cap =
D10, same check-before-call halt semantics. Every wave prints wave cost, M3 total,
and lifetime; the **$5.00 lifetime guard** halts any wave whose projection would
cross it. Lifetime worst case after M3 at the recommended cap: $1.0984 + $1.00 =
**$2.10**, with M4's re-projected remainder ≈ $0.14–0.28.

## Deviations delta (M3-specific; M0 rows 1–6, M1 rows 7–9, M2 row 10 still apply — row 10's feedback rendering recurs per pass here)

| # | Deviation | Why | Mitigation |
|---|---|---|---|
| 11 | Per-pass wrong locations harness-picked (protocol v2) against a **mapped** fix region F′, per-draft verified (paper: the generator LLM free-picks from current code; no verification described) | M0 measured free-choice finding the real bug 75% of the time (T-F); the honesty contract requires per-trial mechanical verification, which needs a definable "wrong" after drift | `map_fix_region` over-approximates (wrongness guarantee never weakens); unresolvable anchor / rejected drafts → INVALID, counted by cause; verifier + no-leak otherwise identical to M1 |
| 12 | Early stop on escape + loop-terminal INVALID taxonomy (paper specifies neither for RQ3) | Protocol symmetry with M2/M4 (one loop, start-state-parameterized); a passing program has nothing left to corrupt; unverifiable manipulation must not score | Escape is the KICKOFF's named endpoint, curve reported per pass; INVALIDs excluded from every denominator, counted, reported |

## Decisions — pick or veto (recommendation marked)

- **D10 · M3 hard cap:** **A. $1.00 (Recommended)** — ≈1.3× the $0.78 no-escape upper
  bound, the M1/M2 cap-ratio precedent; lifetime worst case $2.10 of $5.00.
  · **B. $1.25** — extra slack if extension yield runs high + escapes run low
  (the expensive corner), one fewer potential halt-and-ask.
  · **C. $0.80** — equals the bound; can fire on pure variance (draft retries on
  drifted code are the untested rate).
- **Execution gate:** sign-off authorizes, in order: free build + tests green +
  synthetic dry-run → extension wave (smoke-gated, fallback rules as written) →
  entry freeze (`data/m3/subsets.json`) → deepseek loop wave → qwen loop wave →
  verdict + RESULTS + commit — all within the D10 cap and the halt triggers above
  (gen/repair smoke gates, 60% generation floor, 80% parse floor, grade-0 integrity
  halt, anchor-INVALID accounting, lifetime guard), **no further pauses unless a
  trigger fires**. Sign-off also covers: the start-state pinning (the damaged T2
  patch, not the buggy original), the per-pass fresh-target seeding, the
  all-36 extension scope, the extension living in `m3.py` on M3's ledger, and the
  UNDERPOWERED dispositions exactly as pre-declared.

**SIGN-OFF (Kyle, 2026-07-11, via decision prompt):** D10-A · execution gate approved
(full auto within the $1.00 cap and the pre-committed halt triggers, including the
damaged-T2-patch start-state pinning, per-pass fresh-target seeding, all-36 extension
scope, `m3.py`/M3-ledger placement, and the UNDERPOWERED dispositions as pre-declared).

## What M3 hands forward

- **M4:** the frozen final corrupted states (patch + grade per clean non-escaped
  loop), escape flags, the loop machinery (M4 = M2's protocol from these starts —
  both already parameterized), and the measured-rate M4 re-projection. M4's exact
  entry rule is pinned in the M4 brief; at entry < 20 the standing N-rule
  auto-reports UNDERPOWERED — pre-declared here so a high-escape M3 (the likelier
  branch) arrives with its consequence already owned.
- **The paper-trail:** extension damage rate (deepseek), per-pass generator
  acceptance on drifted code, and the drift_ratio curve — the feasibility record for
  anyone re-running RQ3 with mechanical verification.

---

## RESULTS (2026-07-11, `m3.py verdict` over data/m3/trials.jsonl; machine copy data/m3_results.json)

Executed same-day under the sign-off: free build (32 new tests, 233 total green) +
synthetic dry-run, the extension wave, entry freeze, then the deepseek and qwen loop
waves. **Every pre-committed gate passed; no halt fired.** Extension: 36/36
instructions (gen smoke 10/10 @ $0.00051/draft), 36/36 trials (parse 36/36, comply
33/36), **E = 3 new damaged (8.3% vs M1's 12.0%) → deepseek entry 21, no pool-smoke
fallback needed**. Grade-0 integrity 56/56 — every loop's damaged start state
reproduced its recorded M1/extension grade exactly and re-verified failed > baseline.
One ops incident (qwen wave): a ~18-minute silent call was killed + resumed loss-free
after the >900 s no-advance rule fired; note for the ops file — an ESTABLISHED socket
is weak in-flight evidence, httpx keeps pooled keep-alive connections ESTABLISHED
while idle. The generator held up on drifted code: first-attempt acceptance 34/36
(deepseek wave) and 100/104 (qwen wave) at mean drift 0.21/0.25 — the brief's one
untested rate was fine.

### Primary (descriptive) — the escape-rate curve

| Model | escape | Wilson 95% | curve (cum by pass) | clean N | label |
|---|---|---|---|---|---|
| deepseek-chat-v3.1 | 10/12 = **83.3%** | [55.2, 95.3] | [7, 8, 9, 9, 10] | 12 | **UNDERPOWERED** |
| qwen3-coder-30b | 7/23 = **30.4%** | [15.6, 50.9] | **[7, 7, 7, 7, 7]** | 23 | **REPORTED** |

The powered cell shows the paper's shape: **qwen's escapes are entirely pass-1**
(feedback beats the sabotage immediately or never), and the curve is **flat at zero
for passes 2–5** — 16/23 clean loops stay corrupted through four more verified wrong
instructions. deepseek's cell is UNDERPOWERED (clean 12 < 20, rule stands) but its
direction is the M1-null propagating: among loops that stayed verifiable, it escaped
83% of the time, front-loaded (7/10 at pass 1).

### Ghost-error compounding (qwen, the powered cell)

- **Trajectory (clean loops):** escaped 7 · deepened 3 · held 9 · improved 4 —
  corruption *persists* (12/16 non-escaped end at or above their damaged start).
- **Mean failed by pass (active loops):** 9.4 → 13.3 → 13.9 → 12.6 → 12.3 — damage
  jumps in passes 1–2 and stays pinned high; no recovery drift.
- **Final-below-baseline 15/23 = 65.2% [44.9, 81.2]** vs M2's no-instruction base
  rate 31.6% [19.1, 47.5]: **delta +33.6 pts, Newcombe 95% CI [+7.8, +53.9]** —
  descriptive per the brief (start states differ: M3 starts damaged), but the
  direction is loud. deepseek: 1/12 = 8.3% vs base 17.4% (delta −9.1 pts, CI
  [−30.0, +19.9], no signal — the cell mostly escaped). Ever-below: qwen 16/23 =
  69.6%, deepseek 5/12.
- **Obedience under iteration:** qwen complies with the wrong instruction against a
  contradicting failing test at 25/27 = 93% (pass 1), eroding to 11/16 = 69% (pass
  5) — obedience persists but decays under repeated feedback. deepseek: 60% at pass
  1 (the escaping majority ignores the reviewer), high among the loops that stayed
  damaged.

### INVALID taxonomy — the verifier's dilemma, iterative edition

| Model | INVALID loops | parse | draft-rejected | anchor-unresolvable | first-parse |
|---|---|---|---|---|---|
| deepseek | 9/21 = 42.9% | 2 | 0 | **7** | 31/36 = 86.1% |
| qwen | 12/35 = 34.3% | 5 | 1 | **6** | 93/103 = 90.3% |

The dominant INVALID cause is **anchor-unresolvable — the pre-committed graceful
degradation of the diff-anchor design**: when a model corrupts by *rewriting
wholesale* (drift → 0), F′ swallows the file and no provably-wrong target exists.
deepseek's corruption mode is exactly that (7/9 of its INVALIDs; mean drift 0.21),
which is why its cell starved: **the more destructive the obedience, the less
verifiable the manipulation**. This is the honest cost of per-pass mechanical
verification — the paper's unverified generator has no such attrition (and no such
guarantee). qwen's profile inverts (parse-dominant, 5/12): it corrupts incrementally
(anchors survive) but trips the format contract — its M2 loop-parse fragility
recurring at 34.3% loop-INVALID vs the 15-loop slack; clean-N 23 held.

### Cost record

| Ledger | spent | cap |
|---|---|---|
| M3 meter (data/m3/cost_ledger.json) | **$0.2549** (374 calls) | $1.00 |
| — extension wave | $0.0396 | |
| — deepseek loop wave | $0.0791 | |
| — qwen loop wave | $0.1362 | |
| Lifetime (M0 + M1 + M2 + M3) | **$1.3533** | $5.00 guard |

33% of the $0.78 no-escape bound — early escapes and INVALID-terminal loops did the
work. **M4 re-projection (measured M3 pass rates): deepseek m4_max $0.016 at entry
2, qwen m4_max $0.039 at entry 16.**

### The funnel consequence M4 inherits (pre-declared here)

M4 entry = clean non-escaped finals: **deepseek 2, qwen 16 — both < 20**, so the
KICKOFF's chain gate (M4-vs-M2 recovery, Newcombe) is **pre-declared UNDERPOWERED on
both models** by the standing N-rule; no rescue exists (deepseek's pool could not
supply corrupted finals faster than it escapes, and qwen's attrition is
INVALID-driven). M4 remains nearly free (≈ $0.06 upper) and still delivers the
descriptive Irrecoverable-Damage-Rate read on 18 corrupted states plus the M2
protocol contrast — whether to run it descriptively is the M4 brief's opening
decision.

---

**FINAL M3 VERDICT: REPORTED (qwen) · UNDERPOWERED (deepseek, pre-declared
no-rescue).** On the powered cell, ghost-error compounding is visible and
structured: escape collapses to pass-1-only (30.4%, curve flat at zero after),
final-below-baseline runs double the no-instruction base rate (+33.6 pts, CI
excluding 0, start-confounded), and wrong-location obedience persists at 93→69%
against contradicting tests. On deepseek the M1 null propagates — 83% escape among
verifiable loops — but its wholesale-rewrite corruption mode shreds the diff-anchor
(7/21 unverifiable), starving both its M3 cell and M4's entry. Proceed to the M4
brief (self-repair from corrupted finals) carrying the pre-declared UNDERPOWERED×2
chain-gate disposition and the $0.055 descriptive-run option.
