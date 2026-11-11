#!/usr/bin/env python3
"""Test mode for create-solution-package-v2: import a package into a throwaway Relate store, check the
landing, run SETUP.md and every query, and write the reports (TESTING.md).

Usage:
  python3 run_queries.py run [PACKAGE ...] [--root DIR] [--run-dir DIR] [--keep] [--timeout 60s]
  python3 run_queries.py judge RUN_DIR/PACKAGE QUERY --status PASS|FAIL|UNSURE|ENGINE-GAP --evidence TEXT
                         [--fix TEXT] [--workaround TEXT] [--override]
  python3 run_queries.py report RUN_DIR

`run` with no PACKAGE tests every package in catalog.json plus any root folder holding an ONTOLOGY.json
that the catalogue does not list. A PACKAGE is a folder name under --root or a path. The scripts decide
everything mechanical (SKIPPED, NEEDS-PARAMS, rejected statements, empty results, row counts against
@sample) and leave the rest as JUDGE: the agent reads the rows against the TESTS.md Invariant and Expected
fields and records PASS, FAIL or UNSURE with `judge`, which re-renders the reports. Nothing here edits a
package. Standard library only."""
import argparse, collections, datetime, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import relate_cli as cl  # noqa: E402
import import_check  # noqa: E402
import ontology_to_cypher as gen  # noqa: E402
from annotations import (find_params, parse_statements, parse_tests, sample_row_count,  # noqa: E402
                         strip_cypher_noise)

STATUSES = ["PASS", "FAIL", "ENGINE-GAP", "SKIPPED", "NEEDS-PARAMS", "UNSURE", "JUDGE"]
FINAL_BY_SCRIPT = {"FAIL", "ENGINE-GAP", "SKIPPED", "NEEDS-PARAMS"}
UNKNOWN = {"UnknownLabelWarning": "label", "UnknownRelationshipTypeWarning": "relationship type",
           "UnknownPropertyKeyWarning": "property key"}
# Errors RELATE.md records as engine gaps for the pinned version: (regex on the message, note).
ENGINE_GAPS = [
    (r"WriteBeforeCallInTransactions", "CALL … IN TRANSACTIONS after a write clause (RELATE.md, import.in_transactions)"),
]
EXPECTS_EMPTY = re.compile(r"\b(no rows|empty|returns nothing|zero rows|0 rows|no results?)\b", re.I)


# ---------------------------------------------------------------- package discovery

def find_root(start):
    for d in [start, *start.parents]:
        if (d / "catalog.json").exists():
            return d
    return start


def packages(root, names):
    if names:
        out = []
        for n in names:
            p = pathlib.Path(n)
            p = p if (p / "ONTOLOGY.json").exists() else root / n
            if not (p / "ONTOLOGY.json").exists():
                sys.exit(f"no ONTOLOGY.json in {p}")
            out.append(p.resolve())
        return out
    listed = []
    if (root / "catalog.json").exists():
        listed = [s["skillId"] for s in json.loads((root / "catalog.json").read_text())["skills"]]
    extra = sorted(p.parent.name for p in root.glob("*/ONTOLOGY.json") if p.parent.name not in listed)
    return [(root / n).resolve() for n in listed + extra if (root / n / "ONTOLOGY.json").exists()]


# ---------------------------------------------------------------- vocabulary and writes

def ontology_vocab(pkg):
    o = json.loads((pkg / "ONTOLOGY.json").read_text(encoding="utf-8"))
    labels = {gen.label_of(n) for n in o["nodes"].values()}
    types = {r["type"] for r in o["relationships"].values()}
    props = {p for e in list(o["nodes"].values()) + list(o["relationships"].values()) for p in (e.get("properties") or {})}
    return labels | types | props


CLAUSE = re.compile(r"\b(MERGE|CREATE|SET|REMOVE|DELETE|DETACH|MATCH|OPTIONAL|WITH|RETURN|UNWIND|CALL|WHERE|ORDER|LIMIT|NEXT|UNION|FOREACH)\b", re.I)


