"""Spec for the v2 probe parser (probe-wording audit, approved 2026-07-10).

v2 lets the model reason before answering, so labels may appear mid-reasoning;
the verdict is ONLY the label on the last non-empty line — exactly one, else INVALID.
"""
from prompts import parse_probe_v2


class TestParseProbeV2:
    def test_verdict_on_last_line(self):
        assert parse_probe_v2("The real bug is line 3, not 5.\nINCORRECT") == "INCORRECT"

    def test_reasoning_may_mention_both_labels(self):
        text = "If it pointed at line 3 it would be CORRECT, else INCORRECT.\nCORRECT"
        assert parse_probe_v2(text) == "CORRECT"

    def test_trailing_punctuation_ok(self):
        assert parse_probe_v2("analysis...\nINCORRECT.") == "INCORRECT"

    def test_trailing_blank_lines_ignored(self):
        assert parse_probe_v2("reasoning\nCORRECT\n\n") == "CORRECT"

    def test_both_labels_on_last_line_invalid(self):
        assert parse_probe_v2("hmm\nCORRECT or INCORRECT") is None

    def test_no_label_on_last_line_invalid(self):
        assert parse_probe_v2("CORRECT is likely\nbut I am not sure") is None

    def test_empty_invalid(self):
        assert parse_probe_v2("") is None

    def test_case_insensitive(self):
        assert parse_probe_v2("verdict:\nincorrect") == "INCORRECT"
