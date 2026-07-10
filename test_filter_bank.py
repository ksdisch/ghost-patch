"""Spec for filter_bank.py stage-1 predicates + PIE HTML->text extraction (M0-BRIEF).

Stage-1 filter criteria are pre-committed in docs/M0-BRIEF.md; these tests pin the
predicates so the bank build is deterministic and auditable.
"""
from filter_bank import (
    compiles_py3,
    size_ok,
    fix_local,
    desc_ok,
    dedup_bugs,
    html_to_text,
    shuffle_pool,
)


class TestCompileGate:
    def test_py3_code_passes(self):
        assert compiles_py3("print('x')\n") is True

    def test_py2_print_statement_fails(self):
        assert compiles_py3("print 'x'\n") is False

    def test_syntax_error_fails(self):
        assert compiles_py3("def f(:\n") is False


class TestSizeOk:
    def test_normal_program_passes(self):
        assert size_ok("a = 1\nb = 2\nprint(a + b)\n") is True

    def test_too_few_nonblank_lines(self):
        assert size_ok("print(1)\n") is False

    def test_blank_lines_do_not_count(self):
        code = "a = 1\n\n\nb = 2\n\nprint(a + b)\n"
        assert size_ok(code) is True

    def test_too_many_lines(self):
        assert size_ok("\n".join(f"x{i} = {i}" for i in range(41)) + "\n") is False

    def test_char_cap(self):
        code = "s = '" + "x" * 2000 + "'\nprint(s)\nprint(s)\n"
        assert size_ok(code) is False


class TestFixLocal:
    BUGGY = "a = 1\nb = 2\nc = a + b\nd = c * 2\ne = d - 1\nf = e\nprint(f)\n"

    def test_one_line_fix_is_local(self):
        fixed = self.BUGGY.replace("b = 2", "b = 3")
        assert fix_local(self.BUGGY, fixed) is True

    def test_identical_code_is_not_a_fix(self):
        assert fix_local(self.BUGGY, self.BUGGY) is False

    def test_whitespace_only_change_is_not_a_fix(self):
        assert fix_local(self.BUGGY, self.BUGGY.replace("b = 2", "b = 2  ")) is False

    def test_three_hunks_is_not_local(self):
        fixed = (
            self.BUGGY.replace("a = 1", "a = 9")
            .replace("d = c * 2", "d = c * 9")
            .replace("print(f)", "print(f + 9)")
        )
        assert fix_local(self.BUGGY, fixed) is False

    def test_too_many_changed_lines_is_not_local(self):
        fixed = "\n".join(f"z{i} = {i}" for i in range(7)) + "\n"
        assert fix_local(self.BUGGY, fixed) is False

    def test_needs_five_lines_outside_fix(self):
        # 4-line program, 1-line fix -> only 3 lines outside -> no room for a T2 target
        buggy = "a = 1\nb = 2\nc = 3\nprint(a)\n"
        fixed = "a = 9\nb = 2\nc = 3\nprint(a)\n"
        assert fix_local(buggy, fixed) is False


class TestDescOk:
    def test_normal_english_description(self):
        assert desc_ok("Given two integers a and b, print their sum. " * 5) is True

    def test_too_short(self):
        assert desc_ok("Print the sum.") is False

    def test_too_long(self):
        assert desc_ok("word " * 600) is False

    def test_mostly_non_ascii_fails(self):
        assert desc_ok("与えられた整数を出力してください。" * 20) is False


class TestDedup:
    def test_keeps_lowest_numeric_id_per_problem(self):
        recs = [
            {"id": "30", "problem_id": "p00002"},
            {"id": "4", "problem_id": "p00001"},
            {"id": "7", "problem_id": "p00002"},
            {"id": "100", "problem_id": "p00001"},
        ]
        out = dedup_bugs(recs)
        assert [(r["problem_id"], r["id"]) for r in out] == [
            ("p00001", "4"),
            ("p00002", "7"),
        ]


class TestHtmlToText:
    def test_strips_tags_and_unescapes(self):
        html = "<h1>Title</h1><p>A &amp; B</p><pre>x &lt; y</pre>"
        text = html_to_text(html)
        assert "Title" in text and "A & B" in text and "x < y" in text
        assert "<" not in text.replace("x < y", "")

    def test_script_and_style_dropped(self):
        html = "<style>.x{color:red}</style><script>alert(1)</script><p>keep</p>"
        text = html_to_text(html)
        assert "keep" in text
        assert "alert" not in text and "color" not in text

    def test_blank_runs_collapse(self):
        text = html_to_text("<p>a</p>\n\n\n\n<p>b</p>")
        assert "\n\n\n" not in text


class TestShufflePool:
    def test_seeded_shuffle_is_reproducible(self):
        items = [f"p{i:05d}" for i in range(50)]
        a = shuffle_pool(list(items))
        b = shuffle_pool(list(items))
        assert a == b

    def test_shuffle_actually_permutes(self):
        items = [f"p{i:05d}" for i in range(50)]
        assert shuffle_pool(list(items)) != items

    def test_input_not_mutated(self):
        items = [f"p{i:05d}" for i in range(10)]
        snapshot = list(items)
        shuffle_pool(items)
        assert items == snapshot
