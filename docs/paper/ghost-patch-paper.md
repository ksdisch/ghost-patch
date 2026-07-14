# Ghost-Patch: A Pre-Committed, Hobby-Scale Reproduction of the "Obey, Diverge, Collapse" Failure Chain on Cheap Code Models

**Kyle Disch** · [github.com/ksdisch/ghost-patch](https://github.com/ksdisch/ghost-patch) · 2026-07-12

*Fourth in a lineage of reproduce-and-measure projects (forge-gap → decay-pin → lossy-wall). All numbers in this paper are lifted verbatim from the repository's committed records — the milestone briefs (`docs/M0-BRIEF.md` … `docs/M4-BRIEF.md`) and their machine copies (`data/m1_results.json` … `data/m4_results.json`). No result is re-derived here. A note on figures: the project recorded all results as tables and JSON; no figure images exist in the repository, so this paper contains tables only.*

---

## Abstract

"Obey, Diverge, Collapse" (arXiv 2607.04537, v1 2026-07-05) reports a four-stage failure chain in code-repair LLMs: models recognize a wrong-location repair instruction as incorrect yet follow it, introduce new "ghost errors," compound them across iterative passes, and land in states that self-guided repair cannot recover. We independently reproduce and measure the chain's *structure* on two cheap models (deepseek-chat-v3.1, qwen3-coder-30b-a3b-instruct) over a 186-problem RunBugRun bank, under a fully pre-committed protocol: deterministic sandboxed grading, per-trial mechanical verification of every injected wrong instruction, verdict gates frozen as code before any paid run, Wilson/Newcombe intervals, and N≥20 per gated cell or automatic UNDERPOWERED. Two links fail honestly at this tier, and we report them as headlines: the awareness precondition does not reproduce (0/6 piloted models clear the probe gate under two wordings; the paper's own Kimi K2.5 reads ~25% aware here vs its reported 63%), and the single-pass repair drop is NULL on both subjects (+4.0 pts [−2.2, +10.3]; +3.6 pts [−3.4, +10.6]). The chain's back half is visible where powered: feedback-driven self-repair recovers 78.3%/52.6% from clean starts, but under sustained verified sabotage qwen escapes only at pass 1 (30.4%, flat after), and afterward half its corrupted states (6/12) never re-cross the buggy baseline in five saboteur-free passes. The M4-vs-M2 gate lands UNDERPOWERED ×2 exactly as pre-declared, direction matching the paper. Total spend: $1.42.

---

## 1. Introduction

Iterative LLM code repair has a claimed failure mode that is qualitatively worse than "the model can't fix the bug": under a confident but misdirected instruction, the model damages working structure, the damage compounds across repair iterations, and the final state is unrecoverable even relative to the original buggy program. "Obey, Diverge, Collapse" (arXiv 2607.04537) published this chain days before this project began, on five frontier models, with a promised code appendix that is absent from v1. It is unreplicated, and its filter, prompts, and harness are unpublished.

This paper's contribution is deliberately narrow: an **independent, pre-committed, hobby-budget reproduction** of the chain's four claims on cheap models, with every verdict rendered by a script that was written and dry-run before the paid data existed. We do not invent mechanisms, we do not chase the paper's point estimates (direction and structure only), and we treat null results as first-class findings. Under this discipline the project produced:

