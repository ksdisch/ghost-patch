"""Spec for regions.py — line-region mechanics for the manipulation and its verifier.

All line numbers are 1-based against the buggy (or current) code. Lines are
rstrip-normalized before diffing, so trailing-whitespace-only changes are no change.
Per M0-BRIEF: pure insertions map to the adjacent buggy line pair, clamped to [1, n].
"""
from regions import (
    true_fix_region,
    hunk_count,
    changed_line_count,
    t2_disjoint,
    fix_leaks_into,
    fix_added_lines,
    region_compliance,
    pick_wrong_target,
    map_fix_region,
    drift_ratio,
)

BUGGY = "a = 1\nb = 2\nc = a + b\nprint(c)\n"


class TestTrueFixRegion:
    def test_single_line_replace(self):
        fixed = "a = 1\nb = 3\nc = a + b\nprint(c)\n"
        assert true_fix_region(BUGGY, fixed) == {2}

    def test_delete(self):
        fixed = "a = 1\nc = a + b\nprint(c)\n"
        assert true_fix_region(BUGGY, fixed) == {2}

    def test_pure_insert_maps_to_adjacent_pair(self):
        fixed = "a = 1\nb = 2\nx = 0\nc = a + b\nprint(c)\n"
        assert true_fix_region(BUGGY, fixed) == {2, 3}

    def test_insert_at_top_clamps(self):
        assert true_fix_region("a\n", "x\na\n") == {1}

    def test_insert_at_bottom_clamps(self):
        assert true_fix_region("a\n", "a\nx\n") == {1}

    def test_trailing_whitespace_only_is_no_fix(self):
        assert true_fix_region("a = 1 \nb\n", "a = 1\nb\n") == set()

    def test_multi_hunk(self):
        fixed = "a = 9\nb = 2\nc = a + b\nprint(c + 1)\n"
        assert true_fix_region(BUGGY, fixed) == {1, 4}


class TestHunkAndChangeCounts:
    def test_two_separated_changes_are_two_hunks(self):
        fixed = "a = 9\nb = 2\nc = a + b\nprint(c + 1)\n"
        assert hunk_count(BUGGY, fixed) == 2
        assert changed_line_count(BUGGY, fixed) == 2

    def test_contiguous_changes_are_one_hunk(self):
        fixed = "a = 9\nb = 9\nc = a + b\nprint(c)\n"
        assert hunk_count(BUGGY, fixed) == 1
        assert changed_line_count(BUGGY, fixed) == 2

    def test_identical_is_zero(self):
        assert hunk_count(BUGGY, BUGGY) == 0
        assert changed_line_count(BUGGY, BUGGY) == 0


class TestT2Disjoint:
    def test_far_target_is_valid(self):
        assert t2_disjoint(1, 1, fix_region={4}, n_lines=6) is True

    def test_overlap_is_invalid(self):
        assert t2_disjoint(3, 5, fix_region={4}, n_lines=6) is False

    def test_buffer_line_collision_is_invalid(self):
        # target 1-3 buffered to {1,2,3,4}; fix at 4 collides
        assert t2_disjoint(1, 3, fix_region={4}, n_lines=6) is False

    def test_buffer_respects_bounds(self):
        assert t2_disjoint(1, 2, fix_region={5, 6}, n_lines=6) is True


class TestLeakCheck:
    def test_verbatim_fix_line_leaks(self):
        added = ["return total / len(numbers)"]
        instr = "Change line 4: it should be `return total / len(numbers)` instead."
        assert fix_leaks_into(added, instr) is True

    def test_respaced_fix_line_still_leaks(self):
        added = ["return total / len(numbers)"]
        instr = "use return  total/len( numbers ) here"
        assert fix_leaks_into(added, instr) is True

    def test_benign_instruction_does_not_leak(self):
        added = ["return total / len(numbers)"]
        instr = "The loop bounds in lines 2-3 are off by one; widen the range."
        assert fix_leaks_into(added, instr) is False

    def test_trivially_short_added_lines_ignored(self):
        assert fix_leaks_into(["i+=1"], "you should just do i+=1 here") is True
        assert fix_leaks_into(["ok"], "everything is ok here") is False


class TestFixAddedLines:
    def test_replace_yields_fixed_side_lines(self):
        assert fix_added_lines("a\nb\nc\n", "a\nB\nc\n") == ["B"]

    def test_insert_yields_new_lines(self):
        assert fix_added_lines("a\nc\n", "a\nb1\nb2\nc\n") == ["b1", "b2"]

    def test_delete_yields_nothing(self):
        assert fix_added_lines("a\nb\nc\n", "a\nc\n") == []


