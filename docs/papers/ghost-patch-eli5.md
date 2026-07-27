# Ghost-Patch: A Pre-Committed, Hobby-Scale Reproduction of the "Obey, Diverge, Collapse" Failure Chain on Cheap Code Models

> **This is a plain-English rewrite.** It mirrors the original paper 1:1 — same headings,
> same paragraphs, same order. Nothing is summarized, merged, dropped, or reordered; only
> the language changes. Tables are reproduced exactly as they appear in the original, each
> followed by an italic *"In plain words"* line. The references section is carried through
> untouched.
>
> **Original paper:** *Ghost-Patch: A Pre-Committed, Hobby-Scale Reproduction of the "Obey, Diverge, Collapse" Failure Chain on Cheap Code Models*
> **Author:** Kyle Disch
> **Source:** `docs/paper/ghost-patch-paper.md` (this repository, `main`)
> **Rewrite generated:** 2026-07-27

---

**Kyle Disch** · [github.com/ksdisch/ghost-patch](https://github.com/ksdisch/ghost-patch) · 2026-07-12

*Fourth in a series of projects that take a published finding and re-measure it (forge-gap → decay-pin → lossy-wall). Every number in this paper is copied straight out of the records already committed to this repository — the milestone write-ups (`docs/M0-BRIEF.md` … `docs/M4-BRIEF.md`) and their machine-readable twins (`data/m1_results.json` … `data/m4_results.json`). Nothing is recalculated here. A note about figures: the project saved all its results as tables and data files; there are no chart images in the repository, so this paper contains tables only.*

---

## Abstract

"Obey, Diverge, Collapse" (arXiv 2607.04537, version 1, published 2026-07-05) describes a four-stage failure sequence in large language models (LLMs) that fix code: the model can tell that a repair instruction points at the wrong place, follows it anyway, introduces brand-new "ghost errors," piles more of them on with each repair attempt, and ends up in a state that its own self-guided repair cannot climb out of. We independently re-ran and measured the *shape* of that sequence on two cheap models (deepseek-chat-v3.1 and qwen3-coder-30b-a3b-instruct) across a 186-problem set drawn from RunBugRun, under a protocol locked down in advance: grading done by a sandboxed program with no randomness in it, machine-checking of every planted wrong instruction on every single trial, pass/fail rules frozen as working code before any money was spent, Wilson and Newcombe error bars (standard recipes for putting a plausible range around a percentage and around the gap between two percentages), and a rule that any tested cell with fewer than 20 trials is automatically labelled UNDERPOWERED. Two links in the sequence fail honestly at this price tier, and we report them as headlines: the "the model knows better" precondition does not reproduce (0 of 6 models tested clear the awareness check under two different question wordings; the paper's own Kimi K2.5 reads about 25% aware in our hands versus the 63% the paper reports), and the drop in repair quality from a single wrong instruction is statistically indistinguishable from zero on both subjects (+4.0 points, plausible range [−2.2, +10.3]; +3.6 points, [−3.4, +10.6]). The back half of the sequence is visible wherever we had enough trials to see it: repair driven by test feedback recovers 78.3% / 52.6% of broken programs when starting from a clean state, but under repeated, machine-verified sabotage qwen only ever escapes on the first attempt (30.4%, flat thereafter), and afterwards half of its damaged programs (6 of 12) never get back to as good as the original buggy version across five sabotage-free attempts. The comparison between the final stage and the recovery stage lands UNDERPOWERED on both models exactly as we predicted in advance, with the direction of the effect matching the paper. Total money spent: $1.42.

---

## 1. Introduction

Getting an LLM to fix code by repeated attempts has a claimed failure mode that is qualitatively worse than "the model just can't fix the bug": handed a confident but misaimed instruction, the model wrecks parts of the program that were working, the wreckage accumulates over repair rounds, and the end result is beyond rescue even compared with the original broken program. "Obey, Diverge, Collapse" (arXiv 2607.04537) published this sequence days before this project started, using five top-tier models, and promised a code appendix that never appeared in version 1. Nobody has independently repeated it, and the paper's problem-selection rules, prompts, and test harness are all unpublished.

This paper's contribution is intentionally narrow: an **independent re-run on a hobby budget, with every judgement rule locked in beforehand**, testing the sequence's four claims on cheap models, where every verdict is delivered by a script that was written and rehearsed before any of the paid data existed. We are not inventing mechanisms, we are not trying to hit the paper's exact percentages (we check direction and shape only), and we treat "we found nothing" as a genuine result rather than a failure. Working this way, the project produced:

1. **Two headline non-results.** The paper's "knows better but complies anyway" premise does not hold up at the cheap tier — when asked to play evaluator and judge an instruction, models perform near coin-flip level across six models and two question wordings (§5.1) — and the drop in repair quality from a single wrong-location instruction is indistinguishable from zero on both surviving subjects at 150 problems each (§5.2). Cheap models here are *blind* and compliant, and compliance on its own does not produce net damage in a single pass.
2. **The back half of the sequence, measured.** Wherever we still had enough trials, the paper's shape shows up: escaping from repeated, machine-verified sabotage collapses to "first attempt or never" (§5.4), and half of the resulting damaged programs never get back to as good as the original buggy version once the sabotage stops (§5.5) — with the caveat, declared in advance, that the final comparison is short of trials because of measured drop-off through the pipeline, not because we chose a small sample.
3. **A re-runnable test harness and a record of what didn't work.** A Docker-sandboxed grading pipeline over RunBugRun with no LLM judging anywhere in it; an instruction generator whose wrongness is *proven on every trial* instead of assumed; and two measurement lessons worth carrying forward (the verifier's dilemma and the way response length grows with how badly the code has been mangled, §6).

Everything below says plainly what was planted by us (all wrong instructions and all damaged program states are faults we injected, and verified as such), what came back as no-effect, and what had too few trials to judge.

## 2. The target paper and its claims

As recorded in this repository's notes (`docs/M0-BRIEF.md`, "What the paper settles"), the paper tests five top-tier models (GPT-5.3 Codex, Sonnet 4.6, Qwen3-Coder, GLM-5, Kimi K2.5) on 538 filtered problems and claims:

- **Research question 1 (obey):** given a broken program, its problem description, and a confident instruction that points at the wrong part of the code (condition T2), models repair it *worse* than when given no instruction at all (condition T3) — pass rates drop by roughly 7 to 21 percentage points — *while* a separate question that asks the model to act as an evaluator shows it can label that same instruction INCORRECT (weakest model: Kimi K2.5 at 340 of 538, about 63%). This pairing of "aware" with "fails anyway" is the paper's headline statistical result, reported as highly unlikely to be chance on all five models.
- **Research question 2 (recovery ceiling):** on the problems where the no-instruction condition failed, let the model repair on its own, showing it the most recent failing test, for at most 5 rounds, stopping early if every test passes.
- **Research question 3 (diverge / compound):** starting from the wrong-instruction trials where damage was confirmed (more failing tests than the original broken program had), run 5 further rounds, each carrying a freshly written wrong instruction (the generator sees only the current code — the paper uses GPT-5.1 Codex for this); between 5% and 22% of the 538 problems qualify to enter, depending on the model.
- **Research question 4 (collapse):** run research question 2's procedure starting from research question 3's damaged end states; the headline number is the **Irrecoverable Damage Rate (IDR)** — the fraction that never get back to as good as the original broken program within 5 rounds.

Version 1 of the paper ships no code, no prompts, and no data (its Appendix 9 covers ethics only), so every prompt and filter below is ours, built to match the structure described in the paper's §3. Every place we departed from it is owned up to in per-milestone tables in the briefs (13 rows in total).

## 3. Methods

### 3.1 Task, data, and the frozen bank

The task is repairing single-file Python programs: given a broken program and a description of what it should do, produce a complete corrected program, graded against hidden pairs of input and expected output. The data is the Python portion of RunBugRun (data release v0.0.1: `python_test0` = 9,611 bugs across 1,342 problems; `python_valid0` = 2,054 across 671; `tests_all` = test pairs for 3,926 problems), with English problem descriptions taken from PIE4Perf — the same translation source RunBugRun itself credits — covering essentially everything (1,340 of 1,342 and 670 of 671). Downloads are pinned to specific file checksums so the data can never silently change (`fetch_runbugrun.py`).

The paper's rule for narrowing to 538 problems is unpublished, so our problem set comes from our own **two-stage filter, written and locked before any paid call** (`filter_bank.py`). Stage 1 checks things that need no model at all: both the broken and fixed versions must compile under CPython 3.12; there must be a usable English description; at least 3 tests (we consider at most 20 per problem); the program must be 3 to 40 non-blank lines; the real fix must be small and localized (at most 2 edit blocks and 6 changed lines, measured from our own standardized comparison of the two versions) with at least 5 lines outside the area being fixed; and only one bug per problem, because the statistical methods we use assume the trials are independent of one another. That leaves a **frozen pool of 1,062 problems** (out of 11,665 bugs examined), shuffled once using the fixed seed 2607. Stage 2 is a free run through the sandbox over the front of that pool: the fixed version must pass every selected test, and the broken version must fail at least one **and pass at least one** — the *room-to-get-worse* requirement, without which the phrase "more failing tests than the baseline" has no meaning (roughly a third of the problems we smoke-tested failed it).

**We set a quality bar for the harness in advance, and it failed on the first try.** The pre-registered check (fixed version passes everything, broken version fails something, on at least 90% of smoke-tested problems) initially read **86.0%** under strict output matching / 88.3% under the looser numeric variant, across 300 problems. The diagnosis: we were picking the wrong *tests* — 30 of 35 failures were bugs whose revealing test happened to fall outside the "lowest 20 by ID" cap. The single adjustment we had permitted ourselves in advance (choosing tests that actually expose the bug, which swapped 29 of them) brought the repeat check to **95.0% / 98.0%, PASS**, and we adopted and froze the stricter exact-match rule. The problem set froze at **186 problems** (`data/bank.json`); the first milestone's main run uses the first 150; any later growth only ever extends that frozen ordering.

### 3.2 Sandboxed, deterministic grading

Candidate programs run inside a fresh Docker container per program (`python:3.12-slim`, no network access, 1 CPU, 512 MB of memory, at most 128 processes, read-only filesystem, non-root user), with each test run as its own process under a 5-second wall-clock limit. Grading happens **outside the container** under the frozen exact-match rules (strip trailing spaces from each line, drop trailing blank lines, then require an exact match) — the container never sees the expected outputs, so a program cannot grade itself. Pass or fail is fully repeatable; there are no LLM judges anywhere in this project.

### 3.3 The manipulation, and why its wrongness is provable

There are three conditions: T1 (a correct instruction), T2 (an instruction pointing at the wrong location), and T3 (no instruction). All instructions are **faults we manufactured**: drafted by a fixed model that is never itself a test subject (`openai/gpt-5.1-codex-mini`, with its internal deliberation dialled to low) as structured fields (target lines, a quoted snippet to anchor on, a diagnosis, and a directive), then poured into a fixed template that reads fluently. Every draft wrong instruction has to survive a **mechanical check**: (a) the quoted snippet really does match the code at the lines cited; (b) the targeted region, plus one line either side, is provably nowhere near the region the real fix touches (computed from a standardized comparison of broken and fixed versions); and (c) no line added by the real fix shows up in the instruction once whitespace is normalized, so the answer cannot leak. Drafts that fail the check never make it into a trial; the trials they would have belonged to are marked INVALID — excluded from every denominator, counted, and reported.

Letting the generator choose freely failed, and failed honestly: given a program of 40 lines or fewer, it *found the actual bug* most of the time (only 5 of 20 first attempts survived the check, and 39 of the 41 rejections were for pointing too close to the real fix). The one revision we had allowed ourselves — **protocol version 2, where the harness picks the target** — has the harness deterministically assign a region that is provably far from the real fix (chosen by a fixed per-problem seed) and leaves the generator to write only the confident-sounding rationale. That lifted the acceptance rate to 13 of 13 (100%) and better mirrors the paper's *deliberately* misdirected human-written instructions. In the third milestone, where the code changes on every round, we track the real fix region forward by mapping it through a standardized comparison (`regions.map_fix_region`), deliberately **erring on the side of marking too much as off-limits** — the guarantee that the instruction is wrong never weakens, and the price is paid instead in discarded trials, which we count by cause. One limit is stated up front in the brief: the check proves the instruction is away from the *original* fix region as tracked forward; there is no ground truth for the ghost errors the model introduces mid-loop (the paper's unverified generator faces exactly the same exposure, minus the guarantee).

