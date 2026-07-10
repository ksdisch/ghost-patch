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
