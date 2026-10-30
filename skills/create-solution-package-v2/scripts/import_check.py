#!/usr/bin/env python3
"""Load a package's sample data into a Cypherlite store and check it landed as ONTOLOGY.json says.

Usage: python3 import_check.py <package-dir> --store DIR [--out DIR] [--no-load]

Test mode steps 3 and 4 (TESTING.md). Generates import.cypher with ontology_to_cypher.py, runs it one
statement per call with --load-csv-dir <package>/sample-data, then compares the graph with expectations
computed here, independently, in Python from the CSVs, using Import's conversion rules:
- counts: nodes per label and relationships per (from label, type, to label);
- properties: each declared property present wherever its CSV cell is non-empty, with its declared type;
- keys: mapping-key values present and unique;
- multiplicity: each relationship end's count / min_count / max_count;
- constraints: every constraint the generator emitted is in SHOW CONSTRAINTS;
- TESTS.md: counts stated in the sample-data profile, compared with the CSVs and the graph.
Any failed check (or failed import statement) makes the import IMPORT-FAIL. A TESTS.md profile count
that disagrees is a stale-TESTS.md finding and does not by itself fail the import.
Writes import.cypher and import.json to --out. Exit 0 OK, 1 IMPORT-FAIL, 2 the generator refused.
Standard library only."""
import argparse, collections, csv, datetime, decimal, json, pathlib, re, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cypherlite_cli as cl  # noqa: E402
import ontology_to_cypher as gen  # noqa: E402

ISO_DATETIME = re.compile(gen.ISO_DATETIME.replace("\\\\", "\\"))
CYPHER_TYPE = {"STRING": "STRING", "INTEGER": "INTEGER", "FLOAT": "FLOAT", "BOOLEAN": "BOOLEAN",
               "ZONED DATETIME": "ZONED DATETIME"}


def py_conv(v, typ):
    """Import's conversion of one CSV cell, in Python (ontology_to_cypher.conv is the Cypher twin)."""
    if v is None or v == "":
        return None
    if typ == "STRING":
        return v
    t = v.strip()
    try:
        if typ == "INTEGER":
            try:
                return int(t)
            except ValueError:
                return int(decimal.Decimal(t))
        if typ == "FLOAT":
            return float(t)
        if typ == "BOOLEAN":
            return t.lower() in ("1", "true", "yes")
        if typ == "ZONED DATETIME":
            if not ISO_DATETIME.match(t):
                return None
            d = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
            return (d if d.tzinfo else d.replace(tzinfo=datetime.UTC)).astimezone(datetime.UTC)
    except (ValueError, ArithmeticError):
        return None
    raise gen.ShapeError(f"type {typ!r} not supported")


def read_rows(pkg, table):
    with gen.resolve_csv(pkg, table).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader)]
        return [dict(zip(header, r)) for r in reader if r]