def writes(cypher):
    """Labels, relationship types and property keys a statement writes (MERGE/CREATE patterns, SET)."""
    text = strip_cypher_noise(cypher)
    names = set()
    for m in re.finditer(r"\b(MERGE|CREATE)\b", text, re.I):
        nxt = CLAUSE.search(text, m.end())
        seg = text[m.end(): nxt.start() if nxt else len(text)]
        if re.match(r"\s*(CONSTRAINT|INDEX|FULLTEXT|POINT|RANGE|TEXT|VECTOR)\b", seg, re.I):
            continue
        names |= set(re.findall(r":\s*`?([A-Za-z_]\w*)", seg))
        names |= set(re.findall(r"[{,]\s*`?([A-Za-z_]\w*)`?\s*:", seg))
    for m in re.finditer(r"\bSET\b", text, re.I):
        nxt = CLAUSE.search(text, m.end())
        seg = text[m.end(): nxt.start() if nxt else len(text)]
        names |= set(re.findall(r"\b\w+\s*:\s*`?([A-Za-z_]\w*)", seg))
        names |= set(re.findall(r"\b\w+\.`?([A-Za-z_]\w*)`?\s*(?:=|\+=)", seg))
    return names


PATTERN_MAP = re.compile(r"(?<![\w`])[(\[]\s*`?\w*`?(?:\s*:\s*!?`?\w+`?(?:\s*[|&]\s*!?`?\w+`?)*)?\s*$")
SUBQUERY = re.compile(r"\b(COUNT|EXISTS|COLLECT|CALL)\s*(\([^)]*\))?\s*$", re.I)


def local_keys(cypher, params):
    """Keys a query defines for itself: map-literal and map-projection keys (not pattern property maps, whose
    keys are node or relationship properties) and the keys of map-valued parameters. A property access on
    such a map is not drift, though Relate's EXPLAIN reports the key as unknown."""
    text = strip_cypher_noise(cypher)
    keys = set()
    for m in re.finditer(r"\{", text):
        before = text[:m.start()]
        if PATTERN_MAP.search(before) or SUBQUERY.search(before):
            continue
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        keys |= set(re.findall(r"(?:^|[{,])\s*`?([A-Za-z_]\w*)`?\s*:(?!:)", text[m.end():j - 1]))

    def walk(v):
        if isinstance(v, dict):
            keys.update(v)
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(params)
    return keys


def classify(stmt, skipped_writes):
    """Reasons a statement must be SKIPPED: APOC, GDS or fulltext, or it reads what a skipped one writes."""
    text = strip_cypher_noise(stmt["cypher"])
    heading, prereq = stmt["heading"], stmt["tags"].get("prerequisites", "")
    reasons = []
    for rx, why in ((r"\bapoc\.", "calls APOC"), (r"\bgds\.", "calls GDS"),
                    (r"\bdb\.index\.fulltext\.", "calls a fulltext procedure, and Relate's fulltext index ignores "
                                                 "the analyser (RELATE.md, proc.fulltext_query)")):
        if re.search(rx, text, re.I):
            reasons.append(why)
    if not reasons and (re.search(r"\((requires|needs) (APOC|GDS)\)|^GDS\b", heading)
                        or re.search(r"^\s*(APOC|GDS)\b|\b(APOC|GDS)\s+(plugin|library)\b|\bfulltext index\b", prereq, re.I)):
        reasons.append("needs APOC, GDS or a fulltext index, per its heading or @prerequisites")
    hit = reads_from(stmt, skipped_writes)
    if hit:
        reasons.append(f"reads {hit[0]}, which only the skipped '{hit[1]}' writes")
    return reasons


def reads_from(stmt, written):
    """(name, writer) when the statement reads a label or type that only the given statements write."""
    text = strip_cypher_noise(stmt["cypher"])
    for name, src in written.items():
        if re.search(rf"[:|!]\s*`?{re.escape(name)}`?\b", text):
            return name, src
    return None


# ---------------------------------------------------------------- one package