### 3.4 Statistics, gates, and budget discipline

Every rate we judge is a percentage wrapped in a **Wilson score interval** — a standard recipe for the range of true values that percentage is consistent with. Differences between two conditions use **Newcombe intervals** (the "square and add" recipe, his method 10, for comparing two separate groups; his 1998 paired variant with a discordance correction, written φ̂, for the first milestone's within-problem comparison of the wrong-instruction and no-instruction conditions) — all implemented in `stats.py`, unit-tested, with no outside statistics libraries. A range that includes zero means no effect or a small one, and we say so; a range that merely touches zero does not count as excluding it. Any judged cell with fewer than 20 usable trials **automatically reports UNDERPOWERED — no rescues, no exceptions**. Verdicts are always per model, never pooled. Every verdict script (`m0.py` through `m4.py`) was written, unit-tested (256 tests passing by the fourth milestone), and rehearsed on made-up data **before** the paid run it judges; the rules for killing, swapping, or halting a run were committed before the runs they govern. Each milestone ran under a hard spending cap with a meter that checks before every call and a lifetime guard of $5.00; cost estimates based on measured rates and roughly 5-call smoke tests came before every paid batch.

## 4. Experimental setup

**Subjects.** Six cheap models available through OpenRouter entered the first pilot (main roster: qwen3-coder-30b-a3b-instruct, glm-4.7-flash, llama-3.1-8b-instruct; comparison set: deepseek-chat-v3.1, mistral-small-3.2-24b-instruct, kimi-k2.5 — the paper's own model). Pre-committed pilot rules eliminated four of them (§5.1); the sequence was then run on **deepseek-chat-v3.1** ($0.21 in / $0.79 out per million tokens) and **qwen3-coder-30b-a3b-instruct** ($0.07 / $0.27) — the latter a cheap relative of one of the paper's models. Subjects had their internal deliberation turned off; the repair budget was 3,200 tokens (a measured floor); parsing takes the last fenced code block, requires it to compile cleanly, and allows exactly one plain retry before marking the trial INVALID.

**The five milestones.**

- **M0 (does this even fit?):** the first 12 problems in the set × the three conditions, plus 24 evaluator-role questions per model, judged against pre-committed rules on capability, skepticism, awareness, and parsing; plus the harness, problem-set, and generator checks from §3.
- **M1 (research question 1, re-scoped):** single-pass repair, 3 conditions × 150 problems × 2 models, with the same problems seen by every condition. The main measure is the drop in pass rate from the no-instruction condition to the wrong-instruction condition (paired Newcombe interval; to count as REPRODUCED it needed a range excluding 0 *and* a drop of at least 10 points). After the awareness non-result in M0, the evaluator-question leg was dropped by signed decision — M1 claims only the behavioural drop.
- **M2 (research question 2):** on each model's set of failed no-instruction problems, self-guided repair starting from the *original broken program*: each round the model sees the description, the current code, and the first failing test (its input, the expected output, and what the program actually produced, truncated to 1,000 characters), for at most 5 rounds, stopping early if everything passes. No sabotage. Output: the recovery ceiling and the round-by-round curve — the anchor that M4 is compared against.
- **M3 (research question 3):** starting from each model's confirmed-damage wrong-instruction states (deepseek's entry pool topped up by a pre-committed extra wave of 36 wrong-instruction-only trials, following the frozen ordering), the same loop plus **a fresh verified wrong instruction every round** (the generator sees only the current code). "Escape" means every test passes despite the sabotage. Declared descriptive in advance — not a pass/fail gate.
- **M4 (research question 4):** M2's loop exactly as written, but starting from M3's frozen damaged end states (byte-for-byte identical starting points, checked at round zero). The main measure is the **Irrecoverable Damage Rate**, defined exactly as the paper defines it. One decision was pinned before the run (decision D12): two entry states sat at or below the baseline (they improved during M3 without escaping) and therefore count as recovered at round zero by definition — all 18 were run, but the rate's denominator is the 16 states that were genuinely damaged at entry, with that pair reported separately and an all-18 sensitivity line included.

Every loop's starting state and every feedback block shown to the model is mechanically re-checked against the frozen record before the round begins (72 of 72 in M2, 56 of 56 in M3, 18 of 18 in M4 — the halt-on-drift alarm never fired).

## 5. Results

### 5.1 M0 — the awareness precondition fails across the tier (null #1)

Compliance is emphatically present in the pilot — every model mechanically follows the wrong-location instruction on 9 to 11 of the 12 problems, and damage does occur — but **when asked to play evaluator, the models perform at roughly coin-flip level everywhere**. Judged against the pre-committed rule (a pass needs at least 8 of 12 wrong instructions labelled INCORRECT, with a sanity check that correct ones are not also being flagged):

| Model | probe v1 (T2✓/T1✓) | probe v2 (T2✓/T1✓) | pilot verdict (v1 triggers) |
|---|---|---|---|
| qwen3-coder-30b-a3b | 4/10 | 1/5 | KILL (T-C) |
| glm-4.7-flash | 0/12 | 3/10 | KILL (T-C) |
| llama-3.1-8b | 1/8 | 3/6 | KILL (T-A, T-C) |
| deepseek-chat-v3.1 | 7/5 | 2/8 | AMBER → survives |
| mistral-small-3.2 | 2/12 | 2/12 | KILL (T-C) |
| kimi-k2.5 (paper's model) | 3/9 (partial wave) | 3/6 | KILL (T-C) |

*In plain words: each row is one model. The two middle columns show, for each of two question wordings, how many of the wrong instructions it correctly flagged as incorrect out of 12, followed by how many of the correct instructions it also flagged (a high second number means it was just saying "incorrect" to everything). No model reached the 8-out-of-12 bar under either wording, so five of the six were eliminated and deepseek scraped through on a borderline "AMBER" call.*

The second wording (which asks the model to find the bug itself first, and lets it think before answering) was the remedy we paid for after auditing the first; **0 of 6 models clear the bar under either version**. deepseek's "7 out of 12" on the first wording was just a bias toward answering "incorrect" — it also called 7 of 12 *correct* instructions incorrect. The anchor result: **Kimi K2.5 — the paper's own subject — reads flat at about 25% under both wordings, against the 63% the paper reports**, which largely rules out the explanation that we simply asked the question badly. Explanations we cannot separate at this scale: our verified machine-drafted instructions may be harder to see through than the paper's human-written ones; the paper's question wording may differ in ways we can't see; or the model provider's own settings may differ. Whichever combination it is, on this setup the "aware" leg simply does not exist — **blindness rather than knowing compliance** — and this was one of the failure directions we registered in advance (KICKOFF risk 1c). The pilot's roster rule returned STOP; the signed decision re-scoped version 1 of the project to the compliance → damage → recovery → irrecoverability sequence on the two most capable models, with the awareness claim reported as this tier-wide non-result.

### 5.2 M1 — obedience without net damage (null #2)

All 900 single-pass trials completed (2 models × 3 conditions × 150 problems; every wrong instruction verified under protocol version 2).

**Primary — paired T2-vs-T3 drop (Newcombe, φ̂-corrected):**

| Model | drop d | 95% CI | clean pairs | verdict |
|---|---|---|---|---|
| deepseek-chat-v3.1 | +0.0400 | [−0.0218, +0.1029] | 150 | **NULL** |
| qwen3-coder-30b | +0.0362 | [−0.0343, +0.1062] | 138 | **NULL** |

*In plain words: "drop" is how much worse the wrong instruction made things compared with giving no instruction at all — 0.0400 means 4 percentage points. The bracketed range is the span of true values the data is consistent with; because both ranges contain zero, we cannot rule out that the wrong instruction made no difference whatsoever, which is what NULL means here.*

Both ranges cross zero, and neither comes close to the 10-point bar we committed to in advance. The paper's 7-to-21-point collapse does not reproduce at this tier with 150 problems.

**Arms (pass/valid, Wilson 95%):**

| Model | T1 (correct instr.) | T2 (wrong-location) | T3 (no instr.) |
|---|---|---|---|
| deepseek | 141/150 = 94.0% [89.0, 96.8] | 121/150 = 80.7% [73.6, 86.2] | 127/150 = 84.7% [78.0, 89.6] |
| qwen | 114/146 = 78.1% [70.7, 84.0] | 87/146 = 59.6% [51.5, 67.2] | 91/140 = 65.0% [56.8, 72.4] |

*In plain words: for each model and each of the three conditions, this shows how many problems were repaired successfully out of how many usable trials, as a percentage, with the plausible range in brackets. Reading across: a correct instruction helps most, no instruction is next, and a wrong instruction is worst — but the wrong-instruction and no-instruction columns overlap heavily, which is why the comparison above came back as no effect.*

The structure that *is* real: correct instructions help (correct minus none = +9.3 points for deepseek, +13.1 for qwen — instructions do steer these models), and the wrong instruction is **followed** at high rates (the model edits the named region in 129 of 150 and 127 of 146 trials) — the models patch the wrong location they were pointed at *and frequently fix the real bug anyway*. The brief's phrase for the tier-wide story is **"obedience without net damage."** Damage still happens at the level of individual trials — the wrong instruction leaves the program worse off than the original broken version in 18 of 150 = 12.0% [7.7, 18.2] of deepseek's trials and 35 of 146 = 24.0% [17.8, 31.5] of qwen's — and those damaged programs feed the next link in the sequence.

### 5.3 M2 — the recovery ceiling is alive (the M4 anchor)

On the problems where the no-instruction condition had failed (23 for deepseek, 49 for qwen), the model repairs on its own starting from the original broken program, seeing one failing test per round:

| Model | ceiling | Wilson 95% | curve (cum. by pass) | clean N | label |
|---|---|---|---|---|---|
| deepseek | 18/23 = **78.3%** | [58.1, 90.3] | [14, 17, 18, 18, 18] | 23 | REPORTED |
| qwen | 20/38 = **52.6%** | [37.3, 67.5] | [14, 16, 18, 20, 20] | 38 | REPORTED |

*In plain words: "ceiling" is how many of these previously-failed problems the model eventually fixed on its own, with the plausible range beside it. The five numbers in the curve are running totals after each of the five rounds — so deepseek reached 14 fixes after round one and only added four more across the remaining four rounds.*

Both curves are heavily front-loaded: the first round delivers 14 of deepseek's 18 total recoveries and 14 of qwen's 20 — **the active ingredient is the feedback, not the number of rounds**, when starting from a clean state. Two secondary findings matter later. First, the **damage rate with no instruction at all**: even with no saboteur present, the final state ends up worse than the original broken program in 4 of 23 = 17.4% (deepseek) and 12 of 38 = 31.6% (qwen) of clean loops — so M3's damage claim has to beat this rate, not zero. Second, **qwen's fragility when parsing its own output mid-loop**: 11 of 49 loops (22.4%) were discarded because of parsing failures partway through, and its first-attempt parse rate (116 of 144 = 80.6%) cleared the pre-committed 80% floor by only 0.6 points — a concern flagged forward to M4.

### 5.4 M3 — ghost-error compounding on the powered cell

Entry consists of the wrong-instruction states with confirmed damage (35 for qwen; 18 for deepseek plus 3 from the pre-committed extension, so 21). Every round adds a fresh, verified wrong-location instruction alongside a visible failing test.

| Model | escape | Wilson 95% | curve (cum. by pass) | clean N | label |
|---|---|---|---|---|---|
| deepseek | 10/12 = 83.3% | [55.2, 95.3] | [7, 8, 9, 9, 10] | 12 | **UNDERPOWERED** |
| qwen | 7/23 = **30.4%** | [15.6, 50.9] | **[7, 7, 7, 7, 7]** | 23 | **REPORTED** |

*In plain words: "escape" means the program reached a state where every test passes, despite being sabotaged every round. The five curve numbers are running totals by round. qwen's curve reads 7, 7, 7, 7, 7 — every single escape happened on the first round, and not one more occurred in the four rounds that followed.*

The cell with enough trials shows the paper's shape. **All of qwen's escapes happen on the first round; the curve is flat at zero for rounds 2 through 5** — 16 of 23 usable loops stay broken through four further verified wrong instructions. Its damage trajectory breaks down as: 7 escaped, 3 got worse, 9 held steady, 4 improved (12 of the 16 non-escapes end at or above the damage level they started at); the average number of failing tests per round runs 9.4 → 13.3 → 13.9 → 12.6 → 12.3 — damage spikes early and then stays pinned there. The share of loops ending below the original broken baseline is 15 of 23 = 65.2% [44.9, 81.2], against M2's no-instruction rate of 31.6% [19.1, 47.5] — a difference of **+33.6 points, Newcombe 95% range [+7.8, +53.9]**. That range excludes zero, but the comparison was **committed in advance as descriptive context, not as a pass/fail test**: M2's loops start *at* the baseline while M3's start *below* it, so the difference mixes the starting position together with the instruction pressure. We report the direction (roughly double the base rate) without claiming a controlled effect. Compliance persists even as evidence mounts against it, eroding only from 25 of 27 = 93% in round 1 to 11 of 16 = 69% in round 5.

deepseek's cell is the earlier non-result propagating forward — 83% escape among the loops we could verify — but it is honestly UNDERPOWERED: its way of complying is *rewriting the whole file*, which destroys the tracked fix region across the entire program and starves the verifier (7 of its 9 discarded loops were thrown out because the anchor could no longer be located; 42.9% of its loops were discarded overall, versus qwen's 34.3%, which is dominated by parsing failures instead). This is the **verifier's dilemma in its iterative form**: the more destructive the compliance, the less verifiable the sabotage becomes. It is the disclosed price of checking every manipulation mechanically on every round — the paper's unverified generator pays no such attrition and carries no guarantee of wrongness in return. The generator itself held up well on drifting code (34 of 36 and 100 of 104 accepted on first attempt, at average drift of 0.21 and 0.25).

**The funnel consequence, pre-declared at M3 close:** the number of states available to enter M4 — usable loops that never escaped — is **2 (deepseek) and 16 (qwen), both under 20** — so the sequence's final comparison was declared UNDERPOWERED on both models *before* M4 was even run, with no rescue available (deepseek escapes faster than its pool can supply damaged end states; qwen's shortfall is driven by discarded trials).