def expectations(pkg):
    """What the graph should hold, from the CSVs alone."""
    pkg, o, maps, _ = gen.load(pkg)
    nodes_decl, rels_decl = o["nodes"], o["relationships"]
    nodes, rels, bad = {}, {}, collections.defaultdict(list)

    def note_bad(owner, prop, typ, raw, table):
        if raw not in (None, "") and py_conv(raw, typ) is None:
            bad[(owner, prop, typ, table)].append(raw)
    for m in (m for m in maps if m["type"] == "NODE"):
        decl = nodes_decl[m["node"]]
        label, props = gen.label_of(decl), decl["properties"]
        state = collections.OrderedDict()
        for r in read_rows(pkg, m["table"]):
            for p, b in m["properties"].items():
                note_bad(label, p, props[p]["type"], r.get(b["column"]), m["table"])
            key = tuple(py_conv(r.get(m["properties"][k]["column"]), props[k]["type"]) for k in m["key"])
            if any(x is None for x in key):
                continue
            vals = state.setdefault(key, {})
            for p, b in m["properties"].items():
                vals[p] = py_conv(r.get(b["column"]), props[p]["type"])  # SET: later rows overwrite, null clears
        nodes[label] = {"entity": m["node"], "table": m["table"], "key": list(m["key"]), "ids": set(state),
                        "props": {p: (props[p]["type"], sum(1 for v in state.values() if v.get(p) is not None))
                                  for p in m["properties"]}}
    for m in (m for m in maps if m["type"] == "RELATIONSHIP"):
        decl = rels_decl[m["relationship"]]
        a, b = gen.label_of(nodes_decl[decl["from"]["node"]]), gen.label_of(nodes_decl[decl["to"]["node"]])
        group = rels.setdefault((a, decl["type"], b), {"entities": [], "tables": [], "ids": collections.OrderedDict(),
                                                       "props": {}, "keyed": set()})
        group["entities"].append(m["relationship"])
        group["tables"].append(m["table"])
        group["keyed"].add(bool(m["key"]))
        rprops, mp = decl.get("properties") or {}, m.get("properties") or {}

        def end_key(side, node_id):
            nmap = next(x for x in maps if x["type"] == "NODE" and x["node"] == node_id)
            return [(side["properties"][k]["column"], nodes_decl[node_id]["properties"][k]["type"])
                    for k in nmap["key"] if k in side["properties"]]
        fk, tk = end_key(m["from_node"], decl["from"]["node"]), end_key(m["to_node"], decl["to"]["node"])
        for r in read_rows(pkg, m["table"]):
            for p, bnd in mp.items():
                note_bad(decl["type"], p, rprops[p]["type"], r.get(bnd["column"]), m["table"])
            f = tuple(py_conv(r.get(c), t) for c, t in fk)
            t_ = tuple(py_conv(r.get(c), t) for c, t in tk)
            if any(x is None for x in f + t_):
                continue
            rk = tuple((k, py_conv(r.get(mp[k]["column"]), rprops[k]["type"])) for k in m["key"])
            vals = group["ids"].setdefault((f, t_, rk), {})
            for p, bnd in mp.items():
                vals[p] = py_conv(r.get(bnd["column"]), rprops[p]["type"])
        for p in mp:
            group["props"][p] = rprops[p]["type"]
    for (a, t, b), g in rels.items():
        g["dangling"] = [(f, to) for (f, to, _) in g["ids"] if f not in nodes[a]["ids"] or to not in nodes[b]["ids"]]
        g["prop_counts"] = {p: (typ, sum(1 for v in g["ids"].values() if v.get(p) is not None))
                            for p, typ in g["props"].items()}
    return o, nodes, rels, bad


