#!/usr/bin/env python3
"""Thin wrapper over the relate CLI, shared by the create-solution-package-v2 test-mode scripts.

Every call sets RELATE_TELEMETRY=0 (telemetry defaults to on), uses --mode envelope, passes
--max-rows 0 unless told otherwise (the CLI caps rows at 100 under an agent harness), and binds
parameters as JSON: a bare `123` would arrive as an INTEGER, so strings are always quoted.
RELATE.md records the behaviours relied on here. Standard library only; Python 3.9 or later.

When Relate is not installed, BIN is None, version() returns None, and require() exits with the install
guidance instead of a traceback. check_relate.py reports the same state to the user."""
from __future__ import annotations

import dataclasses, json, os, shutil, subprocess, sys, time

PINNED_VERSION = "0.1.3"   # RELATE.md, "Pinned version"; change both together
MIN_PYTHON = (3, 9)
DEFAULT_PATH = os.path.expanduser("~/.local/bin/relate")   # where Relate's install.sh puts it


def find_binary():
    """The relate binary to use: $RELATE_BIN, then `relate` on PATH, then ~/.local/bin/relate; None if absent."""
    for cand in (os.environ.get("RELATE_BIN"), shutil.which("relate"), DEFAULT_PATH):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


BIN = find_binary()
ENV = {**os.environ, "RELATE_TELEMETRY": "0"}

MISSING = f"""Relate is not installed, so test mode cannot run.

Relate is the embedded Cypher engine test mode imports packages into. Install it (macOS or Linux;
the repository is internal, so the installer needs a GitHub token with access to relatedb/relate):

  gh api repos/relatedb/relate/contents/distribution/install.sh -H "Accept: application/vnd.github.raw" \\
    | GITHUB_TOKEN=$(gh auth token) sh

It installs to {DEFAULT_PATH}. Then check with:  python3 <skill-path>/scripts/check_relate.py
Without Relate, a package can still be built, but no query is executed: every query needs manual
testing on Aura (SKILL.md, "Without Relate")."""


def require():
    """Exit with the install guidance when Relate or a new enough Python is missing."""
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"Python {'.'.join(map(str, MIN_PYTHON))} or later is needed; this is {sys.version.split()[0]}.")
    if not BIN:
        sys.exit(MISSING)


@dataclasses.dataclass
class Result:
    exit: int
    envelopes: list
    error: dict | None
    stderr: str
    seconds: float

    @property
    def last(self):
        return self.envelopes[-1] if self.envelopes else {}

    @property
    def rows(self):
        return self.last.get("rows", [])

    @property
    def columns(self):
        return self.last.get("columns", [])

    @property
    def notifications(self):
        return [n for e in self.envelopes for n in e.get("notifications", [])]

    @property
    def message(self):
        if self.error:
            return " ".join(str(self.error.get("message", "")).split())
        lines = self.stderr.strip().splitlines()
        return lines[-1] if self.exit and lines else ""

    @property
    def error_class(self):
        """exit code plus the envelope's error code and kind, e.g. '6 validation_error/semantic'."""
        if not self.exit:
            return ""
        e = self.error or {}
        return f"{self.exit} {e.get('code', '?')}/{e.get('kind', '?')}"

    def table(self):
        """Rows as lists in column order (envelope rows are maps with sorted keys)."""
        return [[r.get(c) for c in self.columns] for r in self.rows]


def run(statement=None, db=":memory:", *, script=None, csv_dir=None, params=None, timeout="60s",
        max_rows=0, mode="envelope", extra=(), env=None, wall=900):
    """Run one statement (-c) or a script on stdin (`query`) and parse the envelope lines."""
    args = [BIN, "--database", str(db), "--mode", mode]
    if max_rows is not None:
        args += ["--max-rows", str(max_rows)]
    if timeout:
        args += ["--timeout", str(timeout)]
    if csv_dir:
        args += ["--load-csv-dir", str(csv_dir)]
    for k, v in (params or {}).items():
        args += ["--param", f"{k}={json.dumps(v)}"]
    args += list(extra)
    args += ["query"] if script is not None else ["-c", statement]
    t = time.monotonic()
    try:
        p = subprocess.run(args, input=script, capture_output=True, text=True,
                           env={**ENV, **(env or {})}, timeout=wall)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = 124, e.stdout or "", f"wall-clock limit of {wall}s exceeded"
        out = out.decode() if isinstance(out, bytes) else out
    secs = time.monotonic() - t
    envelopes, error = [], None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if set(obj) == {"error"}:
            error = obj["error"]
        else:
            envelopes.append(obj)
    return Result(code, envelopes, error, err, secs)


def version():
    """`relate --version --json` as a dict, or None when Relate is missing or does not answer."""
    if not BIN:
        return None
    try:
        p = subprocess.run([BIN, "--version", "--json"], capture_output=True, text=True, env=ENV, timeout=30)
        return json.loads(p.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def plan_operators(plan):
    """Flatten an EXPLAIN plan tree into its operatorType names."""
    if not plan:
        return []
    return [plan.get("operatorType", "")] + [o for c in plan.get("children", []) for o in plan_operators(c)]