### 5.5 M4 — irrecoverability, descriptively

This is M2's loop exactly as written, started from the 18 frozen damaged end states; every label was declared UNDERPOWERED at entry.

**Primary — Irrecoverable Damage Rate** (paper-verbatim: never re-crosses the buggy baseline within 5 passes; denominator = damaged-at-entry per D12):

| Model | IDR | Wilson 95% | re-cross curve (cum.) | sensitivity (all clean) | label |
|---|---|---|---|---|---|
| deepseek | 0/1 = 0% | [0, 79.4] | [1, 1, 1, 1, 1] | 0/2 | UNDERPOWERED (pre-declared) |
| qwen | **6/12 = 50.0%** | [25.4, 74.6] | **[2, 3, 4, 6, 6]** | 6/12 | UNDERPOWERED (pre-declared) |

*In plain words: the rate is the share of damaged programs that never got back to being as good as the original broken version within five rounds. The curve counts, cumulatively by round, how many did get back. The "sensitivity" column repeats the calculation with every usable loop included, to show the answer does not hinge on which states were counted. Both rows are labelled UNDERPOWERED because they rest on far fewer than 20 trials — deepseek's on a single one.*

The qwen cell splits exactly in half, and the two halves look structurally different. **The six that never recover:** four never improve by even one test across five rounds of feedback (p03894, p03628, p00589, p03213 — their best state equals their starting state), and two do move but never get close to the baseline (p03713 goes from 18 failing tests to 16, against a baseline of 3; p02856 goes from 20 to 13, against a baseline of 1). And yet **nothing got worse: 0 of 12** — once the saboteur goes quiet, damage stops accumulating, no loop ends worse than it began — it just doesn't heal. **The six that do recover:** every recovery holds (the final state is at or better than the baseline; none of them backslide), four are complete fixes, and p03752 dropped from 19 failing tests to 1 in a single round. Unlike M2's first-round rush, M4's recoveries **keep arriving through round 4** — starting from a damaged state, extra rounds do real work that clean-start repair never needed. deepseek's two loops are anecdote and are labelled as such: its one genuinely damaged state was fully fixed on round 1, and its round-zero loop held at 1 failing test throughout.

