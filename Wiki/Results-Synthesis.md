# Results-Synthesis

## Purpose
Answers "what did this repro actually measure, end to end?" for anyone auditing or
citing the project. Collects the headline numbers, pre-registered prediction vs
observed verdict per link, and the cost/scale envelope across all five milestones
into one place — no single source file contains all of it.

## Key understanding

### What the project set out to measure

**Fact** — The project aimed to reproduce the four-link "Obey, Diverge, Collapse"
chain of arXiv 2607.04537 on cheap models under a hobby budget: (1) models are
aware a wrong-location repair instruction is wrong yet follow it anyway (M0/M1);
(2) following it depresses single-pass repair (M1); (3) self-guided iterative
repair compounds ghost errors (M3); (4) corrupted states are irrecoverable (M4).
Source: [`docs/KICKOFF.md`](../docs/KICKOFF.md), [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) preamble.

**Decision** — D1, [`Decisions.md`](../Decisions.md): the full chain was approved under the
honesty contract, <$5 budget, with every verdict rendered by pre-committed gate
scripts.

### The awareness leg: precondition failed before the chain ran

**Fact** — M0 ran a fit-pilot over 6 models × 24 probes under two wording variants.
Result: 0/6 models cleared the T-C awareness trigger (≥8/12 labeled INCORRECT on
T2 instructions). The anchor model, kimi-k2.5 (the paper's own model, which the
paper measured at 63% aware), came in at ~25% under both wordings — ruling out
simple probe under-elicitation. Sources: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "M0 pilot
outcome" + § "Probe-wording audit".

**Inference** — Two readings remain unresolved (see Uncertainties): genuine
tier-level blindness, or methodological gap from the paper's unpublished probe
wording. The briefs deliberately leave them open. **Fact**: the disposition
re-scoped v1 to the obedience/damage chain on the two surviving models —
deepseek-chat-v3.1 and qwen3-coder-30b-a3b-instruct — with the awareness null
reported as a first-class finding. Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "FINAL M0
VERDICT".

**Fact** — M0 total spend: $0.3269 ($0.25 pilot hard cap hit mid-kimi, extended
to $0.35 for the probe audit). Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "FINAL M0
VERDICT".

### M1 — obedience/damage: NULL × 2

**Fact** — Over K=150 paired problems (T2 wrong-location vs T3 no-instruction):

| Model | drop d | 95% CI | verdict |
|---|---|---|---|
| deepseek-chat-v3.1 | +0.0400 | [−0.0218, +0.1029] | NULL |
| qwen3-coder-30b | +0.0362 | [−0.0343, +0.1062] | NULL |

Both CIs straddle zero; neither model meets the pre-committed bar
(CI excludes 0 **and** point drop ≥10 pts). Source: [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) RESULTS.

**Fact** — Obedience itself was high: deepseek 129/150 region-comply, qwen
127/146. The mechanism is "obedience without net damage" — models patch the
instructed wrong location and still often fix the real bug. Source:
[`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) RESULTS § "Arms".

**Fact** — M1 spend: $0.5840 (900 trials, generation wave included).

### M2 — recovery ceiling: REPORTED × 2 (anchor alive)

**Fact** — Self-guided 5-pass repair from the clean buggy start on the failed-T3
subset:

| Model | ceiling | Wilson 95% | curve (cum by pass) |
|---|---|---|---|
| deepseek | 18/23 = **78.3%** | [58.1, 90.3] | [14, 17, 18, 18, 18] |
| qwen | 20/38 = **52.6%** | [37.3, 67.5] | [14, 16, 18, 20, 20] |

Both front-loaded at pass 1 (14/18 and 14/20 of all recovery). Neither
model hit the FLOOR flag (Wilson lower > 0.05), so the M4 directional gate
had room. Source: [`docs/M2-BRIEF.md`](../docs/M2-BRIEF.md) RESULTS.

**Fact** — M2 spend: $0.1874. Early stops accounted for 54% under the
no-early-stop bound.

### M3 — ghost-error compounding: REPORTED (qwen) / UNDERPOWERED (deepseek, pre-declared)

**Fact** — 5-pass iterative repair with a fresh verified wrong-location instruction
each pass, on the T2-damaged subset:

| Model | escape | Wilson 95% | curve (cum) | clean N | label |
|---|---|---|---|---|---|
| deepseek | 10/12 = 83.3% | [55.2, 95.3] | [7,8,9,9,10] | 12 | UNDERPOWERED |
| qwen | 7/23 = **30.4%** | [15.6, 50.9] | **[7,7,7,7,7]** | 23 | REPORTED |

**Fact** — In the powered qwen cell: all 7 escapes happen at pass 1; passes 2–5
produce zero additional escapes. Final-below-baseline 15/23 = 65.2% vs M2's
no-instruction base rate 31.6% — Newcombe delta +33.6 pts, 95% CI [+7.8, +53.9]
(descriptive; start states differ). Source: [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) RESULTS.

**Fact** — deepseek's cell starved because its corruption mode is wholesale
rewriting: 7/21 INVALIDs were anchor-unresolvable (the diff-anchor design's honest
degradation when the model rewrites the whole file, making no provably-wrong target
constructible). Source: [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) RESULTS § "INVALID taxonomy".

**Fact** — M3 spend: $0.2549 (33% of the no-escape upper bound; early escapes and
INVALID-terminal loops reduced actual spend).

### M4 — irrecoverability: UNDERPOWERED × 2 (pre-declared), descriptive IDR delivered

**Fact** — M3 left 2 deepseek / 16 qwen clean non-escaped finals — both < 20,
triggering the pre-declared UNDERPOWERED chain-gate disposition at M3 close.
**Decision** — D3, [`Decisions.md`](../Decisions.md): M4 ran descriptively to complete the
four-script chain.

**Fact** — Irrecoverable Damage Rate (IDR), paper-verbatim definition: never
re-crosses the buggy-patch baseline within 5 passes:

| Model | IDR | Wilson 95% | re-cross curve | label |
|---|---|---|---|---|
| deepseek | 0/1 | [0, 79.4] | [1,1,1,1,1] | UNDERPOWERED |
| qwen | **6/12 = 50%** | [25.4, 74.6] | [2,3,4,6,6] | UNDERPOWERED |

**Fact** — In the qwen cell: the stuck half (6/12) never improves at all (four
loops show no test improvement across five feedback passes); the recovering half
re-crosses durably (zero transient re-crosses; unlike M2's pass-1 front-load, M4
re-crosses accrue through pass 4 — iteration depth does real work from corrupted
starts). Source: [`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) RESULTS.

