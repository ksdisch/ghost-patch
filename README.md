# ghost-patch

Hobby-scale reproduction of **"Obey, Diverge, Collapse"** (arXiv 2607.04537): code LLMs correctly flag a wrong-location repair instruction as incorrect, follow it anyway, compound Ghost Errors across iterative repair passes, and land in a corrupted state that self-guided repair cannot recover — not even back to the original buggy baseline.

**Status:** scoped — kickoff approved 2026-07-10. Next: Milestone 0 (fit-pilot). No results yet.

## Why

Fourth in a lineage of honest, hobby-budget reproductions (forge-gap → decay-pin → lossy-wall). The paper is days old (v1 2026-07-05), unreplicated, and its promised code appendix is missing from v1 — an independent reproduction has real standalone value. New muscle this round: sandboxed execution of untrusted, model-generated code against deterministic test suites (RunBugRun).

## What success looks like (v1)

All four chained claims (RQ1–RQ4) get pre-committed verdict scripts that run on real data and render **REPRODUCED / PARTIAL / NULL / UNDERPOWERED** per claim, on ≥2 pilot-surviving cheap models, with Wilson/Newcombe CIs. Every scored wrong-instruction trial is mechanically verified. A null is a reportable headline.

## Ground rules (honesty contract)

Reproduce and measure, never invent. Judge-free deterministic scoring only. Pre-committed gates as code, dry-run before paid data. Direction + structure, never point estimates. The paper's code (if a v2 ever ships it): reference-only, never imported.

Full brief: [docs/KICKOFF.md](docs/KICKOFF.md)
