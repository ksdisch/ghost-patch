# PROJECT.md

## Purpose
Hobby-scale, pre-committed reproduction of "Obey, Diverge, Collapse" (arXiv 2607.04537): measure whether code LLMs recognize a wrong-location repair instruction as incorrect, follow it anyway, compound ghost errors across iterative repair passes, and land in a state self-guided repair cannot recover (fourth in the forge-gap → decay-pin → lossy-wall lineage).

## Scope
**IN (v1 — complete):** the four-link chain M0 (awareness precondition) → M1 (obey) → M2 (recover) → M3 (compound) → M4 (irrecoverable), measured on deepseek-chat-v3.1 and qwen3-coder-30b-a3b-instruct over a frozen 186-problem RunBugRun bank, with every verdict rendered by pre-committed gate scripts (`m0.py`…`m4.py`) dry-run before paid data existed.

**OUT / deferred / never:** the gated post-v1 "cure" arm (does failing-test evidence or a refusal license in the wrong instruction collapse obedience?) — parked unless Kyle re-opens it; importing the paper's own code if a v2 ships it (reference-only, per the honesty contract); point-estimate claims (direction + structure only).

## Current status
Complete — the chain closed end-to-end at M4 (2026-07-11); close-out (research paper, presenter pack, README chain-verdict rewrite) merged 2026-07-14. Chain verdict: obey M1 NULL ×2 → recover M2 REPORTED ×2 → compound M3 REPORTED (qwen) / UNDERPOWERED (deepseek) → irrecoverable M4 UNDERPOWERED ×2 as pre-declared, with descriptive IDR 6/12 = 50%. Lifetime spend $1.4244 against the $5.00 guard. No active work.

## Next actions
1. None — v1 is closed. Re-open only if the parked cure arm is revived (see `docs/KICKOFF.md` post-v1 section and the paper's conclusion).
2. For audit/reproduction: refetch raw data via `fetch_runbugrun.py` (checksum-pinned; `data/raw/` is gitignored), then run `pytest` (256 tests green at M4 close).

## Boundaries
- **Honesty contract (non-negotiable, `docs/KICKOFF.md`):** reproduce-and-measure, never invent; deterministic judge-free grading in a network-less Docker sandbox; per-trial mechanical verification of every manufactured fault; pre-committed gates as code; nulls are headlines; Wilson/Newcombe intervals; any gated cell under 20 clean trials auto-reports UNDERPOWERED.
- **Budget:** <$5 lifetime via the metered OpenRouter client's check-before-call guard; meter frozen at $1.4244.
- **Secrets:** `.env` holds the OpenRouter API key — never commit or print it (`.env.example` is the committed stub).
- **Data:** `data/raw/` gitignored + refetchable; everything derived (pool, bank, logs, trial artifacts, results JSON) is committed; frozen-pool prefix discipline (seed 2607).
