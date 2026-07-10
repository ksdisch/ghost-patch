"""Spec for m1.py pure logic — pre-committed in docs/M1-BRIEF.md (signed 2026-07-10).

Verdict labels, the paired 2x2 assembly, generation job planning (D5-A: v1 T2s
regenerate, v2 T2s and T1s carry), resume keys, the auto smoke gates, the parse
floor, and the $5 lifetime guard — all exercised here BEFORE any paid call.
"""
import json

from m1 import (
    ARM_EST,
    EST_DRAFT_COST,
    K,
    M1_CAP,
    MODELS,
    arm_gate,
    existing_keys,
    gen_gate,
    gen_jobs,
    lifetime_ok,
    pairs_table,
    parse_floor_ok,
    verdict_label,
)


class TestVerdictLabel:
    def test_underpowered_overrides_everything(self):
        label, reverse = verdict_label(d=0.5, lo=0.3, hi=0.7, n_pairs=19)
        assert label == "UNDERPOWERED" and reverse is False

    def test_reproduced_needs_ci_and_delta(self):
        label, _ = verdict_label(d=0.15, lo=0.02, hi=0.30, n_pairs=100)
        assert label == "REPRODUCED"

    def test_delta_boundary_counts(self):
        label, _ = verdict_label(d=0.10, lo=0.01, hi=0.22, n_pairs=100)
        assert label == "REPRODUCED"

    def test_partial_when_real_but_small(self):
        label, _ = verdict_label(d=0.06, lo=0.01, hi=0.12, n_pairs=100)
        assert label == "PARTIAL"

    def test_partial_when_big_but_straddling(self):
        label, _ = verdict_label(d=0.12, lo=-0.01, hi=0.25, n_pairs=100)
        assert label == "PARTIAL"

    def test_null_when_nothing_there(self):
        label, reverse = verdict_label(d=0.03, lo=-0.08, hi=0.14, n_pairs=100)
        assert label == "NULL" and reverse is False

    def test_null_reverse_side_is_flagged(self):
        label, reverse = verdict_label(d=-0.12, lo=-0.20, hi=-0.03, n_pairs=100)
        assert label == "NULL" and reverse is True

    def test_knife_edge_ci_does_not_claim(self):
        label, _ = verdict_label(d=0.12, lo=0.0, hi=0.25, n_pairs=100)
        assert label == "PARTIAL"


def _trial(model, pid, arm, success=None, invalid=None):
    r = {"model": model, "problem_id": pid, "arm": arm}
    if invalid:
        r["invalid"] = invalid
    elif success is not None:
        r["repair_success"] = success
    return r


class TestPairsTable:
    def test_2x2_assembly_and_exclusions(self):
        m = "demo/model"
        records = [
            _trial(m, "p1", "T3", True), _trial(m, "p1", "T2", True),    # both
            _trial(m, "p2", "T3", True), _trial(m, "p2", "T2", False),   # mech only
            _trial(m, "p3", "T3", False), _trial(m, "p3", "T2", True),   # base only
            _trial(m, "p4", "T3", False), _trial(m, "p4", "T2", False),  # neither
            _trial(m, "p5", "T3", True), _trial(m, "p5", "T2", invalid="x"),  # excluded
            _trial(m, "p6", "T3", True),                                  # no T2 at all
            _trial(m, "p7", "T3", True), _trial(m, "p7", "T1", True),     # T1 irrelevant
            _trial("other/model", "p1", "T2", True),                      # other model
        ]
        t = pairs_table(records, m)
        assert (t["both"], t["mech_only"], t["base_only"], t["neither"]) == (1, 1, 1, 1)
        assert t["n_pairs"] == 4

    def test_ungraded_trial_is_not_a_valid_arm(self):
        m = "demo/model"
        records = [
            _trial(m, "p1", "T3", True),
            {"model": m, "problem_id": "p1", "arm": "T2", "patch": None},  # never graded
        ]
        assert pairs_table(records, m)["n_pairs"] == 0


