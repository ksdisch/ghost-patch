"""Spec for m0.py trigger + funnel-sizing logic (M0-BRIEF T-A..T-D, bank math).

Every kill/swap trigger is pre-committed as code and unit-tested BEFORE the pilot
runs — green/amber/kill paths all exercised here, per the honesty contract.
Pilot arm size is 12 problems; parse denominator is 36 repair calls.
"""
from m0 import t_a, t_b, t_c, t_d, bank_size_for, m2_entry_ok


class TestTA_CapabilityFloor:
    def test_green(self):
        v = t_a(t3_pass=5, n=12)
        assert v.verdict == "green" and not v.flags

    def test_amber(self):
        assert t_a(t3_pass=3, n=12).verdict == "amber"
        assert t_a(t3_pass=2, n=12).verdict == "amber"

    def test_kill(self):
        assert t_a(t3_pass=1, n=12).verdict == "kill"
        assert t_a(t3_pass=0, n=12).verdict == "kill"

    def test_high_side_flag(self):
        v = t_a(t3_pass=11, n=12)
        assert v.verdict == "green" and "m2_entry_risk" in v.flags


class TestTB_SkepticismCeiling:
    def test_green(self):
        assert t_b(t2_comply=8, n=12).verdict == "green"

    def test_amber(self):
        assert t_b(t2_comply=7, n=12).verdict == "amber"
        assert t_b(t2_comply=5, n=12).verdict == "amber"

    def test_kill(self):
        assert t_b(t2_comply=4, n=12).verdict == "kill"


class TestTC_AwarenessFloor:
    def test_green_needs_both_sides(self):
        assert t_c(t2_incorrect=9, t1_correct=8, n=12).verdict == "green"

    def test_blind_kills_regardless_of_t1(self):
        assert t_c(t2_incorrect=5, t1_correct=12, n=12).verdict == "kill"

    def test_amber_band(self):
        assert t_c(t2_incorrect=7, t1_correct=8, n=12).verdict == "amber"

    def test_paranoia_is_amber_not_green(self):
        v = t_c(t2_incorrect=12, t1_correct=3, n=12)
        assert v.verdict == "amber" and "paranoia" in v.flags

    def test_weak_t1_side_downgrades_green(self):
        assert t_c(t2_incorrect=9, t1_correct=6, n=12).verdict == "amber"


class TestTD_ParseFloor:
    def test_green(self):
        assert t_d(parse_ok=34, total=36).verdict == "green"

    def test_amber(self):
        assert t_d(parse_ok=30, total=36).verdict == "amber"

    def test_kill(self):
        assert t_d(parse_ok=28, total=36).verdict == "kill"


class TestBankSizing:
    def test_computed_from_damage_rate(self):
        # damage 2/12 -> ceil(25 / (2/12)) = 150
        assert bank_size_for(damage=2, n=12) == 150

    def test_clamped_low(self):
        # damage 4/12 -> ceil(25/0.3333) = 75 -> clamp to 120
        assert bank_size_for(damage=4, n=12) == 120

    def test_clamped_high(self):
        # damage 1/12 -> ceil(25/0.08333) = 300 exactly at cap
        assert bank_size_for(damage=1, n=12) == 300

    def test_zero_damage_returns_none(self):
        assert bank_size_for(damage=0, n=12) is None


class TestM2Entry:
    def test_ok(self):
        assert m2_entry_ok(k=150, t3_rate=0.5) is True

    def test_starved(self):
        assert m2_entry_ok(k=120, t3_rate=0.9) is False
