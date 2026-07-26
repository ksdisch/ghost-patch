# Decisions

Project-level decisions only. Milestone-level decisions (with lettered options and Kyle's sign-offs) live in the per-milestone briefs `docs/M0-BRIEF.md` … `docs/M4-BRIEF.md` — those briefs are the source of truth; this table indexes the ones that shape the whole project.

| ID | Decision | Status | Date | Source/Rationale |
|----|----------|--------|------|-----------------|
| D1 | Kickoff brief approved: reproduce the four-link chain of arXiv 2607.04537 on cheap models under the honesty contract, <$5 budget, milestones M0–M4 with pre-committed gates | Approved | 2026-07-10 | `docs/KICKOFF.md` (header: "scoped (approved 2026-07-10)") |
| D2 | Repo conventions set in M0: flat scripts at root; per-milestone verdict scripts `m0.py`…`m4.py` with subcommands; pytest TDD for pure logic; briefs at `docs/M<N>-BRIEF.md`; `data/raw/` gitignored + refetchable, everything derived committed; frozen-pool prefix discipline (seed 2607) | Approved | 2026-07-10 | `CLAUDE.md` "Conventions (set in M0)"; `docs/M0-BRIEF.md` |
| D3 | M4 ran descriptively under signed brief: D11-A (run descriptively), D12-A (all 18 loops run, damaged-16 IDR primary), D13-A + execution gate (full auto within the $0.10 cap and pre-committed halt triggers) | Approved | 2026-07-11 | `docs/M4-BRIEF.md` SIGN-OFF (Kyle, via decision prompt) |
| D4 | v1 close-out: research paper + presenter pack merged (PR #14), README rewritten with chain-verdict table (PR #15); v1 declared complete per KICKOFF's success criterion | Approved | 2026-07-14 | `CLAUDE.md` status; merges dfde4e4 / 0cafc77 |
| D5 | Post-v1 cure arm (failing-test evidence / refusal license in the wrong instruction) stays parked unless Kyle re-opens it | Proposed | 2026-07-14 | `docs/KICKOFF.md` post-v1 gated section; paper conclusion; `README.md` |
