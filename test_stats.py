"""Spec for stats.py — Wilson interval, Newcombe difference, excludes_zero.

Pattern ported from lossy-wall's stats.py as our own code (KICKOFF tech stack).
Golden values computed by hand from the Wilson formula at z = 1.96.
"""
import pytest

from stats import wilson, newcombe_diff, excludes_zero


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


class TestExcludesZero:
    def test_clear_positive_effect(self):
        assert excludes_zero(0.05, 0.30) is True

    def test_clear_negative_effect(self):
        assert excludes_zero(-0.30, -0.05) is True

    def test_straddling_zero_is_no_claim(self):
        assert excludes_zero(-0.10, 0.20) is False

    def test_boundary_touching_zero_is_no_claim(self):
        assert excludes_zero(0.0, 0.20) is False
