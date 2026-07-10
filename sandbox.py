"""sandbox.py — Docker-isolated execution of untrusted (model-generated) programs.

One container per program run: `python:3.12-slim`, `--network=none`, CPU/mem/pids caps,
read-only rootfs + small tmpfs, non-root. Inside, a tiny runner executes each test as a
fresh Python process with a wall timeout and emits one JSON line per test (rc, stdout,
timed_out). Expected outputs never enter the container — grading happens host-side
(grading.py), so a sandboxed program cannot grade itself.

Infra failures (docker itself breaking) raise SandboxError and are never silently
recorded as test failures — the honesty contract separates "program failed" from
"we failed to run the program".
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from grading import compare_outputs

IMAGE = "python:3.12-slim"
TEST_TIMEOUT_S = 5
CONTAINER_TIMEOUT_S = 120
STDOUT_CAP = 262_144  # 256 KiB per test

# Runs inside the container. Reads /work/tests/in_<i>.txt, runs /work/prog.py per test
# in a fresh process, JSON line per test to stdout. stdout goes to a tmpfs file first
# so a print-flood is bounded by the tmpfs cap, then truncated to STDOUT_CAP.
_RUNNER = r"""
import json, subprocess, sys
n = int(sys.argv[1]); timeout = float(sys.argv[2]); cap = int(sys.argv[3])
for i in range(n):
    out_path = f"/tmp/out_{i}"
    with open(f"/work/tests/in_{i}.txt", "rb") as fin, open(out_path, "wb") as fout:
        try:
            proc = subprocess.run(
                [sys.executable, "/work/prog.py"],
                stdin=fin, stdout=fout, stderr=subprocess.DEVNULL, timeout=timeout,
            )
            rc, timed_out = proc.returncode, False
        except subprocess.TimeoutExpired:
            rc, timed_out = -9, True
        except OSError:
            rc, timed_out = -1, False
    with open(out_path, "rb") as f:
        data = f.read(cap)
    print(json.dumps({"i": i, "rc": rc, "timed_out": timed_out,
                      "stdout": data.decode("utf-8", errors="replace")}), flush=True)
"""


class SandboxError(RuntimeError):
    """Docker/infra failure — distinct from a program failing its tests."""


@dataclass
class TestRun:
    rc: int
    stdout: str
    timed_out: bool


def run_tests(
    code: str,
    inputs: list[str],
    *,
    timeout_s: float = TEST_TIMEOUT_S,
    container_timeout_s: float = CONTAINER_TIMEOUT_S,
) -> list[TestRun]:
    """Run `code` once per test input in a single throwaway container."""
    name = f"ghost-patch-{uuid.uuid4().hex[:12]}"
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        (work / "prog.py").write_text(code)
        (work / "_runner.py").write_text(_RUNNER)
        tdir = work / "tests"
        tdir.mkdir()
        for i, s in enumerate(inputs):
            (tdir / f"in_{i}.txt").write_text(s)
        cmd = [
            "docker", "run", "--rm", "--name", name,
            "--network=none", "--cpus=1", "--memory=512m", "--pids-limit=128",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "-u", "65534:65534",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{work}:/work:ro",
            IMAGE,
            "python", "/work/_runner.py", str(len(inputs)), str(timeout_s), str(STDOUT_CAP),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=container_timeout_s
            )
        except subprocess.TimeoutExpired as e:
            subprocess.run(["docker", "kill", name], capture_output=True)
            raise SandboxError(f"container exceeded {container_timeout_s}s wall cap") from e

    results: dict[int, TestRun] = {}
    for line in proc.stdout.splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        results[rec["i"]] = TestRun(rec["rc"], rec["stdout"], rec["timed_out"])
    if len(results) != len(inputs):
        raise SandboxError(
            f"runner emitted {len(results)}/{len(inputs)} verdicts "
            f"(docker rc={proc.returncode}, stderr={proc.stderr[-500:]!r})"
        )
    return [results[i] for i in range(len(inputs))]


def grade_program(code: str, tests: list[dict], *, mode: str, **kw) -> dict:
    """Sandbox + host-side grading. tests: [{'input': ..., 'output': ...}].

    A test PASSES iff rc == 0, not timed out, and stdout matches under `mode`.
    """
    runs = run_tests(code, [t["input"] for t in tests], **kw)
    per_test = [
        r.rc == 0 and not r.timed_out and compare_outputs(t["output"], r.stdout, mode)
        for r, t in zip(runs, tests)
    ]
    return {
        "passed": sum(per_test),
        "failed": len(per_test) - sum(per_test),
        "per_test": per_test,
    }