def profile_counts(tests_md):
    """Counts the TESTS.md sample-data profile states: rows like | `Label` | 1,010 | or | `TYPE` (A → B) | 557 |."""
    if not tests_md.exists():
        return []
    text = tests_md.read_text(encoding="utf-8")
    m = re.search(r"^## Sample-data profile\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    out = []
    for line in (m.group(1) if m else "").splitlines():
        r = re.match(r"^\|\s*`([^`]+)`\s*(?:\(([^)]*)\))?\s*\|\s*([\d,]+)\b", line)
        if r:
            ends = re.split(r"\s*(?:→|->)\s*", r.group(2)) if r.group(2) and ("→" in r.group(2) or "->" in r.group(2)) else None
            out.append({"name": r.group(1), "ends": ends, "count": int(r.group(3).replace(",", "")), "line": line.strip()})
    return out


def one(store, stmt):
    r = cl.run(stmt, store)
    if r.exit:
        raise RuntimeError(f"{stmt[:120]}: {r.error_class}: {r.message}")
    return r.rows


def q(name):
    return gen.q(name)


def check_graph(pkg, store, stmts):
    o, nodes, rels, bad = expectations(pkg)
    checks = []

    def add(check, subject, expected, observed, ok, detail=""):
        checks.append({"check": check, "subject": subject, "expected": expected, "observed": observed,
                       "ok": bool(ok), "detail": detail})

    for label, e in nodes.items():
        n = one(store, f"MATCH (n:{q(label)}) RETURN count(n) AS c")[0]["c"]
        add("count", label, len(e["ids"]), n, n == len(e["ids"]))
        cols, parts = {}, []
        for i, (p, (typ, _)) in enumerate(e["props"].items()):
            cols[p] = i
            parts.append(f"count(n.{q(p)}) AS p{i}, sum(CASE WHEN n.{q(p)} IS NOT NULL AND NOT n.{q(p)} IS :: "
                         f"{CYPHER_TYPE[typ]} THEN 1 ELSE 0 END) AS w{i}")
        row = one(store, f"MATCH (n:{q(label)}) RETURN " + ", ".join(parts))[0]
        for p, (typ, want) in e["props"].items():
            i = cols[p]
            add("property", f"{label}.{p}", f"{want} {typ}", f"{row[f'p{i}']} present, {row[f'w{i}']} wrong type",
                row[f"p{i}"] == want and row[f"w{i}"] == 0)
        keys = ", ".join(f"n.{q(k)} AS k{i}" for i, k in enumerate(e["key"]))
        dup = one(store, f"MATCH (n:{q(label)}) WITH {keys}, count(*) AS c WHERE c > 1 RETURN count(*) AS d")[0]["d"]
        nulls = one(store, f"MATCH (n:{q(label)}) WHERE " + " OR ".join(f"n.{q(k)} IS NULL" for k in e["key"])
                    + " RETURN count(n) AS c")[0]["c"]
        add("key", f"{label}({', '.join(e['key'])})", "unique, never null", f"{dup} duplicated, {nulls} null",
            dup == 0 and nulls == 0)
    for (a, t, b), g in rels.items():
        subject = f"(:{a})-[:{t}]->(:{b})"
        n = one(store, f"MATCH (:{q(a)})-[r:{q(t)}]->(:{q(b)}) RETURN count(r) AS c")[0]["c"]
        want = len(g["ids"])
        detail = ""
        if g["dangling"]:
            detail = (f"{len(g['dangling'])} CSV relationships reference an endpoint no node row creates, "
                      f"e.g. {g['dangling'][0]} ({', '.join(g['tables'])}); Import drops them silently too")
        if len(g["keyed"]) > 1:
            detail += "; mappings with and without a key share this type and endpoints, so MERGE order matters"
        add("count", subject, want, n, n == want, detail.strip("; "))
        if g["prop_counts"]:
            parts = [f"count(r.{q(p)}) AS p{i}, sum(CASE WHEN r.{q(p)} IS NOT NULL AND NOT r.{q(p)} IS :: "
                     f"{CYPHER_TYPE[typ]} THEN 1 ELSE 0 END) AS w{i}" for i, (p, (typ, _)) in enumerate(g["prop_counts"].items())]
            row = one(store, f"MATCH (:{q(a)})-[r:{q(t)}]->(:{q(b)}) RETURN " + ", ".join(parts))[0]
            for i, (p, (typ, want_p)) in enumerate(g["prop_counts"].items()):
                add("property", f"{t}.{p} {subject}", f"{want_p} {typ}", f"{row[f'p{i}']} present, {row[f'w{i}']} wrong type",
                    row[f"p{i}"] == want_p and row[f"w{i}"] == 0)
    for rk, rel in o["relationships"].items():
        a, b = gen.label_of(o["nodes"][rel["from"]["node"]]), gen.label_of(o["nodes"][rel["to"]["node"]])
        for end, spec in (("from", rel["from"]), ("to", rel["to"])):
            if not any(spec.get(c) is not None for c in ("count", "min_count", "max_count")):
                continue
            lo = spec.get("count", spec.get("min_count"))
            hi = spec.get("count", spec.get("max_count"))
            anchor, pat = (a, f"(n)-[r:{q(rel['type'])}]->(:{q(b)})") if end == "from" else (b, f"(:{q(a)})-[r:{q(rel['type'])}]->(n)")
            cond = " OR ".join(x for x in ((f"c < {lo}" if lo is not None else ""), (f"c > {hi}" if hi is not None else "")) if x)
            row = one(store, f"MATCH (n:{q(anchor)}) OPTIONAL MATCH {pat} WITH n, count(r) AS c "
                             f"RETURN count(n) AS nodes, sum(CASE WHEN {cond} THEN 1 ELSE 0 END) AS bad, min(c) AS lo, max(c) AS hi")[0]
            add("multiplicity", f"{rk}.{end} ({anchor})", f"{lo}..{hi if hi is not None else 'many'}",
                f"{row['bad']} of {row['nodes']} outside; observed {row['lo']}..{row['hi']}", row["bad"] == 0,
                "pooled with any other mapping of the same type and endpoints")
    for (owner, prop, typ, table), raws in sorted(bad.items()):
        add("conversion", f"{owner}.{prop}", f"every non-empty cell converts to {typ}",
            f"{len(raws)} do not, e.g. {raws[0]!r}", False,
            f"{table}: Import loads these as null, silently; the property is missing on those entities")
    labels = {r["label"] for r in one(store, "CALL db.labels() YIELD label RETURN label")}
    types = {r["relationshipType"] for r in one(store, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")}
    extra_l, extra_t = sorted(labels - set(nodes)), sorted(types - {t for (_, t, _) in rels})
    add("vocabulary", "labels and types", "only the reference ontology's", f"extra labels {extra_l}, extra types {extra_t}",
        not extra_l and not extra_t)
    shown = {r["name"] for r in one(store, "SHOW CONSTRAINTS YIELD name RETURN name")}
    for s in stmts:
        if s["kind"] == "constraint" and not s.get("skipped"):
            add("constraint", s["name"], "present", "present" if s["name"] in shown else "missing", s["name"] in shown)

    findings = []
    for pc in profile_counts(pkg / "TESTS.md"):
        name, ends = pc["name"], pc["ends"]
        if name in nodes:
            csv_n = len(nodes[name]["ids"])
            graph_n = one(store, f"MATCH (n:{q(name)}) RETURN count(n) AS c")[0]["c"]
        else:
            groups = [(k, g) for k, g in rels.items() if k[1] == name and (not ends or (k[0], k[2]) == tuple(ends))]
            if not groups:
                continue
            csv_n = sum(len(g["ids"]) for _, g in groups)
            graph_n = sum(one(store, f"MATCH (:{q(a)})-[r:{q(t)}]->(:{q(b)}) RETURN count(r) AS c")[0]["c"] for (a, t, b), _ in groups)
        subject = name + (f" ({' → '.join(ends)})" if ends else "")
        ok = pc["count"] == csv_n == graph_n
        add("tests-profile", subject, pc["count"], f"CSV {csv_n}, graph {graph_n}", ok,
            "" if ok else "stale TESTS.md profile or data: " + pc["line"])
        if not ok:
            findings.append(f"TESTS.md profile says {subject} = {pc['count']}; the CSVs give {csv_n} and the graph {graph_n}")
    return checks, findings, nodes, rels


def load(pkg, store, out=None):
    """Generate import.cypher (saved to out) and run it statement by statement."""
    pkg = pathlib.Path(pkg)
    stmts, notes = gen.generate(pkg)
    if out:
        pathlib.Path(out).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(out) / "import.cypher").write_text(gen.render(stmts, notes, pkg.resolve().name), encoding="utf-8")
    ran = []
    for s in stmts:
        if s.get("skipped"):
            ran.append({**s, "exit": None, "seconds": 0, "error": s["skipped"]})
            continue
        r = cl.run(s["cypher"], store, csv_dir=pkg / "sample-data", timeout="600s")
        ran.append({**s, "exit": r.exit, "seconds": round(r.seconds, 3), "error": f"{r.error_class}: {r.message}" if r.exit else ""})
    return ran, notes


def run(pkg, store, out=None, do_load=True):
    pkg = pathlib.Path(pkg)
    t0 = time.monotonic()
    ran, notes = load(pkg, store, out) if do_load else (gen.generate(pkg)[0], [])
    checks, findings, _, _ = check_graph(pkg, store, ran)
    failed_stmts = [s for s in ran if s.get("exit")]
    failed = [c for c in checks if not c["ok"] and c["check"] != "tests-profile"]
    status = "IMPORT-FAIL" if failed_stmts or failed else "OK"
    result = {"status": status, "seconds": round(time.monotonic() - t0, 2), "notes": notes,
              "statements": [{k: s.get(k) for k in ("kind", "entity", "name", "table", "exit", "seconds", "error", "skipped")}
                             for s in ran],
              "checks": checks, "findings": findings,
              "summary": {"statements": len(ran), "failed_statements": len(failed_stmts),
                          "checks": len(checks), "failed_checks": len(failed),
                          "profile_mismatches": len(findings)}}
    if out:
        (pathlib.Path(out) / "import.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--store", required=True)
    ap.add_argument("--out")
    ap.add_argument("--no-load", action="store_true")
    a = ap.parse_args()
    try:
        res = run(a.package, a.store, a.out, not a.no_load)
    except gen.ShapeError as e:
        print(f"ERROR {e}")
        sys.exit(2)
    print(f"{res['status']} in {res['seconds']}s: {res['summary']}")
    for s in res["statements"]:
        if s.get("exit"):
            print(f"STATEMENT-FAIL {s['kind']} {s['entity']}: {s['error']}")
    for c in res["checks"]:
        if not c["ok"]:
            print(f"{'FINDING' if c['check'] == 'tests-profile' else 'CHECK-FAIL'} {c['check']} {c['subject']}: "
                  f"expected {c['expected']}, observed {c['observed']} {c['detail']}")
    sys.exit(0 if res["status"] == "OK" else 1)
