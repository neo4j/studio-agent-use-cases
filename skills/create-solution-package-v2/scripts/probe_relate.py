#!/usr/bin/env python3
"""Probe the installed Relate for every behaviour test mode relies on (RELATE.md).

Usage: python3 probe_relate.py <repo-root> [--out DIR] [--only PREFIX] [--jobs N]

Each case runs against a fresh temporary directory store and is recorded as
  SUPPORTED    - behaves as Neo4j does
  UNSUPPORTED  - rejected or failed; the error is recorded
  DIFFERENT    - runs, but the observed behaviour differs from Neo4j's (both are recorded)
A case marked `verify` states Neo4j's behaviour from its documentation or implementation rather than
from a live run, and belongs on the Aura parity list.

Besides the hand-written cases it (a) inventories the Cypher constructs every package's QUERIES.md and
SETUP.md actually use and maps each to the cases covering it, flagging any construct no case covers,
and (b) EXPLAINs every annotated statement in every package (the corpus). Writes probe.json and
probe.md under --out (default output/relate-tests/probe-<timestamp>/). Standard library only."""
import argparse, collections, concurrent.futures, csv, dataclasses, datetime, json, math, os, pathlib
import re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import relate_cli as cl  # noqa: E402
from annotations import parse_statements, strip_cypher_noise  # noqa: E402

ROOT = None  # repo root, set in main


@dataclasses.dataclass
class Case:
    id: str
    area: str
    title: str
    stmt: str = ""
    setup: tuple = ()
    expect: list | None = None   # rows Neo4j returns, as lists in column order
    ordered: bool = True
    neo4j: str = ""              # Neo4j's behaviour in words
    csv: dict | None = None      # {relative path: bytes} written to a fresh --load-csv-dir
    params: dict | None = None
    rejects: bool = False        # Neo4j rejects the statement
    check: object = None         # custom judge: fn(R, store, csv_dir) -> (status, observed)
    verify: bool = False
    timeout: str = "30s"
    tol: float = 1e-9
    env: dict | None = None
    uses: tuple = ()


CASES = []


def case(*a, **k):
    CASES.append(Case(*a, **k))


# ---------------------------------------------------------------- comparison helpers

def same(a, b, tol):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if type(a) is not type(b):
            return False
        return math.isclose(a, b, rel_tol=tol, abs_tol=1e-12) if isinstance(a, float) else a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    return a == b


def rows_equal(got, want, ordered, tol):
    if not ordered:
        key = lambda r: json.dumps(r, sort_keys=True, default=str)
        got, want = sorted(got, key=key), sorted(want, key=key)
    return len(got) == len(want) and all(same(g, w, tol) for g, w in zip(got, want))


