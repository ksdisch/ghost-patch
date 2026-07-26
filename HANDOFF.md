# HANDOFF.md

_Last updated: 2026-07-26_

## What was just done
- Project wiki initialized (PROJECT.md, HANDOFF.md, Sources.md, Decisions.md; CLAUDE.md wired) — this commit.
- Before that: global Claude Code tooling vendored via `/claudify-repo` (PR #16, commit 917752e).
- Project close-out (2026-07-14): research paper + presenter pack merged (`docs/paper/`, PR #14); README rewritten with the chain-verdict table (PR #15, merge 0cafc77).

## Where things stand
v1 is COMPLETE and the project is closed. All four paper claims were rendered by pre-committed verdict scripts on real data (M4 closed 2026-07-11): M1 obey NULL ×2, M2 recover REPORTED ×2 (78.3% / 52.6%), M3 compound REPORTED on qwen (pass-1-only escape) / UNDERPOWERED on deepseek, M4 irrecoverability UNDERPOWERED ×2 exactly as pre-declared, with descriptive IDR 6/12 = 50% (corruption stops compounding but doesn't heal). Lifetime spend $1.4244 of the $5.00 guard, frozen. The repo is idle; the only future work on the books is the parked, gated cure arm.

## Immediate next move
None — the project is closed. If it is ever resumed, the next arm is the gated cure experiment (failing-test evidence / refusal license in the wrong instruction), per `docs/KICKOFF.md` and the paper's conclusion; it stays parked unless Kyle re-opens it.

## Open questions / blockers
- None blocking. The cure arm is Proposed/parked, not scheduled.

## Files touched recently
- `PROJECT.md`, `HANDOFF.md`, `Sources.md`, `Decisions.md` — new wiki files (this commit)
- `CLAUDE.md` — Project Wiki section appended (this commit)
- `.claude/` — vendored commands/skills from claude-config (PR #16)
- `README.md`, `docs/paper/` — close-out artifacts (PRs #14–#15, 2026-07-14)
