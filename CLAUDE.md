# ghost-patch — project context

Reproduction #4 (lineage: forge-gap → decay-pin → lossy-wall). Reproduce and measure the "Obey, Diverge, Collapse" failure chain (arXiv 2607.04537) on cheap models: aware-but-obedient wrong-location repair (M1) → recovery ceiling (M2) → ghost-error compounding (M3) → irrecoverability (M4).

- **Source of truth:** `docs/KICKOFF.md` (approved 2026-07-10). Milestones, gates, and the honesty contract live there — follow them exactly.
- **Current milestone:** M4 COMPLETE (2026-07-11) — **the chain is closed end-to-end.** Irrecoverability ran descriptively under D11-A (signed brief): chain gate **UNDERPOWERED ×2 exactly as pre-declared at M3 close** (entry 2/16 < 20), direction M4 < M2 on both models (Newcombe M2−M4 +28.3 pts [−17.0,+70.6] deepseek · +19.3 pts [−12.3,+43.9] qwen — CIs straddle 0, no gate moves). Descriptive IDR (paper verbatim, D12-A population): **qwen 6/12 = 50% [25.4,74.6] — half the ghost-error states never re-cross the buggy baseline in 5 saboteur-free feedback passes** (4 never improve a single test; deepened 0/12 — corruption stops compounding but doesn't heal), while the recovering half re-crosses **durably** (0 transient; 4 full fixes) and accrues through pass 4 (curve [2,3,4,6,6]) — unlike M2's pass-1 front-load, iteration depth does real work from corrupted states. deepseek 0/1 (its M1 null propagates to the last link; 2-loop cell = anecdote). Grade-0 integrity 18/18. One trigger fired + was disposed live by Kyle (recorded in `m4.py` + brief RESULTS): qwen parse floor 68.9% < 80%, all misses `finish_reason=length` on corrupted starts (response length scales with corruption; 4 INVALID loops incl. the pass-0 loop p03593). Full chain verdict: **obey M1 NULL×2 → recover M2 REPORTED×2 (78/53%) → compound M3 REPORTED-qwen (pass-1-only escape, damage 2× base) → irrecoverable M4 UNDERPOWERED×2 (descriptive 50% stuck-half)**. Records: `docs/M4-BRIEF.md` (+ M0–M3 briefs). Spend: **$1.4244 lifetime** (M4 meter $0.0711/$0.10, frozen at close).
- **Riskiest assumption (post-M4):** none — v1 scope is done (all four claims rendered by pre-committed verdict scripts on real data, per KICKOFF's success criterion). Project close-out is **complete (2026-07-14)**: research paper + presenter pack merged (`docs/paper/`, PR #14), README rewritten with the chain-verdict table (branch `docs/readme-closeout`); the gated post-v1 cure arm stays parked unless Kyle re-opens it. Lessons banked for future arms: diff-anchor attrition scales with rewrite radius (≥40% INVALID slack for wholesale rewriters); repair-response length scales with corruption depth — a frozen token budget measured on pristine code under-parses on corrupted starts (budget parse slack or pre-measure on damaged states).
- **Honesty contract (non-negotiable):** reproduce-and-measure, never invent; deterministic judge-free scoring; per-trial mechanical verification of the manipulation; pre-committed gates as code, dry-run before paid runs; nulls are headlines; direction + structure, never point estimates; N≥20 clean trials per gated cell or the gate auto-reports UNDERPOWERED; the paper's code (if a v2 ships it) is reference-only, never imported.
- **Budget:** hobby, <$5 target. Measured-rate cost estimate before every paid wave; N≈5 smoke before every paid arm.
- **Conventions (set in M0):** flat scripts at repo root; per-milestone verdict scripts (`m0.py`…`m4.py`) with subcommands; `test_*.py` alongside (pytest, TDD for pure logic); per-milestone briefs at `docs/M<N>-BRIEF.md` with decisions + pre-committed triggers; `data/raw/` gitignored + refetchable via `fetch_runbugrun.py`, everything derived (pool, bank, smoke/run logs, trial artifacts) committed under `data/`; frozen-pool prefix discipline for the bank (seed 2607, growth only extends the prefix).

## Claude tooling for this repo

Global commands (`.claude/commands/`) and skills (`.claude/skills/`) vendored from `ksdisch/claude-config` via `/claudify-repo`, so they work in cloud/web sessions and for collaborators. ✅ = cloud-safe (pure reasoning + repo edits). 💻 = **local-only** — needs local tools (browser MCP, Chrome, local TTS/voice, or the local `nlm` CLI / NotebookLM MCP) and will NOT work in a cloud/web session.

### Commands

- ✅ `/autonomous-milestone` — plan/build/test/verify a target end-to-end, or triage the backlog into ranked candidates; ultracode multi-agent orchestration.
- ✅ `/begin` — open a session: orient on branch/commits/open PRs, recap the last `/wrap` log, route into the session-start spec. (Optional audio recap is local-only.)
- 💻 `/boot_server` — detect how the project is served, start the dev server in the background, open it in Chrome.
- ✅ `/brainstorm` — multi-mode structured brainstorm (Moonshot default; QuickWin, Subtract, Harden, Premortem, Friction, Delight, Positioning, Reach); blind agent teams + critic gate → `docs/ideas/` vision docs + backlog stubs.
- 💻 `/catchup` — mid-session audio catch-up as an MP3 (local TTS); keeps working after.
- ✅ `/claudify-repo` — vendor global commands/skills into this repo and/or brainstorm repo-specific automations.
- 💻 `/envsetup` — open `.env` in the editor + the credential's generation page in Chrome, with a key stub pre-added.
- ✅ `/explore-plan` — explore → plan → confirm before any code; proposes 2–3 ranked approaches and waits for a pick.
- ✅ `/handoff` — generate a paste-ready handoff prompt for a fresh session; captures lessons + plan state. (Optional audio is local-only.)
- 💻 `/mock-sql-audio` — full simulated SQL mock interview as an MP3 (local two-voice TTS).
- ✅ `/mock-sql-demo` — text self-play mock SQL interview (interviewer + ideal candidate), then a debrief.
- 💻 `/mock-sql-interview` — live voice mock SQL interview (local voice mode).
- ✅ `/prompt-optimize` — one-shot prompt rewrite: diagnose, pick a workflow archetype + model + effort, return a ready-to-paste prompt. Advisory only.
- ✅ `/reframe-orchestrator` — reframe `.claude/orchestrator.md` into a mode-independent invariants & gates doc; docs-only.
- 💻 `/screenshot-iterate` — visual loop: implement against a mock, screenshot the running app, compare, iterate.
- 💻 `/smoke-test` — set up a manual smoke test: opens the needed pages in Chrome (auto-boots the dev server) and hands over a do-this-see-that checklist saved under `docs/smoke/`.
- ✅ `/tdd` — test-first loop: write failing tests, confirm they fail for the right reason, commit, then code until green without touching the tests.
- ✅ `/trim-context` — find and fix Claude Code token bloat (oversized CLAUDE.md, bloated memory, `.claude/` cruft); auto-applies fixes.
- ✅ `/wrap` — end-of-session recap: the why, vocabulary, active-recall quiz, next moves; saves a dated file. (Optional audio is local-only.)

### Skills (auto-trigger by description, or invoke by name)

- ✅ `artifacts-audit` — audit which engineering artifacts the repo should have; writes `docs/artifacts-plan.md`. Plans only.
- ✅ `artifacts-generate` — generate artifacts from `docs/artifacts-plan.md` (one-at-a-time or batch). Companion to `artifacts-audit`.
- 💻 `audio-series` — episodic NotebookLM audio series for an existing notebook (needs `nlm`/NotebookLM MCP).
- ✅ `bug-hunt` — proactive bug hunt: fan out finder agents, adversarially verify findings, ranked triage list; optional hand-off to a fix flow.
- 💻 `interview-prep` — init/maintain a NotebookLM interview-prep notebook from the local job-search dossier (needs `nlm`/NotebookLM MCP).
- ✅ `kickoff` — deep one-question-at-a-time discovery interview → approved kickoff brief + phased plan → scaffold the project + GitHub repo.
- 💻 `match-the-mock` — implement a UI against a mock and iterate via browser screenshots until it matches.
- ✅ `mini` — kick off a new mini project under `~/Projects/mini/` (short interview + scaffold).
- 💻 `narrate` — turn a short brief into a single-voice MP3 narration (local Kokoro TTS).
- 💻 `nlm-skill` — expert guide for the NotebookLM CLI (`nlm`) and MCP server.
- 💻 `notebook-assist` — refine artifacts / brainstorm / manage sources for an existing NotebookLM notebook.
- 💻 `notebook-init` — initialize a new NotebookLM notebook end-to-end.
- 💻 `notebook-merge` — merge 2+ overlapping NotebookLM notebooks into one unified notebook.
- ✅ `project-guide` — comprehensive point-in-time guide to the project (purpose, architecture, history, interview lens); saves a dated file. (Optional audio is local-only.)
- ✅ `research-paper` — end-of-project research paper + presenter pack from a completed repo's recorded results; opens a PR for review, never merges.
- ✅ `seed-hunt` — end-of-project seed hunt: verify closure, harvest lessons into the selection bar, sweep arXiv, decision brief. (Optional audio is local-only.)
- ✅ `ship-and-route` — land outstanding git work behind a review gate, walk the findings, route the next move with a starter prompt.
- 💻 `video-series` — episodic NotebookLM video series for an existing notebook (needs `nlm`/NotebookLM MCP).

To vendor more global tooling or brainstorm repo-specific automations, run `/claudify-repo`.

## Operating Constraints

@.claude/operating-constraints.md