def fmt(v, n=300):
    s = json.dumps(v, default=str, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + "…"


def err(r):
    return f"{r.error_class}: {r.message}"


# ---------------------------------------------------------------- import cases

BASIC = b"id,name\n1,alpha\n2,beta\n"
LOAD = "LOAD CSV WITH HEADERS FROM '{url}' AS row RETURN row.id AS id, row.name AS name"
case("import.path.file_root", "Import", "LOAD CSV from file:///x.csv under --load-csv-dir",
     LOAD.format(url="file:///x.csv"), csv={"x.csv": BASIC}, expect=[["1", "alpha"], ["2", "beta"]],
     neo4j="Resolves against the import directory.", uses=("LOAD CSV",))
case("import.path.file_sub", "Import", "LOAD CSV from file:///sub/x.csv",
     LOAD.format(url="file:///sub/x.csv"), csv={"sub/x.csv": BASIC}, expect=[["1", "alpha"], ["2", "beta"]],
     neo4j="Resolves against the import directory.")
case("import.path.bare", "Import", "LOAD CSV from bare x.csv",
     LOAD.format(url="x.csv"), csv={"x.csv": BASIC}, rejects=True,
     neo4j="Rejected: a bare path is not a URL (Invalid URL).", verify=True)
case("import.path.escape", "Import", "LOAD CSV from file:///../x.csv (outside the directory)",
     LOAD.format(url="file:///../x.csv"), csv={"x.csv": BASIC}, rejects=True,
     neo4j="Rejected or resolved inside the import directory; never reads outside it.")
case("import.empty_cell", "Import", "Empty cell: unquoted ,, and quoted \"\"",
     "LOAD CSV WITH HEADERS FROM 'file:///e.csv' AS row "
     "RETURN row.b IS NULL AS isNull, row.b = '' AS isEmpty, 'b' IN keys(row) AS hasKey, row.c AS c",
     csv={"e.csv": b'a,b,c\n1,,3\n4,"",6\n'}, expect=[[True, None, True, "3"], [False, True, True, "6"]],
     neo4j="Unquoted empty field is null with the key present; quoted \"\" is ''.", verify=True)
case("import.crlf", "Import", "CRLF line endings: no trailing \\r on the last column",
     "LOAD CSV WITH HEADERS FROM 'file:///c.csv' AS row RETURN row.b AS b, size(row.b) AS n",
     csv={"c.csv": b"a,b\r\n1,x\r\n2,y\r\n"}, expect=[["x", 1], ["y", 1]],
     neo4j="Line terminator stripped.")
case("import.quoting", "Import", "Quoted fields with commas, doubled quotes and newlines",
     "LOAD CSV WITH HEADERS FROM 'file:///q.csv' AS row RETURN row.a AS a, row.b AS b",
     csv={"q.csv": b'a,b\n1,"x,y"\n2,"say ""hi"""\n3,"line1\nline2"\n'},
     expect=[["1", "x,y"], ["2", 'say "hi"'], ["3", "line1\nline2"]], neo4j="RFC 4180 quoting.")
case("import.bom", "Import", "UTF-8 BOM on the header row",
     "LOAD CSV WITH HEADERS FROM 'file:///b.csv' AS row RETURN row.id AS id, keys(row) AS keys",
     csv={"b.csv": b"\xef\xbb\xbfid,name\n1,alpha\n"}, expect=[["1", ["id", "name"]]],
     neo4j="BOM stripped; the first key is 'id'.")
case("import.whitespace", "Import", "Leading and trailing whitespace in values",
     "LOAD CSV WITH HEADERS FROM 'file:///w.csv' AS row RETURN row.b AS b",
     csv={"w.csv": b"a,b\n1,  x  \n"}, expect=[["  x  "]], neo4j="Preserved.", verify=True)
case("import.in_transactions", "Import", "LOAD CSV with CALL (row) { … } IN TRANSACTIONS",
     "LOAD CSV WITH HEADERS FROM 'file:///x.csv' AS row CALL (row) { CREATE (:X {id: row.id}) } "
     "IN TRANSACTIONS OF 1 ROWS",
     csv={"x.csv": BASIC}, expect=[], neo4j="Supported in an implicit transaction.")
for fn, exp, note in (
        ("toInteger", [1, None, None, 5], "'1.0'→1 (BigDecimal fallback); ' 5'→5, confirmed on Aura 2026-10-30"),
        ("toFloat", [1.0, None, None, 5.0], "' 5'→5.0, confirmed on Aura 2026-10-30"),
        ("toBoolean", [None, True, None, None], "case-insensitive 'true'/'false', otherwise null")):
    case(f"import.coerce.{fn}", "Import", f"{fn} on '1.0', 'TRUE', '' and ' 5'",
         f"RETURN {fn}('1.0') AS a, {fn}('TRUE') AS b, {fn}('') AS c, {fn}(' 5') AS d",
         expect=[exp], neo4j=note, verify=True, uses=(fn,))
case("import.coerce.import_boolean", "Import", "Import's BOOLEAN conversion toLower(trim(v)) IN ['1','true','yes']",
     "UNWIND ['true', 'TRUE', ' yes ', '1', 'false', 'no'] AS v RETURN toLower(trim(v)) IN ['1', 'true', 'yes'] AS b",
     expect=[[True], [True], [True], [True], [False], [False]], neo4j="Plain list membership.")


def datetime_cases():
    """One case per distinct ZONED DATETIME value shape found in the packages' CSVs, plus the shapes
    create mode may meet."""
    shapes = collections.OrderedDict()
    for o in sorted(ROOT.glob("*/ONTOLOGY.json")):
        m = json.loads(o.read_text())
        for mp in m["extensions"]["data_source_mappings"]["mapping0"]:
            decl = m["nodes"][mp["node"]] if mp["type"] == "NODE" else m["relationships"][mp["relationship"]]
            cols = [b["column"] for p, b in (mp.get("properties") or {}).items()
                    if decl["properties"][p]["type"] == "ZONED DATETIME"]
            if not cols:
                continue
            with (o.parent / "sample-data" / mp["table"]).open(newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    for c in cols:
                        if r[c]:
                            shapes.setdefault(re.sub(r"\d", "9", r[c]), (r[c], o.parent.name))
    for i, (shape, (v, pkg)) in enumerate(shapes.items()):
        case(f"import.datetime.package{i + 1}", "Import", f"datetime() on the package format {shape} (e.g. {pkg})",
             "RETURN toString(datetime($v)) AS s, datetime($v).epochSeconds AS e", params={"v": v},
             expect=[[v, int(datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())]],
             neo4j="Parses; toString returns the ISO form.", uses=("datetime()",))
    for cid, v, want, note in (
            ("midnight", "2024-01-02T00:00:00Z", "2024-01-02T00:00:00Z", "seconds printed even when zero (confirmed on Aura 2026-10-30)"),
            ("millis", "2024-01-02T03:04:05.123Z", "2024-01-02T03:04:05.123Z", "fraction kept"),
            ("offset", "2024-01-02T03:04:05+01:00", "2024-01-02T03:04:05+01:00", "offset kept"),
            ("date_only", "2024-01-02", "2024-01-02T00:00:00Z", "midnight in the default time zone (UTC on Aura)"),
            ("no_zone", "2024-01-02T03:04:05", "2024-01-02T03:04:05Z", "default time zone (UTC on Aura)")):
        case(f"import.datetime.{cid}", "Import", f"datetime('{v}')", "RETURN toString(datetime($v)) AS s",
             params={"v": v}, expect=[[want]], neo4j=note, verify="confirmed" not in note)
    case("import.datetime.space", "Import", "datetime('2024-01-02 03:04:05') with a space separator",
         "RETURN datetime($v) AS d", params={"v": "2024-01-02 03:04:05"}, rejects=True,
         neo4j="Rejected: the ISO parser needs 'T'.", verify=True)


def throughput_check(R, store, csv_dir):
    import ontology_to_cypher as gen
    pkg = ROOT / "patient-journey"
    stmts, _ = gen.generate(pkg)
    t0, failed = None, []
    import time
    t0 = time.monotonic()
    for s in stmts:
        if s.get("skipped"):
            continue
        r = cl.run(s["cypher"], store, csv_dir=pkg / "sample-data", timeout="600s")
        if r.exit:
            failed.append(f"{s['kind']} {s['entity']}: {err(r)}")
    secs = time.monotonic() - t0
    n = cl.run("MATCH (n) RETURN count(n) AS n", store).rows
    m = cl.run("MATCH ()-[r]->() RETURN count(r) AS n", store).rows
    lines = sum(1 for f in (pkg / "sample-data").glob("*.csv") for _ in f.open(encoding="utf-8"))
    obs = (f"{len(stmts)} statements in {secs:.1f}s for {lines} CSV lines; "
           f"{n[0]['n'] if n else '?'} nodes, {m[0]['n'] if m else '?'} relationships")
    if failed:
        return "UNSUPPORTED", obs + "; failed: " + "; ".join(failed[:4])
    return "SUPPORTED", obs


case("import.throughput.patient_journey", "Import", "Full patient-journey import (generated script, one call per statement)",
     check=throughput_check, neo4j="Aura Import: tens of seconds for this size.", timeout="600s")


# ---------------------------------------------------------------- schema cases

def constraint_check(create, writes, rejected, title_note=""):
    """Create a constraint, then run writes; `rejected` lists the indexes of writes Neo4j rejects."""
    def check(R, store, csv_dir):
        r = R(create)
        if r.exit:
            return "UNSUPPORTED", err(r)
        obs, wrong = [], []
        for i, w in enumerate(writes):
            x = R(w)
            want = i in rejected
            got = bool(x.exit)
            obs.append(f"{'rejected' if got else 'accepted'}: {w}")
            if got != want:
                wrong.append(f"{w} was {'rejected' if got else 'accepted'}" + (f" ({err(x)})" if got else ""))
        if wrong:
            return "DIFFERENT", "; ".join(wrong) + " (Neo4j does the opposite)"
        first = next((R(writes[i]) for i in rejected), None) if rejected else None
        return "SUPPORTED", "; ".join(obs) + (f" [{err(first)}]" if first and first.exit else "")
    return check


case("schema.node_key.single", "Schema", "Single-property NODE KEY (Import's statement form)",
     check=constraint_check("CREATE CONSTRAINT `id_K_key` IF NOT EXISTS\nFOR (n:`K`)\nREQUIRE (n.`id`) IS NODE KEY;",
                            ["CREATE (:K {id: 1})", "CREATE (:K {id: 1})", "CREATE (:K {name: 'x'})",
                             "MERGE (:K {id: 2})"], {1, 2}),
     neo4j="Enforces uniqueness and existence (Enterprise/Aura).", uses=("IS NODE KEY",))
case("schema.node_key.composite", "Schema", "Composite NODE KEY with tuple syntax",
     check=constraint_check("CREATE CONSTRAINT IF NOT EXISTS FOR (n:`C`) REQUIRE (n.`a`, n.`b`) IS NODE KEY",
                            ["CREATE (:C {a: 1, b: 1})", "CREATE (:C {a: 1, b: 1})", "CREATE (:C {a: 1, b: 2})",
                             "CREATE (:C {a: 2})"], {1, 3}),
     neo4j="Enforces the pair's uniqueness and both properties' existence.")
case("schema.unique", "Schema", "IS UNIQUE",
     check=constraint_check("CREATE CONSTRAINT IF NOT EXISTS FOR (n:U) REQUIRE n.id IS UNIQUE",
                            ["CREATE (:U {id: 1})", "CREATE (:U {id: 1})", "CREATE (:U {name: 'x'})"], {1}),
     neo4j="Rejects duplicates, allows a missing property.", uses=("IS UNIQUE",))
case("schema.exists", "Schema", "Property existence IS NOT NULL (Import's must_exist)",
     check=constraint_check("CREATE CONSTRAINT `name_E_propertyExistence` IF NOT EXISTS\nFOR (n:`E`)\nREQUIRE n.`name` IS NOT NULL;",
                            ["CREATE (:E {name: 'x'})", "CREATE (:E {id: 1})"], {1}),
     neo4j="Rejects a node without the property (Enterprise/Aura).")
case("schema.rel_exists", "Schema", "Relationship property existence (Import's must_exist on a relationship)",
     check=constraint_check("CREATE CONSTRAINT `w_T_propertyExistence` IF NOT EXISTS\nFOR ()-[n:`T`]-()\nREQUIRE n.`w` IS NOT NULL;",
                            ["CREATE ()-[:T {w: 1}]->()", "CREATE ()-[:T]->()"], {1}),
     neo4j="Rejects a relationship without the property (Enterprise/Aura).")
case("schema.rel_key", "Schema", "IS RELATIONSHIP KEY",
     check=constraint_check("CREATE CONSTRAINT IF NOT EXISTS FOR ()-[n:`T`]-() REQUIRE (n.`k`) IS RELATIONSHIP KEY",
                            ["CREATE ()-[:T {k: 1}]->()", "CREATE ()-[:T {k: 1}]->()", "CREATE ()-[:T]->()"], {1, 2}),
     neo4j="Enforces uniqueness and existence (Enterprise/Aura).")
case("schema.rel_unique", "Schema", "Relationship IS UNIQUE",
     check=constraint_check("CREATE CONSTRAINT IF NOT EXISTS FOR ()-[n:`T`]-() REQUIRE (n.`k`) IS UNIQUE",
                            ["CREATE ()-[:T {k: 1}]->()", "CREATE ()-[:T {k: 1}]->()", "CREATE ()-[:T]->()"], {1}),
     neo4j="Rejects duplicates, allows a missing property.")
case("schema.property_type", "Schema", "Property type constraint IS :: STRING",
     check=constraint_check("CREATE CONSTRAINT IF NOT EXISTS FOR (n:PT) REQUIRE n.x IS :: STRING",
                            ["CREATE (:PT {x: 'a'})", "CREATE (:PT {x: 1})"], {1}),
     neo4j="Rejects a wrongly typed value (Enterprise/Aura). Import never emits it.")


def show_constraints_check(R, store, csv_dir):
    r = R("CREATE CONSTRAINT `id_K_key` IF NOT EXISTS FOR (n:`K`) REQUIRE (n.`id`) IS NODE KEY")
    if r.exit:
        return "UNSUPPORTED", "could not create a NODE KEY: " + err(r)
    s = R("SHOW CONSTRAINTS")
    if s.exit:
        return "UNSUPPORTED", err(s)
    row = s.rows[0] if s.rows else {}
    want = ["id", "name", "type", "entityType", "labelsOrTypes", "properties", "ownedIndex", "propertyType"]
    obs = f"columns {s.columns}; row {fmt(row, 400)}"
    missing = [c for c in want if c not in s.columns]
    if missing or row.get("type") != "NODE_KEY":
        return "DIFFERENT", obs + f"; missing {missing}" if missing else obs
    return "SUPPORTED", obs


case("schema.show_constraints", "Schema", "SHOW CONSTRAINTS output shape", check=show_constraints_check,
     neo4j="Columns id, name, type, entityType, labelsOrTypes, properties, ownedIndex, propertyType (2025.x adds "
           "enforcedLabel); type NODE_KEY.")


def seek_check(R, store, csv_dir):
    r = R("CREATE CONSTRAINT IF NOT EXISTS FOR (n:`K`) REQUIRE (n.`id`) IS NODE KEY")
    if r.exit:
        return "UNSUPPORTED", "could not create a NODE KEY: " + err(r)
    R("UNWIND range(1, 20000) AS i CREATE (:K {id: i, name: toString(i)})")
    R("UNWIND range(1, 20000) AS i CREATE (:L {id: i, name: toString(i)})")

    def profile(label):
        p = R(f"PROFILE MATCH (n:{label} {{id: 15000}}) RETURN n.name")

        def walk(node):
            a = node.get("args", {})
            if "StartReason" in a:
                yield f"{node.get('operatorType')} {a.get('Details', '')} start={a['StartReason']}", a.get("TimeNs", 0)
            for ch in node.get("children", []):
                yield from walk(ch)
        return list(walk(p.last.get("plan") or {}))
    keyed, plain = profile("K"), profile("L")
    tk, tp = sum(t for _, t in keyed), sum(t for _, t in plain)
    obs = (f"20,000 nodes: with NODE KEY {[o for o, _ in keyed]} {tk / 1e6:.2f} ms; "
           f"without a constraint {[o for o, _ in plain]} {tp / 1e6:.2f} ms")
    if tk * 5 < tp:
        seek = any("Seek" in o for o, _ in keyed)
        return "SUPPORTED", "the key lookup is served by the constraint (" + \
            ("the plan names an index seek; Neo4j's operator is NodeUniqueIndexSeek" if seek else
             "the plan does not name a seek operator: Neo4j shows NodeUniqueIndexSeek") + "); " + obs
    return "DIFFERENT", "no evidence the constraint serves the lookup; " + obs


case("schema.node_key.seek", "Schema", "A NODE KEY gives the planner an index to seek on", check=seek_check,
     neo4j="NodeUniqueIndexSeek on the key.")


def setup_index_cases():
    """Every CREATE INDEX / FULLTEXT / POINT statement in the packages' SETUP.md, exactly as written."""
    for setup in sorted(ROOT.glob("*/SETUP.md")):
        for s in parse_statements(setup):
            if not re.search(r"\bCREATE\s+(\w+\s+)?INDEX\b", s["cypher"], re.I):
                continue
            pkg = setup.parent.name
            name = re.search(r"INDEX\s+(\w+)", s["cypher"]).group(1)
            kind = (re.search(r"CREATE\s+(FULLTEXT|POINT)\s+INDEX", s["cypher"], re.I) or [None, "RANGE"])[1].upper()

            def check(R, store, csv_dir, block=s["block"], name=name, kind=kind):
                r = R(block)
                if r.exit:
                    return "UNSUPPORTED", err(r)
                again = R(block)
                show = R("SHOW INDEXES")
                row = next((x for x in show.rows if x.get("name") == name), None)
                if row is None:
                    return "DIFFERENT", f"created, but SHOW INDEXES lists {[x.get('name') for x in show.rows]}"
                obs = f"created; IF NOT EXISTS rerun exit {again.exit}; SHOW INDEXES type {row.get('type')!r}"
                if str(row.get("type", "")).upper() != kind:
                    return "DIFFERENT", obs + f" (Neo4j: {kind})"
                return "SUPPORTED", obs
            case(f"schema.setup.{pkg}.{name}", "Schema", f"{pkg} SETUP.md: {s['tags'].get('name', name)}",
                 check=check, neo4j=f"Creates a {kind} index; rerun is a no-op.",
                 uses=({"FULLTEXT": "CREATE FULLTEXT INDEX", "POINT": "CREATE POINT INDEX"}.get(kind, "CREATE INDEX"),))


FIX = ("CREATE (a:P {id: 1, name: 'a'}), (b:P {id: 2, name: 'b'}), (c:P {id: 3, name: 'c'}), "
       "(d:P {id: 4, name: 'd'}), (e:P {id: 5, name: 'e'}), "
       "(a)-[:R {w: 1}]->(b), (b)-[:R {w: 2}]->(c), (c)-[:R {w: 3}]->(d), (a)-[:R {w: 10}]->(d), "
       "(a)-[:S {w: 4}]->(e), (e)-[:S {w: 5}]->(c)")


def visualization_check(R, store, csv_dir):
    r = R("CALL db.schema.visualization()")
    if r.exit:
        return "UNSUPPORTED", err(r)
    row = r.rows[0] if r.rows else {}
    labels = sorted(n.get("name") or (n.get("labels") or [None])[0] or n.get("properties", {}).get("name", "?")
                    if isinstance(n, dict) else str(n) for n in row.get("nodes", []))
    obs = f"columns {r.columns}; {len(row.get('nodes', []))} nodes {labels}, {len(row.get('relationships', []))} relationships; " \
          f"first node {fmt((row.get('nodes') or [None])[0], 200)}"
    if r.columns != ["nodes", "relationships"]:
        return "DIFFERENT", obs
    return "SUPPORTED", obs


case("schema.visualization", "Schema", "CALL db.schema.visualization()", setup=(FIX,), check=visualization_check,
     neo4j="One row: nodes (one virtual node per label) and relationships (one per type and label pair).")


def show_indexes_check(R, store, csv_dir):
    R("CREATE INDEX i_P_name IF NOT EXISTS FOR (n:P) ON (n.name)")
    r = R("SHOW INDEXES")
    if r.exit:
        return "UNSUPPORTED", err(r)
    return "SUPPORTED", f"columns {r.columns}; rows {fmt(r.rows, 300)}"


case("schema.show_indexes", "Schema", "SHOW INDEXES output shape", check=show_indexes_check,
     neo4j="Columns id, name, state, populationPercent, type, entityType, labelsOrTypes, properties, indexProvider, "
           "owningConstraint, lastRead, readCount.")


# ---------------------------------------------------------------- Cypher cases

def cy(cid, title, stmt, expect, uses=(), **k):
    case(f"cypher.{cid}", "Cypher", title, stmt, setup=k.pop("setup", (FIX,)), expect=expect, uses=uses, **k)


COUNT_ROWS = [[1, 2], [2, 1], [3, 1], [4, 0], [5, 0]]
cy("collect_subquery", "COLLECT { … } with ORDER BY",
   "MATCH (p:P {id: 1}) RETURN COLLECT { MATCH (p)-[:R]->(x) RETURN x.id ORDER BY x.id } AS ids", [[[2, 4]]],
   uses=("COLLECT {}",))
cy("count_subquery", "COUNT { pattern }",
   "MATCH (p:P) RETURN p.id AS id, COUNT { (p)-[:R]->() } AS n ORDER BY id", COUNT_ROWS, uses=("COUNT {}",))
cy("count_subquery_where", "count{ … } > 1 in WHERE, lower case",
   "MATCH (p:P) WHERE count{ (p)-[:R]->() } > 1 RETURN p.id", [[1]], uses=("COUNT {}",))
cy("exists_pattern", "EXISTS { pattern }",
   "MATCH (p:P) WHERE EXISTS { (p)-[:R]->(:P {id: 4}) } RETURN p.id ORDER BY p.id", [[1], [3]], uses=("EXISTS {}",))
cy("exists_match_where", "EXISTS { MATCH … WHERE … }",
   "MATCH (p:P) WHERE EXISTS { MATCH (p)-[r:R]->() WHERE r.w > 5 } RETURN p.id", [[1]], uses=("EXISTS {}",))
cy("call_importing_with", "CALL { WITH p … } (importing WITH)",
   "MATCH (p:P) CALL { WITH p MATCH (p)-[:R]->(x) RETURN count(x) AS n } RETURN p.id, n ORDER BY p.id", COUNT_ROWS,
   uses=("CALL {}",))
cy("call_unit", "CALL { … } without imports",
   "CALL { MATCH (n:P) RETURN count(n) AS c } RETURN c", [[5]], uses=("CALL {}",))
cy("call_scoped", "CALL (p) { … }",
   "MATCH (p:P) CALL (p) { MATCH (p)-[:R]->(x) RETURN count(x) AS n } RETURN p.id, n ORDER BY p.id", COUNT_ROWS,
   uses=("CALL (x) {}",))
cy("call_scoped_next", "CALL (i) { … NEXT … } (Cypher 25)",
   "CYPHER 25 UNWIND [1, 2] AS i CALL (i) { MATCH (p:P) WHERE p.id <= i RETURN p NEXT RETURN count(p) AS c } "
   "RETURN i, c ORDER BY i", [[1, 1], [2, 2]], uses=("CALL (x) {}", "NEXT"))
cy("shortest_path", "Legacy shortestPath *1..5",
   "MATCH (a:P {id: 1}), (d:P {id: 4}) MATCH path = shortestPath((a)-[:R*1..5]->(d)) RETURN length(path)", [[1]],
   uses=("shortestPath",))
cy("shortest_path_zero", "Legacy shortestPath *0..8 between distinct nodes",
   "MATCH (a:P {id: 1}), (c:P {id: 3}) MATCH path = shortestPath((a)-[:R*0..8]->(c)) "
   "RETURN [n IN nodes(path) | n.id] AS ids", [[[1, 2, 3]]], uses=("shortestPath",))
cy("shortest_path_same_node", "Legacy shortestPath *0..8 from a node to itself",
   "MATCH (a:P {id: 1}) MATCH path = shortestPath((a)-[:R*0..8]->(a)) RETURN length(path)", [[0]],
   neo4j="Zero-length path when the lower bound is 0.", verify=True, uses=("shortestPath",))
cy("all_shortest_paths", "Legacy allShortestPaths, undirected, type disjunction, *..8",
   "MATCH (a:P {id: 1}), (c:P {id: 3}) MATCH path = allShortestPaths((a)-[:R|S*..8]-(c)) "
   "RETURN [n IN nodes(path) | n.id] AS ids", [[[1, 2, 3]], [[1, 4, 3]], [[1, 5, 3]]], ordered=False,
   uses=("allShortestPaths",))
cy("varlength_bounded", "Bounded variable length *1..2",
   "MATCH (:P {id: 1})-[:R*1..2]->(x) RETURN x.id ORDER BY x.id", [[2], [3], [4]], uses=("var-length",))
cy("varlength_upper_only", "Variable length *..3",
   "MATCH (:P {id: 1})-[:R*..3]->(x) RETURN x.id ORDER BY x.id", [[2], [3], [4], [4]], uses=("var-length",))
cy("qpp_group", "Quantified path pattern ((x)-[:R]->(y)){1,3}",
   "MATCH (:P {id: 1}) ((x)-[:R]->(y)){1,3} (z) RETURN z.id ORDER BY z.id", [[2], [3], [4], [4]], uses=("QPP",))
cy("qpp_rel_quantifier", "Quantified relationship -[:R]->{1,8}",
   "MATCH (:P {id: 1})-[:R]->{1,8}(z) RETURN z.id ORDER BY z.id", [[2], [3], [4], [4]], uses=("QPP",))
cy("qpp_plus", "Quantified relationship -[:R]->+",
   "MATCH (:P {id: 1})-[:R]->+(z) RETURN z.id ORDER BY z.id", [[2], [3], [4], [4]], uses=("QPP",))
cy("qpp_star", "Quantified relationship -[:R]->* (includes zero hops)",
   "MATCH (:P {id: 1})-[:R]->*(z) RETURN z.id ORDER BY z.id", [[1], [2], [3], [4], [4]], uses=("QPP",))
cy("qpp_inner_where", "QPP with a WHERE inside the group",
   "MATCH (:P {id: 1}) ((x)-[r:R]->(y) WHERE r.w < 5){1,3} (z) RETURN z.id ORDER BY z.id", [[2], [3], [4]],
   uses=("QPP",))
cy("qpp_inline_node_where", "QPP with an inline node predicate (y:P WHERE …)",
   "MATCH (:P {id: 1}) ((x)-[:R]->(y:P WHERE y.id < 4)){1,3} (z) RETURN z.id ORDER BY z.id", [[2], [3]],
   uses=("QPP",))
cy("qpp_group_variables", "QPP group variables become lists, and concatenate",
   "MATCH (s:P {id: 1}) ((x)-[:R]->(y)){2} (z) RETURN [n IN y | n.id] AS ys, size([s] + y) AS n", [[[2, 3], 3]],
   uses=("QPP",))
cy("qpp_cycle", "QPP closing a cycle (s) … (s)",
   "MATCH (s:Q) ((x)-[:T]->(y)){3} (s) RETURN s.id ORDER BY s.id", [[1], [2], [3]],
   setup=("CREATE (a:Q {id: 1})-[:T]->(b:Q {id: 2})-[:T]->(c:Q {id: 3})-[:T]->(a)",), uses=("QPP",))
cy("rel_type_negation", "Relationship type negation [r:!R]",
   "MATCH (:P {id: 1})-[r:!R]->(x) RETURN x.id", [[5]], uses=("label expression !",))
cy("node_label_disjunction", "Node label disjunction (x:P|Q)",
   "MATCH (x:P|Q) RETURN count(x)", [[5]], uses=("node label disjunction",))
cy("rel_type_predicate", "Relationship type predicate WHERE r:S",
   "MATCH (:P {id: 1})-[r]->(x) WHERE r:S RETURN x.id", [[5]], uses=("type predicate r:TYPE",))
cy("repeatable_elements_allreduce", "MATCH REPEATABLE ELEMENTS with allReduce (Cypher 25)",
   "CYPHER 25 MATCH REPEATABLE ELEMENTS p = (:P {id: 1})-[rs:R]->{1,3}(x) "
   "WHERE allReduce(acc = 0, r IN rs | acc + r.w, acc <= 6) RETURN x.id ORDER BY x.id", [[2], [3], [4]],
   uses=("REPEATABLE ELEMENTS", "allReduce"))
cy("pattern_predicate", "Pattern predicate WHERE NOT (p)-[:R]->()",
   "MATCH (p:P) WHERE NOT (p)-[:R]->() RETURN p.id ORDER BY p.id", [[4], [5]], uses=("pattern predicate",))
cy("start_end_node", "startNode / endNode",
   "MATCH (:P {id: 1})-[r:S]->() RETURN startNode(r).id, endNode(r).id", [[1, 5]], uses=("startNode/endNode",))
cy("element_id", "elementId() comparison",
   "MATCH (a:P), (b:P) WHERE elementId(a) < elementId(b) RETURN count(*) AS c, valueType(elementId(a)) AS t",
   [[10, "STRING NOT NULL"]], uses=("elementId()",))
cy("reduce", "reduce() with numbers and with a map accumulator",
   "RETURN reduce(acc = 0, x IN [1, 2, 3] | acc + x) AS s, "
   "reduce(acc = {c: 0.0}, v IN [{c: 1.5}, {c: 2.0}] | {c: acc.c + v.c}) AS m", [[6, {"c": 3.5}]], uses=("reduce()",))
cy("reduce_relationships", "reduce() over relationships(path)",
   "MATCH p = (:P {id: 1})-[:R*3]->(:P {id: 4}) RETURN reduce(x = 1, r IN relationships(p) | x * r.w) AS v", [[6]],
   uses=("reduce()",))


def haversine(lat1, lon1, lat2, lon2, radius):
    p1, p2, dl, dp = map(math.radians, (lat1, lat2, lon2 - lon1, lat2 - lat1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


LONDON_PARIS = haversine(51.5074, -0.1278, 48.8566, 2.3522, 6378140.0)
cy("point_distance_wgs84", "point.distance between two WGS-84 points",
   "RETURN point.distance(point({latitude: 51.5074, longitude: -0.1278}), "
   "point({latitude: 48.8566, longitude: 2.3522})) AS d", [[LONDON_PARIS]], tol=1e-6,
   neo4j=f"Haversine with Neo4j's radius 6378140 m: {LONDON_PARIS:.1f} m (6371000 m would give "
         f"{haversine(51.5074, -0.1278, 48.8566, 2.3522, 6371000.0):.1f}); Aura gave 343941.08471254294 on 2026-10-30.",
   uses=("point()", "point.distance"))
cy("point_distance_cartesian", "point.distance between Cartesian points",
   "RETURN point.distance(point({x: 0, y: 0}), point({x: 3, y: 4})) AS d", [[5.0]], uses=("point.distance",))
cy("point_property", "A point stored as a property and read back",
   "MATCH (p:P {id: 1}) SET p.c = point({latitude: 51.5, longitude: -0.12}) RETURN p.c.latitude AS lat, p.c.srid AS srid",
   [[51.5, 4326]], uses=("point()",))
cy("date", "date() from a string and from a datetime",
   "RETURN toString(date('2024-01-02')) AS a, toString(date(datetime('2024-01-02T03:04:05Z'))) AS b",
   [["2024-01-02", "2024-01-02"]], uses=("date()",))
cy("date_now", "date() and datetime() with no argument",
   "RETURN date() IS NOT NULL AS a, date() = date(datetime()) AS b", [[True, True]], uses=("date()", "datetime()"))
cy("datetime_to_string", "toString(datetime) on the packages' format",
   "RETURN toString(datetime('2024-01-02T03:04:05Z')) AS a", [["2024-01-02T03:04:05Z"]],
   uses=("datetime()", "toString()"))
cy("datetime_vs_date", "Comparing a datetime with a date",
   "RETURN datetime('2024-01-02T00:00:00Z') >= date('2024-01-01') AS c", [[None]],
   neo4j="null: the types are not comparable (the packages' prose relies on this).", uses=("datetime()",))
cy("datetime_param", "datetime($p) from a date-only string parameter",
   "RETURN datetime($d) >= datetime('2024-01-01T00:00:00Z') AS c, toString(datetime($d)) AS s",
   [[True, "2024-06-01T00:00:00Z"]], params={"d": "2024-06-01"}, neo4j="Midnight UTC on Aura.", verify=True,
   uses=("datetime()",))
cy("duration_months", "datetime + duration({months: 1}) clamps to month end",
   "RETURN toString(datetime('2024-01-31T00:00:00Z') + duration({months: 1})) AS a", [["2024-02-29T00:00:00Z"]],
   uses=("duration()",))
cy("duration_between", "duration.between and duration.inDays",
   "RETURN toString(duration.between(datetime('2024-01-01T00:00:00Z'), datetime('2024-03-15T12:00:00Z'))) AS a, "
   "duration.inDays(date('2024-01-01'), date('2024-03-15')).days AS b", [["P2M14DT12H", 74]],
   uses=("duration.*",))
cy("duration_compare", "datetime comparison after adding a duration",
   "RETURN datetime('2024-01-01T00:00:00Z') + duration({months: 3}) > datetime('2024-03-31T00:00:00Z') AS a", [[True]],
   uses=("duration()",))
cy("round", "round() with and without precision",
   "RETURN round(3.14159, 2) AS a, round(2.5) AS b, round(1234.5678, 1) AS c", [[3.14, 3.0, 1234.6]],
   uses=("round()",))
cy("round_half", "round() half-way cases: round(2.675, 2), round(-2.5)",
   "RETURN round(2.675, 2) AS a, round(-2.5) AS b", [[2.68, -2.0]],
   neo4j="2.68 and -2.0, confirmed on Aura 2026-10-30.",
   uses=("round()",))
cy("to_string_numbers", "toString() on floats and integers",
   "RETURN toString(1.0) AS a, toString(12.5) AS b, toString(100) AS c, toString(0.1 + 0.2) AS d, toString(150.0) AS e",
   [["1.0", "12.5", "100", "0.30000000000000004", "150.0"]], neo4j="Java Double.toString.", uses=("toString()",))
cy("integer_division", "Integer division and modulo",
   "RETURN 7 / 2 AS a, 7 % 3 AS b, 7 / 2.0 AS c", [[3, 1, 3.5]])
cy("misc_functions", "size, head, last, range, coalesce, toLower, replace, any/all/single, slicing, abs, casts",
   "RETURN size('abc') AS a, size([1, 2]) AS b, head([1, 2]) AS c, last([1, 2]) AS d, range(1, 3) AS e, "
   "coalesce(null, 2) AS f, toLower('AB') AS g, replace('a-b', '-', '_') AS h, any(x IN [1, 2] WHERE x > 1) AS i, "
   "all(x IN [1, 2] WHERE x > 0) AS j, single(x IN [1, 2] WHERE x > 1) AS k, [1, 2, 3, 4][..3] AS l, abs(-2) AS m, "
   "toInteger(3.9) AS n, toFloat(3) AS o",
   [[3, 2, 1, 2, [1, 2, 3], 2, "ab", "a_b", True, True, True, [1, 2, 3], 2, 3, 3.0]])
cy("list_comprehension", "List comprehension",
   "RETURN [x IN range(1, 5) WHERE x % 2 = 1 | x * 10] AS l", [[[10, 30, 50]]], uses=("list comprehension",))
cy("pattern_comprehension", "Pattern comprehension",
   "MATCH (a:P {id: 1}) UNWIND [(a)-[:R]->(x) | x.id] AS i RETURN i ORDER BY i", [[2], [4]],
   uses=("pattern comprehension",))
cy("dynamic_property", "Dynamic property access n[key] and map[key]",
   "MATCH (p:P {id: 1}) WITH p, 'name' AS k, {a: 1} AS m RETURN p[k] AS v, m['a'] AS w", [["a", 1]],
   uses=("dynamic property access",))
cy("chained_comparison", "Chained comparison 0.80 <= x <= 1.00",
   "WITH 0.9 AS x, 0.5 AS y RETURN 0.80 <= x <= 1.00 AS a, 0.80 <= y <= 1.00 AS b", [[True, False]],
   uses=("chained comparison",))
cy("regex", "Regular expression with (?i) and \\b (identity-validation SETUP.md)",
   r"RETURN 'n/a' =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*' AS a, "
   r"'Test@x.com' =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*' AS b, "
   r"'contest@x.com' =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*' AS c", [[True, True, False]],
   neo4j="Java regex semantics.", uses=("regex =~",))
cy("union", "UNION and UNION ALL",
   "RETURN 1 AS x UNION RETURN 2 AS x UNION RETURN 1 AS x", [[1], [2]], ordered=False, uses=("UNION",))
cy("next", "NEXT query chaining (Cypher 25)",
   "CYPHER 25 MATCH (p:P) RETURN p.id AS id NEXT RETURN count(*) AS c", [[5]], uses=("NEXT",))
cy("next_merge", "NEXT feeding a MERGE (configurable-bom shape)",
   "CYPHER 25 MATCH (a:P {id: 1})-[r:R]->(b) RETURN a AS s, r AS r, b AS t "
   "NEXT MERGE (s)-[x:Z {w: r.w}]->(t) RETURN count(x) AS c", [[2]], uses=("NEXT", "MERGE"))
cy("cypher25_prefix", "CYPHER 25 version prefix", "CYPHER 25 RETURN 1 AS x", [[1]], uses=("CYPHER 25",))
cy("optional_match", "OPTIONAL MATCH with no match",
   "MATCH (p:P {id: 4}) OPTIONAL MATCH (p)-[:R]->(x) RETURN p.id AS id, x.id AS xid", [[4, None]],
   uses=("OPTIONAL MATCH",))
cy("set_label", "SET n:Label, then match on it",
   "MATCH (p:P {id: 1}) SET p:Flagged WITH count(*) AS _ MATCH (q:Flagged) RETURN q.id", [[1]], uses=("SET label",))
cy("delete", "DELETE relationships and count them",
   "MATCH ()-[r:S]->() DELETE r RETURN count(*) AS c", [[2]], uses=("DELETE",))
def limit_check(R, store, csv_dir):
    R("UNWIND range(1, 1500) AS i CREATE (:N {i: i})")
    full = R("MATCH (a:N), (b:N) WHERE a.i < b.i RETURN count(*) AS c", timeout="300s")
    one_row = R("MATCH (a:N), (b:N) WHERE a.i < b.i RETURN a.i LIMIT 1", timeout="300s")
    obs = f"count(*) of {full.rows[0]['c'] if full.rows else '?'} matches: {full.seconds:.2f} s; LIMIT 1: {one_row.seconds:.2f} s"
    return ("DIFFERENT" if one_row.seconds > 0.25 * full.seconds else "SUPPORTED"), obs


def allreduce_check(R, store, csv_dir):
    R("UNWIND range(1, 8) AS i CREATE (:N {i: i})")
    R("MATCH (a:N), (b:N) WHERE a <> b CREATE (a)-[:R {w: 1}]->(b)")
    times, counts = {}, {}
    for k in (4, 6):
        r = R(f"CYPHER 25 MATCH REPEATABLE ELEMENTS (a:N {{i: 1}})-[rs:R]->{{1,{k}}}(b) "
              "WHERE allReduce(acc = 0, r IN rs | acc + r.w, acc <= 1) RETURN count(*) AS n", timeout="300s")
        times[k], counts[k] = r.seconds, (r.rows[0]["n"] if r.rows else r.message)
    obs = (f"8-node complete graph; allReduce fails after the first hop, so every bound returns {counts[4]} walks. "
           f"Bound 4: {times[4]:.2f} s; bound 6: {times[6]:.2f} s")
    return ("DIFFERENT" if times[6] > 5 * max(times[4], 0.01) else "SUPPORTED"), obs


case("cypher.allreduce_pruning", "Cypher", "allReduce prunes REPEATABLE ELEMENTS expansion early", check=allreduce_check,
     neo4j="allReduce is evaluated during expansion, so a failing prefix is never extended; the cost does not grow "
           "with the bound when every walk fails at the first hop (from the Cypher 25 documentation).", verify=True,
     uses=("REPEATABLE ELEMENTS", "allReduce"))
case("cypher.limit_short_circuit", "Cypher", "LIMIT stops pattern enumeration early", check=limit_check,
     neo4j="Streams: LIMIT 1 returns after the first match, far faster than counting every match.")
cy("value_type", "valueType() and IS :: type predicates (used by the landing checks)",
   "RETURN valueType('a') AS a, valueType(1) AS b, valueType(1.0) AS c, valueType(true) AS d, "
   "valueType(datetime('2024-01-02T03:04:05Z')) AS e, 'a' IS :: STRING AS f, datetime() IS :: ZONED DATETIME AS g",
   [["STRING NOT NULL", "INTEGER NOT NULL", "FLOAT NOT NULL", "BOOLEAN NOT NULL", "ZONED DATETIME NOT NULL", True, True]])


# ---------------------------------------------------------------- procedures

def fulltext_check(R, store, csv_dir):
    # '123-45-0000' shares the 123 and 45 groups but is four edits away: a keyword analyser keeps each SSN
    # one token, so it must not match. An engine that splits on '-' matches it through the shared groups.
    R("CREATE (:SSN {ssn: '123-45-6789'}), (:SSN {ssn: '123-45-6788'}), (:SSN {ssn: '123-45-0000'}), "
      "(:SSN {ssn: '999-99-9999'})")
    block = next((s["block"] for s in parse_statements(ROOT / "identity-validation" / "SETUP.md")
                  if "FULLTEXT" in s["cypher"]), None)
    c = R(block)
    if c.exit:
        return "UNSUPPORTED", "index creation failed: " + err(c)
    r = R(r"MATCH (s:SSN {ssn: '123-45-6789'}) WITH s, replace(s.ssn, '-', '\\-') AS e "
          "CALL db.index.fulltext.queryNodes('ssnFuzzyIndex', e + '~1') YIELD node, score RETURN node.ssn AS ssn ORDER BY ssn")
    if r.exit:
        return "UNSUPPORTED", err(r)
    got = [x["ssn"] for x in r.rows]
    want = ["123-45-6788", "123-45-6789"]
    R("CREATE (:SSN {ssn: 'hello world'})")
    probes = []
    for term in ("123", "123-45-6789", "123\\\\-45\\\\-6789", "hello", "hello~1", "helo~1", "hello world"):
        x = R(f"CALL db.index.fulltext.queryNodes('ssnFuzzyIndex', '{term}') YIELD node RETURN node.ssn AS ssn")
        probes.append(f"{term!r}→{[y['ssn'] for y in x.rows] if not x.exit else err(x)}")
    a = R("CALL db.index.fulltext.listAvailableAnalyzers()")
    obs = (f"query the package uses returned {got}; other terms: {'; '.join(probes)}; "
           f"listAvailableAnalyzers: {err(a) if a.exit else 'ok'}")
    return ("SUPPORTED" if got == want else "DIFFERENT"), obs


case("proc.fulltext_query", "Procedures", "db.index.fulltext.queryNodes, keyword analyser, fuzzy ~1 (identity-validation)",
     check=fulltext_check, neo4j="Lucene: the exact SSN and the one-edit neighbour.", uses=("db.index.fulltext",))
case("proc.apoc_text", "Procedures", "apoc.text.jaroWinklerDistance", "RETURN apoc.text.jaroWinklerDistance('martha', 'marhta') AS d",
     neo4j="Requires the APOC plugin.", uses=("apoc.*",))
case("proc.apoc_coll", "Procedures", "apoc.coll.toSet", "RETURN apoc.coll.toSet([1, 1, 2]) AS s",
     neo4j="Requires the APOC plugin.", uses=("apoc.*",))
case("proc.gds_project", "Procedures", "gds.graph.project", "CALL gds.graph.project('g', 'P', 'R')", setup=(FIX,),
     neo4j="Requires the GDS plugin.", uses=("gds.*",))


def procedures_check(R, store, csv_dir):
    r = R("SHOW PROCEDURES YIELD name RETURN name ORDER BY name")
    if r.exit:
        return "UNSUPPORTED", err(r)
    names = [x["name"] for x in r.rows]
    return "SUPPORTED", f"{len(names)} procedures: {', '.join(names)}"


case("proc.show_procedures", "Procedures", "SHOW PROCEDURES (what is available)", check=procedures_check)


# ---------------------------------------------------------------- CLI cases

def envelope_check(R, store, csv_dir):
    r = R("RETURN 1 AS x, 'a' AS y")
    keys = sorted(r.last)
    want = {"columnTypes", "columns", "notifications", "rows", "truncated"}  # what relate_cli.py reads
    extra = sorted(set(keys) - want)
    obs = f"keys {keys}" + (f" (extra, unused: {extra})" if extra else "") + f"; {fmt(r.last)}"
    return ("SUPPORTED" if want <= set(keys) else "DIFFERENT"), obs


case("cli.envelope", "CLI", "--mode envelope shape", check=envelope_check, neo4j="n/a (CLI contract)")


def exit_check(stmt, want, **kw):
    def check(R, store, csv_dir):
        r = R(stmt, **kw)
        obs = f"exit {r.exit}; error {fmt(r.error, 250)}"
        return ("SUPPORTED" if r.exit == want else "DIFFERENT"), obs
    return check


case("cli.exit_syntax", "CLI", "Exit code for a syntax error", check=exit_check("RETRN 1", 6), neo4j="n/a (expect 6)")
case("cli.exit_semantic", "CLI", "Exit code for an undefined variable", check=exit_check("RETURN nope", 6), neo4j="n/a (expect 6)")
case("cli.exit_unknown_function", "CLI", "Exit code for an unknown function",
     check=exit_check("RETURN foo.bar(1)", 6), neo4j="n/a (expect 6)")
case("cli.exit_unknown_procedure", "CLI", "Exit code for an unknown procedure",
     check=exit_check("CALL apoc.help('x')", 6), neo4j="n/a (6 expected; APOC/GDS gaps classify on it)")
case("cli.exit_timeout", "CLI", "Exit code for --timeout",
     # Two small ranges rather than one huge one: Relate refuses range(1, 1000000000) as a 97 GB value
     # (exit 1, kind capacity) before the timeout can fire.
     check=exit_check("UNWIND range(1, 100000) AS a UNWIND range(1, 100000) AS b WITH a WHERE a < 0 "
                      "RETURN count(*)", 7, timeout="300ms"),
     neo4j="n/a (expect 7)")
case("cli.exit_runtime", "CLI", "Exit code for a runtime error (division by zero)",
     check=exit_check("RETURN 1 / 0 AS x", 1), neo4j="Neo4j raises an ArithmeticException (/ by zero).")
case("cli.missing_param", "CLI", "A statement whose $parameter is not supplied",
     "MATCH (n:P {id: $id}) RETURN n", setup=(FIX,), rejects=True, neo4j="Rejected: Expected parameter(s): id.")


def explain_no_params_check(R, store, csv_dir):
    r = R("EXPLAIN MATCH (n:P {id: $id}) RETURN n")
    return ("SUPPORTED" if r.exit == 0 else "UNSUPPORTED"), f"exit {r.exit}; {err(r) if r.exit else 'plan returned'}"


case("cli.explain_without_params", "CLI", "EXPLAIN with an unsupplied $parameter", setup=(FIX,),
     check=explain_no_params_check, neo4j="EXPLAIN plans without parameter values.")


def row_cap_check(R, store, csv_dir):
    default = R("UNWIND range(1, 150) AS x RETURN x", max_rows=None)
    zero = R("UNWIND range(1, 150) AS x RETURN x", max_rows=0)
    warn = default.stderr.strip().splitlines()[0] if default.stderr.strip() else ""
    obs = (f"default: {len(default.rows)} rows, truncated={default.last.get('truncated')}, stderr {warn!r}; "
           f"--max-rows 0: {len(zero.rows)} rows, truncated={zero.last.get('truncated')}")
    ok = len(zero.rows) == 150 and not zero.last.get("truncated")
    return ("SUPPORTED" if ok else "DIFFERENT"), obs


case("cli.row_cap", "CLI", "Row cap under the agent harness, with and without --max-rows 0", check=row_cap_check,
     neo4j="n/a (CLI contract)")


def params_check(R, store, csv_dir):
    r = R("RETURN $s AS s, $i AS i, $f AS f, $q AS q, $l AS l, $m AS m",
          params={"s": "hello", "i": 5, "f": 1.5, "q": "123", "l": [1, "a"], "m": {"k": [1, 2]}})
    bare = R("RETURN $a AS a, $b AS b", params=None, extra=["--param", "a=hello", "--param", "b=123"])
    obs = (f"JSON-encoded: {fmt(r.table())} types {r.last.get('columnTypes')}; "
           f"bare a=hello b=123: {fmt(bare.table())} types {bare.last.get('columnTypes')}")
    ok = not r.exit and same(r.table(), [["hello", 5, 1.5, "123", [1, "a"], {"k": [1, 2]}]], 1e-9)
    return ("SUPPORTED" if ok else "DIFFERENT"), obs


case("cli.params", "CLI", "--param with a string, integer, float, quoted number, list and map", check=params_check,
     neo4j="n/a (bare 123 binds an INTEGER, so strings must be JSON-quoted)")


def json_values_check(R, store, csv_dir):
    r = R("RETURN datetime('2024-01-02T03:04:05Z') AS dt, date('2024-01-02') AS d, "
          "duration({months: 1, days: 2}) AS dur, point({latitude: 1.0, longitude: 2.0}) AS pt, "
          "1.0 AS f, 1 AS i, 1.5e300 AS big")
    if r.exit:
        return "UNSUPPORTED", err(r)
    return "SUPPORTED", f"{fmt(r.rows[0], 600)}; columnTypes {r.last.get('columnTypes')}"


case("cli.json_values", "CLI", "JSON form of datetime, date, duration, point, float and integer values",
     check=json_values_check, neo4j="n/a (serialisation)", uses=("datetime()",))


def json_graph_check(R, store, csv_dir):
    r = R("MATCH p = (a:P {id: 1})-[r:R]->(b:P {id: 2}) RETURN a, r, p")
    if r.exit:
        return "UNSUPPORTED", err(r)
    return "SUPPORTED", f"{fmt(r.rows[0], 900)}; columnTypes {r.last.get('columnTypes')}"


case("cli.json_graph", "CLI", "JSON form of a node, a relationship and a path", setup=(FIX,), check=json_graph_check,
     neo4j="n/a (serialisation)")


def notification_check(stmt, want):
    def check(R, store, csv_dir):
        r = R("EXPLAIN " + stmt)
        if r.exit:
            return "UNSUPPORTED", err(r)
        ns = r.notifications
        hit = [n for n in ns if want.lower() in (str(n.get("code", "")) + str(n.get("title", ""))).lower()]
        obs = "; ".join(f"{n.get('code')} {n.get('gql_status')} {n.get('severity')}: {n.get('description')}" for n in ns) or "none"
        return ("SUPPORTED" if hit else "DIFFERENT"), obs
    return check


for cid, stmt, want in (
        ("unknown_label", "MATCH (n:Nope) RETURN n", "UnknownLabel"),
        ("unknown_rel_type", "MATCH ()-[r:NOPE]->() RETURN r", "UnknownRelationshipType"),
        ("unknown_property", "MATCH (n:P) WHERE n.nope = 1 RETURN n", "UnknownPropertyKey"),
        ("unbounded_varlength", "MATCH (a:P)-[:R*]->(b) RETURN b", "UnboundedVariableLengthPattern")):
    case(f"cli.notify.{cid}", "CLI", f"EXPLAIN notification: {want}", setup=(FIX,), check=notification_check(stmt, want),
         neo4j=f"Neo.ClientNotification.Statement.{want}{'Warning' if 'Unknown' in want else ''}")
case("cli.comment_semicolon", "CLI", "A ; inside a leading /* … */ comment (annotation blocks)",
     "/* @name x\n * @usage a; b\n */\nRETURN 1 AS x", expect=[[1]], neo4j="n/a (Neo4j drivers send one statement)")
case("cli.line_comment_semicolon", "CLI", "A ; inside a // comment", "// a; b\nRETURN 1 AS x", expect=[[1]],
     neo4j="n/a")
case("cli.string_semicolon", "CLI", "A ; inside a string literal", "RETURN 'a;b' AS x", expect=[["a;b"]], neo4j="n/a")
case("cli.trailing_semicolon", "CLI", "A trailing ; on a one-shot statement", "RETURN 1 AS x;", expect=[[1]], neo4j="n/a")


def store_check(R, store, csv_dir):
    a = R("CREATE (:A {x: 1})")
    b = R("MATCH (a:A) RETURN count(a) AS c")
    m1 = cl.run("CREATE (:A {x: 1})", ":memory:")
    m2 = cl.run("MATCH (a:A) RETURN count(a) AS c", ":memory:")
    obs = f"directory: second call sees {b.rows}; :memory:: second call sees {m2.rows}"
    ok = not a.exit and b.rows == [{"c": 1}] and m2.rows == [{"c": 0}] and not m1.exit
    return ("SUPPORTED" if ok else "DIFFERENT"), obs


case("cli.store_types", "CLI", "One-shot calls on a directory store vs :memory:", check=store_check, neo4j="n/a")


def clone_check(R, store, csv_dir):
    R("CREATE (:A {x: 1})-[:T]->(:A {x: 2})")
    dest = pathlib.Path(tempfile.mkdtemp(prefix="cl-probe-clone-")) / "copy"
    try:
        p = subprocess.run([cl.BIN, "clone", str(store), str(dest)], capture_output=True, text=True, env=cl.ENV)
        if p.returncode:
            return "UNSUPPORTED", f"exit {p.returncode}: {p.stderr.strip()}"
        c = cl.run("MATCH (a)-[r]->(b) RETURN count(r) AS c", dest)
        w = cl.run("CREATE (:A {x: 3})", dest)
        s = R("MATCH (a:A) RETURN count(a) AS c")
        obs = f"clone sees {c.rows}; write to clone exit {w.exit}; source still {s.rows}"
        ok = c.rows == [{"c": 1}] and s.rows == [{"c": 2}]
        return ("SUPPORTED" if ok else "DIFFERENT"), obs
    finally:
        shutil.rmtree(dest.parent, ignore_errors=True)


case("cli.clone", "CLI", "relate clone SOURCE DEST", check=clone_check, neo4j="n/a")


def script_check(R, store, csv_dir):
    r = cl.run(None, store, script="CREATE (:B);\nRETRN 1;\nCREATE (:B);\n")
    c = R("MATCH (b:B) RETURN count(b) AS c")
    obs = f"exit {r.exit}; error {fmt(r.error, 250)}; :B nodes after {c.rows}"
    return ("SUPPORTED" if r.exit == 6 and c.rows == [{"c": 1}] else "DIFFERENT"), obs


case("cli.script_stops", "CLI", "A stdin script stops at the first failed statement", check=script_check, neo4j="n/a")


def read_only_check(R, store, csv_dir):
    R("CREATE (:A)")
    r = R("CREATE (:A)", extra=["--read-only"])
    q = R("MATCH (a:A) RETURN count(a) AS c", extra=["--read-only"])
    obs = f"write under --read-only: exit {r.exit} {err(r) if r.exit else ''}; read: {q.rows}"
    return ("SUPPORTED" if r.exit and q.rows == [{"c": 1}] else "DIFFERENT"), obs


case("cli.read_only", "CLI", "--read-only rejects writes and allows reads", check=read_only_check, neo4j="n/a")


# ---------------------------------------------------------------- ontology namespace

def ontology_check(R, store, csv_dir):
    env = {"RELATE_PREVIEW": "ontology"}
    doc = (ROOT / "patient-journey" / "ONTOLOGY.json").read_text()
    s = R("CALL db.ontology.set($doc)", params={"doc": doc}, env=env)
    obs = [f"set(package document): exit {s.exit}{' ' + err(s) if s.exit else ''}"]
    status = "SUPPORTED"
    if s.exit:
        o = json.loads(doc)
        ext = o["extensions"]
        o["extensions"] = {"tables": ext.get("data_source_tables"), "mappings": ext.get("data_source_mappings")}
        s2 = R("CALL db.ontology.set($doc)", params={"doc": json.dumps(o)}, env=env)
        obs.append(f"set(with extensions renamed to tables/mappings): exit {s2.exit}{' ' + err(s2) if s2.exit else ''}")
        status = "DIFFERENT" if not s2.exit else "UNSUPPORTED"
        if s2.exit:
            return status, "; ".join(obs)
    a = R("CALL db.ontology.apply()", env=env)
    obs.append(f"apply(): exit {a.exit}{' ' + err(a) if a.exit else ''}")
    c = R("SHOW CONSTRAINTS YIELD name, type RETURN type, count(*) AS n ORDER BY type", env=env)
    obs.append(f"constraints after apply: {fmt(c.table())}")
    g = R("CALL db.ontology.get('json') YIELD ontology RETURN size(ontology) AS n", env=env)
    obs.append(f"get(): {fmt(g.table())}")
    return status, "; ".join(obs)


case("ontology.set_apply", "Ontology", "db.ontology.set/apply with a package's ONTOLOGY.json (RELATE_PREVIEW=ontology)",
     check=ontology_check, neo4j="Packages pin ontology-graph-spec 1.0.0 with extensions data_source_tables/"
                                 "data_source_mappings; Aura has no db.ontology.* procedures.")


def namespace_check(R, store, csv_dir):
    r = R("RETURN 1 AS x", extra=["--namespace", "system_ontologies"])
    s = R("SHOW DATABASES YIELD name, access RETURN name, access")
    return "SUPPORTED", f"query in system_ontologies: exit {r.exit} {err(r) if r.exit else ''}; SHOW DATABASES {fmt(s.table())}"


case("ontology.namespace", "Ontology", "The fixed system_ontologies namespace", check=namespace_check,
     neo4j="Aura: SHOW DATABASES lists neo4j and system.")


# ---------------------------------------------------------------- construct inventory and corpus

CONSTRUCTS = [  # (construct, regex over Cypher with comments and strings removed)
    ("LOAD CSV", r"\bLOAD\s+CSV\b"),
    ("IS NODE KEY", r"\bIS\s+NODE\s+KEY\b"),
    ("IS UNIQUE", r"\bIS\s+UNIQUE\b"),
    ("COLLECT {}", r"\bCOLLECT\s*\{"),
    ("COUNT {}", r"\bCOUNT\s*\{"),
    ("EXISTS {}", r"\bEXISTS\s*\{"),
    ("CALL {}", r"\bCALL\s*\{"),
    ("CALL (x) {}", r"\bCALL\s*\([^)]*\)\s*\{"),
    ("shortestPath", r"\bshortestPath\s*\("),
    ("allShortestPaths", r"\ballShortestPaths\s*\("),
    ("var-length", r"\[[^\]]*\*\s*\d*\s*(\.\.\s*\d*)?\s*\]"),
    ("QPP", r"\}\s*\(|(?:->|-)\s*[+*]\s*\(|\)\s*[+*]\s*\n\s*\(|\)\s*\{\s*\d+\s*(,\s*\d*\s*)?\}"),
    ("label expression !", r"[:|&]\s*!\s*\w"),
    ("node label disjunction", r"\(\w*\s*:\s*\w+\s*\|\s*\w+"),
    ("type predicate r:TYPE", r"\b(?:WHEN|WHERE|AND|OR|NOT)\s+\w+:[A-Z_]+\b"),
    ("REPEATABLE ELEMENTS", r"\bREPEATABLE\s+ELEMENTS\b"),
    ("allReduce", r"\ballReduce\s*\("),
    ("NEXT", r"^\s*NEXT\s*$"),
    ("CYPHER 25", r"^\s*CYPHER\s+25\b"),
    ("UNION", r"\bUNION\b"),
    ("OPTIONAL MATCH", r"\bOPTIONAL\s+MATCH\b"),
    ("pattern predicate", r"\bNOT\s+\(\w*(:\w+)?\)\s*[-<]"),
    ("MERGE", r"\bMERGE\b"),
    ("SET label", r"\bSET\s+\w+:\w+"),
    ("DELETE", r"\bDELETE\b"),
    ("point()", r"(?<![\w.])point\s*\("),
    ("point.distance", r"\bpoint\.distance\s*\("),
    ("date()", r"(?<![\w.])date\s*\("),
    ("datetime()", r"(?<![\w.])datetime\s*\("),
    ("duration()", r"(?<![\w.])duration\s*\("),
    ("duration.*", r"\bduration\.\w+\s*\("),
    ("elementId()", r"\belementId\s*\("),
    ("reduce()", r"(?<![\w.])reduce\s*\("),
    ("round()", r"\bround\s*\("),
    ("toString()", r"\btoString\s*\("),
    ("toInteger", r"\btoInteger\s*\("),
    ("toFloat", r"\btoFloat\s*\("),
    ("toBoolean", r"\btoBoolean\s*\("),
    ("startNode/endNode", r"\b(startNode|endNode)\s*\("),
    ("list comprehension", r"\[\s*\w+\s+IN\b"),
    ("pattern comprehension", r"\[\s*\(\w*(:\w+)?\)\s*[-<]"),
    ("dynamic property access", r"(?<![\w$])[a-z]\w*\[\s*[a-zA-Z_][\w.]*\s*\]"),
    ("chained comparison", r"[\d.]+\s*<=?\s*[^<>=\n]+?\s*<=?\s*[\d.]+"),
    ("regex =~", r"=~"),
    ("db.index.fulltext", r"\bdb\.index\.fulltext\.\w+"),
    ("apoc.*", r"\bapoc\.\w"),
    ("gds.*", r"\bgds\.\w"),
    ("CREATE INDEX", r"\bCREATE\s+INDEX\b"),
    ("CREATE FULLTEXT INDEX", r"\bCREATE\s+FULLTEXT\s+INDEX\b"),
    ("CREATE POINT INDEX", r"\bCREATE\s+POINT\s+INDEX\b"),
]


def package_statements():
    out = []
    for qf in sorted(ROOT.glob("*/QUERIES.md")):
        for fname in ("SETUP.md", "QUERIES.md"):
            for s in parse_statements(qf.parent / fname):
                s["package"], s["file"] = qf.parent.name, fname
                out.append(s)
    return out


def inventory(stmts):
    uses = collections.defaultdict(lambda: collections.Counter())
    for s in stmts:
        text = strip_cypher_noise(s["cypher"])
        for name, rx in CONSTRUCTS:
            n = len(re.findall(rx, text, re.M | (0 if name in ("NEXT", "CYPHER 25") else re.I)))
            if n:
                uses[name][s["package"]] += n
    return uses


def corpus_cases(stmts):
    by_pkg = collections.defaultdict(list)
    for s in stmts:
        if s["annotated"]:
            by_pkg[s["package"]].append(s)
    for pkg, items in by_pkg.items():
        for i, s in enumerate(items, 1):
            def check(R, store, csv_dir, s=s):
                r = R("EXPLAIN " + s["cypher"])
                if r.exit:
                    return "UNSUPPORTED", err(r)
                return "SUPPORTED", "plans"
            case(f"corpus.{pkg}.{s['file'][:-3].lower()}.{i:02d}", "Corpus",
                 f"{pkg} {s['file']}: {s['heading']}", check=check, neo4j="Plans on Neo4j/Aura (with plugins where needed).")


# ---------------------------------------------------------------- runner

def execute(c):
    store = pathlib.Path(tempfile.mkdtemp(prefix="cl-probe-store-"))
    csv_dir = None
    try:
        if c.csv:
            csv_dir = pathlib.Path(tempfile.mkdtemp(prefix="cl-probe-csv-"))
            for name, data in c.csv.items():
                (csv_dir / name).parent.mkdir(parents=True, exist_ok=True)
                (csv_dir / name).write_bytes(data)

        def R(stmt, **kw):
            kw.setdefault("timeout", c.timeout)
            kw.setdefault("env", c.env)
            return cl.run(stmt, store, csv_dir=csv_dir, **kw)

        for s in c.setup:
            r = R(s)
            if r.exit:
                return "UNSUPPORTED", f"setup failed: {err(r)}"
        if c.check:
            return c.check(R, store, csv_dir)
        r = R(c.stmt, params=c.params)
        if c.rejects:
            if r.exit:
                return "SUPPORTED", f"rejected as on Neo4j: {err(r)}"
            return "DIFFERENT", f"accepted, returning {fmt(r.table())}"
        if r.exit:
            return "UNSUPPORTED", err(r)
        got = r.table()
        if c.expect is not None and not rows_equal(got, c.expect, c.ordered, c.tol):
            return "DIFFERENT", f"returned {fmt(got)}; Neo4j returns {fmt(c.expect)}"
        return "SUPPORTED", f"returned {fmt(got)}"
    except Exception as e:  # a probe bug must not hide the other cases
        return "ERROR", f"probe error: {type(e).__name__}: {e}"
    finally:
        shutil.rmtree(store, ignore_errors=True)
        if csv_dir:
            shutil.rmtree(csv_dir, ignore_errors=True)


RANK = {"ERROR": 4, "UNSUPPORTED": 3, "DIFFERENT": 2, "SUPPORTED": 1}


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = pathlib.Path(a.out) if a.out else ROOT / "output" / "relate-tests" / f"probe-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    datetime_cases()
    setup_index_cases()
    stmts = package_statements()
    corpus_cases(stmts)
    todo = [c for c in CASES if c.id.startswith(a.only)]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(execute, todo))
    rows = []
    for c, (status, observed) in zip(todo, results):
        rows.append({"id": c.id, "area": c.area, "title": c.title, "status": status, "observed": observed,
                     "neo4j": c.neo4j, "verify": c.verify, "statement": c.stmt, "uses": list(c.uses)})

    inv = inventory(stmts)
    by_construct = collections.defaultdict(list)
    for r in rows:
        for u in r["uses"]:
            by_construct[u].append(r)
    inv_rows = []
    for name, _ in CONSTRUCTS:
        n = sum(inv[name].values())
        covering = by_construct.get(name, [])
        worst = max((x["status"] for x in covering), key=RANK.get, default="UNCOVERED" if n else "")
        inv_rows.append({"construct": name, "uses": n, "packages": dict(inv[name]),
                         "cases": [x["id"] for x in covering], "worst": worst})

    version = cl.version()
    (out / "probe.json").write_text(json.dumps({"version": version, "cases": rows, "inventory": inv_rows}, indent=1))
    md = [f"# Relate capability probe", "", f"Version: `{json.dumps(version)}`  ", f"Run: {stamp}", ""]
    counts = collections.Counter(r["status"] for r in rows)
    md += ["| Status | Cases |", "| --- | --- |"] + [f"| {k} | {v} |" for k, v in sorted(counts.items())] + [""]
    md += ["## Construct inventory (packages' QUERIES.md and SETUP.md)", "",
           "| Construct | Uses | Packages | Worst status | Cases |", "| --- | --- | --- | --- | --- |"]
    for r in inv_rows:
        if r["uses"] or r["cases"]:
            md.append(f"| {r['construct']} | {r['uses']} | {len(r['packages'])} | {r['worst']} | {len(r['cases'])} |")
    for area in dict.fromkeys(r["area"] for r in rows):
        md += ["", f"## {area}", "", "| Case | Status | Observed | Neo4j |", "| --- | --- | --- | --- |"]
        for r in rows:
            if r["area"] != area or (area == "Corpus" and r["status"] == "SUPPORTED"):
                continue
            cell = lambda s: s.replace("|", "\\|").replace("\n", " ")
            md.append(f"| `{r['id']}` {cell(r['title'])} | {r['status']}{' (verify)' if r['verify'] else ''} | "
                      f"{cell(r['observed'])} | {cell(r['neo4j'])} |")
        if area == "Corpus":
            ok = sum(1 for r in rows if r["area"] == "Corpus" and r["status"] == "SUPPORTED")
            md.append(f"\n{ok} corpus statements plan; only the others are listed.")
    (out / "probe.md").write_text("\n".join(md) + "\n")
    print(f"{len(rows)} cases: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + f" -> {out}")
    for r in rows:
        if r["status"] != "SUPPORTED":
            print(f"{r['status']:<12} {r['id']}: {r['observed'][:220]}")
    for r in inv_rows:
        if r["worst"] == "UNCOVERED" and not a.only:
            print(f"UNCOVERED    construct {r['construct']} ({r['uses']} uses)")


if __name__ == "__main__":
    main()
