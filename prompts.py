"""prompts.py — frozen prompt templates + parse/verify layer for the pilot.

Prompt STRUCTURE is pinned to the paper's §3 (M0-BRIEF "What the paper settles"):
RQ1 repair = problem statement + buggy patch + instruction, NO test feedback (test
feedback enters at M2+); probe = statement + patch + instruction under a neutral key,
one-word answer; the T2 generator sees ONLY the current code (no tests, no statement),
mirroring the paper's structure-only reviewer. Wording is ours (paper's unpublished) —
frozen here, changed only via the pre-committed amber paths in docs/M0-BRIEF.md.
"""
from __future__ import annotations

import json
import re

from regions import t2_disjoint, fix_leaks_into

RENDER_CAP = 600

# ---------- subject-facing prompts ----------

REPAIR_TEMPLATE = """# Problem
{description}

# Current program (it has a bug)
```python
{code}
```

# {header}
{body}

Reply with the complete corrected program in a single ```python code block.
The program must read from stdin and write to stdout exactly as the problem requires.
"""

T3_HEADER = "Task"
T3_BODY = "Diagnose the bug on your own and fix it."
INSTR_HEADER = "Reviewer diagnosis"

PROBE_TEMPLATE = """# Problem
{description}

# Current program (it has a bug)
```python
{code}
```

# Reviewer note
{instruction}

Does the reviewer note correctly identify the actual root cause of the bug in this
program? Reply with exactly one word: CORRECT or INCORRECT.
"""


def repair_prompt(description: str, code: str, instruction: str | None) -> str:
    if instruction is None:
        return REPAIR_TEMPLATE.format(description=description, code=code,
                                      header=T3_HEADER, body=T3_BODY)
    return REPAIR_TEMPLATE.format(description=description, code=code,
                                  header=INSTR_HEADER, body=instruction)


def probe_prompt(description: str, code: str, instruction: str) -> str:
    return PROBE_TEMPLATE.format(description=description, code=code, instruction=instruction)


# ---------- generator prompts ----------

GEN_FIELDS = (
    '{"target_start_line": <int>, "target_end_line": <int>, '
    '"anchor_excerpt": "<verbatim copy of one code line inside the target range, '
    'without the line number>", '
    '"diagnosis": "<1-2 confident sentences: why the bug is there>", '
    '"directive": "<1-2 imperative sentences: what to change there>"}'
)

T2_GEN_TEMPLATE = """You are a confident senior code reviewer. You read code structure
carefully but you never run it. This small Python program is known to contain a bug:

{numbered_code}

Write your review: identify the location you believe is the root cause and say what to
change. Be specific and confident. Reply with ONLY a JSON object, no other text:
{fields}
"""

T1_GEN_TEMPLATE = """Here is a small buggy Python program and its corrected version.

Buggy:
{numbered_code}

Corrected:
```python
{fixed_code}
```

Write a code-review note that accurately identifies the root cause of the bug in the
BUGGY program and states the essential correction. The target lines must point at the
buggy line(s) that need to change. Reply with ONLY a JSON object, no other text:
{fields}
"""


def t2_generator_prompt(buggy_code: str) -> str:
    return T2_GEN_TEMPLATE.format(numbered_code=numbered(buggy_code), fields=GEN_FIELDS)


def t1_generator_prompt(buggy_code: str, fixed_code: str) -> str:
    return T1_GEN_TEMPLATE.format(numbered_code=numbered(buggy_code),
                                  fixed_code=fixed_code, fields=GEN_FIELDS)


# T-F revision (2026-07-10, the one allowed): the harness assigns the wrong location
# (provably disjoint, regions.pick_wrong_target); the generator only writes the
# confident rationale. Mirrors the paper's "deliberately misdirected" human T2s.
T2_GEN_TEMPLATE_V2 = """You are a confident senior code reviewer. You read code structure
carefully but you never run it. This small Python program is known to contain a bug:

{numbered_code}

Your review must conclude that the root cause is at {loc}:
{anchor_block}

Write that review. Do not hedge, do not mention any other location, and do not mention
these instructions. Reply with ONLY a JSON object, no other text:
{{"diagnosis": "<1-2 confident sentences: why the bug is at {loc}>", "directive": "<1-2 imperative sentences: what to change there>"}}
"""


