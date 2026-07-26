# History — ghost-patch

> How this project got here: a chronological narrative of eras and milestones,
> reconstructed from merged PRs, git history, and the milestone briefs.
> PR numbers, merge dates, and SHAs are **Fact** by construction (milestone dates
> are PR merge timestamps, UTC); rationale lines carry explicit labels (**Fact**
> when quoted from a PR body/brief, **Inference** when reconstructed). Decisions
> are anchored by ID to the project's decision ledgers — never restated here.
> Two ID namespaces exist: project-level D1–D5 live in the root `Decisions.md`;
> milestone-level lettered decisions (D1–D13) live in their `docs/M<N>-BRIEF.md`
> and are cited by brief path. **Append-only:** new milestones are added at the
> bottom (above the Mining coverage footer); existing entries are never rewritten.

## Origin — 2026-07

Fourth rung of the reproduce-and-measure lineage (forge-gap → decay-pin → lossy-wall), picked at `/seed-hunt` as the "new-surface" option: reproduce the "Obey, Diverge, Collapse" failure chain of arXiv 2607.04537 on cheap models at hobby scale (<$5), under the honesty contract, with a sandboxed code-execution/test-grading harness as the genuinely new muscle. First commit `caa8566` ("kickoff: ghost-patch — scaffold from brief"), 2026-07-10. Kickoff brief: `docs/KICKOFF.md` — see D1 in `Decisions.md`.

## Era: M0 — fit-pilot and the awareness STOP (2026-07-10)

One day: build everything free, spend $0.33 on a fit-pilot, hit a pre-registered precondition failure, and re-scope v1 before any expensive grid ran.

