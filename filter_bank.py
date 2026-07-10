"""filter_bank.py — the pre-committed stage-1 bank filter + frozen pool assembly.

Criteria are pre-committed in docs/M0-BRIEF.md; this file is their executable form.
Run as a script it reads data/raw/, applies stage 1, and writes the frozen ordered
pool to data/pool.json (committed). Stage 2 (the sandbox smoke) consumes the pool
in order — see m0.py.

Determinism guarantees: fixed shuffle seed (2607), dedup by lowest numeric bug id,
problems sorted before shuffling, test selection by lowest test id capped at 20.
"""
from __future__ import annotations

import gzip
import html
import json
import random
import re
from html.parser import HTMLParser
from pathlib import Path

from regions import true_fix_region, hunk_count, changed_line_count

SEED = 2607
RAW = Path(__file__).parent / "data" / "raw"
POOL_PATH = Path(__file__).parent / "data" / "pool.json"

MIN_LINES, MAX_LINES = 3, 40
MAX_CHARS = 2000
MAX_HUNKS = 2
MAX_CHANGED_LINES = 6
MIN_LINES_OUTSIDE_FIX = 5
MIN_DESC, MAX_DESC = 100, 2500
MIN_ASCII_RATIO = 0.9
MIN_TESTS, MAX_TESTS = 3, 20


# ---------- stage-1 predicates (unit-tested) ----------

def compiles_py3(code: str) -> bool:
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # bug code is full of SyntaxWarning noise
            compile(code, "<bug>", "exec")
        return True
    except (SyntaxError, ValueError):
        return False


def size_ok(code: str) -> bool:
    nonblank = [ln for ln in code.splitlines() if ln.strip()]
    return MIN_LINES <= len(nonblank) <= MAX_LINES and len(code) <= MAX_CHARS


def fix_local(buggy: str, fixed: str) -> bool:
    region = true_fix_region(buggy, fixed)
    if not region:
        return False  # whitespace-only / identical "fix" is not a fix
    if hunk_count(buggy, fixed) > MAX_HUNKS:
        return False
    if changed_line_count(buggy, fixed) > MAX_CHANGED_LINES:
        return False
    n = len(buggy.splitlines())
    return n - len(region) >= MIN_LINES_OUTSIDE_FIX


def desc_ok(text: str) -> bool:
    if not (MIN_DESC <= len(text) <= MAX_DESC):
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text) >= MIN_ASCII_RATIO


def dedup_bugs(records: list[dict]) -> list[dict]:
    """One bug per problem_id: lowest numeric id wins; output sorted by problem_id."""
    best: dict[str, dict] = {}
    for rec in records:
        pid = rec["problem_id"]
        if pid not in best or int(rec["id"]) < int(best[pid]["id"]):
            best[pid] = rec
    return [best[pid] for pid in sorted(best)]


def shuffle_pool(items: list) -> list:
    out = list(items)
    random.Random(SEED).shuffle(out)
    return out


# ---------- PIE HTML -> text ----------

class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in {"p", "br", "div", "pre", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html_src: str) -> str:
    parser = _TextExtractor()
    parser.feed(html.unescape("") + html_src)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------- pool assembly (script mode) ----------

def _iter_jsonl_gz(path: Path):
    with gzip.open(path, "rt") as f:
        for line in f:
            yield json.loads(line)


def load_descriptions() -> dict[str, str]:
    """problem_id -> extracted English statement text, from the PIE zip."""
    import zipfile

    zf = zipfile.ZipFile(RAW / "pie_problem_statements.zip")
    out: dict[str, str] = {}
    for name in zf.namelist():
        m = re.search(r"(p\d{5})\.html$", name)
        if m:
            out[m.group(1)] = html_to_text(zf.read(name).decode("utf-8", errors="replace"))
    return out


def load_tests() -> dict[str, list[dict]]:
    """problem_id -> selected tests (lowest id, capped at MAX_TESTS)."""
    by_pid: dict[str, list[dict]] = {}
    for rec in _iter_jsonl_gz(RAW / "tests_all.jsonl.gz"):
        by_pid.setdefault(rec["problem_id"], []).append(rec)
    for pid, tests in by_pid.items():
        tests.sort(key=lambda t: int(t["id"]))
        by_pid[pid] = tests[:MAX_TESTS]
    return by_pid


def build_pool() -> dict:
    """Apply stage 1 over test0 then valid0; return the frozen pool + funnel counts."""
    descs = load_descriptions()
    tests = load_tests()
    funnel = {"bugs_seen": 0, "compile": 0, "size": 0, "fix_local": 0, "desc": 0, "tests": 0}
    survivors: list[dict] = []
    for split in ("python_test0", "python_valid0"):
        for rec in _iter_jsonl_gz(RAW / f"{split}.jsonl.gz"):
            funnel["bugs_seen"] += 1
            buggy, fixed = rec["buggy_code"], rec["fixed_code"]
            if not (compiles_py3(buggy) and compiles_py3(fixed)):
                continue
            funnel["compile"] += 1
            if not (size_ok(buggy) and size_ok(fixed)):
                continue
            funnel["size"] += 1
            if not fix_local(buggy, fixed):
                continue
            funnel["fix_local"] += 1
            desc = descs.get(rec["problem_id"])
            if desc is None or not desc_ok(desc):
                continue
            funnel["desc"] += 1
            sel = tests.get(rec["problem_id"], [])
            if len(sel) < MIN_TESTS:
                continue
            funnel["tests"] += 1
            survivors.append(
                {
                    "bug_id": rec["id"],
                    "problem_id": rec["problem_id"],
                    "split": split,
                    "buggy_code": buggy,
                    "fixed_code": fixed,
                    "description": desc,
                    "test_ids": [int(t["id"]) for t in sel],
                }
            )
    deduped = dedup_bugs([{**s, "id": s["bug_id"]} for s in survivors])
    for d in deduped:
        d.pop("id")
    ordered = shuffle_pool(deduped)
    return {"seed": SEED, "funnel": funnel, "unique_problems": len(deduped), "pool": ordered}


if __name__ == "__main__":
    result = build_pool()
    POOL_PATH.parent.mkdir(exist_ok=True)
    POOL_PATH.write_text(json.dumps(result, indent=1))
    f = result["funnel"]
    print(f"funnel: {f}")
    print(f"unique problems after dedup: {result['unique_problems']}")
    print(f"pool written to {POOL_PATH}")