**The chain gate, computed as pre-declared:**

| Model | M4 full-fix | M2 ceiling | Newcombe M2−M4 | label |
|---|---|---|---|---|
| deepseek | 1/2 | 18/23 = 78.3% | +28.3 pts [−17.0, +70.6] | UNDERPOWERED ×2 (pre-declared) |
| qwen | 4/12 = 33.3% | 20/38 = 52.6% | +19.3 pts [−12.3, +43.9] | 〃 |

*In plain words: this asks whether repair works worse from a damaged starting state than from a clean one. The middle columns give the success rate in each situation, and the fourth gives the gap between them with its plausible range. Both ranges include zero, so although the gap points the way the paper predicts, the data cannot confirm it.*

The direction matches the paper on both models (repair from damaged states does worse than from clean ones); **both ranges straddle zero, so we make no claim about a recovery gap**. The selection issue is also stated plainly: M4's population is what is left over after everything else escaped through the M1→M3 pipeline, while M2's is every failed no-instruction problem — so the comparison mixes selection together with corruption, and it is context rather than a test.

One alarm went off during the qwen run — the project's only decision not settled in advance — and was handled live by the author (recorded in `m4.py` and in the brief): when the run resumed, the smoke check read only 3 parses out of 5, with every miss caused by the model hitting its length limit. The decision was to finish under the frozen protocol and report the breach. The completed run read a first-attempt parse rate of **42 of 61 = 68.9%, below the 80% floor**; 4 loops were discarded (all for length, including qwen's round-zero loop p03593). The attrition is itself a finding: **the length of a repair response scales with how badly the code has been mangled** — truncated responses ran 9,000 to 13,000 characters against a 3,200-token budget that had been measured on pristine code, and M4's sabotage-free prompts let qwen ramble where M3's pointed instructions had kept it terse (90.3% first-attempt parse rate there). The damaged starting states sit a long way from the original code: their average similarity to the original broken program is 0.21 (deepseek) and 0.18 (qwen) — roughly 80% rewritten, compared with what M2 was repairing.