**Fact** — One trigger fired: qwen first-parse 68.9% < 80% floor (all misses
`finish_reason=length` — response length scales with corruption depth; Kyle
disposed it mid-wave as finish-under-frozen-protocol, breach reported not
re-halted). Source: [`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) RESULTS, recorded in `m4.py`.

**Fact** — M4 spend: $0.0711. Lifetime total: **$1.4244** of the $5.00 guard.

### Full chain verdict and cost envelope

**Fact** — Chain verdict (from [`CLAUDE.md`](../CLAUDE.md), [`PROJECT.md`](../PROJECT.md)):

> obey M1 NULL×2 → recover M2 REPORTED×2 (ceiling 78%/53%) → compound M3
> REPORTED-qwen (pass-1-only escape, damage 2× base) / UNDERPOWERED-deepseek →
> irrecoverable M4 UNDERPOWERED×2 (descriptive 50% stuck-half)

**Fact** — Spend by milestone:

| Milestone | Spend | Notes |
|---|---|---|
| M0 | $0.3269 | $0.25 cap hit; extended to $0.35 for probe audit |
| M1 | $0.5840 | 900 trials + generation wave |
| M2 | $0.1874 | Early stops: 54% of upper bound |
| M3 | $0.2549 | 33% of upper bound |
| M4 | $0.0711 | 90% of upper bound (parse retries ate early-stop savings) |
| **Lifetime** | **$1.4244** | Against $5.00 guard; 2 models, 4 chain links |

**Inference** — What $1.42 on two cheap models bought: the full M1–M4 chain verdict
on 150–186 problems per model, 900+ trials, all four milestone gate scripts dry-run
before paid data. What it could not buy: statistical power at M3/M4 (both cells
UNDERPOWERED, pre-declared from funnel math); a second probe wording that reproduces
the paper's 63% awareness on kimi; evidence about frontier models or the paper's
exact prompt wording (both unpublished).

## Sources

- [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) — M0 pilot table, probe audit, spend, funnel pre-declaration
- [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) — primary endpoint, arms table, damage rates, M1 spend
- [`docs/M2-BRIEF.md`](../docs/M2-BRIEF.md) — recovery ceiling, curves, self-damage base rates, M2 spend
- [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) — escape curves, compounding trajectory, INVALID taxonomy, M3 spend
- [`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) — IDR table, per-loop structure, trigger fired, M4 spend
- [`CLAUDE.md`](../CLAUDE.md) — chain verdict summary, lifetime spend
- [`PROJECT.md`](../PROJECT.md) — current status
- [`Decisions.md`](../Decisions.md) — D1 (scope), D3 (M4 descriptive run)

## Uncertainties & contradictions

**Unresolved** — Why cheap models show near-chance awareness vs the paper's 63%
(kimi-k2.5): the briefs list two non-separable explanations: (a) genuine tier-level
blindness, (b) methodology gap from the paper's unpublished probe wording and/or
provider-side configuration differences. The M0 probe audit rules out simple
under-elicitation but cannot separate the residual. See
[`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Probe-wording audit".

**Unresolved** — M3/M4 UNDERPOWERED: the funnel starved on a structural constraint
(fast escape + high INVALID rate), not a budget one. Running more bank problems
would not resolve this without either a different subject model or a looser
verifier. Noted in [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) RESULTS § "The funnel consequence M4
inherits".

## Related pages

- [Methodology-Guardrails](Methodology-Guardrails.md)

## Relevance to current work

The project is closed (v1 complete 2026-07-14). A future reader comes here to
understand what the chain measured without reading five briefs sequentially — useful
for citing specific headline numbers, understanding what the $1.42 budget can and
cannot support as evidence, or deciding whether to revive the parked cure arm
(see D5, [`Decisions.md`](../Decisions.md)).

_Last reviewed: 2026-07-26_
