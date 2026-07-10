"""Spec for stats.py — Wilson interval, Newcombe difference, excludes_zero.

Pattern ported from lossy-wall's stats.py as our own code (KICKOFF tech stack).
Golden values computed by hand from the Wilson formula at z = 1.96.
"""
import pytest

from stats import wilson, newcombe_diff, newcombe_paired_diff, excludes_zero


class TestWilson:
    def test_no_data_means_no_knowledge(self):
        assert wilson(0, 0) == (0.0, 1.0)

    def test_zero_of_twenty_upper_bound_stays_honest(self):
        # 0/20 is "consistent with ~0%", never "proved 0%".
        lo, hi = wilson(0, 20)
        assert lo == pytest.approx(0.0, abs=1e-9)
        assert hi == pytest.approx(0.16113, abs=2e-4)

    def test_half_and_half_is_symmetric(self):
        lo, hi = wilson(10, 20)
        assert lo == pytest.approx(0.29929, abs=2e-4)
        assert hi == pytest.approx(0.70071, abs=2e-4)

    def test_all_hits_mirrors_zero_hits(self):
        lo, hi = wilson(20, 20)
        assert lo == pytest.approx(1 - 0.16113, abs=2e-4)
        assert hi == pytest.approx(1.0, abs=1e-9)

    def test_never_escapes_unit_interval(self):
        for k, n in [(0, 1), (1, 1), (1, 3), (11, 12), (5, 200)]:
            lo, hi = wilson(k, n)
            assert 0.0 <= lo <= hi <= 1.0


class TestNewcombeDiff:
    def test_maximal_separation(self):
        d, lo, hi = newcombe_diff(0, 20, 20, 20)
        assert d == pytest.approx(1.0)
        assert lo == pytest.approx(0.77213, abs=2e-4)
        assert hi == pytest.approx(1.0, abs=1e-9)

    def test_no_difference_straddles_zero(self):
        d, lo, hi = newcombe_diff(10, 20, 10, 20)
        assert d == pytest.approx(0.0)
        assert lo < 0.0 < hi

    def test_direction_sign_convention(self):
        # d = p_mech - p_base: mech higher -> positive d.
        d, _, _ = newcombe_diff(2, 12, 9, 12)
        assert d > 0
        d_rev, _, _ = newcombe_diff(9, 12, 2, 12)
        assert d_rev < 0

    def test_empty_arm_degrades_to_full_uncertainty(self):
        d, lo, hi = newcombe_diff(0, 0, 5, 10)
        assert d == pytest.approx(0.5)
        assert lo < 0.0  # base arm knows nothing, interval must be wide
        assert 0.0 <= hi <= 1.0 + 1e-9


class TestNewcombePairedDiff:
    """Newcombe (1998) paired difference — square-and-add Wilson with phi-hat
    correction. Table args: (both, mech_only, base_only, neither); M1 passes
    mech = T3, base = T2, so d = pass(T3) - pass(T2) = (mech_only - base_only)/n.
    """

    def test_zero_phi_reduces_to_unpaired(self):
        # e*h == f*g -> phi-hat = 0 -> must equal the unpaired square-and-add
        # on the same marginals. e=6 f=3 g=2 h=1: eh=6=fg; n=12, mech 9/12, base 8/12.
        d, lo, hi = newcombe_paired_diff(6, 3, 2, 1)
        d_u, lo_u, hi_u = newcombe_diff(8, 12, 9, 12)
        assert d == pytest.approx(d_u)
        assert lo == pytest.approx(lo_u)
        assert hi == pytest.approx(hi_u)

    def test_positive_correlation_narrows_the_interval(self):
        # e=8 f=3 g=1 h=8: eh=64 >> fg=3 -> phi-hat > 0 -> tighter than unpaired.
        d, lo, hi = newcombe_paired_diff(8, 3, 1, 8)
        d_u, lo_u, hi_u = newcombe_diff(9, 20, 11, 20)
        assert d == pytest.approx(d_u)
        assert (hi - lo) < (hi_u - lo_u)

    def test_degenerate_marginal_falls_back_to_zero_phi(self):
        # base arm never succeeds (e=g=0) -> a marginal product is 0 -> phi-hat 0.
        d, lo, hi = newcombe_paired_diff(0, 5, 0, 5)
        d_u, lo_u, hi_u = newcombe_diff(0, 10, 5, 10)
        assert d == pytest.approx(d_u)
        assert lo == pytest.approx(lo_u)
        assert hi == pytest.approx(hi_u)

    def test_all_concordant_pairs_collapse_to_zero_width(self):
        # Perfect agreement (f=g=0, phi-hat=1) with symmetric Wilson bounds:
        # no discordance, no evidence of any difference.
        d, lo, hi = newcombe_paired_diff(10, 0, 0, 10)
        assert d == pytest.approx(0.0)
        assert lo == pytest.approx(0.0, abs=1e-9)
        assert hi == pytest.approx(0.0, abs=1e-9)

    def test_reverse_direction_excludes_zero_from_below(self):
        # base strictly better: d negative, interval fully below zero.
        d, lo, hi = newcombe_paired_diff(0, 0, 10, 10)
        assert d == pytest.approx(-0.5)
        assert hi < 0.0

    def test_no_pairs_means_no_knowledge(self):
        d, lo, hi = newcombe_paired_diff(0, 0, 0, 0)
        assert (d, lo, hi) == (0.0, -1.0, 1.0)

    def test_interval_stays_inside_difference_range(self):
        for table in [(1, 1, 1, 1), (0, 12, 0, 0), (5, 0, 7, 3), (2, 9, 1, 8)]:
            d, lo, hi = newcombe_paired_diff(*table)
            assert -1.0 <= lo <= d <= hi <= 1.0


class TestExcludesZero:
    def test_clear_positive_effect(self):
        assert excludes_zero(0.05, 0.30) is True

    def test_clear_negative_effect(self):
        assert excludes_zero(-0.30, -0.05) is True

    def test_straddling_zero_is_no_claim(self):
        assert excludes_zero(-0.10, 0.20) is False

    def test_boundary_touching_zero_is_no_claim(self):
        assert excludes_zero(0.0, 0.20) is False