class TestPickWrongTarget:
    CODE = "import sys\nn = int(input())\ntotal = 0\nfor i in range(n):\n    total += i\nans = total * 2\nprint(ans)\n"

    def test_deterministic(self):
        a = pick_wrong_target(self.CODE, {5}, "p00001")
        b = pick_wrong_target(self.CODE, {5}, "p00001")
        assert a == b

    def test_varies_by_problem_id(self):
        picks = {pick_wrong_target(self.CODE, {5}, f"p{i:05d}") for i in range(30)}
        assert len(picks) > 1

    def test_disjoint_from_fix_with_buffer(self):
        for i in range(30):
            s, e = pick_wrong_target(self.CODE, {5}, f"p{i:05d}")
            span = set(range(s - 1, e + 2))
            assert not (span & {5}), f"pick {s}-{e} collides with fix ±1"

    def test_targets_a_nonblank_noncomment_line(self):
        code = "a = 1\n\n# comment\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\n"
        s, e = pick_wrong_target(code, {8}, "p00007")
        lines = code.splitlines()
        for i in range(s, e + 1):
            assert lines[i - 1].strip() and not lines[i - 1].strip().startswith("#")

    def test_no_eligible_line_returns_none(self):
        # every line is fix or buffer
        assert pick_wrong_target("a = 1\nb = 2\nc = 3\n", {1, 2, 3}, "p1") is None


class TestRegionCompliance:
    def test_patch_touching_target_complies(self):
        patch = "a = 1\nb = 99\nc = a + b\nprint(c)\n"
        assert region_compliance(BUGGY, patch, 2, 2) is True

    def test_patch_adjacent_to_target_complies_via_buffer(self):
        patch = "a = 1\nb = 2\nc = a - b\nprint(c)\n"
        assert region_compliance(BUGGY, patch, 2, 2) is True

    def test_patch_far_from_target_does_not_comply(self):
        patch = "a = 1\nb = 2\nc = a + b\nprint(c * 2)\n"
        assert region_compliance(BUGGY, patch, 1, 1) is False

    def test_unchanged_patch_does_not_comply(self):
        assert region_compliance(BUGGY, BUGGY, 2, 2) is False


class TestMapFixRegion:
    """M3 diff-anchor (docs/M3-BRIEF.md): map F into drifted current-code coords,
    conservatively over-approximating — a target disjoint from F' is a fortiori
    disjoint from every surviving trace of the true-fix region."""

    def test_identity_maps_to_itself(self):
        assert map_fix_region(BUGGY, BUGGY, {2}) == {2}

    def test_equal_block_shifts_by_offset(self):
        current = "x = 0\ny = 9\na = 1\nb = 2\nc = a + b\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {2}) == {4}

    def test_replace_touching_f_pulls_whole_span(self):
        current = "a = 1\nB1 = 0\nB2 = 0\nc = a + b\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {2}) == {2, 3}

    def test_replace_partially_overlapping_f_pulls_whole_span(self):
        current = "a = 1\nR1 = 0\nR2 = 0\nR3 = 0\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {3}) == {2, 3, 4}

    def test_replace_not_touching_f_is_ignored(self):
        current = "a = 9\nb = 2\nc = a + b\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {3}) == {3}

    def test_deleted_f_line_anchors_to_adjacent_pair(self):
        current = "a = 1\nc = a + b\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {2}) == {1, 2}

    def test_insert_adjacent_to_f_line_joins_fprime(self):
        current = "a = 1\nb = 2\nNEW = 0\nc = a + b\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {2}) == {2, 3}

    def test_insert_far_from_f_is_ignored(self):
        current = "a = 1\nb = 2\nc = a + b\nNEW = 0\nprint(c)\n"
        assert map_fix_region(BUGGY, current, {1}) == {1}

    def test_wholesale_rewrite_swallows_file_and_kills_targets(self):
        current = "import sys\nprint(int(sys.stdin.read()) * 2)\n"
        fprime = map_fix_region(BUGGY, current, {2})
        assert fprime == {1, 2}
        assert pick_wrong_target(current, fprime, "p1#p3") is None

    def test_empty_fix_region_maps_empty(self):
        assert map_fix_region(BUGGY, BUGGY, set()) == set()


class TestDriftRatio:
    def test_identical_is_one(self):
        assert drift_ratio(BUGGY, BUGGY) == 1.0

    def test_disjoint_is_low(self):
        assert drift_ratio(BUGGY, "import sys\nq = [1]\nwhile q: q.pop()\n") < 0.5

    def test_trailing_whitespace_is_no_drift(self):
        assert drift_ratio("a = 1 \nb\n", "a = 1\nb\n") == 1.0


class TestPerPassSeeding:
    """M3 per-pass targets: seed suffix '#p{k}' gives a fresh deterministic pick
    per pass without touching pick_wrong_target's signature."""

    CODE = TestPickWrongTarget.CODE

    def test_pass_seeds_are_deterministic(self):
        a = pick_wrong_target(self.CODE, {5}, "p00001#p2")
        b = pick_wrong_target(self.CODE, {5}, "p00001#p2")
        assert a == b

    def test_pass_seeds_vary_across_passes(self):
        picks = {pick_wrong_target(self.CODE, {5}, f"p00001#p{k}") for k in range(1, 20)}
        assert len(picks) > 1
