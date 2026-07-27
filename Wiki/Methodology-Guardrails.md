# Methodology-Guardrails

## Purpose
Answers "how did this project ensure its numbers are honest?" for a reviewer or
future arm-builder. The honesty machinery is scattered across five milestone briefs,
KICKOFF, and Decisions.md; no single file assembles it. This page synthesizes the
pre-registration contract, statistical choices, UNDERPOWERED/null rules, and the
key deviation table into one place.

## Key understanding

### The honesty contract (pre-committed before any paid call)

**Fact** — The project operates under an explicit honesty contract stated in
[`docs/KICKOFF.md`](../docs/KICKOFF.md) and carried verbatim into [`CLAUDE.md`](../CLAUDE.md):

> Reproduce-and-measure, never invent; deterministic judge-free grading; per-trial
> mechanical verification of the manufactured fault; pre-committed gates as code,
> dry-run before paid runs; nulls are headlines; direction + structure, never point
> estimates; N≥20 clean trials per gated cell or the gate auto-reports UNDERPOWERED;
> the paper's code (if a v2 ships it) is reference-only, never imported.

**Inference** — The contract is load-bearing, not decorative: every gate in the
five milestone briefs traces to a specific clause of it. The two observable
consequences are (1) a null verdict at M1 became the headline rather than a
rescue attempt, and (2) M3/M4's UNDERPOWERED disposition was pre-declared at M3
close rather than discovered post-hoc.

### Pre-registration: gates written as code before paid data ran

