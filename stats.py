"""stats.py — proportion confidence intervals (pattern ported from lossy-wall, our own code).

Every gated rate in this project is a **proportion**: k hits out of n trials (repair rate,
obedience rate, awareness rate, damage rate, irrecoverable rate). Mean ± std is the wrong
ruler for a rate — it can hand back intervals below 0% or above 100%. These are the right
rulers, and the KICKOFF honesty contract in code form:

  - `wilson(k, n)` — the **Wilson score interval**: the honest range a single cell's true
    rate likely sits in given only n samples. Well-behaved at the edges (k=0, k=n) and
    never escapes [0, 1] — and our cells live at the edges (M4 recovery ≈ 0 is a headline
    candidate). k=0 at n=20 reads [0%, ~16%]: "consistent with ~0%", never "proved 0%".

  - `newcombe_diff(...)` — the **Newcombe interval** for the *difference* between two
    cells' rates (his square-and-add method 10): combines each arm's own Wilson interval
    instead of assuming one pooled normal spread, so it stays trustworthy near 0%/100%
    and at small n. The gated deltas ride on it: M1's paired T2-vs-T3 drop and M4's
    M4-vs-M2 recovery gap both gate on the interval excluding zero (direction + CI, never
    point estimates).

  - `excludes_zero(lo, hi)` — the claim gate: an interval that straddles 0 means "no
    clear effect", and a claim that doesn't clear its gate doesn't get made.

Pure functions, no model, no network; unit-tested in test_stats.py.
"""
from __future__ import annotations

import math

Z_95 = 1.96  # two-sided 95% standard-normal critical value


def wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval (lo, hi) for a proportion k/n.

    Centred on a slightly shrunk estimate (pulled toward 1/2), asymmetric near the
    edges — the honest behaviour for small n. `n = 0` returns (0.0, 1.0): with no
    data the interval is the whole range.
    """
    if n <= 0:
        return (0.0, 1.0)
    phat = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def newcombe_diff(
    k_base: int, n_base: int, k_mech: int, n_mech: int, z: float = Z_95
) -> tuple[float, float, float]:
    """Newcombe interval for the difference d = p_mech - p_base. Returns (d, lo, hi).

    Convention: arm 1 ("base") is the reference, arm 2 ("mech") the arm expected higher;
    positive d with (lo, hi) above 0 is a real advantage for arm 2. Call sites name the
    arms explicitly — e.g. M1 passes base=T2 pass rate, mech=T3 pass rate (the drop),
    M4 passes base=M4 recovery, mech=M2 recovery (the ceiling gap).
    """
    p1 = k_base / n_base if n_base else 0.0
    p2 = k_mech / n_mech if n_mech else 0.0
    l1, u1 = wilson(k_base, n_base, z)
    l2, u2 = wilson(k_mech, n_mech, z)
    d = p2 - p1
    lo = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return (d, lo, hi)


def newcombe_paired_diff(
    both: int, mech_only: int, base_only: int, neither: int, z: float = Z_95
) -> tuple[float, float, float]:
    """Newcombe (1998) interval for a *paired* difference d = p_mech - p_base.

    Args are the 2x2 discordance table over pairs: `both` succeed in both arms,
    `mech_only` succeeds only in the mech arm, `base_only` only in the base arm,
    `neither` in neither. Square-and-add on each arm's Wilson interval, with the
    cross-term scaled by phi-hat (the table's correlation); a degenerate marginal
    sets phi-hat to 0, which reduces exactly to the unpaired square-and-add.
    M1's gate passes mech = T3 (no instruction), base = T2 (wrong location), so
    a positive d with (lo, hi) above 0 is a real T2 drop. Returns (d, lo, hi).
    """
    e, f, g, h = both, mech_only, base_only, neither
    n = e + f + g + h
    if n <= 0:
        return (0.0, -1.0, 1.0)
    p_mech, p_base = (e + f) / n, (e + g) / n
    d = p_mech - p_base
    marginals = (e + f) * (g + h) * (e + g) * (f + h)
    phi = (e * h - f * g) / math.sqrt(marginals) if marginals > 0 else 0.0
    l_mech, u_mech = wilson(e + f, n, z)
    l_base, u_base = wilson(e + g, n, z)
    dl_mech, du_mech = p_mech - l_mech, u_mech - p_mech
    dl_base, du_base = p_base - l_base, u_base - p_base
    lo = d - math.sqrt(max(0.0, dl_mech**2 - 2 * phi * dl_mech * du_base + du_base**2))
    hi = d + math.sqrt(max(0.0, du_mech**2 - 2 * phi * du_mech * dl_base + dl_base**2))
    return (d, max(-1.0, lo), min(1.0, hi))


def excludes_zero(lo: float, hi: float) -> bool:
    """True iff the difference interval (lo, hi) does NOT straddle 0 — a real effect.

    Boundary-touching intervals do not count as exclusion: no claim on a knife edge.
    """
    return lo > 0.0 or hi < 0.0
