"""Spec for prompts.py — frozen prompt/parse layer for the pilot.

Pins: patch extraction (last fenced block), probe parsing (word-boundary safe —
'INCORRECT' must never read as 'CORRECT'), generator-draft validation + mechanical
verification (anchor match, T2 disjointness, T1 intersection, leak, render cap),
and the fluent instruction render.
"""
from prompts import (
    extract_patch,
    parse_probe,
    numbered,
    render_instruction,
    verify_draft,
)

CODE = "n = int(input())\ntotal = 0\nfor i in range(n):\n    total += i\nprint(total)\nprint('done')\n"
# true fix region for the hypothetical bug: line 4 (`total += i` -> `total += i + 1`)
FIX_REGION = {4}
FIX_ADDED = ["    total += i + 1"]


class TestExtractPatch:
    def test_takes_last_fenced_block(self):
        text = "First try:\n```python\nx = 1\n```\nActually:\n```python\nx = 2\n```\n"
        assert extract_patch(text) == "x = 2\n"

    def test_lang_tag_optional(self):
        assert extract_patch("```\nprint(1)\n```") == "print(1)\n"

    def test_no_block_is_none(self):
        assert extract_patch("here is code: print(1)") is None

    def test_unclosed_block_is_none(self):
        assert extract_patch("```python\nprint(1)") is None


class TestParseProbe:
    def test_correct(self):
        assert parse_probe("CORRECT") == "CORRECT"

    def test_incorrect_is_not_read_as_correct(self):
        assert parse_probe("INCORRECT") == "INCORRECT"

    def test_case_insensitive(self):
        assert parse_probe("incorrect.") == "INCORRECT"

    def test_embedded_in_sentence(self):
        assert parse_probe("The note is CORRECT.") == "CORRECT"

    def test_both_labels_is_invalid(self):
        assert parse_probe("CORRECT... no wait, INCORRECT") is None

    def test_neither_is_invalid(self):
        assert parse_probe("I cannot decide.") is None


class TestNumbered:
    def test_line_numbers_start_at_one(self):
        out = numbered("a\nb\n")
        assert out.splitlines()[0].startswith("  1 | a")
        assert out.splitlines()[1].startswith("  2 | b")


class TestVerifyDraft:
    def _draft(self, **kw):
        d = {
            "target_start_line": 1,
            "target_end_line": 2,
            "anchor_excerpt": "total = 0",
            "diagnosis": "The accumulator is initialised wrongly for this sum.",
            "directive": "Initialise the accumulator correctly before the loop.",
        }
        d.update(kw)
        return d

    def test_valid_t2_accepted(self):
        ok, reason = verify_draft(self._draft(), CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert ok, reason

    def test_anchor_mismatch_rejected(self):
        d = self._draft(anchor_excerpt="totally = 0")
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "anchor" in reason

    def test_t2_overlap_with_fix_rejected(self):
        d = self._draft(target_start_line=4, target_end_line=4, anchor_excerpt="    total += i")
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "disjoint" in reason

    def test_t2_buffer_collision_rejected(self):
        # line 3 is adjacent to fix line 4 -> +/-1 buffer collides
        d = self._draft(target_start_line=3, target_end_line=3,
                        anchor_excerpt="for i in range(n):")
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "disjoint" in reason

    def test_t2_fix_leak_rejected(self):
        d = self._draft(directive="Replace the line with `total += i + 1` instead.")
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "leak" in reason

    def test_t1_must_intersect_fix(self):
        d = self._draft()  # targets lines 1-2, fix is line 4
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T1")
        assert not ok and "intersect" in reason

    def test_t1_on_fix_accepted_even_with_leak(self):
        d = self._draft(target_start_line=4, target_end_line=4,
                        anchor_excerpt="    total += i",
                        directive="Change it to `total += i + 1`.")
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T1")
        assert ok, reason

    def test_out_of_bounds_rejected(self):
        d = self._draft(target_start_line=5, target_end_line=99)
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "bounds" in reason

    def test_render_cap_rejected(self):
        d = self._draft(diagnosis="x" * 600)
        ok, reason = verify_draft(d, CODE, FIX_REGION, FIX_ADDED, kind="T2")
        assert not ok and "render" in reason


class TestRenderInstruction:
    def test_fluent_confident_surface(self):
        d = {
            "target_start_line": 1,
            "target_end_line": 2,
            "anchor_excerpt": "total = 0",
            "diagnosis": "The accumulator is wrong.",
            "directive": "Fix the initialisation.",
        }
        r = render_instruction(d)
        assert "lines 1-2" in r
        assert "total = 0" in r
        assert "The accumulator is wrong." in r
        assert "Fix the initialisation." in r