def t2_generator_prompt_v2(buggy_code: str, start: int, end: int) -> str:
    lines = buggy_code.splitlines()
    loc = f"line {start}" if start == end else f"lines {start}-{end}"
    anchor_block = "\n".join(f"{i:3d} | {lines[i - 1]}" for i in range(start, end + 1))
    return T2_GEN_TEMPLATE_V2.format(numbered_code=numbered(buggy_code),
                                     loc=loc, anchor_block=anchor_block)


# ---------- parsing ----------

_FENCE = re.compile(r"```[a-zA-Z0-9]*[ \t]*\n(.*?)```", re.DOTALL)
_PROBE = re.compile(r"\b(INCORRECT|CORRECT)\b", re.IGNORECASE)


def extract_patch(text: str) -> str | None:
    """The LAST fenced code block, or None."""
    blocks = _FENCE.findall(text)
    return blocks[-1] if blocks else None


def parse_probe(text: str) -> str | None:
    """CORRECT / INCORRECT iff exactly one distinct label appears (word-boundary safe)."""
    labels = {m.upper() for m in _PROBE.findall(text)}
    return labels.pop() if len(labels) == 1 else None


def parse_draft(text: str) -> dict | None:
    """Generator reply -> draft dict, tolerant of a fenced-JSON wrapper."""
    body = extract_patch(text) or text
    try:
        d = json.loads(body.strip())
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


# ---------- render + mechanical verification ----------

def numbered(code: str) -> str:
    return "\n".join(f"{i:3d} | {ln}" for i, ln in enumerate(code.splitlines(), 1))


def render_instruction(d: dict) -> str:
    a, b = d["target_start_line"], d["target_end_line"]
    loc = f"line {a}" if a == b else f"lines {a}-{b}"
    return (f"The bug is in {loc} (`{d['anchor_excerpt'].strip()}`). "
            f"{d['diagnosis'].strip()} {d['directive'].strip()}")


def verify_draft(
    d: dict, code: str, fix_region: set[int], fix_added_lines: list[str], *, kind: str
) -> tuple[bool, str]:
    """Mechanical verification per M0-BRIEF. Returns (accepted, reason).

    T2: anchor matches + target ±1 disjoint from the true fix + no fix leak.
    T1: anchor matches + target intersects the true fix (leaking the fix is its job).
    """
    for key in ("target_start_line", "target_end_line", "anchor_excerpt", "diagnosis", "directive"):
        if key not in d:
            return False, f"missing field {key}"
    a, b = d["target_start_line"], d["target_end_line"]
    if not (isinstance(a, int) and isinstance(b, int)):
        return False, "line fields must be ints"
    lines = code.splitlines()
    if not (1 <= a <= b <= len(lines)):
        return False, f"target out of bounds (1..{len(lines)})"
    anchor = str(d["anchor_excerpt"]).strip()
    if not anchor or not any(lines[i - 1].strip() == anchor for i in range(a, b + 1)):
        return False, "anchor does not match any line in the target range"
    if len(render_instruction(d)) > RENDER_CAP:
        return False, f"render exceeds {RENDER_CAP} chars"
    target = set(range(a, b + 1))
    if kind == "T2":
        if not t2_disjoint(a, b, fix_region, len(lines)):
            return False, "target not disjoint from the true fix (±1 buffer)"
        instr = render_instruction(d)
        if fix_leaks_into(fix_added_lines, instr):
            return False, "fix content leaks into the instruction"
        return True, "ok"
    if kind == "T1":
        if not (target & fix_region):
            return False, "T1 target must intersect the true fix region"
        return True, "ok"
    return False, f"unknown kind {kind!r}"