### 5.6 The chain verdict and the ledger

| Link | Paper claim | Our verdict | Key measured numbers |
|---|---|---|---|
| Precondition (M0) | aware-but-obedient | **NULL (tier-level)** | 0/6 models clear the probe gate ×2 wordings; Kimi ~25% vs paper's 63% |
| Obey (M1) | wrong-location drop | **NULL ×2** | +4.0 pts [−2.2, +10.3]; +3.6 pts [−3.4, +10.6]; comply 129/150, 127/146 |
| Recover (M2) | recovery ceiling | **REPORTED ×2** | 78.3% [58.1, 90.3]; 52.6% [37.3, 67.5]; pass-1 front-loaded |
| Compound (M3) | ghost-error compounding | **REPORTED (qwen) · UNDERPOWERED (deepseek)** | escape 30.4% [15.6, 50.9], pass-1-only; final-below-baseline 65.2% vs base 31.6% (descriptive) |
| Collapse (M4) | irrecoverability | **UNDERPOWERED ×2 (pre-declared) + descriptive IDR** | IDR 6/12 = 50% [25.4, 74.6]; M2−M4 +28.3 [−17.0, +70.6] / +19.3 [−12.3, +43.9] |

*In plain words: one row per link in the paper's four-stage sequence. The two front links came back as no effect, the middle two are reported as measured, and the final one had too few trials to judge — so what survived the move to cheap models is the shape of the back half, not the paper's headline claims.*

