#!/usr/bin/env python3
"""Thin wrapper over the relate CLI, shared by the create-solution-package-v2 test-mode scripts.

Every call sets RELATE_TELEMETRY=0 (telemetry defaults to on), uses --mode envelope, passes
--max-rows 0 unless told otherwise (the CLI caps rows at 100 under an agent harness), and binds
parameters as JSON: a bare `123` would arrive as an INTEGER, so strings are always quoted.
RELATE.md records the behaviours relied on here. Standard library only."""
import dataclasses, json, os, shutil, subprocess, time

BIN = shutil.which("relate") or os.path.expanduser("~/.local/bin/relate")
ENV = {**os.environ, "RELATE_TELEMETRY": "0"}


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
    p = subprocess.run([BIN, "--version", "--json"], capture_output=True, text=True, env=ENV)
    return json.loads(p.stdout)


def plan_operators(plan):
    """Flatten an EXPLAIN plan tree into its operatorType names."""
    if not plan:
        return []
    return [plan.get("operatorType", "")] + [o for c in plan.get("children", []) for o in plan_operators(c)]
