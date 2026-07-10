"""grading.py — the two pre-registered output-comparison semantics (M0-BRIEF D4).

Grading happens host-side: the sandbox returns raw stdout per test, and this module
decides PASS/FAIL against the expected output. The smoke (T-E) adopts whichever
pre-registered semantics first clears the >=90% fidelity gate — S-exact preferred —
and the choice is frozen for every later milestone. Nothing here is heuristic at
score time: same inputs, same verdict, forever.
"""
from __future__ import annotations

FLOAT_TOL = 1e-4


def _normalize_lines(text: str) -> list[str]:
    """rstrip each line, drop trailing blank lines (S-exact normalization)."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _is_floaty(token: str) -> bool:
    """Token is written as a float (contains '.' or an exponent marker)."""
    return "." in token or "e" in token.lower()


def _parses_finite(token: str) -> float | None:
    try:
        v = float(token)
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):  # nan / inf -> not finite
        return None
    return v


def _tokens_match_float(a: str, b: str) -> bool:
    if a == b:
        return True
    va, vb = _parses_finite(a), _parses_finite(b)
    if va is None or vb is None:
        return False
    if not (_is_floaty(a) or _is_floaty(b)):
        return False  # two bare ints spelled differently are just different
    diff = abs(va - vb)
    if diff <= FLOAT_TOL:
        return True
    scale = max(abs(va), abs(vb))
    return scale > 0 and diff / scale <= FLOAT_TOL


def compare_outputs(expected: str, actual: str, mode: str) -> bool:
    """PASS/FAIL verdict for a program's stdout against the expected output.

    mode "exact"  -> S-exact: normalized lines must match exactly.
    mode "float"  -> S-float: token-wise with 1e-4 abs/rel tolerance for tokens
                     where both parse as finite floats and at least one is written
                     with '.'/'e'; line and token counts must match.
    """
    exp, act = _normalize_lines(expected), _normalize_lines(actual)
    if mode == "exact":
        return exp == act
    if mode != "float":
        raise ValueError(f"unknown comparison mode: {mode!r}")
    if len(exp) != len(act):
        return False
    for eline, aline in zip(exp, act):
        etok, atok = eline.split(), aline.split()
        if len(etok) != len(atok):
            return False
        for e, a in zip(etok, atok):
            if not _tokens_match_float(e, a):
                return False
    return True