def compact(v, depth=0):
    """Readable rendering of an envelope value: nodes, relationships and paths drawn in Cypher style."""
    if isinstance(v, dict) and v.get("kind") == "node":
        props = v.get("properties", {})
        key = next((props[k] for k in ("name", "id", "code", "description") if k in props), None)
        return f"(:{':'.join(v.get('labels', []))}{' ' + json.dumps(key, ensure_ascii=False) if key is not None else ''})"
    if isinstance(v, dict) and v.get("kind") == "relationship":
        return f"[:{v.get('type')}]"
    if isinstance(v, list) and v and all(isinstance(x, dict) and x.get("kind") in ("node", "relationship") for x in v):
        parts, prev = [], None
        for x in v:
            if x["kind"] == "node":
                if prev:
                    parts.append(("-" if prev["start_node"] == last["id"] else "<-") + compact(prev) +
                                 ("->" if prev["start_node"] == last["id"] else "-"))
                parts.append(compact(x))
                last, prev = x, None
            else:
                prev = x
        return "".join(parts)
    if isinstance(v, list):
        return "[" + ", ".join(compact(x, depth + 1) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {compact(x, depth + 1)}" for k, x in v.items()) + "}"
    return json.dumps(v, ensure_ascii=False)


def preflight(pkg):
    p = subprocess.run([sys.executable, str(HERE / "check_annotations.py"), str(pkg)], capture_output=True, text=True)
    lines = (p.stdout + p.stderr).splitlines()
    return {"blockers": [l for l in lines if l.startswith("BLOCKER")], "warnings": [l for l in lines if l.startswith("WARN")],
            "exit": p.returncode, "done": "done" in lines}


def run_statement(stmt, store, params, timeout):
    return cl.run(stmt["block"], store, params=params, timeout=timeout)


def test_package(pkg, out, args):
    t0 = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    res = {"package": pkg.name, "path": str(pkg), "relate": cl.version(), "started": datetime.datetime.now().isoformat(timespec="seconds"),
           "status": "", "preflight": None, "import": None, "setup": [], "queries": [], "findings": [], "store": None}
    pf = preflight(pkg)
    res["preflight"] = pf
    if pf["blockers"] or not pf["done"]:
        res["status"] = "BLOCKED"
        res["findings"] += pf["blockers"] or [f"check_annotations.py did not finish (exit {pf['exit']})"]
        return finish(res, out, t0)
    store = pathlib.Path(tempfile.mkdtemp(prefix=f"relate-{pkg.name}-"))
    res["store"] = str(store)
    try:
        try:
            imp = import_check.run(pkg, store, out)
        except gen.ShapeError as e:
            res["status"] = "BLOCKED"
            res["findings"].append(f"ontology_to_cypher.py refused the ONTOLOGY.json: {e}")
            return finish(res, out, t0)
        res["import"] = imp
        res["status"] = imp["status"]
        res["findings"] += imp["findings"]
        untrusted = imp["status"] != "OK"
        tests = parse_tests(pkg / "TESTS.md")
        vocab = ontology_vocab(pkg)
        skill_text = (pkg / "SKILL.md").read_text(encoding="utf-8") if (pkg / "SKILL.md").exists() else ""
        setup = [s for s in parse_statements(pkg / "SETUP.md") if s["annotated"]]
        queries = [s for s in parse_statements(pkg / "QUERIES.md") if s["annotated"]]
        all_writes = {}
        for s in setup + queries:
            for n in writes(s["cypher"]) - vocab:
                all_writes.setdefault(n, s["heading"])
        skipped_writes, blocked_writes = {}, {}
        for s in setup:
            reasons = classify(s, skipped_writes)
            rec = {"heading": s["heading"], "line": s["line"]}
            if reasons:
                rec.update(status="SKIPPED", reason="; ".join(reasons))
                skipped_writes.update({n: s["heading"] for n in writes(s["cypher"]) - vocab})
            else:
                r = cl.run(s["block"], store, timeout=args.timeout)
                rec.update(status="OK" if not r.exit else "FAILED", exit=r.exit, seconds=round(r.seconds, 3),
                           rows=len(r.rows), error=f"{r.error_class}: {r.message}" if r.exit else "")
            res["setup"].append(rec)
        rows_dir = out / "rows"
        rows_dir.mkdir(exist_ok=True)
        for i, s in enumerate(queries, 1):
            res["queries"].append(test_query(i, s, store, tests.get(s["heading"]), vocab, all_writes, skill_text,
                                             skipped_writes, blocked_writes, untrusted, rows_dir, args))
    finally:
        if args.keep:
            res["kept_store"] = str(store)
        else:
            shutil.rmtree(store, ignore_errors=True)
    return finish(res, out, t0)