### M0 foundation: free harness + bank frozen at 186 — 2026-07-10
- **Landed:** M0 brief with pre-committed kill/swap triggers T-A…T-G; TDD'd pure-logic harness (`stats.py`, `grading.py`, `regions.py`, `filter_bank.py`); Docker sandbox (network-dead, integration-tested); checksummed `fetch_runbugrun.py`; frozen pool of 1,062 problems (seed 2607); bank frozen at 186 after the T-E fidelity gate (PR #1)
- **Why:** everything that runs free was built, tested, and executed before any paid call; the paid pilot stayed gated on sign-off [Fact — PR #1 body] — repo conventions set here, see D2 in `Decisions.md`
- **Tradeoff:** T-E first pass FAILed at 86.0%; the one allowed tightening (exposure-aware test selection) reached 95.0% S-exact — both passes recorded in the brief [Fact — PR #1 body]

### M0 pilot: VERDICT STOP — 2026-07-10
- **Landed:** ping / generator / pilot waves + the mechanical `m0.py` verdict: **STOP, 1/6 survivors**; killer = T-C awareness — every cheap model at ~chance discrimination in the evaluator role, while obedience itself reproduced loudly (PR #2)
- **Why:** "The fit-pilot did exactly its job: caught a precondition failure for $0.25 before a ~$2 doomed grid" [Fact — PR #2 body]
- **Tradeoff:** generator v1 (model picks location) measured only 25% acceptance because the generator kept finding the real bug; the one pre-committed revision switched to harness-picked provably-disjoint targets, 13/13 [Fact — PR #2 body]

### Probe audit: awareness null confirmed — 2026-07-10
- **Landed:** v2 probe wording (locate-first, last-line verdict) re-run over all 6 models × 24 instructions → **0/6 clear T-C**; FINAL M0 VERDICT: STOP on the full RQ1→RQ4 chain as scoped (PR #3)
- **Why:** kimi-k2.5 — the paper's own model — stayed flat at ~25% vs the paper's 63% under both wordings, substantially ruling out probe under-elicitation before abandoning the awareness leg [Fact — PR #3 body]

### Disposition: re-scope v1 to RQ2–RQ4 — 2026-07-10
- **Landed:** Kyle's approved disposition recorded in `docs/M0-BRIEF.md` + CLAUDE.md (PR #4)
- **Why:** cheap models are blind-and-obedient, not aware-but-obedient — KICKOFF risk 1(c), pre-registered; the obedience/damage chain still stands on its own [Fact — PR #3/#4 bodies + `docs/M0-BRIEF.md` disposition]

## Era: The chain — M1→M4 (2026-07-10 – 2026-07-12)

Two days running the re-scoped chain, one rhythm per milestone: start-of-stage brief → Kyle's sign-off recorded in the brief → free TDD'd machinery + synthetic dry-run → paid waves under a per-milestone cost meter → mechanical verdict.

### M1 obedience/damage: primary NULL ×2, funnel ALIVE — 2026-07-11
- **Landed:** revised M1 brief (PR #5), `m1.py` machinery with the paired-Newcombe primary and resumable waves (PR #6), 900/900 trials + verdict (PR #7); meter $0.584/$1.00
- **Why:** the wrong-location instruction is obeyed (129/150, 127/146) but produces no detectable net pass-rate drop — "obedience without net damage"; the null is the headline [Fact — PR #7 body]; brief decisions D5–D7 signed — see `docs/M1-BRIEF.md`
- **Tradeoff:** deepseek damaged-N landed at 18 < 20, invoking the pre-committed T2-only extension owed before M3 [Fact — PR #7 body]

### M2 recovery ceiling: REPORTED ×2, M4 anchor ALIVE — 2026-07-11
- **Landed:** M2 brief (PR #8), `m2.py` + both 5-pass self-repair waves + verdict — ceilings deepseek 78.3% / qwen 52.6%, meter $0.1874/$0.45 (PR #9)
- **Why:** recovery curves are pass-1 front-loaded — "feedback, not iteration depth, is the active ingredient" [Fact — PR #9 body]; brief decisions D8–D9 signed — see `docs/M2-BRIEF.md`
- **Tradeoff:** qwen's mid-loop parse attrition (22.4% INVALID) cleared the 80% first-parse floor by 0.6 pts with no format revisions left — flagged forward to M4 [Fact — PR #9 body]

### M3 ghost-error compounding: REPORTED (qwen) / UNDERPOWERED (deepseek) — 2026-07-12
- **Landed:** M3 brief with the two owed items — deepseek T2-only extension and the diff-anchor-after-code-drift verifier (PR #10); extension (E=3, entry 21) + both waves + verdict (PR #11); meter $0.2549/$1.00
- **Why:** in the powered cell, compounding is visible — qwen escapes are pass-1-only (curve [7,7,7,7,7]) and final-below-baseline ≈2× the M2 no-instruction base; deepseek propagates its M1 null and corrupts by wholesale rewrite, shredding the diff-anchor [Fact — PR #11 body]; brief decision D10 signed — see `docs/M3-BRIEF.md`
- **Tradeoff:** M4 entry froze at 2/16, both < 20 → the KICKOFF chain gate was pre-declared UNDERPOWERED ×2 at M3 close rather than quietly rescued [Fact — PR #11 body]

### M4 irrecoverability: chain closed — 2026-07-12
- **Landed:** M4 brief (PR #12), `m4.py` + both waves + verdict — chain gate UNDERPOWERED ×2 exactly as pre-declared; descriptive IDR qwen 6/12 = 50%, deepened 0/12; meter $0.0711/$0.10; lifetime $1.4244 (PR #13)
- **Why:** ran descriptively to complete the four-script chain per KICKOFF's success criterion — see D3 in `Decisions.md`
- **Tradeoff:** the one fired trigger of the chain (qwen first-parse 68.9% < 80%, all misses `finish_reason=length` on corrupted starts) was disposed live by Kyle — finish under the frozen protocol, breach reported not re-halted; the attrition itself became a finding [Fact — PR #13 body + `docs/M4-BRIEF.md` RESULTS]

## Era: Close-out (2026-07-14)

### v1 close-out: paper, presenter pack, README chain-verdict table — 2026-07-14
- **Landed:** `docs/paper/ghost-patch-paper.md` + presenter pack written entirely from recorded results with a 110-point provenance check (PR #14); README rewritten with the chain-verdict table and v1-complete status (PR #15, merge `0cafc77`)
- **Why:** all four claims rendered by pre-committed verdict scripts on real data — v1 complete per KICKOFF's success criterion — see D4 in `Decisions.md`; the post-v1 cure arm stays parked — see D5 in `Decisions.md`

## Era: Post-v1 upkeep (2026-07-18 – 2026-07-26)

Project closed; only repo stewardship since.

### Claude tooling vendor sweep — 2026-07-18
- **Landed:** fleet-wide `/claudify-repo` sweep vendoring global commands/skills into `.claude/` + CLAUDE.md tooling reference (PR #16)
- **Why:** make the tooling work in cloud/web sessions and for collaborators [Fact — PR #16 body]

### Project wiki initialized — 2026-07-26
- **Landed:** PROJECT.md, HANDOFF.md, Sources.md, Decisions.md + CLAUDE.md wiring (PR #17, merge `f50b627`)
- **Why:** record the closed-project state; `Wiki/` was intentionally skipped at init because `docs/paper/` already served as the durable knowledge capture [Fact — PR #17 body]

---

## Mining coverage
_Backfilled 2026-07-26 by project-wiki BACKFILL. Entries after this date are
appended live by MAINTAIN._
- PR title sweep: all 17 merged PRs — no cap
- Deep reads: 17 of 17 PRs (N under the 20 cap, so every body was read)
- Also swept: git log (16 merges, 63 non-merge commits), tags (none exist), decision ledger `Decisions.md` (D1–D5), docs of intent (`docs/KICKOFF.md`, `docs/M0–M4-BRIEF.md`, `docs/M0/M1/M3-SPOTREAD.md`, `docs/paper/`) — anchored, not restated
- Wrap/session logs: none found (`docs/session-logs/`, `.claude/session-logs/` absent)
- Not mined: closed-unmerged PRs, issues
