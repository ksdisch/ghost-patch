"""Spec for grading.py — the two pre-registered output-comparison semantics (M0-BRIEF D4).

S-exact: rstrip each line, drop trailing blank lines, exact match.
S-float: S-exact normalization, then token-wise float tolerance (abs or rel <= 1e-4)
for tokens where both parse as finite floats and at least one is written with '.' or 'e';
line and token counts must match.

These are THE scoring semantics for every milestone — silent corruption here poisons
everything downstream, hence the exhaustive edge cases.
"""
from grading import compare_outputs


class TestSExact:
    M = "exact"

    def test_identical(self):
        assert compare_outputs("1\n2\n", "1\n2\n", self.M) is True

    def test_trailing_spaces_on_lines_ignored(self):
        assert compare_outputs("1 \n2\t\n", "1\n2\n", self.M) is True

    def test_trailing_blank_lines_ignored(self):
        assert compare_outputs("1\n2\n\n\n", "1\n2", self.M) is True

    def test_missing_final_newline_equivalent(self):
        assert compare_outputs("YES\n", "YES", self.M) is True

    def test_different_content_fails(self):
        assert compare_outputs("1\n2\n", "1\n3\n", self.M) is False

    def test_internal_blank_lines_matter(self):
        assert compare_outputs("1\n\n2\n", "1\n2\n", self.M) is False

    def test_leading_whitespace_matters(self):
        assert compare_outputs(" 1\n", "1\n", self.M) is False

    def test_float_formatting_differences_fail_exact(self):
        assert compare_outputs("1.0\n", "1.00\n", self.M) is False

    def test_case_sensitive(self):
        assert compare_outputs("YES\n", "yes\n", self.M) is False

    def test_empty_vs_empty(self):
        assert compare_outputs("", "", self.M) is True

    def test_empty_vs_blank_lines(self):
        assert compare_outputs("", "\n\n", self.M) is True


class TestSFloat:
    M = "float"

    def test_float_formatting_differences_pass(self):
        assert compare_outputs("1.0\n", "1.00\n", self.M) is True

    def test_within_absolute_tolerance(self):
        assert compare_outputs("0.33333\n", "0.33334\n", self.M) is True

    def test_outside_tolerance_fails(self):
        assert compare_outputs("0.3\n", "0.4\n", self.M) is False

    def test_relative_tolerance_for_large_values(self):
        # abs diff 0.1 > 1e-4, but rel diff 1e-6 <= 1e-4.
        assert compare_outputs("100000.1\n", "100000.2\n", self.M) is True

    def test_int_vs_float_spelling_of_same_number(self):
        assert compare_outputs("5\n", "5.0\n", self.M) is True

    def test_bare_int_tokens_compare_exactly(self):
        # neither token written with '.' or 'e' -> exact token match required
        assert compare_outputs("5\n", "6\n", self.M) is False

    def test_non_numeric_tokens_exact(self):
        assert compare_outputs("abc def\n", "abc def\n", self.M) is True
        assert compare_outputs("abc\n", "abd\n", self.M) is False

    def test_token_count_must_match(self):
        assert compare_outputs("1 2\n", "1\n", self.M) is False

    def test_line_count_must_match(self):
        assert compare_outputs("1\n2\n", "1\n", self.M) is False

    def test_mixed_line(self):
        assert compare_outputs("ans 3.14159 ok\n", "ans 3.14160 ok\n", self.M) is True

    def test_trailing_whitespace_still_normalized(self):
        assert compare_outputs("1.0 \n", "1.00\n", self.M) is True

    def test_scientific_notation(self):
        assert compare_outputs("1e-3\n", "0.001\n", self.M) is True