def test_query(i, s, store, section, vocab, all_writes, skill_text, skipped_writes, blocked_writes, untrusted, rows_dir, args):
    q = {"n": i, "heading": s["heading"], "line": s["line"], "status": "", "reason": "", "untrusted": untrusted,
         "params": {}, "param_sources": {}, "notes": [], "notifications": [], "findings": [],
         "tests": (section or {}).get("fields", {}), "sample": s["tags"].get("sample", ""),
         "judgement": None}
    if section is None:
        q["findings"].append("TESTS.md has no section with this heading")
    reasons = classify(s, skipped_writes)
    if reasons:
        q.update(status="SKIPPED", reason="; ".join(reasons) + ". Needs manual testing on Aura.")
        skipped_writes.update({n: s["heading"] for n in writes(s["cypher"]) - vocab})
        return q
    blocked = reads_from(s, blocked_writes)
    if blocked:
        q.update(status="NEEDS-PARAMS", reason=f"reads {blocked[0]}, which only '{blocked[1]}' writes, and that query "
                                               "had no parameter values, so it never ran")
        blocked_writes.update({n: s["heading"] for n in writes(s["cypher"]) - vocab})
        return q
    values, sources, notes, missing = find_params(s, section)
    q.update(params=values, param_sources=sources)
    q["notes"] += notes
    ex = cl.run("EXPLAIN " + s["cypher"], store, params=values, timeout=args.timeout)
    drift, local = [], local_keys(s["cypher"], values)
    if ex.exit:
        q["notes"].append(f"EXPLAIN failed: {ex.error_class}: {ex.message}")
    for n in ex.notifications:
        code = str(n.get("code", "")).rsplit(".", 1)[-1]
        q["notifications"].append(f"{n.get('code')} {n.get('gql_status')}: {n.get('description')}")
        if code in UNKNOWN:
            name = (re.findall(r"`([^`]+)`", n.get("description", "")) or ["?"])[0]
            if name in vocab:
                q["notes"].append(f"{UNKNOWN[code]} {name} is declared in ONTOLOGY.json but absent from the store at this point")
            elif code == "UnknownPropertyKeyWarning" and name in local:
                q["notes"].append(f"property key {name} is a key of a map the query builds or a parameter supplies, not drift")
            elif name in all_writes:
                if re.search(rf"\b{re.escape(name)}\b", skill_text):
                    q["notes"].append(f"{UNKNOWN[code]} {name} is written by '{all_writes[name]}' and documented in SKILL.md; "
                                      "absent from the store at this point")
                else:
                    drift.append(f"{UNKNOWN[code]} {name} is written by '{all_writes[name]}' but not documented in SKILL.md")
            else:
                drift.append(f"unknown {UNKNOWN[code]} {name}: not in ONTOLOGY.json and written by no query")
        elif code == "UnboundedVariableLengthPattern":
            q["findings"].append(f"unbounded variable-length pattern: {n.get('description')}")
    if missing:
        q.update(status="NEEDS-PARAMS", reason=f"no value for {', '.join('$' + m for m in missing)} in TESTS.md, @sample or @params")
        blocked_writes.update({n: s["heading"] for n in writes(s["cypher"]) - vocab})
        q["notes"] += [f"unverifiable until {', '.join('$' + m for m in missing)} has a value (it may be a key of that "
                       f"parameter): {d}" for d in drift]
        return q
    r = run_statement(s, store, values, args.timeout)
    q.update(exit=r.exit, seconds=round(r.seconds, 3), columns=r.columns, row_count=len(r.rows),
             rows_head=r.rows[:25], error=f"{r.error_class}: {r.message}" if r.exit else "")
    (rows_dir / f"{i:02d}.json").write_text(json.dumps({"columns": r.columns, "rows": r.rows}, default=str), encoding="utf-8")
    if drift:
        q.update(status="FAIL", reason="drift caught by EXPLAIN: " + "; ".join(drift))
        return q
    if r.exit:
        gap = next((note for rx, note in ENGINE_GAPS if re.search(rx, r.message)), None)
        if gap:
            q.update(status="ENGINE-GAP", reason=f"{r.error_class}: {r.message} — {gap}")
        elif r.exit == 7:
            q.update(status="FAIL", reason=f"timed out after {args.timeout}; triage per TESTING.md step 6")
        else:
            q.update(status="FAIL", reason=f"statement failed ({r.error_class}: {r.message}); triage per TESTING.md step 6")
        return q
    expected_text = " ".join(q["tests"].get(k, "") for k in ("Invariant", "Expected"))
    want_n = sample_row_count(s)
    if not r.rows and re.search(r"\bRETURN\b", strip_cypher_noise(s["cypher"]), re.I) and not EXPECTS_EMPTY.search(expected_text):
        q.update(status="FAIL", reason="empty result, and TESTS.md does not expect one")
    elif want_n is not None and len(r.rows) != want_n:
        q.update(status="FAIL", reason=f"{len(r.rows)} rows; @sample says {want_n}")
    else:
        q.update(status="JUDGE", reason="mechanical checks passed; judge the rows against TESTS.md")
    return q