**Fact** — Every milestone produced a `mN.py --synthetic` dry-run (all verdict
paths exercised on fixtures) before any paid call. The "gates as code, dry-run
before paid" pattern is listed as a pre-commitment in each brief's Waves section.
Sources: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "M0 task list", [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Waves",
[`docs/M2-BRIEF.md`](../docs/M2-BRIEF.md) § "Waves", [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) § "Waves",
[`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) § "Waves".

**Fact** — Trigger thresholds (T-A through T-G at M0; the primary endpoint condition
at M1; the FLOOR rule at M2; the UNDERPOWERED auto-rule everywhere) were all
published in the brief before the relevant wave ran. None were adjusted
post-observation. Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Pre-committed kill/swap
triggers"; [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Primary endpoint".

### Seed and bank discipline: frozen pool, prefix growth only

**Fact** — The problem bank is drawn from a frozen pool ordered by seed 2607.
The bank is always a prefix of that pool; any expansion extends the prefix and
never re-picks problems. Sources: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Pre-committed bank
filter" ("frozen pool / bank prefix" definition); **Decision** — D2,
[`Decisions.md`](../Decisions.md).

**Fact** — The deepseek T2-only extension at M3 (36 problems from `bank[150:186]`)
was pre-committed at M1 close and drew from the same frozen prefix — no new smoke
was needed because `bank[186]` was already frozen at M0. Source:
[`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) § "Owed item 1".

**Fact** — The bank filter itself is two-stage and deterministic: Stage 1 (static,
encoded in `filter_bank.py`) and Stage 2 (sandbox smoke, S-exact semantics). The
T-E fidelity gate (≥90% of fixed-code passes + buggy-code fails) had to be cleared
before any paid call; on first pass it measured 86.0% and required one allowed
tightening (exposure-aware test selection), then reached 95.0%. Source:
[`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Pre-committed bank filter" + T-E record.

### Statistical method: paired Newcombe at M1, unpaired at M4

**Fact** — The M1 primary is a paired T2-vs-T3 pass-rate drop with a
φ̂-corrected paired Newcombe CI (Newcombe 1998, implemented in `stats.py` as
`newcombe_paired_diff`, TDD). The paired design isolates the manipulation from
problem-difficulty variation. Source: [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Primary endpoint".

**Fact** — Wilson 95% CIs are used for all single-proportion rates throughout
M0–M4. The unpaired Newcombe (`newcombe_diff`) is used for the M4-vs-M2 recovery
contrast (genuinely different populations). Sources: [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md),
[`docs/M2-BRIEF.md`](../docs/M2-BRIEF.md) § "Endpoints", [`stats.py`](../stats.py).

**Fact** — Point estimates are never asserted as claims; direction and CI structure
are the evidence units. This is explicit in the KICKOFF honesty contract and
enforced in every brief's "Honest expectation" passage.

### What counted as NULL and UNDERPOWERED

**Fact** — The M1 primary REPRODUCED-analog bar required two simultaneous
conditions: CI excludes 0 on the drop side **and** point drop ≥10 pts (the KICKOFF
δ). A CI excluding 0 with drop <10 pts was PARTIAL, not REPRODUCED. Source:
[`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Primary endpoint + pre-committed gate".

**Fact** — The UNDERPOWERED rule is unconditional: any gated cell with clean-N
<20 auto-reports UNDERPOWERED with no rescue. This fired at M3 (deepseek clean
N=12) and at M4 (both models, entry <20). The rule was published in the KICKOFF
and restated in each brief's "N-check" section. Sources:
[`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) "Roster rule"; [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) § "Entry subsets";
[`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) § "Entry subsets".

**Inference** — The UNDERPOWERED outcome at M3/M4 was foreseeable from funnel math.
The M3 brief pre-declared it before the M3 wave ran: "M4-deepseek UNDERPOWERED a
live, pre-declared outcome." This was not a post-hoc rationalization.

### What would have falsified the claim

**Fact** — The pre-committed kill triggers at M0 (T-A through T-G) defined exact
swap-and-stop conditions before the pilot ran. Three models were swapped in from
the bench; all six roster/bench models ultimately killed. The M0 verdict was
mechanically driven by the trigger table, not by judgment after the fact. Source:
[`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Pre-committed kill/swap triggers".

**Fact** — A M0 STOP on the full chain would have been the project kill condition
(and was in fact triggered: STOP on the full RQ1→RQ4 chain, disposition to
re-scope). The re-scope itself required Kyle's sign-off, recorded in the brief.
Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "FINAL M0 VERDICT" + disposition.

**Fact** — The M1 primary being NULL (as it was) was a pre-declared possible
outcome. The brief's "Honest expectation" section stated before the run: "A
deepseek NULL is a live outcome and would be a headline alongside the awareness
null, not a failure of M1." Source: [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Primary endpoint".

### Per-trial mechanical verification of the manufactured fault

**Fact** — Every T2 instruction is mechanically verified before use: (a) the anchor
excerpt matches the code at the cited lines, (b) the target region ±1 buffer is
provably disjoint from the true-fix region F, (c) no fix-added line appears in the
instruction text (no-leak). Unverifiable instructions are counted as
INVALID-instruction and excluded. Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) § "Mechanical
definitions".

**Fact** — At M3, the verifier was extended with `map_fix_region` to re-anchor F
into current (drifted) code coordinates before computing disjointness. The
design over-approximates F′ (conservative: the wrongness guarantee never weakens).
The honest cost is more INVALIDs: deepseek's 7/21 anchor-unresolvable INVALIDs
are the verifier doing its job on a wholesale-rewriter. Source:
[`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) § "Owed item 2".

### Budget honesty: measured-rate cost estimate before every wave

**Fact** — Every milestone required a measured-rate cost estimate before the wave
ran, a per-wave hard cap, and a $5.00 lifetime guard implemented as a
check-before-call halt in the OpenRouter client. The M0 hard cap ($0.25) fired
mid-kimi and halted the wave as designed. Source: [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) §
"T-G · Budget"; [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) § "Cap regime".

### Deviations from the paper

**Fact** — The briefs maintain a cumulative deviation table (rows 1–13 across M0–M3)
rather than hiding differences. The five structural deviations from M0 that apply
to all milestones:

| # | Deviation | Source |
|---|---|---|
| 1 | Cheap models, not frontier | [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) Deviations table |
| 2 | T1/T2 instructions LLM-drafted + mechanically verified (paper: human for RQ1) | 〃 |
| 3 | Our own 2-stage bank filter (paper's 538-problem filter unpublished) | 〃 |
| 4 | Prompt wording ours (paper's prompts unpublished) | 〃 |
| 5 | N: hobby scale with Wilson/Newcombe CIs (paper: 538) | 〃 |

**Inference** — Deviation 4 is the least resolvable: the paper's prompts are not
public as of v1, so the methodology gap cannot be narrowed without the paper
publishing them or a v2.

## Sources

- [`docs/KICKOFF.md`](../docs/KICKOFF.md) — honesty contract (verbatim source), scope, UNDERPOWERED rule
- [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) — kill triggers, bank filter, T-E gate, mechanical definitions, deviation table rows 1–6
- [`docs/M1-BRIEF.md`](../docs/M1-BRIEF.md) — primary endpoint pre-commitment, paired Newcombe, NULL/PARTIAL/REPRODUCED bar, pre-run expectation, deviation rows 7–9
- [`docs/M2-BRIEF.md`](../docs/M2-BRIEF.md) — FLOOR rule, pass-1 start-state pin rationale, per-pass mechanical checks
- [`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) — diff-anchor verifier design, INVALID taxonomy, pre-declared UNDERPOWERED, deviation rows 11–12
- [`docs/M4-BRIEF.md`](../docs/M4-BRIEF.md) — D11 rationale, D12 population pin, deviation row 13
- [`CLAUDE.md`](../CLAUDE.md) — honesty contract (carried verbatim)
- [`Decisions.md`](../Decisions.md) — D1 (scope), D2 (conventions)
- [`stats.py`](../stats.py) — Wilson/Newcombe implementation (the math the claims rest on)

## Uncertainties & contradictions

**Unresolved** — The paper's probe wording, T2 instruction generation method for
RQ1 (human vs LLM), and bank filter are all unpublished in v1. Three of the five
structural deviations cannot be fully resolved until the paper publishes supplemental
materials. See [`docs/M0-BRIEF.md`](../docs/M0-BRIEF.md) Deviations table.

**Unresolved** — The no-leak verifier checks only the *original* fix's added lines.
It cannot prove disjointness from ghost errors introduced mid-M3 loops. The M3
brief states this limit explicitly: "Our claim is scoped accordingly."
[`docs/M3-BRIEF.md`](../docs/M3-BRIEF.md) § "Owed item 2".

## Related pages

- [Results-Synthesis](Results-Synthesis.md)

## Relevance to current work

The project is closed. A future reader or arm-builder comes here to understand
which honesty constraints are reusable (the pre-registration pattern, the
bank-prefix discipline, the UNDERPOWERED auto-rule) and which deviations need
closing before a result can be compared directly to the paper's numbers (probe
wording, prompt wording, bank filter definition).

_Last reviewed: 2026-07-26_
