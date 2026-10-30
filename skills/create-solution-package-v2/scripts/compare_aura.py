#!/usr/bin/env python3
"""Compare a test-mode run with results exported from a manual Aura run of the same queries (parity).

Usage: python3 compare_aura.py RUN_DIR/PACKAGE [--aura DIR]
       python3 compare_aura.py RUN_DIR/PACKAGE --kit     (write AURA_PARITY_KIT.md for the manual Aura run)

Reads the Cypherlite rows test mode saved (rows/NN.json) and the Aura JSON exports (aura/NN.json, as
Aura's Query tool exports them: an array of row objects). Both sides are reduced to one canonical form
before comparing:
- nodes become (label, key value), using each label's mapping key from ONTOLOGY.json;
- relationships become their type and properties;
- paths become the node/relationship sequence with directions;
- temporal values become ISO strings with seconds;
- floats are compared to 12 significant digits.
Rows are compared as multisets. Where the query has an ORDER BY, the sequence of sort-key values must also
agree, which allows ties in any order. A query with LIMIT and no ORDER BY returns an arbitrary subset, so
only its size and overlap are reported. A mismatch is re-tested after CYPHERLITE.md's known rendering
difference (toString of a datetime drops zero seconds) is normalised, and labelled as such.
Also compares aura/constraints.json and aura/rel-counts.json with the generated import, when present.
Writes parity.json and parity.md beside the package report. Standard library only."""
import argparse, collections, datetime, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ontology_to_cypher as gen  # noqa: E402
from annotations import parse_statements, strip_cypher_noise  # noqa: E402

TEMPORAL_KEYS = {"year", "month", "day"}
SHORT_DT = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d)(Z|[+-]\d\d:\d\d)")


def iso(m):
    """Aura's structured temporal map to an ISO string."""
    if not {"hour", "minute"} <= set(m):
        return f"{m['year']:04d}-{m['month']:02d}-{m['day']:02d}"
    frac = f".{m['nanosecond']:09d}".rstrip("0") if m.get("nanosecond") else ""
    s = f"{m['year']:04d}-{m['month']:02d}-{m['day']:02d}T{m['hour']:02d}:{m['minute']:02d}:{m.get('second', 0):02d}{frac}"
    off = m.get("timeZoneOffsetSeconds")
    if off is None:
        return s
    if off == 0:
        return s + "Z"
    sign = "+" if off > 0 else "-"
    return s + f"{sign}{abs(off) // 3600:02d}:{abs(off) % 3600 // 60:02d}"


class Canon:
    def __init__(self, keys):
        self.keys = keys  # label -> [key properties]

    def node(self, labels, props):
        label = sorted(labels)[0] if labels else "?"
        key = tuple(self.value(props.get(k)) for k in self.keys.get(label, [])) or ("?",)
        return ["node", label, list(key)]

    def value(self, v):
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, float):
            return float(f"{v:.12g}")
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            if v.get("kind") == "node":                       # Cypherlite node
                return self.node(v.get("labels", []), v.get("properties", {}))
            if v.get("kind") == "relationship":               # Cypherlite relationship
                return ["rel", v["type"], self.value(v.get("properties", {}))]
            if "segments" in v and "start" in v:              # Aura path
                out = [self.value(v["start"])]
                for seg in v["segments"]:
                    r = seg["relationship"]
                    forward = r.get("start") == seg["start"].get("identity")
                    out += [("->" if forward else "<-") + r["type"], self.value(seg["end"])]
                return ["path", out]
            if {"identity", "labels", "properties"} <= set(v):  # Aura node
                return self.node(v["labels"], v["properties"])
            if {"identity", "type", "start", "end"} <= set(v):  # Aura relationship
                return ["rel", v["type"], self.value(v.get("properties", {}))]
            if TEMPORAL_KEYS <= set(v):                        # Aura temporal
                return iso(v)
            return {k: self.value(x) for k, x in sorted(v.items())}
        if isinstance(v, list):
            if v and all(isinstance(x, dict) and x.get("kind") in ("node", "relationship") for x in v):
                out, prev_node = [], None                     # Cypherlite path
                for x in v:
                    if x["kind"] == "node":
                        prev_node = x
                        out.append(self.value(x))
                    else:
                        out.append(("->" if x["start_node"] == prev_node["id"] else "<-") + x["type"])
                return ["path", out]
            return [self.value(x) for x in v]
        return v


def soften(v):
    """Apply CYPHERLITE.md's known rendering difference: toString(datetime) without zero seconds."""
    if isinstance(v, str):
        return SHORT_DT.sub(lambda m: m.group(1) + ":00" + m.group(2), v)
    if isinstance(v, list):
        return [soften(x) for x in v]
    if isinstance(v, dict):
        return {k: soften(x) for k, x in v.items()}
    return v


