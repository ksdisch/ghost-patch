# Sources

| Source | Location | Type | Authoritative for |
|--------|----------|------|-------------------|
| Target paper "Obey, Diverge, Collapse" | arXiv 2607.04537 | external paper | The claims under reproduction (RQ1–RQ4); its v1 code appendix is absent — reference-only if a v2 ships it |
| Kickoff brief | `docs/KICKOFF.md` | brief | Scope, phased plan (M0–M4 + gated cure arm), honesty contract, budget; approved 2026-07-10 |
| Milestone briefs | `docs/M0-BRIEF.md` … `docs/M4-BRIEF.md` | brief | Source of truth for per-milestone pre-committed decisions, triggers, and appended RESULTS (incl. signed decision IDs, e.g. M4's D11-A/D12-A/D13-A) |
| Spot-read samples | `docs/M0-SPOTREAD.md`, `docs/M1-SPOTREAD.md`, `docs/M3-SPOTREAD.md` | export | Human-audited samples of accepted wrong instructions |
| Research paper | `docs/paper/ghost-patch-paper.md` | writeup | Full results narrative; every number lifted verbatim from committed records |
| Presenter pack | `docs/paper/ghost-patch-presenter-pack.md` | writeup | 60-second story, claim-by-claim provenance map, anticipated Q&A |
| Machine results | `data/m1_results.json` … `data/m4_results.json`, `data/pilot_results.json`, `data/smoke_results.json` | export | Gate outputs and measured numbers, machine-readable |
| Trial artifacts + cost ledgers | `data/m1/` … `data/m4/` | export | Per-trial evidence backing every results JSON |
| Frozen bank + pool | `data/bank.json`, `data/pool.json` | export | The 186-problem bank and seed-2607 pool (frozen-prefix discipline) |
| Verdict gates as code | `m0.py` … `m4.py` (+ `test_*.py`) | spec (executable) | The pre-committed gates and triggers themselves; 256 tests green at M4 close |
| README | `README.md` | summary | Chain-verdict table and repo map (derived from the above, not primary) |
