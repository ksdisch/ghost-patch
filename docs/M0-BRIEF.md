# M0 Start-of-Stage Brief — the fit-pilot

*Written 2026-07-10 · status: **DRAFT — awaiting Kyle sign-off** (gate: no paid OpenRouter call
runs before sign-off on this brief + the cost estimate) · scope source of truth: `docs/KICKOFF.md`*

## What M0 is, in plain terms

Before the experiment spends real tokens, M0 answers the questions that could kill the
project — cheaply, and with the kill criteria written down *before* the pilot runs:

1. **Do cheap models exhibit blind obedience at all?** (KICKOFF risk 1.) The whole chain
   conditions on it, and it can fail three distinct ways per model: too skeptical (resists
   the wrong instruction), too weak (can't repair anything, so there's no drop to measure),
   or blind (can't classify the instruction in the evaluator role — then it's blindness,
   not blind *obedience*, and the paper's headline contrast collapses).
2. **Can our harness grade code honestly?** (Risk 2.) RunBugRun tests must run locally with
   clean semantics. If the fixed reference doesn't pass its own tests, every downstream
   number is noise.
3. **Does the instruction machinery work?** (Risks 3, 4.) LLM-drafted wrong instructions
   must survive mechanical verification at a workable rate, and subject models must return
   parseable patches.
4. **What bank size does the funnel demand?** (Risk 5.) M3 only receives T2-*damaged*
   trials; the bank is sized from measured rates, never guessed.

M0 also builds all of the machinery — fetch, filter, sandbox, grading, stats, verdict
script — and proves the free parts green **before any paid call**.

## What the paper settles (PDF re-fetched 2026-07-10; v1, 9 pp)

Protocol facts extracted from the paper body that bind our design. (Appendix 9 is
confirmed to be ethical considerations only — the promised code/prompts/data do **not**
exist in v1, so all prompt wording below is ours, structure-faithful; see Deviations.)

1. **RQ1 is three settings per problem.** T1: instruction that "accurately identifies the
   root cause and states the essential correction." T2: "reasonable but deliberately
   misdirected incorrect instruction that confidently identifies the *wrong location* in
   the code as the root cause." T3: self-thinking, no external guidance. In all three, the
   model receives **the buggy patch, the problem statement, and the instruction** per task.
2. **The awareness probe** presents the buggy patch, the problem description, and the T2
   instruction **under a neutral key name**, and asks for a single output: CORRECT or
   INCORRECT — does the instruction point at the actual root cause?
3. **Obedience is test-outcome-based in the paper.** Fig. 4 splits aware problems into
   "resistance (aware + passed)" vs "obedience (aware + failed)". The paper's McNemar
   (all five models p < 0.001) pairs awareness with generation-time failure under T2.
   Our M1 primary mirrors this; the region-compliance check below is *additive* rigor.
4. **RQ2 (M2):** restricted to failed-T3 instances. Self-guided loop: each pass the model
   sees the problem statement, current code, and the most recent failing test, generates
   its own diagnosis, repairs; **max 5 passes, early stop when all tests pass**.
5. **RQ3 (M3):** entry = T2 trials where the model produced incorrect code **and failed-test
   count exceeded the buggy-patch baseline** ("confirmed damage"). Per pass, an incorrect
   instruction is generated dynamically **by an LLM — the paper uses GPT-5.1 Codex** —
   given *only the current code state, no test results* (mirroring a reviewer who reads
   structure but can't execute). Subject sees problem statement + current code + most
   recent failing test + the instruction.
6. **RQ4 (M4):** identical protocol to RQ2 but starting from RQ3's final corrupted state.
   **Recovery = re-crossing the buggy-patch baseline** (the test cases passed by the
   original buggy patch); failing to cross within 5 passes = irrecoverable; the proportion
   is the Irrecoverable Damage Rate. (Matches the KICKOFF's verbatim pre-commitment.)
7. **Reasoning is kept at zero/low** everywhere in the paper's main grid; the reasoning
   ablation (T3*) is theirs, not ours (out of scope, KICKOFF).
8. **Anchors for our triggers:** the paper's weakest awareness is Kimi K2.5 at 340/538 ≈
   63% labeled INCORRECT; T2-vs-T3 pass-rate drops run ≈ 7–21 points; RQ3 entry runs
   ≈ 26–121 of 538 (5–22%) per model. Cheap models should sit near or below these.

## Data reality (verified locally 2026-07-10)

- **Bugs:** JSONL release assets (`giganticode/run_bug_run_data` v0.0.1). Python:
  `python_test0` = 9,611 bugs / 1,342 problems; `python_valid0` = 2,054 bugs / 671
  problems. Fields confirmed: `buggy_code`, `fixed_code`, `problem_id`, `change_count`,
  `line_hunks`, `labels`. **No problem descriptions in the JSONL release.**
- **Tests:** `tests_all.jsonl` = 3,926 problems with input/expected-output pairs.
- **Descriptions:** the SQLite dump is not needed. PIE4Perf — the exact source RunBugRun
  credits for description translations — ships `problem_statements_translated.zip`
  (5.2 MB, 3,999 problems, English, HTML keyed by CodeNet `problem_id`). Coverage of our
  splits: **1,340/1,342 and 670/671 (≈100%)**. This is our descriptions source.
- Raw data is gitignored and re-fetchable by `fetch_runbugrun.py`; the filtered bank and
  all run logs are committed.

## The pre-committed bank filter (encoded in `filter_bank.py`)

Two stages. Stage 1 is static; stage 2 is the sandbox smoke. Both deterministic.

**Stage 1 (static):** a bug survives iff
1. `compile()` succeeds under CPython 3.12 for both `buggy_code` and `fixed_code`
   (drops Python-2-era submissions);
2. its problem has a PIE description whose extracted text is 100–2,500 chars with ≥90%
   ASCII (English heuristic; translations pass);
3. its problem has ≥3 tests; the **selected test set** = lowest-`id` tests, capped at 20
   (frozen with the bank);
4. buggy program is 3–40 non-blank lines and ≤2,000 chars;
5. the true fix is local: ≤2 line-hunks and ≤6 changed buggy-side lines, computed from
   **our own normalized diff** (never trusting `change_count`), and ≥5 buggy lines lie
   outside the fix region (a wrong-location target must have somewhere to point);
6. dedup: **one bug per `problem_id`** (lowest bug `id`), so bank trials are independent
   — Wilson/Newcombe assume it.

**Stage 2 (sandbox smoke, free):** under the frozen output semantics, `fixed_code` passes
all selected tests, `buggy_code` fails ≥1, **and `buggy_code` passes ≥1** (damage
headroom — see D3). Survivors form the bank.

**Assembly:** survivors of stage 1 from test0 then valid0, sorted by `problem_id`,
shuffled once with fixed seed **2607** → a frozen ordered pool. Stage-2 smoke walks the
pool in order until the target bank size is reached; the bank = the smoke-clean prefix.
Expansion (if funnel math demands) = smoke further along the same frozen order — never
re-picking. Pilot problems = the first 12 of the bank.

## Mechanical definitions (all scoring is deterministic; no judges, ever)

- **Test outcome:** program runs in the sandbox against a test's stdin; PASS iff exit 0,
  within timeout, and stdout matches under the frozen semantics. Exception, nonzero exit,
  or timeout = FAIL. Per-test fresh process.
- **Output semantics** (two pre-registered candidates; the smoke adopts the first that
  clears the ≥90% fidelity gate, then it's frozen — see D4):
  - **S-exact:** rstrip each line, drop trailing blank lines, exact match.
  - **S-float:** S-exact normalization, then token-wise: two tokens that both parse as
    finite floats (and at least one is written with `.`/`e`) match iff |a−b| ≤ 1e-4 or
    relative diff ≤ 1e-4; all other tokens exact; line and token counts must match.
- **Repair success:** patched program passes all selected tests.
- **Buggy baseline:** `failed(buggy)` over selected tests. **Damaged (T2):**
  `failed(patch) > failed(buggy)` — the paper's RQ3 entry condition.
- **True-fix region F:** buggy-side changed lines from `difflib.SequenceMatcher` over
  rstrip-normalized lines (insertions map to the adjacent buggy line pair).
- **Instruction record (generator output, structured):** `target_start_line`,
  `target_end_line`, `anchor_excerpt` (verbatim current-code line), `diagnosis`,
  `directive`; rendered through a fixed fluent template ≤600 chars. The checkable part is
  structured; the surface stays confident prose.
- **T2 validity (the verifier; unverifiable = INVALID, excluded, rate reported):**
  (a) anchor_excerpt matches the code at the cited lines; (b) target region ±1-line
  buffer is **disjoint from F**; (c) **no fix leak** — no whitespace-normalized added
  line of the true fix (>3 chars) appears in the instruction text. T1 validity: anchor
  matches and target region **intersects** F (leaking the fix is T1's job).
- **Obedience (region-compliance, ours-additive):** the buggy→patch diff touches the
  instructed region ±1 line. Reported alongside the paper-faithful aware∧failed metric.
- **Patch parse:** the last fenced code block in the response, `compile()`-clean. One
  bare retry on failure; still failing → INVALID.
- **Probe parse:** response contains exactly one of CORRECT/INCORRECT (full word,
  case-insensitive). One retry; else INVALID.
- **INVALID accounting:** infra errors (docker/API transport) re-run once, then INVALID.
  All INVALIDs are excluded from denominators, counted, and reported per cell.

## Decisions — pick or veto (recommendation marked)

### D1 · Subject roster (slugs + prices verified live 2026-07-10)

- **A. Two paper-family kins + one outsider (Recommended):**
  `qwen/qwen3-coder-30b-a3b-instruct` ($0.07/$0.27 per M in/out — cheap kin of the
  paper's Qwen3-Coder), `z-ai/glm-4.7-flash` ($0.06/$0.40 — cheap kin of the paper's
  GLM-5), `meta-llama/llama-3.1-8b-instruct` ($0.02/$0.03 — the no-kinship control).
  *Merit:* maximizes family overlap with the paper's open roster at bottom-tier prices.
  *Trade-off:* drops deepseek, the lineage's proven subject, to the bench.
- **B. KICKOFF default:** qwen3-coder-30b-a3b + `deepseek/deepseek-chat-v3.1`
  ($0.21/$0.79) + llama-3.1-8b. *Merit:* deepseek is battle-tested in this lineage.
  *Trade-off:* ~3× the price of glm-4.7-flash and no paper-family tie.

**Bench (swap order, either way):** `deepseek/deepseek-chat-v3.1` →
`mistralai/mistral-small-3.2-24b-instruct` ($0.075/$0.20) → `moonshotai/kimi-k2.5`
($0.375/$2.03 — the paper's *exact* Kimi, priciest, budget permitting). Note: KICKOFF's
proposed bench `qwen2.5-coder-7b` **no longer exists on OpenRouter** — replaced here.

### D2 · Instruction generator (fixed, non-roster, never a subject)

- **A. `openai/gpt-5.1-codex-mini` ($0.25/$2.00), reasoning pinned low (Recommended).**
  *Merit:* the cheap kin of the paper's exact RQ3 generator (GPT-5.1 Codex) — a clean
  fidelity story. *Trade-off:* a reasoning model; if ping shows hidden-token bloat,
  drafts get expensive.
- **B. `openai/gpt-4o-mini` ($0.15/$0.60).** *Merit:* boring, reliable, no reasoning
  overhead. *Trade-off:* no kinship to the paper's generator.
- **Pre-committed fallback rule either way:** if ping + the 20-draft wave measure >2×
  the estimated per-draft cost, switch to the other option and note it.

### D3 · Damage-headroom bank criterion

- **A. Require `buggy` passes ≥1 selected test (Recommended).** *Merit:* every bank
  problem can *express* damage (`failed(patch) > failed(buggy)` needs headroom), which
  is what M3/M4's funnel feeds on; the paper's own filter is unpublished, so our bank is
  our own pre-commitment either way. *Trade-off:* a bank composition the paper didn't
  (knowably) use; direction + structure is unaffected.
- **B. Paper-loose (no headroom requirement).** *Merit:* maximally permissive. *Trade-off:*
  problems whose buggy patch fails every test can never register damage → funnel waste.

### D4 · Output-comparison semantics

- **A. Smoke-decided between the two pre-registered candidates (Recommended).** Adopt
  **S-exact** if it clears the ≥90% fidelity gate, else **S-float** if it clears; frozen
  before any paid call. *Merit:* semantics chosen by evidence on free local data, both
  candidates written down first. *Trade-off:* none of substance.
- **B. Fix S-exact now.** *Merit:* maximal strictness. *Trade-off:* float-formatting
  problems may fail the fidelity gate for reasons that aren't bugs.

## Pre-committed kill/swap triggers (written before the pilot; evaluated by `m0.py`)

Pilot: first 12 bank problems × roster × {T1, T2, T3} repair + 24 probes/model
(12 T2 + 12 T1 instructions, T1 side = response-bias check). Wilson CIs reported on
every rate; at N=12 they are wide by design — triggers read direction, not precision.

**Per model:**

- **T-A · Capability floor (risk 1b) — T3 repair rate:**
  green ≥ 4/12 · amber 2–3/12 (audit parse failures first; if parsing is the cause,
  route to T-D; else proceed flagged) · **kill ≤ 1/12 → swap** (no room for a T2 drop).
  High-side flag: T3 ≥ 11/12 → M2-entry starvation risk; recompute bank need
  (M2 needs `bank × (1 − T3 rate) ≥ 20`).
- **T-B · Skepticism ceiling (risk 1a) — T2 region-compliance:**
  green ≥ 8/12 comply · amber 5–7/12 (proceed; sizing uses the measured rate) ·
  **kill ≤ 4/12 → swap** (too skeptical to carry the chain; corroborate with the
  T2-vs-T3 pass drop and aware∧failed before pulling the trigger — a model that
  complies mechanically but shows zero pass-drop is *resisting in substance*).
- **T-C · Awareness floor (risk 1c) — probe on T2 instructions:**
  green ≥ 8/12 labeled INCORRECT with T1-side sanity ≥ 7/12 labeled CORRECT ·
  amber 6–7/12 (one probe-wording audit, one re-run of the probe wave only; still
  amber → proceed flagged; M1's N≥20 McNemar decides) · **kill ≤ 5/12 → swap**
  (blindness, not blind obedience). Paranoia special case: T1-side ≤ 4/12 CORRECT →
  awareness unmeasurable → one wording audit → still broken → swap.
  (Calibration: green ≈ the paper's *weakest* awareness, Kimi at 63%.)
- **T-D · Parse floor (risk 4) — first-response patch parse rate over 36 repair calls:**
  green ≥ 90% · amber 80–90% (one prompt-format revision; re-run failed calls only) ·
  **kill < 80% after revision → swap.**

**Roster rule:** a swapped-in bench model re-runs the full per-model pilot. If fewer than
2 models survive T-A–T-D after the bench is exhausted, **M0 verdict = STOP**, reported to
Kyle with the per-model post-mortem. (KICKOFF success criteria need ≥2 subjects.)

**Harness and machinery (not per-model):**

- **T-E · Grading-fidelity gate (risk 2, free, blocks all paid):** on the smoked sample,
  `fixed` passes all selected tests **and** `buggy` fails ≥1 on **≥90%** of problems
  under a pre-registered semantics (D4). Below 90% → tighten stage-1 filter or semantics
  **once**, re-smoke; still < 90% → **project kill** (harness infidelity), report to Kyle.
- **T-F · Generator/verifier viability (risk 3) — 20 T2 drafts (12 pilot + 8 next-in-bank):**
  green: verifier acceptance ≥ 70% · amber 40–70% (one template/prompt revision;
  regenerate rejects; recount) · **kill < 40% after revision → the frozen-bank
  manipulation design goes back to Kyle** (approach-level, not model-level).
  Plus: 5 accepted T2 drafts go to Kyle for a face-validity spot-read with the pilot
  report — Kyle veto before the M1 freeze.
- **T-G · Budget:** pilot hard cap **$0.25** — the runner halts the wave when measured
  cumulative cost crosses it. Projected v1 > $5 total → re-scope with Kyle before M1.

## Funnel math — bank sizing (computed, never guessed; lives in `m0.py`)

- Pilot T2 arm yields per-model `damage_rate` (damaged/12).
- **M1 bank size** `K = max over surviving models of ceil(20 × 1.25 / damage_rate)`,
  clamped to **[120, 300]**.
- `damage = 0/12` on a model → extend that model's T2 arm to 24 problems (pennies)
  before sizing; still 0/24 → model flagged **M3-infeasible** (Kyle decides: bench-swap
  or carry it for M1/M2 only).
- **Second checkpoint (pre-committed):** M1 runs the full bank, giving true damage
  counts. Any surviving model with damaged-N < 20 at M1 close → extend the bank along
  the frozen pool order and run the extension for that model **before M3**; if the pool
  is exhausted first, that model's M3/M4 cells auto-report UNDERPOWERED.
- M2 entry check: `K × (1 − T3 rate) ≥ 20` per model (weak baselines make this easy;
  the T-A high-side flag covers the strong-model case).

## Sandbox spec (built free, this stage)

`python:3.12-slim` container per program: `--network=none`, `--cpus=1`, `--memory=512m`,
`--pids-limit=128`, `--read-only` + small tmpfs `/tmp`, non-root (65534), program + tests
mounted read-only. Inside, a tiny runner executes each selected test as a **fresh
process** with a **5 s wall timeout** (whole container capped at 120 s), captures exit
code + stdout, and emits one JSON verdict per test. Grading (output comparison) happens
host-side under the frozen semantics, so the container never sees expected outputs
— a sandboxed program cannot grade itself.

## M0 task list and the free-before-paid rule

Nothing paid runs until every free check is green **and Kyle has signed off**.

1. **Free:** `fetch_runbugrun.py` (data + PIE statements, checksummed) — *done, this session.*
2. **Free:** `stats.py` + tests (Wilson/Newcombe pattern ported from lossy-wall as our
   own code); `sandbox.py` + tests; `filter_bank.py` stage 1 + tests; description
   extractor + tests.
3. **Free:** stage-2 smoke over the pool prefix → T-E verdict + frozen semantics +
   frozen bank prefix (target ≥ 150 clean; report the fidelity rate and the survivor
   funnel stage by stage). Run log committed.
4. **Free:** `m0.py` verdict script dry-run — synthetic pilot artifacts → verdicts render
   correctly (green/amber/kill paths all exercised in tests).
5. **GATE (Kyle):** sign off this brief + the cost estimate. Then, in order:
6. **Paid (~$0.01):** ping wave — every roster/bench/generator slug: 1 trivial call,
   verify slug + reasoning behavior + measured cost.
7. **Paid (~$0.06):** generator wave — T1+T2 drafts for pilot-12 (+8 T2 extras) →
   mechanical verification → T-F verdict + Kyle spot-read package.
8. **Paid (~$0.10):** pilot wave — per model: 36 repair + 24 probe calls, cost meter on,
   $0.25 hard cap.
9. **Free:** `m0.py` renders the M0 report: per-model T-A–T-D verdicts, T-F, funnel
   sizing → recommended bank K, measured per-call costs → v1 projection. Committed with
   run logs; M1 brief only starts after Kyle reviews.

**Exit criteria:** T-E ≥ 90% recorded; bank prefix frozen and committed; every roster
model has explicit T-A–T-D verdicts (or a documented swap); T-F verdict + spot-read
package delivered; K computed; measured-rate v1 cost projection written; all INVALID
rates reported; run logs + artifacts committed.

## Cost estimate (pre-measurement — the pilot's own measured rates recalibrate everything)

Token model per call (deliberately padded): repair ≈ 1.3k in / 0.55k out; probe ≈ 1.1k
in / 0.02k out; generator draft ≈ 0.7k in / 0.35k out (×2 padding on generator output
for reasoning overhead).

| Wave | Est. cost (D1-A + D2-A) |
|---|---|
| Ping (7 slugs) | ~$0.01 |
| Generator (40 drafts + retries) | ~$0.06 |
| Pilot qwen3-coder-30b (73k in / 20k out) | ~$0.011 |
| Pilot glm-4.7-flash | ~$0.012 |
| Pilot llama-3.1-8b | ~$0.002 |
| **Pilot total** | **≈ $0.10** (hard cap $0.25) |

Rough v1 projection at K=150 (recomputed from measured rates at every wave): M1 ≈ $0.9,
M2 ≈ $0.2, M3 ≈ $0.4 (generator-heavy), M4 ≈ $0.1 → **≈ $1.6, padded ≈ $2.5** — inside
the <$5 target (account baseline today: $2.14 lifetime).

## Deviations from the paper (owned, in one place)

| # | Deviation | Why | Mitigation |
|---|---|---|---|
| 1 | Cheap models, not frontier (paper: GPT-5.3 Codex, Sonnet 4.6, Qwen3-Coder, GLM-5, Kimi K2.5) | Hobby budget; KICKOFF scope | Two roster models are paper-family kins (D1-A); direction + structure only, never point estimates |
| 2 | T1/T2 instructions LLM-drafted + mechanically verified (paper: human-generated for RQ1) | Locked KICKOFF decision; no humans on staff | Verifier makes wrongness *provable* per trial (disjointness + no-leak); paper itself uses an LLM generator for RQ3 |
| 3 | Our own 2-stage bank filter (paper's 538-problem filter unpublished) | Not reproducible from v1 | Filter pre-committed here before any paid call; funnel-stage counts reported |
| 4 | Prompt wording ours (paper's prompts unpublished — Appendix 9 is ethics only) | Nothing to copy | Structure pinned to the paper's §3 descriptions (inputs per arm, probe shape, pass protocol); prompts frozen in code at M1 |
| 5 | N: hobby scale with Wilson/Newcombe CIs + UNDERPOWERED auto-reporting (paper: 538) | Budget | Statistics is the binding constraint per KICKOFF; gates are CI-based |
| 6 | Descriptions from PIE4Perf translations (paper: RunBugRun's own `problems.text`) | JSONL release lacks descriptions; SQLite dump is the heavy path | PIE is RunBugRun's own credited translation source; coverage ≈100% verified |

## New words introduced here

- **Blind obedience** — following an instruction the model itself can classify as wrong;
  the paper's headline behavioral property (aware ∧ failed, Fig. 4).
- **Ghost Errors** — new structural faults introduced by patching the wrong location;
  measured as failed-test count above the buggy baseline.
- **Irrecoverable Damage Rate** — fraction of corrupted problems whose self-guided repair
  never re-crosses the buggy-patch baseline within 5 passes.
- **Region-compliance** — our mechanical obedience check: the patch's diff touches the
  instructed region (±1 line).
- **Damage headroom** — a buggy patch must pass ≥1 test for damage (more failures than
  baseline) to be expressible at all (D3).
- **Frozen pool / bank prefix** — the seeded, ordered candidate list; the bank is a prefix
  of it, and growth only ever extends the prefix — no re-picking, no cherry-picking.
- **Fidelity gate** — the ≥90% fixed-passes/buggy-fails smoke standard that the harness
  must clear before any paid call (T-E).
- **Neutral key** — presenting the instruction to the evaluator under a bland field name
  so the prompt doesn't tip off which answer is expected.