def endpoints(v):
    """A path reduced to its two end nodes as an unordered pair, for queries whose path interior is an
    arbitrary choice (head(collect(...)), elementId ordering)."""
    if isinstance(v, list) and len(v) == 2 and v[0] == "path":
        nodes = [x for x in v[1] if isinstance(x, list)]
        return ["path-ends", sorted([nodes[0], nodes[-1]], key=json.dumps)]
    if isinstance(v, list):
        return [endpoints(x) for x in v]
    return v


ARBITRARY = re.compile(r"\bhead\s*\(\s*collect\s*\(|collect\s*\([^)]*\)\s*\[\s*0\s*\]|\belementId\s*\(", re.I)


def key(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def order_columns(cypher, columns):
    text = strip_cypher_noise(cypher)
    m = list(re.finditer(r"\bORDER\s+BY\b(.*?)(?=\bLIMIT\b|\bSKIP\b|;|$)", text, re.I | re.S))
    if not m:
        return None
    cols = []
    for item in m[-1].group(1).split(","):
        expr = re.sub(r"\s+(ASC|DESC|ASCENDING|DESCENDING)\s*$", "", item.strip(), flags=re.I).strip().strip("`")
        if expr in columns:
            cols.append(expr)
    return cols


def compare_query(n, heading, cypher, cl_rows, cl_cols, aura_rows, canon):
    text = strip_cypher_noise(cypher)
    has_limit = bool(re.search(r"\bLIMIT\b", text, re.I))
    order = order_columns(cypher, cl_cols)
    cols = cl_cols
    if aura_rows and set(aura_rows[0]) != set(cols):
        return {"n": n, "heading": heading, "status": "NOT-COMPARABLE",
                "detail": f"Aura export has columns {sorted(aura_rows[0])}; Cypherlite returned {cols}. The export may be "
                          "from a different query."}
    a = [[canon.value(r.get(c)) for c in cols] for r in aura_rows]
    b = [[canon.value(r.get(c)) for c in cols] for r in cl_rows]
    res = {"n": n, "heading": heading, "aura_rows": len(a), "cypherlite_rows": len(b), "ordered": order is not None}
    if has_limit and order is None:
        overlap = sum((collections.Counter(map(key, a)) & collections.Counter(map(key, b))).values())
        res.update(status="SUBSET", detail=f"LIMIT without ORDER BY: each engine may return any {len(a)} rows. "
                                           f"Sizes {len(a)} and {len(b)}; {overlap} rows in common. Judge Aura's rows "
                                           "against the TESTS.md invariant instead.")
        return res

    def same(x, y):
        return collections.Counter(map(key, x)) == collections.Counter(map(key, y))

    levels = [("", a, b), (" after normalising toString(datetime) seconds", soften(a), soften(b))]
    if ARBITRARY.search(text):
        levels.append((" comparing each path by its end nodes only: the query picks the path interior or the pair "
                       "orientation arbitrarily (head(collect(...)) or elementId order), which no two engines need share",
                       endpoints(soften(a)), endpoints(soften(b))))
    for label, xa, xb in levels:
        if same(xa, xb):
            detail = f"{len(xa)} rows, same multiset{label}"
            if order is not None:
                idx = [cols.index(c) for c in order]
                ka, kb = [[r[i] for i in idx] for r in xa], [[r[i] for i in idx] for r in xb]
                if xa == xb:
                    detail += "; identical order"
                elif ka == kb:
                    detail += f"; order agrees on ORDER BY {order} (rows differ only within ties)"
                else:
                    res.update(status="DIFFERENT", detail=detail + f"; but the ORDER BY {order} sequence differs")
                    return res
            res.update(status="MATCH" if not label else ("MATCH-ARBITRARY-CHOICE" if "end nodes" in label else "MATCH-KNOWN-DIFFERENCE"),
                       detail=detail)
            return res
    ca, cb = collections.Counter(map(key, a)), collections.Counter(map(key, b))
    only_a, only_b = list((ca - cb).elements()), list((cb - ca).elements())
    res.update(status="DIFFERENT", detail=f"{len(only_a)} rows only on Aura, {len(only_b)} only on Cypherlite",
               only_aura=only_a[:5], only_cypherlite=only_b[:5])
    return res


def compare_import(out, aura):
    lines = []
    imp = json.loads((out / "import.json").read_text())
    ours = {s["name"] for s in imp["statements"] if s["kind"] == "constraint" and not s.get("skipped")}
    if (aura / "constraints.json").exists():
        theirs = {c["name"]: c for c in json.loads((aura / "constraints.json").read_text())}
        kinds = collections.Counter(c["type"] for c in theirs.values())
        same = ours == set(theirs)
        lines.append({"check": "constraints", "status": "MATCH" if same else "DIFFERENT",
                      "detail": f"Aura {len(theirs)} ({dict(kinds)}), generated {len(ours)}"
                                + ("" if same else f"; only Aura {sorted(set(theirs) - ours)}, only generated {sorted(ours - set(theirs))}")})
    if (aura / "rel-counts.json").exists():
        theirs = {r["type"]: r["n"] for r in json.loads((aura / "rel-counts.json").read_text())}
        mine = collections.Counter()
        for c in imp["checks"]:
            if c["check"] == "count" and c["subject"].startswith("(:"):
                mine[re.search(r"\[:(\w+)\]", c["subject"]).group(1)] += c["observed"]
        same = theirs == dict(mine)
        lines.append({"check": "relationship counts", "status": "MATCH" if same else "DIFFERENT",
                      "detail": f"Aura {theirs}" + ("" if same else f"; Cypherlite {dict(mine)}")})
    return lines


def literal(v):
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, list):
        return "[" + ", ".join(literal(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {literal(x)}" for k, x in v.items()) + "}"
    return json.dumps(v)


def write_kit(out, res, stmts, aura):
    """The queries test mode ran, in run order, with their parameters as :param lines for Aura's Query tool."""
    L = [f"# Aura parity kit: {res['package']}", "",
         f"Run on a disposable Aura database, after importing `{res['package']}/sample-data/` through the Import flow "
         "with `ONTOLOGY.json`, and after any SETUP.md statements the report lists as run.", "",
         "For each query, set its parameters, run it, and export the result as JSON. Save it as `NN.json`, where NN is the "
         "query number below, in:", "", f"`{aura}`", "",
         "## Import checks (run first)", "", "Save these as `constraints.json` and `rel-counts.json`.", "",
         "```cypher", "SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties RETURN * ORDER BY name", "```", "",
         "```cypher", "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type", "```", ""]
    for q in res["queries"]:
        if q["status"] in ("SKIPPED", "NEEDS-PARAMS"):
            L += [f"## {q['n']:02d}. {q['heading']}", "", f"{q['status']} on Cypherlite: {q['reason']}", ""]
            continue
        s = stmts[q["heading"]]
        text = strip_cypher_noise(s["cypher"])
        ordered = bool(re.search(r"\bORDER\s+BY\b", text, re.I))
        subset = bool(re.search(r"\bLIMIT\b", text, re.I)) and not ordered
        L += [f"## {q['n']:02d}. {q['heading']}", "",
              "Compared " + ("in ORDER BY order" if ordered else "ignoring row order")
              + ("; an arbitrary subset under LIMIT, so judged on its invariants" if subset else "") + ".", ""]
        if q["params"]:
            L += ["```text"] + [f":param {k} => {literal(v)}" for k, v in q["params"].items()] + ["```", ""]
        L += ["```cypher", s["cypher"], "```", ""]
    (out / "aura").mkdir(exist_ok=True)
    (out / "AURA_PARITY_KIT.md").write_text("\n".join(L))
    print(out / "AURA_PARITY_KIT.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package_run")
    ap.add_argument("--aura")
    ap.add_argument("--kit", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.package_run).resolve()
    aura = pathlib.Path(a.aura).resolve() if a.aura else out / "aura"
    res = json.loads((out / "results.json").read_text())
    pkg = pathlib.Path(res["path"])
    _, o, maps, _ = gen.load(pkg)
    keys = {gen.label_of(o["nodes"][m["node"]]): list(m["key"]) for m in maps if m["type"] == "NODE"}
    canon = Canon(keys)
    stmts = {s["heading"]: s for s in parse_statements(pkg / "QUERIES.md") if s["annotated"]}
    if a.kit:
        return write_kit(out, res, stmts, aura)
    rows_out = []
    for q in res["queries"]:
        f = aura / f"{q['n']:02d}.json"
        if q["status"] == "SKIPPED" or not (out / "rows" / f"{q['n']:02d}.json").exists():
            rows_out.append({"n": q["n"], "heading": q["heading"], "status": "NOT-RUN", "detail": "not run on Cypherlite"})
            continue
        if not f.exists():
            rows_out.append({"n": q["n"], "heading": q["heading"], "status": "MISSING", "detail": f"no {f.name}"})
            continue
        cl = json.loads((out / "rows" / f"{q['n']:02d}.json").read_text())
        rows_out.append(compare_query(q["n"], q["heading"], stmts[q["heading"]]["cypher"], cl["rows"], cl["columns"],
                                      json.loads(f.read_text()), canon))
    imp = compare_import(out, aura)
    (out / "parity.json").write_text(json.dumps({"queries": rows_out, "import": imp}, indent=1, default=str))
    L = [f"# Aura parity: {res['package']}", "", f"Cypherlite run {out.parent.name}; Aura exports in `{aura}`.", "",
         "| Check | Status | Detail |", "| --- | --- | --- |"]
    L += [f"| Import: {x['check']} | {x['status']} | {x['detail']} |" for x in imp]
    L += [f"| {r['n']}. {r['heading']} | {r['status']} | {r['detail'].replace('|', '/')} |" for r in rows_out]
    for r in rows_out:
        if r.get("only_aura") or r.get("only_cypherlite"):
            L += ["", f"## {r['n']}. {r['heading']}", "", "Only on Aura:", "```"] + r.get("only_aura", []) + \
                 ["```", "Only on Cypherlite:", "```"] + r.get("only_cypherlite", []) + ["```"]
    (out / "parity.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
