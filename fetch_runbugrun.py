"""fetch_runbugrun.py — fetch + verify the raw data layer into data/raw/ (gitignored).

Sources (verified 2026-07-10, see docs/M0-BRIEF.md "Data reality"):
  - RunBugRun JSONL release assets (giganticode/run_bug_run_data v0.0.1): python bugs
    (test+valid splits) + tests. md5s verified against the release's own Manifest.
  - PIE4Perf problem_statements_translated.zip: English CodeNet problem statements
    (RunBugRun's credited translation source; ~100% coverage of our splits),
    pinned by sha256 observed at first fetch.

The SQLite lrzip dump is deliberately NOT used. Idempotent: valid files are skipped.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).parent / "data" / "raw"
RBR = "https://github.com/giganticode/run_bug_run_data/releases/download/v0.0.1"
PIE = "https://github.com/madaan/pie-perf/raw/main/data/problem_statements_translated.zip"

FILES = {  # name -> (url, algo, digest)
    "python_test0.jsonl.gz": (f"{RBR}/python_test0.jsonl.gz", "md5", "375f056565af619146c12e0e63e3974c"),
    "python_valid0.jsonl.gz": (f"{RBR}/python_valid0.jsonl.gz", "md5", "64b3c22f82916f4809093bb7f519a13b"),
    "tests_all.jsonl.gz": (f"{RBR}/tests_all.jsonl.gz", "md5", "6eaac2b6a535aa8b5213489c6511cb26"),
    "pie_problem_statements.zip": (
        PIE, "sha256", "4699adc312a2ad29c5c3a02cbcc0fa13342196a43ec72614d88e59cb482a30a4"),
}


def _digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, (url, algo, want) in FILES.items():
        dest = RAW / name
        if dest.exists() and _digest(dest, algo) == want:
            print(f"  ok       {name}")
            continue
        print(f"  fetching {name} …", flush=True)
        urllib.request.urlretrieve(url, dest)
        got = _digest(dest, algo)
        if got != want:
            print(f"  FAIL     {name}: {algo} {got} != {want}")
            ok = False
        else:
            print(f"  verified {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
