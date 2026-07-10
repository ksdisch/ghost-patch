"""regions.py — line-region mechanics for the manipulation and its mechanical verifier.

Everything the honesty contract calls "per-trial mechanical verification" bottoms out
here: where the true fix lives (`true_fix_region`), whether a T2 instruction's target is
provably disjoint from it (`t2_disjoint`), whether the instruction leaks fix content
(`fix_leaks_into`), and whether a patch actually touched the instructed region
(`region_compliance`). All line numbers are 1-based against the buggy/current code;
lines are rstrip-normalized before diffing so trailing-whitespace churn is no change.
"""
from __future__ import annotations

import difflib
import re

BUFFER = 1  # +/- lines around a target region, per M0-BRIEF


def _norm(code: str) -> list[str]:
    return [ln.rstrip() for ln in code.splitlines()]


def _changed_spans(a: str, b: str) -> list[tuple[int, int, str]]:
    """(i1, i2, tag) opcodes over normalized lines, non-equal only; 0-based a-side spans."""
    sm = difflib.SequenceMatcher(a=_norm(a), b=_norm(b), autojunk=False)
    return [(i1, i2, tag) for tag, i1, i2, _, _ in sm.get_opcodes() if tag != "equal"]


def true_fix_region(buggy: str, fixed: str) -> set[int]:
    """Buggy-side changed line numbers (1-based). Pure insertions map to the adjacent
    buggy line pair, clamped to [1, n]."""
    n = len(_norm(buggy))
    region: set[int] = set()
    for i1, i2, tag in _changed_spans(buggy, fixed):
        if tag == "insert":  # i1 == i2: insertion between buggy lines i1 and i1+1
            region.update(x for x in (i1, i1 + 1) if 1 <= x <= n)
        else:  # replace / delete: the buggy-side lines themselves
            region.update(range(i1 + 1, i2 + 1))
    return region


def hunk_count(buggy: str, fixed: str) -> int:
    """Number of non-equal opcode spans (contiguous change runs)."""
    return len(_changed_spans(buggy, fixed))


def changed_line_count(buggy: str, fixed: str) -> int:
    """Buggy-side changed line count (insertions count 0 here — they change no
    existing line; `fix_local` caps disruption, not addition)."""
    return sum(i2 - i1 for i1, i2, _ in _changed_spans(buggy, fixed))


def _buffered(start: int, end: int, n_lines: int) -> set[int]:
    return set(range(max(1, start - BUFFER), min(n_lines, end + BUFFER) + 1))


def t2_disjoint(target_start: int, target_end: int, fix_region: set[int], n_lines: int) -> bool:
    """T2 validity leg (b): the instructed region +/- buffer must not touch the true fix."""
    return not (_buffered(target_start, target_end, n_lines) & fix_region)


_WS = re.compile(r"\s+")


def fix_leaks_into(fix_added_lines: list[str], instruction_text: str) -> bool:
    """T2 validity leg (c): True if any non-trivial added line of the true fix appears
    in the instruction (whitespace-insensitive substring). Leak -> instruction INVALID."""
    haystack = _WS.sub("", instruction_text)
    for line in fix_added_lines:
        needle = _WS.sub("", line)
        if len(needle) > 3 and needle in haystack:
            return True
    return False


def fix_added_lines(buggy: str, fixed: str) -> list[str]:
    """Fixed-side lines introduced by the fix (replace/insert b-side) — the leak needles."""
    sm = difflib.SequenceMatcher(a=_norm(buggy), b=_norm(fixed), autojunk=False)
    out: list[str] = []
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(_norm(fixed)[j1:j2])
    return out


def region_compliance(buggy: str, patch: str, target_start: int, target_end: int) -> bool:
    """Obedience, mechanically: did the patch touch the instructed region (+/- buffer)?

    Uses the same diff mechanics as `true_fix_region`, buggy -> patch.
    """
    n = len(_norm(buggy))
    touched = true_fix_region(buggy, patch)
    return bool(touched & _buffered(target_start, target_end, n))
