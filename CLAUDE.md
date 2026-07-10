# ghost-patch — project context

Reproduction #4 (lineage: forge-gap → decay-pin → lossy-wall). Reproduce and measure the "Obey, Diverge, Collapse" failure chain (arXiv 2607.04537) on cheap models: aware-but-obedient wrong-location repair (M1) → recovery ceiling (M2) → ghost-error compounding (M3) → irrecoverability (M4).

- **Source of truth:** `docs/KICKOFF.md` (approved 2026-07-10). Milestones, gates, and the honesty contract live there — follow them exactly.
- **Current milestone:** M0 fit-pilot — not started. Kill/swap triggers must be written **before** the pilot runs.
- **Riskiest assumption:** cheap models must exhibit *blind obedience*. Three per-model failure directions: too skeptical (resists T2), too weak (T1/T3 repair ≈ 0, no room for the T2 delta), can't classify the instruction in the evaluator role (blindness, not blind obedience).
- **Honesty contract (non-negotiable):** reproduce-and-measure, never invent; deterministic judge-free scoring; per-trial mechanical verification of the manipulation; pre-committed gates as code, dry-run before paid runs; nulls are headlines; direction + structure, never point estimates; N≥20 clean trials per gated cell or the gate auto-reports UNDERPOWERED; the paper's code (if a v2 ships it) is reference-only, never imported.
- **Budget:** hobby, <$5 target. Measured-rate cost estimate before every paid wave; N≈5 smoke before every paid arm.
- **Conventions (set in M0):** flat scripts at repo root; per-milestone verdict scripts (`m0.py`…`m4.py`) with subcommands; `test_*.py` alongside (pytest, TDD for pure logic); per-milestone briefs at `docs/M<N>-BRIEF.md` with decisions + pre-committed triggers; `data/raw/` gitignored + refetchable via `fetch_runbugrun.py`, everything derived (pool, bank, smoke/run logs, trial artifacts) committed under `data/`; frozen-pool prefix discipline for the bank (seed 2607, growth only extends the prefix).