def _bank_entry(pid):
    return {"problem_id": pid, "buggy_code": "x = 1\n", "fixed_code": "x = 2\n"}


def _prior(kind, pid, final, protocol=None):
    r = {"kind": kind, "problem_id": pid, "final": final,
         "render": "note" if final else None}
    if protocol:
        r["protocol"] = protocol
    return r


class TestGenJobs:
    def test_d5a_carry_and_regen_rules(self):
        bank = [_bank_entry(p) for p in ("a", "b", "c", "d")]
        prior = [
            _prior("T2", "a", final={"x": 1}, protocol="v2"),  # carries
            _prior("T2", "b", final={"x": 1}),                 # v1-organic -> regen
            _prior("T2", "c", final=None, protocol="v2"),      # never accepted -> job
            _prior("T1", "a", final={"x": 1}),                 # T1 carries
        ]
        jobs, carried = gen_jobs(bank, prior, k=4)
        t2_pids = [e["problem_id"] for kind, e in jobs if kind == "T2"]
        t1_pids = [e["problem_id"] for kind, e in jobs if kind == "T1"]
        assert t2_pids == ["b", "c", "d"]
        assert t1_pids == ["b", "c", "d"]
        carried_keys = {(r["kind"], r["problem_id"]) for r in carried}
        assert carried_keys == {("T2", "a"), ("T1", "a")}

    def test_t2_jobs_come_first_for_the_smoke_gate(self):
        bank = [_bank_entry(p) for p in ("a", "b")]
        jobs, _ = gen_jobs(bank, [], k=2)
        assert [kind for kind, _ in jobs] == ["T2", "T2", "T1", "T1"]

    def test_k_slices_the_bank_prefix(self):
        bank = [_bank_entry(p) for p in ("a", "b", "c")]
        jobs, _ = gen_jobs(bank, [], k=2)
        assert {e["problem_id"] for _, e in jobs} == {"a", "b"}


class TestExistingKeys:
    def test_reads_keys_and_tolerates_blanks(self):
        lines = [
            json.dumps({"model": "m", "problem_id": "p1", "arm": "T3"}),
            "",
            json.dumps({"model": "m", "problem_id": "p1", "arm": "T2", "cost": 0.1}),
        ]
        assert existing_keys(lines) == {("m", "p1", "T3"), ("m", "p1", "T2")}


class TestSmokeGates:
    def test_gen_gate_bands(self):
        assert gen_gate(accepted=7, mean_cost=2 * EST_DRAFT_COST) is True
        assert gen_gate(accepted=6, mean_cost=EST_DRAFT_COST) is False
        assert gen_gate(accepted=10, mean_cost=2.1 * EST_DRAFT_COST) is False

    def test_arm_gate_bands(self):
        est = 0.0005
        assert arm_gate(parse_ok=4, mean_cost=2 * est, arm_est=est) is True
        assert arm_gate(parse_ok=3, mean_cost=est, arm_est=est) is False
        assert arm_gate(parse_ok=5, mean_cost=2.5 * est, arm_est=est) is False

    def test_parse_floor(self):
        assert parse_floor_ok(parse_ok=120, total=150) is True
        assert parse_floor_ok(parse_ok=119, total=150) is False
        assert parse_floor_ok(parse_ok=0, total=0) is True  # nothing ran, nothing broken

    def test_lifetime_guard_at_five_dollars(self):
        assert lifetime_ok(prior_total=4.0, wave_est=1.0) is True
        assert lifetime_ok(prior_total=4.0, wave_est=1.01) is False


class TestSignedConstants:
    def test_roster_and_arm_estimates_line_up(self):
        assert K == 150 and M1_CAP == 1.00
        assert MODELS == ["deepseek/deepseek-chat-v3.1",
                          "qwen/qwen3-coder-30b-a3b-instruct"]
        for slug in MODELS:
            assert set(ARM_EST[slug]) == {"T1", "T2", "T3"}
            assert all(0 < c < 0.01 for c in ARM_EST[slug].values())
