"""Spec for sandbox.py — Docker-isolated execution of untrusted model-generated code.

Integration tests: they run real containers (python:3.12-slim). Skipped cleanly if
Docker isn't available. The invariants under test are the security/semantics spine:
no network, per-test fresh process, wall timeout kills runaways, nonzero exit or
exception = that test fails, expected outputs never enter the container.
"""
import shutil
import subprocess

import pytest

docker_available = shutil.which("docker") is not None and (
    subprocess.run(
        ["docker", "info"], capture_output=True, timeout=30
    ).returncode
    == 0
)

pytestmark = pytest.mark.skipif(not docker_available, reason="docker not available")

from sandbox import run_tests, grade_program  # noqa: E402


class TestRunTests:
    def test_echo_program_runs_per_test(self):
        code = "s = input()\nprint(int(s) * 2)\n"
        results = run_tests(code, ["3\n", "10\n"])
        assert [r.rc for r in results] == [0, 0]
        assert results[0].stdout.strip() == "6"
        assert results[1].stdout.strip() == "20"
        assert not results[0].timed_out

    def test_infinite_loop_times_out_and_fails(self):
        results = run_tests("while True:\n    pass\n", ["\n"], timeout_s=2)
        assert results[0].timed_out is True
        assert results[0].rc != 0

    def test_exception_is_nonzero_exit(self):
        results = run_tests("raise ValueError('boom')\n", ["\n"])
        assert results[0].rc != 0
        assert results[0].timed_out is False

    def test_network_is_dead(self):
        code = (
            "import urllib.request\n"
            "urllib.request.urlopen('https://example.com', timeout=3)\n"
            "print('reached')\n"
        )
        results = run_tests(code, ["\n"], timeout_s=8)
        assert results[0].rc != 0
        assert "reached" not in results[0].stdout


class TestGradeProgram:
    def test_correct_program_passes_all(self):
        code = "a, b = map(int, input().split())\nprint(a + b)\n"
        tests = [
            {"input": "1 2\n", "output": "3\n"},
            {"input": "10 20\n", "output": "30\n"},
        ]
        verdict = grade_program(code, tests, mode="exact")
        assert verdict["passed"] == 2 and verdict["failed"] == 0
        assert verdict["per_test"] == [True, True]

    def test_wrong_program_fails_some(self):
        code = "a, b = map(int, input().split())\nprint(a - b)\n"
        tests = [
            {"input": "1 2\n", "output": "3\n"},
            {"input": "5 0\n", "output": "5\n"},  # a-b == a+b when b == 0
        ]
        verdict = grade_program(code, tests, mode="exact")
        assert verdict["per_test"] == [False, True]
