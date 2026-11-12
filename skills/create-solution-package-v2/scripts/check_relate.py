#!/usr/bin/env python3
"""Cold-start check for create-solution-package-v2: is Relate ready for test mode, and if not, what is missing?

Usage: python3 check_relate.py [--json]

Checks Python, finds the relate binary ($RELATE_BIN, PATH, ~/.local/bin/relate), compares its version
with the pin in RELATE.md and runs one statement. When Relate is missing it checks what the installer
needs instead: a supported OS, the GitHub CLI, a login, and access to the internal relatedb/relate repo.
It installs nothing and changes nothing.

Exit codes:
  0  ready: Relate is installed at the pinned version and runs
  1  not installed (or does not run): test mode is unavailable; build without it or install it
  2  installed at a different version: usable, but re-run probe_relate.py before trusting results
  3  Python is too old for the scripts
Standard library only."""
from __future__ import annotations

import json, os, platform, shutil, subprocess, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import relate_cli as cl  # noqa: E402

INSTALL = ('gh api repos/relatedb/relate/contents/distribution/install.sh -H "Accept: application/vnd.github.raw" '
           '| GITHUB_TOKEN=$(gh auth token) sh')


def sh(*args, timeout=30):
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)


def install_prerequisites():
    """What the installer needs, each as (name, ok, detail)."""
    out = []
    system = platform.system()
    out.append(("supported OS", system in ("Darwin", "Linux"),
                f"{system} {platform.machine()}" + ("" if system in ("Darwin", "Linux") else
                " — the installer supports macOS and Linux only; on Windows, download relate-windows-amd64.exe "
                "from the relatedb/relate release page and set RELATE_BIN to its path")))
    gh = shutil.which("gh")
    out.append(("GitHub CLI (gh)", bool(gh), gh or "not found — install it from https://cli.github.com"))
    if gh:
        # `gh auth token`, not `gh auth status`: status exits 1 if any stored account fails, even when the
        # active one works, and the installer only needs the active account's token.
        code, msg = sh("gh", "auth", "token")
        out.append(("gh logged in", code == 0, "yes" if code == 0 else "no — run: gh auth login"))
        if code == 0:
            code, msg = sh("gh", "api", "repos/relatedb/relate", "--jq", ".full_name")
            out.append(("access to relatedb/relate", code == 0,
                        "yes" if code == 0 else "no — the repository is internal to the Neo4j GitHub organisation; "
                        "ask for access, or build without Relate"))
    out.append(("ssh-keygen (verifies the release signature)", bool(shutil.which("ssh-keygen")),
                shutil.which("ssh-keygen") or "not found — install openssh-client"))
    return out


def main():
    as_json = "--json" in sys.argv[1:]
    r = {"python": sys.version.split()[0], "pinned": cl.PINNED_VERSION, "binary": cl.BIN, "on_path": None,
         "version": None, "runs": None, "status": "", "exit": 1, "prerequisites": [], "advice": []}
    if sys.version_info < cl.MIN_PYTHON:
        r.update(status="python-too-old", exit=3)
        r["advice"].append(f"Python {'.'.join(map(str, cl.MIN_PYTHON))} or later is needed for the scripts.")
    elif not cl.BIN:
        r.update(status="not-installed", exit=1)
        r["prerequisites"] = [{"check": n, "ok": ok, "detail": d} for n, ok, d in install_prerequisites()]
        if all(p["ok"] for p in r["prerequisites"]):
            r["advice"].append(f"Everything the installer needs is in place. Install with:\n  {INSTALL}")
        else:
            r["advice"].append("Fix the items marked missing, then install with:\n  " + INSTALL)
        r["advice"].append("Without Relate, a package can still be built, but no query is executed: every query "
                           "needs manual testing on Aura (SKILL.md, \"Without Relate\").")
    else:
        r["on_path"] = shutil.which("relate") == cl.BIN
        v = cl.version()
        r["version"] = v
        res = cl.run("RETURN 1 AS ok", timeout="30s", wall=60) if v else None
        r["runs"] = bool(res and not res.exit and res.rows == [{"ok": 1}])
        if not v or not r["runs"]:
            r.update(status="broken", exit=1)
            r["advice"].append(f"{cl.BIN} is present but did not answer --version --json or RETURN 1"
                               + (f": {res.message}" if res and res.message else "") + ". Reinstall it:\n  " + INSTALL)
        elif v.get("version") != cl.PINNED_VERSION:
            r.update(status="version-differs", exit=2)
            r["advice"].append(f"Relate {v.get('version')} is installed; the skill is pinned to {cl.PINNED_VERSION}. "
                               "Test mode can run, but re-run the probe first and compare it with RELATE.md:\n"
                               "  python3 <skill-path>/scripts/probe_relate.py <repo-root>")
        else:
            r.update(status="ready", exit=0)
        if r["on_path"] is False:
            r["advice"].append(f"{cl.BIN} is not on PATH. The scripts find it anyway; add "
                               f"{os.path.dirname(cl.BIN)} to PATH to run `relate` by hand.")
    if as_json:
        print(json.dumps(r, indent=2))
    else:
        label = {"ready": "READY", "version-differs": "INSTALLED, DIFFERENT VERSION", "not-installed": "NOT INSTALLED",
                 "broken": "INSTALLED, NOT WORKING", "python-too-old": "PYTHON TOO OLD"}[r["status"]]
        print(f"Relate: {label}")
        print(f"  Python {r['python']}; pinned Relate {r['pinned']}")
        if r["binary"]:
            print(f"  binary {r['binary']}" + ("" if r["on_path"] is not False else " (not on PATH)"))
        if r["version"]:
            print(f"  version {json.dumps(r['version'])}; RETURN 1 {'ok' if r['runs'] else 'failed'}")
        for p in r["prerequisites"]:
            print(f"  [{'ok' if p['ok'] else 'missing'}] {p['check']}: {p['detail']}")
        for a in r["advice"]:
            print("\n" + a)
    sys.exit(r["exit"])


if __name__ == "__main__":
    main()
