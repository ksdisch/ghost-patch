# Ghost-Patch — Presenter Pack

*Companion to `docs/paper/ghost-patch-paper.md`. Purpose: make the author fluent enough to defend the paper claim-by-claim, with every number traceable to a repo file live, in front of an audience.*

## The 60-second story

A days-old, unreplicated paper (arXiv 2607.04537) claims code LLMs *know* a repair instruction points at the wrong place, obey it anyway, compound the damage over iterations, and end up unrecoverable. I reproduced the whole four-claim chain on two cheap models for $1.42, with every verdict script written and dry-run **before** the paid data existed. The front of the chain **failed to reproduce, and that's the headline**: cheap models can't classify the instruction as wrong in the first place (0/6 models — including the paper's own Kimi K2.5, which reads ~25% aware here vs its published 63%), and one wrong instruction causes no net single-pass repair drop (NULL on both subjects). The back of the chain is real where I could power it: under five passes of *mechanically verified* sabotage, qwen escapes only at pass 1 (30.4%, flat after), and once the saboteur stops, half its corrupted states (6/12) never re-cross the original buggy baseline — damage stops compounding (0/12 got worse) but doesn't heal. The final recovery-gap gate is UNDERPOWERED ×2 — declared *before* M4 ran, from measured funnel attrition — direction matching the paper, CIs straddling zero, reported exactly as such.

## The chain at a glance

| Link | Verdict | The number I say out loud |
|---|---|---|
| Precondition: "aware" | NULL (tier-level) | 0/6 models clear the probe gate under two wordings |
| M1 obey → damage | NULL ×2 | drops +4.0 pts [−2.2, +10.3] and +3.6 pts [−3.4, +10.6] |
| M2 recovery ceiling | REPORTED ×2 | 78.3% [58.1, 90.3] / 52.6% [37.3, 67.5], pass-1 front-loaded |
| M3 compounding | REPORTED (qwen) / UNDERPOWERED (deepseek) | escape 30.4% [15.6, 50.9], curve [7,7,7,7,7] |
| M4 irrecoverability | UNDERPOWERED ×2 (pre-declared) + descriptive | IDR 6/12 = 50% [25.4, 74.6] |

## Claim-by-claim provenance (trace any number live from these files)

| # | Claim as stated in the paper | Exact number | Source file |
|---|---|---|---|
| 1 | Awareness fails tier-wide; Kimi anchor | probe tables v1/v2, 0/6 clear; Kimi v1 3/9 (t2✓/t1✓, partial wave), v2 3/6 — "flat at ~25%" vs paper's 63% | `docs/M0-BRIEF.md` (pilot + audit tables); `data/pilot_results.json` (v1 probe counts) |
| 2 | Harness fidelity gated, failed once, fixed once | T-E 86.0% → exposure-aware fix → 95.0% (S-exact), 300 smoked | `docs/M0-BRIEF.md` T-E; `data/smoke_results.json` (`fidelity_exact: 0.95`) |
| 3 | Frozen bank / pool | bank 186 (seed 2607, S-exact); pool 1,062 of 11,665 bugs | `data/bank.json`; `data/pool.json` |
| 4 | M1 primary NULL ×2 | +0.0400 [−0.0218, +0.1029] n=150; +0.0362 [−0.0343, +0.1062] n=138 | `data/m1_results.json` (`drop`, `ci`); `docs/M1-BRIEF.md` RESULTS |
| 5 | Obedience without net damage | comply 129/150 (deepseek), 127/146 (qwen); T1 lift +9.3 / +13.1 pts | `data/m1_results.json` (`t2_comply`, arms); `docs/M1-BRIEF.md` |
| 6 | Single-instruction damage rate | 18/150 = 12.0% [7.7, 18.2]; 35/146 = 24.0% [17.8, 31.5] | `data/m1_results.json` (`t2_damaged`); `docs/M1-BRIEF.md` |
| 7 | M2 ceilings + front-load | 18/23 = 78.3% [58.1, 90.3]; 20/38 = 52.6% [37.3, 67.5]; curves [14,17,18,18,18]/[14,16,18,20,20] | `data/m2_results.json`; `docs/M2-BRIEF.md` RESULTS |
| 8 | No-instruction self-damage base rate | 4/23 = 17.4%; 12/38 = 31.6% | `data/m2_results.json` (`damaged_final`); `docs/M2-BRIEF.md` |
| 9 | M3 escape pass-1-only (powered cell) | 7/23 = 30.4% [15.6, 50.9], curve [7,7,7,7,7]; deepseek 10/12 = 83.3% UNDERPOWERED | `data/m3_results.json` (`curve`); `docs/M3-BRIEF.md` RESULTS |
| 10 | Damage ~2× base under sabotage (descriptive) | 15/23 = 65.2% vs 31.6%; Δ +33.6 pts [+7.8, +53.9], start-confounded | `docs/M3-BRIEF.md` RESULTS (ghost-error section) |
| 11 | Verifier's dilemma attrition | deepseek 9/21 INVALID (7 anchor-unresolvable); qwen 12/35 (parse-dominant) | `data/m3_results.json` (`invalid_by_cause`); `docs/M3-BRIEF.md` |
| 12 | M4 entry starved → gate pre-declared | entry 2 / 16, both < 20 | `docs/M3-BRIEF.md` ("The funnel consequence"); `data/m3_results.json` (`m4_entry`) |
| 13 | IDR: the 50% stuck-half | 6/12 = 50.0% [25.4, 74.6]; re-cross curve [2,3,4,6,6]; deepened 0/12; 4 loops best==start; all 6 re-crosses durable | `data/m4_results.json` (`idr`, `trajectory`, `per_loop`); `docs/M4-BRIEF.md` RESULTS |
| 14 | Chain gate direction w/o claim | M2−M4: +28.3 pts [−17.0, +70.6]; +19.3 pts [−12.3, +43.9] | `data/m4_results.json` (`chain_gate`); `docs/M4-BRIEF.md` |
| 15 | Parse-floor breach + live disposition | 42/61 = 68.9% < 80%; all misses `finish_reason=length`; 4 INVALID loops | `data/m4_results.json`; `docs/M4-BRIEF.md`; comments in `m4.py` |
| 16 | Total spend | $1.4244 lifetime (0.3269/0.5840/0.1874/0.2549/0.0711) | `data/m4_results.json` (`cost.lifetime`); per-brief cost tables |

## Anticipated questions, with the answers I'd give

**Q: You manufactured the corruption. Why is that legitimate?**
Because the phenomenon under test *is* the response to injected wrong instructions — the paper manufactures its gaps too (human-written misdirection in RQ1, an LLM generator in RQ3). The difference is disclosure and proof: every one of my instructions is labeled manufactured and passes a mechanical verifier (anchor matches the code; target region ±1 line provably disjoint from the diff-computed true-fix region; no fix content leaked). Unverifiable = INVALID, excluded, counted, reported. The paper's generator runs unverified.

**Q: Why is a null a result and not a failed project?**
The gates were code before the data existed, so a null is the machine saying "the effect isn't there at this tier," not me rationalizing after the fact. And these nulls are decision-relevant: the paper's premise assumes a competence floor (evaluator-role awareness) that six cheap models — including the paper's own Kimi — don't clear. Anyone porting "LLMs obey wrong instructions into collapse" to cheap models needs exactly this null.

**Q: Why Wilson intervals?**
Every gated quantity is a proportion, and our cells live at the edges (0/1, 6/12, 18/23). Mean±sd can produce intervals outside [0,1]; Wilson never does, behaves at k=0 and k=n, and at n=20 honestly reads "consistent with ~0%," never "proved 0%." Differences use Newcombe (square-and-add on the Wilson bounds; the paired 1998 variant with φ̂ for M1) so small-n edge behavior carries into the deltas. It's in `stats.py`, unit-tested, no external dependencies.

**Q: What's the un-validatable residual?**
Three things I can name precisely. (1) Mid-loop ghost errors: the verifier proves disjointness from the *original* fix region mapped forward through drift — no oracle exists for errors introduced during the loop (the paper has the same exposure, unverified). (2) The Kimi awareness gap: I can't separate instruction hardness (mine are LLM-drafted) from probe wording from provider config at hobby scale — I report the candidates and don't adjudicate. (3) The M4-vs-M2 contrast bundles funnel selection with corruption; it's context, never a gate.

**Q: Why these two models?**
Pre-committed pilot triggers picked them, not preference: six cheap models entered M0; four died on the awareness/capability kill rules; Kyle's signed disposition kept the two most capable (recovery measurement rides on repair ability). qwen3-coder-30b is a cheap kin of a paper-roster family; deepseek is the lineage's proven subject; kimi-k2.5 — the paper's exact model — was benched by the same triggers and served as the calibration anchor.

**Q: The +33.6-point damage delta excludes zero — why don't you call it a win?**
Because the comparison was pre-committed as descriptive: M2's loops start *at* baseline on failed-T3 problems, M3's start *below* baseline on damaged-T2 problems, so the delta bundles start state with instruction pressure. Direction is loud (double the base rate); the controlled claim is not available in this design, so I don't make it.

**Q: The gate is UNDERPOWERED — why not just collect more N?**
Entry can't be sampled; it's *produced* by the funnel (damaged → non-escaped → verifiable). deepseek escapes faster than it damages, and its wholesale-rewrite corruption shreds the diff anchor (the verifier's dilemma) — 7/9 of its INVALIDs are anchor-unresolvable. Manufacturing more entry would mean weakening verification or carving populations; the pre-committed rule (N<20 → auto-UNDERPOWERED, no rescue) exists precisely to forbid that.

**Q: What would you do next?**
The gated cure arm the paper never tests: put the failing-test evidence or an explicit refusal license into the T2 prompt and measure whether obedience and stuckness collapse. M4 is already its natural control (it measures what merely *stopping* the saboteur buys: half the states stay stuck). Roads deliberately not taken: reasoning ablations, frontier subjects, LLM judges — all out of scope by contract.

## Vocabulary crib

- **Ghost errors** — new faults introduced by patching the wrong location; measured as failed-test count above the buggy baseline.
- **IDR** — Irrecoverable Damage Rate: fraction of corrupted states never re-crossing the buggy baseline within 5 passes (paper-verbatim definition).
- **Escape** — passing all tests *despite* an active saboteur (M3's endpoint).
- **Damage headroom** — bank rule: the buggy program must pass ≥1 test, else "worse than baseline" is inexpressible.
- **Frozen prefix** — the seed-2607 pool order; the bank is a prefix of it; growth only extends, never re-picks.
- **T-E fidelity gate** — free pre-paid smoke: fixed passes all / buggy fails ≥1 on ≥90% of problems (final: 95.0% S-exact).
- **Region-compliance** — mechanical obedience check: the patch's diff touches the instructed region ±1 line.
- **Verifier's dilemma** — the better/more destructive the model, the less verifiable the manipulation (free generators find the real bug; wholesale rewrites kill the anchor).
- **Grade-0 integrity** — every loop's start state must reproduce its recorded grade exactly before any paid pass (72/72, 56/56, 18/18 across M2–M4).
- **UNDERPOWERED** — auto-label for any gated cell under 20 clean trials; pre-committed, no rescue, reported as the verdict.