# ---------------------------------------------------------------- reports

def counts(res):
    c = collections.Counter(q["status"] for q in res["queries"])
    return {s: c.get(s, 0) for s in STATUSES}


def finish(res, out, t0):
    res["seconds"] = round(time.monotonic() - t0, 1)
    save(res, out)
    return res


def save(res, out):
    (out / "results.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (out / "report.md").write_text(render_package(res), encoding="utf-8")


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_package(res):
    c = counts(res)
    imp = res.get("import") or {}
    L = [f"# Test report: {res['package']}", "",
         f"- Package: `{res['path']}`",
         f"- Relate: `{json.dumps(res['relate'])}`",
         f"- Started: {res['started']}; {res.get('seconds', '?')} s",
         f"- Import: **{res['status']}**" + (" — query results below are untrusted" if res["status"] == "IMPORT-FAIL" else ""),
         "- Queries: " + ", ".join(f"{k} {v}" for k, v in c.items() if v), ""]
    if res.get("kept_store"):
        L.append(f"- Store kept at `{res['kept_store']}`\n")
    L += ["A pass here is evidence, not proof: Relate is not Aura's engine and `import.cypher` is a second "
          "implementation of Aura's Import. SKIPPED queries still need manual testing on Aura.", ""]
    if res["findings"]:
        L += ["## Findings", ""] + [f"- {f}" for f in res["findings"]] + [""]
    pf = res.get("preflight") or {}
    L += ["## Preflight (check_annotations.py)", "", f"{len(pf.get('blockers', []))} blockers, {len(pf.get('warnings', []))} warnings."]
    L += [f"- `{l}`" for l in pf.get("blockers", []) + pf.get("warnings", [])] + [""]
    if imp:
        s = imp["summary"]
        L += ["## Import", "", f"{s['statements']} statements ({s['failed_statements']} failed) in {imp['seconds']} s; "
              f"{s['checks']} landing checks, {s['failed_checks']} failed; {s['profile_mismatches']} TESTS.md profile mismatches. "
              "`import.cypher` and `import.json` are beside this report.", ""]
        L += [f"- {n}" for n in imp["notes"]]
        bad = [x for x in imp["statements"] if x.get("exit")]
        L += [f"- Statement failed: {x['kind']} {x['entity']}: {x['error']}" for x in bad]
        L += ["", "| Check | Subject | Expected | Observed | OK |", "| --- | --- | --- | --- | --- |"]
        for ch in imp["checks"]:
            if ch["check"] in ("count", "tests-profile") or not ch["ok"]:
                L.append(f"| {ch['check']} | {cell(ch['subject'])} | {cell(ch['expected'])} | {cell(ch['observed'])}"
                         f"{(' — ' + cell(ch['detail'])) if ch['detail'] and not ch['ok'] else ''} | {'yes' if ch['ok'] else '**no**'} |")
        others = [ch for ch in imp["checks"] if ch["check"] not in ("count", "tests-profile")]
        L += ["", f"Property, key, multiplicity, vocabulary and constraint checks: {sum(ch['ok'] for ch in others)} of {len(others)} pass "
              "(failures are listed above).", ""]
    if res["setup"]:
        L += ["## SETUP.md", "", "| Statement | Result |", "| --- | --- |"]
        for s in res["setup"]:
            L.append(f"| {cell(s['heading'])} | {s['status']}{' — ' + cell(s.get('error') or s.get('reason', '')) if s['status'] != 'OK' else ''} |")
        L.append("")
    if res["queries"]:
        L += ["## Queries", "", "| # | Query | Status | Rows | Time (s) | Reason |", "| --- | --- | --- | --- | --- | --- |"]
        for q in res["queries"]:
            L.append(f"| {q['n']} | {cell(q['heading'])} | **{q['status']}** | {q.get('row_count', '')} | {q.get('seconds', '')} | "
                     f"{cell((q['judgement'] or {}).get('evidence') or q['reason'])[:220]} |")
        L.append("")
        for q in res["queries"]:
            L += render_query(q)
    return "\n".join(L) + "\n"


def render_query(q):
    j = q.get("judgement") or {}
    L = [f"### {q['n']}. {q['heading']}", "", f"- **Status: {q['status']}**" + (" (untrusted: import failed)" if q["untrusted"] else ""),
         f"- Reason: {q['reason']}"]
    if j:
        L.append(f"- Judgement: {j['status']} — {j['evidence']}" + (f" (overrode {j['overridden']})" if j.get("overridden") else ""))
        if j.get("fix"):
            L.append(f"- Proposed fix: {j['fix']}")
        if j.get("workaround"):
            L.append(f"- Workaround tried (scratch copy, never counts as PASS): {j['workaround']}")
    if q["params"]:
        L.append("- Parameters: " + ", ".join(f"`${k} = {json.dumps(v, ensure_ascii=False)}` ({q['param_sources'][k]})" for k, v in q["params"].items()))
    L += [f"- Note: {n}" for n in q["notes"]] + [f"- Finding: {f}" for f in q["findings"]]
    L += [f"- Notification: {n}" for n in q["notifications"] if "MissingIndex" not in n]
    for k in ("Invariant", "Expected"):
        if q["tests"].get(k):
            L.append(f"- TESTS.md {k}: " + " ".join(q["tests"][k].split()))
    if q.get("sample"):
        L.append(f"- @sample: {' '.join(q['sample'].split())}")
    if "columns" in q:
        L.append(f"- Ran in {q['seconds']} s, exit {q['exit']}, {q['row_count']} rows, columns {q['columns']}"
                 + (f"; error {q['error']}" if q["error"] else ""))
        if q["rows_head"]:
            L += ["", "```text"] + [" | ".join(compact(r.get(c)) for c in q["columns"])[:400] for r in q["rows_head"][:15]]
            if q["row_count"] > 15:
                L.append(f"… {q['row_count'] - 15} more rows in rows/{q['n']:02d}.json")
            L.append("```")
    return L + [""]


def render_summary(run_dir, results):
    L = [f"# Relate test run {run_dir.name}", "", f"Relate `{json.dumps(results[0]['relate'])}`" if results else "", "",
         "| Package | Import | " + " | ".join(STATUSES[:-1]) + " | Pending | Time (s) |",
         "| --- | --- | " + " | ".join("---" for _ in STATUSES) + " | --- |"]
    for r in results:
        c = counts(r)
        L.append(f"| {r['package']} | {r['status']} | " + " | ".join(str(c[s]) for s in STATUSES) + f" | {r.get('seconds', '')} |")
    L += ["", "## Lines to follow up", ""] + [f"- {x}" for x in attention(results)] + [""]
    return "\n".join(L)


def attention(results):
    out = []
    for r in results:
        if r["status"] in ("IMPORT-FAIL", "BLOCKED"):
            why = "; ".join(r["findings"][:2]) or "; ".join(
                f"{c['check']} {c['subject']}: expected {c['expected']}, observed {c['observed']}"
                for c in (r.get("import") or {}).get("checks", []) if not c["ok"])[:300]
            out.append(f"{r['status']} {r['package']}: {why}")
        for q in r["queries"]:
            if q["status"] in ("FAIL", "ENGINE-GAP", "UNSURE"):
                why = (q.get("judgement") or {}).get("evidence") or q["reason"]
                out.append(f"{q['status']} {r['package']} #{q['n']} {q['heading']}: {' '.join(why.split())[:300]}")
    return out


def load_results(run_dir):
    return [json.loads(p.read_text()) for p in sorted(run_dir.glob("*/results.json"))]


def write_summary(run_dir):
    results = load_results(run_dir)
    (run_dir / "summary.md").write_text(render_summary(run_dir, results), encoding="utf-8")
    return results


# ---------------------------------------------------------------- commands

def cmd_run(a):
    root = pathlib.Path(a.root).resolve() if a.root else find_root(pathlib.Path.cwd().resolve())
    pkgs = packages(root, a.packages)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = pathlib.Path(a.run_dir).resolve() if a.run_dir else root / "output" / "relate-tests" / stamp
    for p in pkgs:
        if run_dir == p or p in run_dir.parents:
            sys.exit("the run directory must not be inside a package folder")
    run_dir.mkdir(parents=True, exist_ok=True)
    for p in pkgs:
        print(f"testing {p.name} …", flush=True)
        r = test_package(p, run_dir / p.name, a)
        c = counts(r)
        print(f"  {r['status']}: " + ", ".join(f"{k} {v}" for k, v in c.items() if v) + f" ({r['seconds']} s)", flush=True)
    results = write_summary(run_dir)
    print_summary(run_dir, results)


def print_summary(run_dir, results):
    print()
    print((run_dir / "summary.md").read_text().split("## Lines to follow up")[0].strip())
    lines = attention(results)
    if lines:
        print("\n" + "\n".join(lines))
    pending = sum(counts(r)["JUDGE"] for r in results)
    print(f"\n{pending} queries await judgement. Reports: {run_dir}")


def find_query(res, key):
    if key.isdigit():
        hits = [q for q in res["queries"] if q["n"] == int(key)]
    else:
        hits = [q for q in res["queries"] if q["heading"] == key] or \
               [q for q in res["queries"] if q["heading"].lower().startswith(key.lower())]
    if len(hits) != 1:
        sys.exit(f"query {key!r} matches {len(hits)} queries")
    return hits[0]


def cmd_judge(a):
    out = pathlib.Path(a.package_run).resolve()
    res = json.loads((out / "results.json").read_text())
    q = find_query(res, a.query)
    if q["status"] in FINAL_BY_SCRIPT and not a.override:
        sys.exit(f"#{q['n']} is {q['status']} by a mechanical check ({q['reason']}); pass --override to change it")
    j = {"status": a.status, "evidence": a.evidence, "fix": a.fix, "workaround": a.workaround,
         "judged": datetime.datetime.now().isoformat(timespec="seconds")}
    if q["status"] != "JUDGE":
        j["overridden"] = f"{q['status']}: {q['reason']}"
    q["judgement"], q["status"] = j, a.status
    save(res, out)
    write_summary(out.parent)
    print(f"#{q['n']} {q['heading']}: {a.status}")


def cmd_report(a):
    run_dir = pathlib.Path(a.run_dir).resolve()
    for p in sorted(run_dir.glob("*/results.json")):
        save(json.loads(p.read_text()), p.parent)
    print_summary(run_dir, write_summary(run_dir))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("packages", nargs="*")
    r.add_argument("--root")
    r.add_argument("--run-dir")
    r.add_argument("--keep", action="store_true", help="keep the Relate store")
    r.add_argument("--timeout", default="60s")
    j = sub.add_parser("judge")
    j.add_argument("package_run")
    j.add_argument("query", help="query number or heading")
    j.add_argument("--status", required=True, choices=["PASS", "FAIL", "UNSURE", "ENGINE-GAP"])
    j.add_argument("--evidence", required=True)
    j.add_argument("--fix")
    j.add_argument("--workaround")
    j.add_argument("--override", action="store_true")
    p = sub.add_parser("report")
    p.add_argument("run_dir")
    a = ap.parse_args()
    {"run": cmd_run, "judge": cmd_judge, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