1. **Two headline nulls.** The paper's "aware-but-obedient" premise does not reproduce at the cheap tier — evaluator-role awareness sits near chance across six models under two probe wordings (§5.1) — and the single-pass wrong-location repair drop is indistinguishable from zero on both surviving subjects at N=150 (§5.2). Cheap models here are *blind* and obedient, and obedience alone does not produce net single-pass damage.
2. **The chain's back half, measured.** Where the funnel stayed powered, the paper's structure appears: escape from sustained, mechanically-verified sabotage collapses to pass-1-only (§5.4), and half of the resulting corrupted states never re-cross the buggy baseline once the saboteur stops (§5.5) — with the pre-declared caveat that the final gate is underpowered by measured funnel attrition, not by design choice.
3. **A reproducible harness and a negative-space record.** A Docker-sandboxed, judge-free grading pipeline over RunBugRun; a manipulation generator whose wrongness is *proven per trial* rather than assumed; and two transferable measurement lessons (the verifier's-dilemma attrition and parse-budget scaling with corruption depth, §6).

Everything below states plainly what is manufactured (all wrong instructions and all corrupted states are injected faults, verified as such), what is null, and what is underpowered.

## 2. The target paper and its claims

As extracted into the repository's records (`docs/M0-BRIEF.md`, "What the paper settles"), the paper tests five frontier models (GPT-5.3 Codex, Sonnet 4.6, Qwen3-Coder, GLM-5, Kimi K2.5) on 538 filtered problems and claims:

- **RQ1 (obey):** given a buggy program, its problem statement, and a confident instruction that misidentifies the bug's location (T2), models repair worse than with no instruction (T3) — pass-rate drops of ≈7–21 points — *while* an evaluator-role probe shows they can label the same instruction INCORRECT (weakest model: Kimi K2.5 at 340/538 ≈ 63%). The awareness/failure pairing is the paper's McNemar headline (reported p < 0.001 on all five models).
- **RQ2 (recovery ceiling):** on failed-T3 instances, self-guided repair with the most recent failing test, max 5 passes, early stop on all-tests-pass.
- **RQ3 (diverge/compound):** from T2 trials with confirmed damage (failed-test count above the buggy baseline), 5 more passes each carrying a fresh LLM-generated wrong instruction (generator sees only current code — the paper uses GPT-5.1 Codex); entry populations run 5–22% of 538 per model.
- **RQ4 (collapse):** RQ2's protocol from RQ3's corrupted finals; **Irrecoverable Damage Rate (IDR)** = fraction never re-crossing the buggy-patch baseline within 5 passes.

The paper's v1 ships no code, prompts, or data (its Appendix 9 is ethics only), so every prompt and filter below is ours, structure-faithful to the paper's §3 descriptions. All deviations are owned in per-milestone tables in the briefs (13 rows total).

## 3. Methods

### 3.1 Task, data, and the frozen bank

The task is single-file Python program repair: given a buggy program and its problem statement, produce a complete corrected program, graded against hidden stdin/stdout test pairs. Data is the RunBugRun Python subset (JSONL release v0.0.1: `python_test0` = 9,611 bugs / 1,342 problems; `python_valid0` = 2,054 / 671; `tests_all` = 3,926 problems' test pairs), with English problem statements from PIE4Perf — RunBugRun's own credited translation source — at ≈100% coverage (1,340/1,342 and 670/671). Fetches are checksum-pinned (`fetch_runbugrun.py`).

The paper's 538-problem filter is unpublished, so the bank is our own **pre-committed two-stage filter** (`filter_bank.py`), written before any paid call. Stage 1 (static): both versions compile under CPython 3.12; usable English description; ≥3 tests (candidate set capped at 20); 3–40 non-blank lines; the true fix is local (≤2 hunks, ≤6 changed lines, computed from our own normalized diff) with ≥5 lines outside the fix region; one bug per problem (independence — Wilson/Newcombe assume it). This yields a **frozen pool of 1,062 problems** (from 11,665 bugs seen), shuffled once with seed 2607. Stage 2 (free sandbox smoke over the pool prefix): the fixed reference passes all selected tests, the buggy version fails ≥1 **and passes ≥1** — the *damage-headroom* requirement, without which "more failures than baseline" is inexpressible (about a third of smoked problems failed it).

**Harness fidelity was gated, and the gate initially failed.** The pre-registered fidelity gate T-E (fixed passes everything, buggy fails something, on ≥90% of smoked problems) first read **86.0%** (S-exact) / 88.3% (S-float) on 300 problems. Diagnosis: test-*selection* infidelity — 30/35 failures were bugs whose exposing test lay outside the lowest-20-by-id cap. The one allowed tightening (exposure-aware selection, 29 swaps) brought the re-smoke to **95.0% / 98.0%, PASS**, and the stricter **S-exact** semantics was adopted and frozen. The bank froze at **186 problems** (`data/bank.json`); the M1 primary runs on the first 150; growth only ever extends the frozen prefix.

### 3.2 Sandboxed, deterministic grading

Candidate programs execute in a per-program Docker container (`python:3.12-slim`, `--network=none`, 1 CPU, 512 MB, pids-limit 128, read-only FS, non-root), each test a fresh process with a 5 s wall timeout. Grading happens **host-side** under the frozen S-exact semantics (rstrip lines, drop trailing blanks, exact match) — the container never sees expected outputs, so a program cannot grade itself. PASS/FAIL is deterministic; there are no LLM judges anywhere in the project.

### 3.3 The manipulation, and why its wrongness is provable

T1 (correct instruction), T2 (wrong-location instruction), T3 (no instruction). All instructions are **manufactured faults**: LLM-drafted by a fixed non-subject generator (`openai/gpt-5.1-codex-mini`, reasoning pinned low) as structured fields (target lines, anchor excerpt, diagnosis, directive) rendered through a fixed fluent template. Every T2 draft must survive a **mechanical verifier**: (a) the anchor excerpt matches the code at the cited lines; (b) the target region ±1 line is provably disjoint from the true-fix region F (computed by normalized diff); (c) no whitespace-normalized added line of the true fix appears in the instruction (no fix leak). Unverifiable drafts never enter a trial; affected trials are INVALID — excluded from every denominator, counted, and reported.

Free-choice drafting failed honestly: the generator *found the real bug* in a ≤40-line program most of the time (first-attempt verifier acceptance 5/20 = 25%; 39/41 rejections were non-disjointness). The one allowed revision — **protocol v2, harness-picked targets**: the harness deterministically assigns a provably-disjoint region (seeded per problem) and the generator writes only the confident rationale — recovered acceptance to 13/13 (100%) and mirrors the paper's *deliberately* misdirected human T2s. In M3, where code drifts every pass, F is re-anchored by mapping it through a normalized diff (`regions.map_fix_region`) with **conservative over-approximation** — the wrongness guarantee never weakens; the cost is INVALID attrition, counted by cause. One scope limit is stated up front in the brief: the verifier proves disjointness from the *original* fix region as mapped forward; no oracle exists for ghost errors introduced mid-loop (the paper's unverified generator has the same exposure, without the guarantee).

### 3.4 Statistics, gates, and budget discipline

Every gated rate is a proportion with a **Wilson score interval**; between-arm differences use **Newcombe intervals** (the square-and-add method 10 for unpaired contrasts; the 1998 paired variant with φ̂ discordance correction for M1's within-problem T2-vs-T3 drop) — implemented in `stats.py`, unit-tested, no external stats dependencies. An interval that includes zero is a null/small effect and is stated as such; boundary-touching does not count as exclusion. Any gated cell with fewer than 20 clean trials **auto-reports UNDERPOWERED — no rescue, no exception**. Verdicts are per-model, never pooled. Every verdict script (`m0.py`–`m4.py`) was written, unit-tested (256 tests green by M4), and dry-run on synthetic fixtures **before** the paid wave it judges; kill/swap/halt triggers were committed before the runs they govern. Each milestone ran under a hard cost cap with a check-before-call meter and a $5.00 lifetime guard; measured-rate cost estimates and ~5-call smoke gates preceded every paid wave.

## 4. Experimental setup

**Subjects.** Six cheap OpenRouter models entered the M0 pilot (roster: qwen3-coder-30b-a3b-instruct, glm-4.7-flash, llama-3.1-8b-instruct; bench: deepseek-chat-v3.1, mistral-small-3.2-24b-instruct, kimi-k2.5 — the paper's own Kimi). Pre-committed pilot triggers killed four (§5.1); the chain ran on **deepseek-chat-v3.1** ($0.21/$0.79 per M tokens) and **qwen3-coder-30b-a3b-instruct** ($0.07/$0.27) — the latter a cheap kin of a paper model. Subject reasoning disabled; repair budget 3,200 tokens (measured floor); parse = last fenced code block, `compile()`-clean, one bare retry then INVALID.

**The five milestones.**

- **M0 (fit-pilot):** first 12 bank problems × {T1, T2, T3} + 24 evaluator probes per model, against pre-committed capability/skepticism/awareness/parse triggers; plus the harness, bank, and generator gates of §3.
- **M1 (RQ1 analog, re-scoped):** single-pass repair, 3 arms × 150 problems × 2 models, paired design. Primary: T2-vs-T3 pass-rate drop (paired Newcombe; REPRODUCED needs CI excluding 0 *and* drop ≥ 10 pts). After M0's awareness null, the probe/McNemar leg was dropped by signed disposition — M1 claims only the behavioral drop.
- **M2 (RQ2):** on each model's failed-T3 subset, self-guided repair from the *original buggy program*: per pass the model sees statement + current code + the first failing test (input, expected, actual; 1,000-char truncation), max 5 passes, early stop on all-tests-pass. No manipulation. Output: the recovery ceiling and curve — M4's anchor.
- **M3 (RQ3):** from each model's confirmed-damage T2 states (deepseek's entry extended by a pre-committed 36-problem T2-only wave along the frozen order), the same loop plus a **fresh verified wrong instruction every pass** (generator sees only current code). Escape = all tests pass despite sabotage. Descriptive by pre-commitment.
- **M4 (RQ4):** M2's loop verbatim from M3's frozen corrupted finals (byte-identical start states, grade-0 integrity checks). Primary: **IDR**, paper-verbatim. A pre-run population pin (D12): two entry states sat at/below baseline (they improved during M3 without escaping) and re-cross at pass 0 by definition — all 18 run, but the IDR denominator is the 16 damaged-at-entry states, with the pair reported separately and an all-18 sensitivity line.

Every loop's start state and every rendered feedback block is mechanically re-verified against the frozen record (grade-0 integrity: 72/72 in M2, 56/56 in M3, 18/18 in M4 — the harness-drift halt never fired).

## 5. Results

### 5.1 M0 — the awareness precondition fails across the tier (null #1)

Obedience is emphatically present in the pilot — every model mechanically complies with the wrong-location instruction on 9–11 of 12 problems, and damage occurs — but **evaluator-role awareness sits near chance everywhere**. Per the pre-committed probe trigger (green ≥ 8/12 INCORRECT on T2 instructions with T1-side sanity):

| Model | probe v1 (T2✓/T1✓) | probe v2 (T2✓/T1✓) | pilot verdict (v1 triggers) |
|---|---|---|---|
| qwen3-coder-30b-a3b | 4/10 | 1/5 | KILL (T-C) |
| glm-4.7-flash | 0/12 | 3/10 | KILL (T-C) |
| llama-3.1-8b | 1/8 | 3/6 | KILL (T-A, T-C) |
| deepseek-chat-v3.1 | 7/5 | 2/8 | AMBER → survives |
| mistral-small-3.2 | 2/12 | 2/12 | KILL (T-C) |
| kimi-k2.5 (paper's model) | 3/9 (partial wave) | 3/6 | KILL (T-C) |

The v2 wording (locate-the-bug-yourself-first, reasoning allowed) was the funded audit remedy; **0/6 models clear the gate under either wording**. deepseek's v1 "7/12" was INCORRECT-leaning response bias (it also called 7/12 *correct* instructions incorrect). The anchor result: **Kimi K2.5 — the paper's own subject — reads flat at ~25% under both wordings against the paper's reported 63%**, which substantially rules out simple probe under-elicitation. Residual explanations that cannot be separated at hobby scale: our verified LLM-drafted instructions may be harder to discriminate than the paper's human-written ones; unpublished probe differences; provider-side configuration. Whichever mix it is, on this setup the "aware" leg does not exist — **blindness, not blind obedience** — a pre-registered failure direction (KICKOFF risk 1c). M0's roster rule rendered STOP; the signed disposition re-scoped v1 to the obedience → damage → recovery → irrecoverability chain on the two most capable models, with the awareness claim reported as this tier-level null.

### 5.2 M1 — obedience without net damage (null #2)

900/900 single-pass trials (2 models × 3 arms × 150 problems; all T2 instructions protocol-v2 verified).

**Primary — paired T2-vs-T3 drop (Newcombe, φ̂-corrected):**

| Model | drop d | 95% CI | clean pairs | verdict |
|---|---|---|---|---|
| deepseek-chat-v3.1 | +0.0400 | [−0.0218, +0.1029] | 150 | **NULL** |
| qwen3-coder-30b | +0.0362 | [−0.0343, +0.1062] | 138 | **NULL** |

Both CIs cross zero and neither approaches the pre-committed 10-point bar. The paper's 7–21-point collapse does not reproduce at this tier at N=150.

**Arms (pass/valid, Wilson 95%):**

| Model | T1 (correct instr.) | T2 (wrong-location) | T3 (no instr.) |
|---|---|---|---|
| deepseek | 141/150 = 94.0% [89.0, 96.8] | 121/150 = 80.7% [73.6, 86.2] | 127/150 = 84.7% [78.0, 89.6] |
| qwen | 114/146 = 78.1% [70.7, 84.0] | 87/146 = 59.6% [51.5, 67.2] | 91/140 = 65.0% [56.8, 72.4] |

The structure that *is* real: correct instructions help (T1 − T3 = +9.3 pts deepseek, +13.1 qwen — instructions steer these models), and the wrong instruction is **obeyed** at high rates (region-compliance 129/150 and 127/146) — the models patch the named wrong location *and still often fix the real bug anyway*. The brief's phrase for the tier-level story: **"obedience without net damage."** Damage still occurs at trial level — T2 leaves the program worse than the buggy baseline in 18/150 = 12.0% [7.7, 18.2] (deepseek) and 35/146 = 24.0% [17.8, 31.5] (qwen) — feeding the chain's next links.

### 5.3 M2 — the recovery ceiling is alive (the M4 anchor)

On failed-T3 subsets (23 deepseek / 49 qwen), self-repair from the buggy original with one failing test visible per pass:

| Model | ceiling | Wilson 95% | curve (cum. by pass) | clean N | label |
|---|---|---|---|---|---|
| deepseek | 18/23 = **78.3%** | [58.1, 90.3] | [14, 17, 18, 18, 18] | 23 | REPORTED |
| qwen | 20/38 = **52.6%** | [37.3, 67.5] | [14, 16, 18, 20, 20] | 38 | REPORTED |

Both curves are front-loaded: pass 1 delivers 14/18 and 14/20 of all recovery — **feedback, not iteration depth, is the active ingredient** on clean starts. Two secondaries matter downstream. First, the **no-instruction self-damage base rate**: even without any saboteur, the final state ends worse than the buggy baseline in 4/23 = 17.4% (deepseek) and 12/38 = 31.6% (qwen) of clean loops — M3's damage claim must clear this, not zero. Second, **qwen's loop-parse fragility**: 11/49 loops (22.4%) went INVALID on mid-loop parse failures, and its first-parse rate (116/144 = 80.6%) cleared the pre-committed 80% floor by 0.6 points — flagged forward to M4.

### 5.4 M3 — ghost-error compounding on the powered cell

Entry = confirmed-damage T2 states (qwen 35; deepseek 18 + 3 from the pre-committed extension = 21). Each pass adds a fresh, verified wrong-location instruction against a visible failing test.

| Model | escape | Wilson 95% | curve (cum. by pass) | clean N | label |
|---|---|---|---|---|---|
| deepseek | 10/12 = 83.3% | [55.2, 95.3] | [7, 8, 9, 9, 10] | 12 | **UNDERPOWERED** |
| qwen | 7/23 = **30.4%** | [15.6, 50.9] | **[7, 7, 7, 7, 7]** | 23 | **REPORTED** |

The powered cell shows the paper's shape. **All of qwen's escapes are pass-1; the curve is flat at zero for passes 2–5** — 16/23 clean loops stay corrupted through four more verified wrong instructions. Its damage trajectory: escaped 7 / deepened 3 / held 9 / improved 4 (12/16 non-escapes end at or above their damaged start); mean failed tests per pass runs 9.4 → 13.3 → 13.9 → 12.6 → 12.3 — damage jumps early and stays pinned. Final-below-baseline hits 15/23 = 65.2% [44.9, 81.2] against M2's no-instruction base rate of 31.6% [19.1, 47.5] — a delta of **+33.6 points, Newcombe 95% CI [+7.8, +53.9]**. That interval excludes zero, but the comparison was **pre-committed as descriptive context, not a gate**: M2's loops start *at* baseline, M3's start *below* it, so the delta bundles start state with instruction pressure. We report the direction (roughly double the base rate) without claiming a controlled effect. Obedience persists under contradicting evidence, eroding from 25/27 = 93% (pass 1) to 11/16 = 69% (pass 5).

deepseek's cell is the M1 null propagating — 83% escape among verifiable loops — but it is UNDERPOWERED honestly: its corruption mode is *wholesale rewriting*, which collapses the drift-mapped fix region over the whole file and starves the verifier (7 of its 9 INVALID loops were `anchor-unresolvable`; 42.9% loop-INVALID overall vs qwen's 34.3%, which is parse-dominant). This is the **verifier's dilemma, iterative edition**: the more destructive the obedience, the less verifiable the manipulation. It is the disclosed price of per-pass mechanical verification — the paper's unverified generator pays no attrition and carries no wrongness guarantee. The generator itself held up on drifted code (first-attempt acceptance 34/36 and 100/104 at mean drift 0.21/0.25).

**The funnel consequence, pre-declared at M3 close:** M4 entry = clean non-escaped finals = **2 (deepseek) and 16 (qwen), both < 20** — so the chain gate was declared UNDERPOWERED ×2 *before* M4 ran, with no rescue possible (deepseek escapes faster than its pool supplies corrupted finals; qwen's attrition is INVALID-driven).

### 5.5 M4 — irrecoverability, descriptively

M2's loop verbatim from the 18 byte-frozen corrupted finals; every label pre-declared UNDERPOWERED at entry.

**Primary — Irrecoverable Damage Rate** (paper-verbatim: never re-crosses the buggy baseline within 5 passes; denominator = damaged-at-entry per D12):

| Model | IDR | Wilson 95% | re-cross curve (cum.) | sensitivity (all clean) | label |
|---|---|---|---|---|---|
| deepseek | 0/1 = 0% | [0, 79.4] | [1, 1, 1, 1, 1] | 0/2 | UNDERPOWERED (pre-declared) |
| qwen | **6/12 = 50.0%** | [25.4, 74.6] | **[2, 3, 4, 6, 6]** | 6/12 | UNDERPOWERED (pre-declared) |

The qwen cell splits in half, and the halves are structurally distinct. **The irrecoverable six:** four never improve by a single test across five feedback passes (p03894, p03628, p00589, p03213 — best equals start), two move but never near baseline (p03713: 18→16 failed vs baseline 3; p02856: 20→13 vs baseline 1). Yet **deepened = 0/12**: with the saboteur silenced, damage stops compounding — no loop ends worse than it started — it just doesn't heal. **The recovering six:** every re-cross is durable (final ≤ baseline; zero transient), four are full fixes, and p03752 fell 19→1 failed in a single pass. Unlike M2's pass-1 front-load, M4's re-crosses **accrue through pass 4** — from corrupted states, iteration depth does real work that clean-start repair never needed. deepseek's two loops are anecdote and labeled so: its one damaged final full-fixed at pass 1; its pass-0 loop held at 1 failed throughout.

**The chain gate, computed as pre-declared:**

| Model | M4 full-fix | M2 ceiling | Newcombe M2−M4 | label |
|---|---|---|---|---|
| deepseek | 1/2 | 18/23 = 78.3% | +28.3 pts [−17.0, +70.6] | UNDERPOWERED ×2 (pre-declared) |
| qwen | 4/12 = 33.3% | 20/38 = 52.6% | +19.3 pts [−12.3, +43.9] | 〃 |

Direction matches the paper on both models (M4 < M2); **both CIs straddle zero, so no recovery-gap claim is made**. The selection confound is also stated: M4's population is the never-escaped residue of the M1→M3 funnel while M2's is all failed-T3 — the contrast bundles selection with corruption and is context, not a gate.

One trigger fired during the qwen wave — the project's only non-pre-committed decision — and was disposed live by the author (recorded in `m4.py` and the brief): the resumed wave's smoke gate re-read parse 3/5, every miss `finish_reason=length`. The disposition: finish under the frozen protocol and report the breach. The completed wave read first-parse **42/61 = 68.9%, below the 80% floor**; 4 loops INVALID (all parse-length, including the qwen pass-0 loop p03593). The attrition is itself a finding: **repair-response length scales with corruption depth** — truncated responses ran 9–13k characters against a 3,200-token budget that was measured on pristine code, and M4's saboteur-free prompts make qwen ramble where M3's targeted instructions kept it terse (90.3% first-parse there). The corrupted starts sit far from the original code: mean similarity ratio to the buggy program 0.21 (deepseek) / 0.18 (qwen) — roughly 80% rewritten relative to what M2 repaired.

### 5.6 The chain verdict and the ledger

| Link | Paper claim | Our verdict | Key measured numbers |
|---|---|---|---|
| Precondition (M0) | aware-but-obedient | **NULL (tier-level)** | 0/6 models clear the probe gate ×2 wordings; Kimi ~25% vs paper's 63% |
| Obey (M1) | wrong-location drop | **NULL ×2** | +4.0 pts [−2.2, +10.3]; +3.6 pts [−3.4, +10.6]; comply 129/150, 127/146 |
| Recover (M2) | recovery ceiling | **REPORTED ×2** | 78.3% [58.1, 90.3]; 52.6% [37.3, 67.5]; pass-1 front-loaded |
| Compound (M3) | ghost-error compounding | **REPORTED (qwen) · UNDERPOWERED (deepseek)** | escape 30.4% [15.6, 50.9], pass-1-only; final-below-baseline 65.2% vs base 31.6% (descriptive) |
| Collapse (M4) | irrecoverability | **UNDERPOWERED ×2 (pre-declared) + descriptive IDR** | IDR 6/12 = 50% [25.4, 74.6]; M2−M4 +28.3 [−17.0, +70.6] / +19.3 [−12.3, +43.9] |

**Spend** (per-milestone meters, `data/m*/cost_ledger.json` records): M0 $0.3269 · M1 $0.5840 · M2 $0.1874 · M3 $0.2549 · M4 $0.0711 — **lifetime $1.4244** against the $5.00 guard (1,227 / 224 / 374 / 87 metered calls across M1–M4), all inside pre-committed caps; the one cap that fired (M0's $0.25 pilot cap, mid-kimi) halted the wave as designed.

## 6. Discussion

**What reproduces at the cheap tier is the chain's structure, not its headline gates.** The paper's story begins with a model that *knows better and obeys anyway*. Our tier's models obey — region-compliance is near ceiling everywhere — but cannot reliably classify the instruction as wrong in the first place, and their obedience produces no net single-pass repair drop: they patch the named wrong location and often fix the real bug in the same response. Both front-of-chain claims land NULL, and we regard those nulls as the project's most decision-relevant output: **the paper's premise appears to require a competence floor that cheap models do not clear.** A practitioner extrapolating "frontier models obey wrong instructions into collapse" down-market would be wrong twice — the failure mode changes shape (blindness, not blind obedience) and the single-pass damage vanishes into noise.

**Damage at this tier is a property of *sustained* sabotage, not single instructions.** One verified wrong instruction: a 12–24% damage rate and a null net drop. Five of them against visible failing tests: the powered model's escape collapses to pass-1-only and its failure count pins at roughly 13 failed tests per active loop. Then, the moment the saboteur stops (M4), compounding stops with it — deepened 0/12 — but healing doesn't resume for half the states. The repo's summary line is accurate to the data: corruption stops compounding but doesn't heal.

**The recoverable/irrecoverable split is structural, not gradual.** Four of qwen's six stuck states never improve by one test in five feedback passes, while the recovering half re-crosses durably and keeps gaining through pass 4. That last point inverts M2's lesson: on clean starts iteration depth bought almost nothing beyond pass 1; from corrupted states it did real work. At these Ns this is direction and structure only — but it is the kind of structure a scaled replication could gate.

**Honest measurement has a measurable price, and we paid it visibly.** Per-pass mechanical verification cost deepseek's M3 cell its power (anchor-unresolvable attrition under wholesale rewriting) and pre-starved the M4 gate. We consider this the right trade: the alternative — scoring unverified manipulations — would make "the instruction was wrong" an assumption rather than a per-trial theorem. The two banked lessons for any successor: budget ≥40% INVALID slack for wholesale-rewriter subjects, and never freeze a token budget measured on pristine code for corrupted-start prompts (response length scales with corruption depth).

## 7. Threats to validity

- **Power.** The M4 chain gate and all M4/M3-deepseek cells are UNDERPOWERED exactly as auto-declared (entry 2/16 < 20; clean 12 < 20). We report direction and CIs; none of those cells supports a gated claim. deepseek's 2-loop M4 cell is labeled anecdote.
- **Confounds we cannot remove.** The M3-vs-M2 damage delta is start-state-confounded (pre-committed as descriptive); the M4-vs-M2 contrast bundles funnel selection with corruption. Both are disclosed at every use.
- **Manufactured manipulations.** Wrong instructions are LLM-drafted with harness-picked targets (protocol v2) and mechanically verified — not the paper's human-written T2s. Verified-but-synthetic instructions may be *harder to discriminate* than human ones, which is one candidate explanation for the awareness null; we cannot separate it from probe wording or provider configuration at this budget, and we say so rather than adjudicate.
- **Bank ≠ paper's bank.** The paper's 538-problem filter is unpublished; ours is pre-committed but different (notably damage headroom and locality requirements), as are our prompts. Comparisons are structural, never point-to-point.
- **Two subjects, one language, one dataset, one provider.** Cheap-tier OpenRouter serving may differ from the paper's deployments in unknown ways (quantization, sampling defaults). S-exact grading is stricter than tolerance-based alternatives (the pre-registered S-float variant graded 98% fidelity vs S-exact's 95% at the gate; S-exact was adopted per the frozen rule).

## 8. Conclusion

We set out to reproduce and measure a four-claim failure chain on cheap models with the verdicts pre-committed as code, and we closed the chain end-to-end for $1.4244: **obey NULL ×2 · recover REPORTED ×2 (78.3%/52.6%) · compound REPORTED on the powered cell (pass-1-only escape at 30.4%) · collapse UNDERPOWERED ×2 as pre-declared, with a descriptive 50% stuck-half (IDR 6/12).** The awareness precondition itself failed to reproduce across six cheap models including the paper's own Kimi K2.5. None of this contradicts the paper on its own (frontier) turf; it maps where the chain's claims do and do not survive the move to bottom-tier models, and it demonstrates that a fully honest reproduction — nulls headlined, gates frozen before data, every manipulation proven wrong per trial — fits inside a $5 hobby budget. The natural next arm (parked, gated): the cure question — does putting the failing-test evidence or an explicit refusal license into the instruction prompt collapse obedience, and does it unstick the stuck half?

## 9. Reproducibility and artifacts

Everything needed to audit or re-run lives in the repository: verdict scripts with subcommands (`m0.py`–`m4.py`), the frozen bank and pool (`data/bank.json`, `data/pool.json`), per-trial JSONL artifacts and per-milestone cost ledgers (`data/m1/`–`data/m4/`), machine-readable results (`data/m*_results.json`), signed per-milestone briefs with pre-committed decisions and RESULTS appended (`docs/M0-BRIEF.md`–`docs/M4-BRIEF.md`), face-validity samples of accepted wrong instructions (`docs/*-SPOTREAD.md`), checksum-pinned data fetching (`fetch_runbugrun.py`), and 256 passing tests. Raw RunBugRun data is gitignored but refetchable; every derived artifact is committed.

## References

The repository deliberately records sources by identifier/URL rather than full bibliographies; we cite exactly what is recorded and add nothing:

1. *Obey, Diverge, Collapse* — arXiv 2607.04537, v1 2026-07-05 (9 pp). The reproduced paper. (Author list not recorded in the project notes; its promised code appendix is absent from v1.)
2. RunBugRun — dataset and JSONL data release v0.0.1: `github.com/giganticode/run_bug_run_data` (fetched with pinned MD5s; see `fetch_runbugrun.py`).
3. PIE4Perf problem statements — `github.com/madaan/pie-perf`, `problem_statements_translated.zip` (RunBugRun's credited translation source; pinned SHA-256).
4. Wilson score interval and Newcombe difference intervals (unpaired square-and-add "method 10"; paired 1998 variant with φ̂ correction) — as named and implemented in `stats.py`; the guardrail statistics here reproduce established practice rather than new methodology.