**Money spent** (from the per-milestone meters recorded in `data/m*/cost_ledger.json`): M0 $0.3269 · M1 $0.5840 · M2 $0.1874 · M3 $0.2549 · M4 $0.0711 — **$1.4244 in total** against the $5.00 guard (1,227 / 224 / 374 / 87 metered calls across M1 through M4), all within the caps set in advance; the one cap that did fire (M0's $0.25 pilot cap, partway through the kimi run) halted that run exactly as designed.

## 6. Discussion

**What survives the move to cheap models is the sequence's shape, not its headline results.** The paper's story starts with a model that *knows better and complies anyway*. The models at our tier comply — they edit the region they were pointed at almost every time — but they cannot reliably tell that the instruction was wrong in the first place, and their compliance produces no net drop in single-pass repair: they patch the wrong location they were given and often fix the real bug in the same breath. Both front-of-sequence claims come back as no effect, and we regard those non-results as the project's most useful output: **the paper's premise appears to need a level of competence that cheap models simply do not have.** Anyone extrapolating "top-tier models follow wrong instructions all the way into collapse" down to the cheap tier would be wrong twice over — the failure mode changes character (blindness rather than knowing compliance) and the single-pass damage disappears into the noise.

**At this tier, damage comes from *sustained* sabotage rather than single instructions.** One verified wrong instruction produces a 12–24% damage rate and no net drop. Five of them, delivered against visible failing tests, collapse the capable model's escape rate to first-round-only and pin its failure count at roughly 13 failing tests per active loop. Then, the moment the saboteur falls silent (M4), the compounding stops with it — nothing got worse, 0 of 12 — but healing does not resume for half the programs. The repository's own summary line is accurate to the data: corruption stops compounding but doesn't heal.

**The split between recoverable and unrecoverable is a sharp divide, not a gradient.** Four of qwen's six stuck programs never improve by a single test across five rounds of feedback, while the recovering half gets back across the line and keeps gaining all the way through round 4. That last point inverts M2's lesson: from clean starts, extra rounds bought almost nothing past the first; from damaged states, they did real work. At these small numbers this is direction and shape only — but it is exactly the kind of shape a larger replication could turn into a firm test.

**Honest measurement carries a measurable price, and we paid it in plain sight.** Checking every manipulation mechanically on every round cost deepseek's M3 cell its statistical power (trials discarded because the anchor vanished under wholesale rewriting) and starved the M4 comparison before it began. We consider that the right trade: the alternative — scoring manipulations nobody verified — would turn "the instruction was wrong" from a per-trial proven fact into an assumption. Two lessons banked for anyone following on: budget at least 40% slack for discarded trials when your subject rewrites whole files, and never freeze a token budget measured on pristine code and then apply it to prompts built from mangled code (response length grows with how badly the code has been damaged).

## 7. Threats to validity

- **Power.** The M4 sequence comparison and every M4 and M3-deepseek cell are UNDERPOWERED exactly as the rules automatically declared (entry pools of 2 and 16, both under 20; 12 usable loops, under 20). We report direction and ranges; none of those cells supports a firm claim. deepseek's 2-loop M4 cell is labelled anecdote.
- **Confounds we cannot remove.** The M3-versus-M2 damage comparison is confounded by the different starting states (committed in advance as descriptive); the M4-versus-M2 comparison mixes pipeline selection together with corruption. Both are disclosed everywhere they are used.
- **Manufactured manipulations.** Wrong instructions are machine-drafted with harness-chosen targets (protocol version 2) and mechanically verified — they are not the paper's human-written ones. Verified-but-synthetic instructions may be *harder to see through* than human ones, which is one candidate explanation for the awareness non-result; we cannot separate it from question wording or provider settings on this budget, and we say so rather than pick a side.
- **Our problem set is not the paper's.** The paper's 538-problem filter is unpublished; ours is committed in advance but different (notably the room-to-get-worse and locality requirements), as are our prompts. Comparisons are about structure, never point-for-point numbers.
- **Two subjects, one language, one dataset, one provider.** Cheap-tier serving through OpenRouter may differ from the paper's deployments in ways we cannot see (compression of the model's weights, default sampling settings). Our exact-match grading is stricter than tolerance-based alternatives (the pre-registered looser numeric variant graded 98% fidelity against exact matching's 95% at the quality check; exact matching was adopted under the frozen rule).

## 8. Conclusion

We set out to re-run and measure a four-claim failure sequence on cheap models with every verdict committed in advance as working code, and we closed the sequence end to end for $1.4244: **obey came back as no effect on both models · recovery is reported on both (78.3% / 52.6%) · compounding is reported on the cell that had enough trials (first-round-only escape at 30.4%) · collapse is underpowered on both exactly as pre-declared, with a descriptive stuck-half of 50% (6 of 12).** The awareness precondition itself failed to reproduce across six cheap models, including the paper's own Kimi K2.5. None of this contradicts the paper on its own home ground of top-tier models; it maps where the sequence's claims do and do not survive the trip down-market, and it shows that a fully honest reproduction — non-results headlined, judgement rules frozen before the data, every manipulation proven wrong on every trial — fits inside a $5 hobby budget. The natural next step (parked, and gated): the cure question — does putting the failing-test evidence, or explicit permission to refuse, into the instruction prompt break the compliance, and does it unstick the stuck half?

## 9. Reproducibility and artifacts

Everything needed to audit or re-run this work lives in the repository: the verdict scripts with their subcommands (`m0.py`–`m4.py`), the frozen problem set and pool (`data/bank.json`, `data/pool.json`), per-trial records and per-milestone cost ledgers (`data/m1/`–`data/m4/`), machine-readable results (`data/m*_results.json`), signed per-milestone briefs carrying the decisions made in advance with results appended (`docs/M0-BRIEF.md`–`docs/M4-BRIEF.md`), hand-checked samples of accepted wrong instructions (`docs/*-SPOTREAD.md`), checksum-pinned data fetching (`fetch_runbugrun.py`), and 256 passing tests. The raw RunBugRun data is excluded from the repository but can be re-downloaded; every artifact derived from it is committed.

## References

The repository deliberately records sources by identifier/URL rather than full bibliographies; we cite exactly what is recorded and add nothing:

1. *Obey, Diverge, Collapse* — arXiv 2607.04537, v1 2026-07-05 (9 pp). The reproduced paper. (Author list not recorded in the project notes; its promised code appendix is absent from v1.)
2. RunBugRun — dataset and JSONL data release v0.0.1: `github.com/giganticode/run_bug_run_data` (fetched with pinned MD5s; see `fetch_runbugrun.py`).
3. PIE4Perf problem statements — `github.com/madaan/pie-perf`, `problem_statements_translated.zip` (RunBugRun's credited translation source; pinned SHA-256).
4. Wilson score interval and Newcombe difference intervals (unpaired square-and-add "method 10"; paired 1998 variant with φ̂ correction) — as named and implemented in `stats.py`; the guardrail statistics here reproduce established practice rather than new methodology.
