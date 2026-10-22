#!/usr/bin/env python3
"""Check ONTOLOGY.json annotations against the bundled sample data (VALIDATION.md section 3b).

Usage: python3 check_annotations.py <package-dir>
Prints BLOCKER / WARN / NOTE / COUNT lines and ends with "done". Standard library only."""
import csv, json, re, sys, pathlib, collections

p = pathlib.Path(sys.argv[1])
m = json.loads((p / "ONTOLOGY.json").read_text())
out = lambda level, msg: print(f"{level} {msg}")

SAMPLE = re.compile(r"e\.g\. `([^`]+)`\.?\s*$")
NUMERIC_OR_CODED = re.compile(r"^(INTEGER|FLOAT|DATE|ZONED |LOCAL |DURATION|BOOLEAN)")

# Blocker: extensions anywhere except root tables/mappings and node display.
for key, val in (m.get("extensions") or {}).items():
    if key not in ("tables", "mappings"):
        out("BLOCKER", f"root extensions.{key} is not permitted")
def scan(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            here = f"{path}.{k}"
            if k == "extensions" and path != "$":
                node_level = re.fullmatch(r"\$\.nodes\.[^.]+", path)
                bad = set(v) - {"display"} if node_level else set(v)
                for b in sorted(bad):
                    out("BLOCKER", f"extensions.{b} at {path} is not permitted")
                continue
            if path == "$" and k == "extensions":
                continue
            scan(v, here)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            scan(v, f"{path}[{i}]")
scan(m, "$")
for k, n in m.get("nodes", {}).items():
    d = (n.get("extensions") or {}).get("display") or {}
    if "x" not in d or "y" not in d:
        out("BLOCKER", f"node {k} has no extensions.display x/y")
    if set(d) - {"x", "y"}:
        out("WARN", f"node {k} display carries {sorted(set(d) - {'x', 'y'})}; packages set x/y only")

# Root identity.
if m.get("id") != p.resolve().name:
    out("BLOCKER", f"id {m.get('id')!r} != package folder {p.resolve().name!r}")
if not m.get("name") or not m.get("description"):
    out("WARN", "root missing name/description")

# Resolve CSVs.
def find_csv(name):
    hits = [f for f in (p / "sample-data").rglob("*.csv")
            if f.relative_to(p / "sample-data").as_posix() == name or f.name == name]
    return hits[0] if len(hits) == 1 else None
tables = (m.get("extensions") or {}).get("tables") or {}
rows = {}
for t, tbl in tables.items():
    cols = [c.get("name") for c in tbl.get("columns", [])]
    if any(not c for c in cols): out("BLOCKER", f"table {t} has a column with no name")
    if len(cols) != len(set(cols)): out("BLOCKER", f"table {t} has duplicate column names")
    f = find_csv(t)
    if f is None:
        out("NOTE", f"table {t} does not resolve to one CSV below sample-data/"); continue
    with f.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != cols:
            out("BLOCKER", f"table {t}: CSV header {reader.fieldnames} != columns {cols} (names and order)")
        rows[t] = list(reader)

mappings = [x for lst in ((m.get("extensions") or {}).get("mappings") or {}).values() for x in lst]
if set(((m.get("extensions") or {}).get("mappings") or {}).keys()) != {"mapping0"}:
    out("BLOCKER", "extensions.mappings must hold exactly one list, keyed mapping0")

# Collect mapped values per (owner, property), and node identities per node key.
values = collections.defaultdict(list)
identities = collections.defaultdict(set)
node_key_props = {}
for mp in mappings:
    if mp["type"] == "NODE":
        node_key_props[mp["node"]] = sorted(mp.get("key", []))
for mp in mappings:
    data = rows.get(mp["table"], [])
    owner = mp.get("node") or mp.get("relationship")
    for prop, pmap in (mp.get("properties") or {}).items():
        values[(owner, prop)] += [r.get(pmap["column"], "") for r in data if r.get(pmap["column"], "") != ""]
    if mp["type"] == "NODE":
        kp = node_key_props[mp["node"]]
        for r in data:
            ident = tuple(r.get(mp["properties"][k]["column"], "") for k in kp)
            if all(ident): identities[mp["node"]].add(ident)

# Per-property checks: description, length, sample, one_of / pattern.
def check_props(owner, props):
    for prop, d in (props or {}).items():
        desc = d.get("description", "")
        if not desc: out("WARN", f"no description: {owner}.{prop}"); continue
        if len(desc) > 1024: out("BLOCKER", f"description over 1024 chars: {owner}.{prop}")
        vals = values.get((owner, prop), [])
        s = SAMPLE.search(desc)
        if NUMERIC_OR_CODED.match(d.get("type", "")) and not s:
            out("WARN", f"no e.g. sample: {owner}.{prop} ({d.get('type')})")
        if s and vals and s.group(1) not in vals:
            out("BLOCKER", f"sample {s.group(1)!r} not in mapped column: {owner}.{prop}")
        if "one_of" in d and "pattern" in d:
            out("BLOCKER", f"both one_of and pattern: {owner}.{prop}")
        if "one_of" in d:
            if d.get("type") != "STRING":
                out("WARN", f"one_of on non-STRING property {owner}.{prop} ({d.get('type')}): values compare as exact text")
            bad = sorted(set(vals) - set(d["one_of"]))
            if bad: out("BLOCKER", f"values outside one_of for {owner}.{prop}: {bad[:5]}")
            if s and s.group(1) not in d["one_of"]: out("BLOCKER", f"sample not in one_of: {owner}.{prop}")
        if "pattern" in d:
            if not (d["pattern"].startswith("^") and d["pattern"].endswith("$")):
                out("WARN", f"pattern not anchored with ^...$: {owner}.{prop}")
            rx = re.compile(d["pattern"])
            bad = sorted({v for v in vals if not rx.fullmatch(v)})
            if bad: out("BLOCKER", f"values not matching pattern for {owner}.{prop}: {bad[:5]}")
for k, n in m.get("nodes", {}).items():
    lab = n.get("label") or (n.get("labels") or {}).get("identifier") or ""
    if ":" in lab or "=" in lab: out("BLOCKER", f"label {lab!r} of node {k} contains ':' or '='")
    if not n.get("description"): out("WARN", f"no description: node {k}")
    elif len(n["description"]) > 1024: out("BLOCKER", f"description over 1024 chars: node {k}")
    check_props(k, n.get("properties"))
for k, r in m.get("relationships", {}).items():
    if not r.get("description"): out("WARN", f"no description: relationship {k}")
    elif len(r["description"]) > 1024: out("BLOCKER", f"description over 1024 chars: relationship {k}")
    check_props(k, r.get("properties"))

# Relationship counts against the data, per node at each end, pooled across every
# mapping of the same relationship entry.
labels = {k: (n.get("label") or (n.get("labels") or {}).get("identifier")) for k, n in m.get("nodes", {}).items()}
pairs_by_rel = collections.defaultdict(set)
for mp in mappings:
    if mp["type"] != "RELATIONSHIP": continue
    rk = mp["relationship"]; rel = m["relationships"].get(rk)
    if rel is None: out("BLOCKER", f"mapping for undeclared relationship {rk}"); continue
    for end, tgt in (("from", mp["from_node"]), ("to", mp["to_node"])):
        if tgt.get("label") != labels.get(rel[end]["node"]):
            out("BLOCKER", f"{rk}: {end}_node.label {tgt.get('label')!r} != label of {rel[end]['node']!r}")
    for r in rows.get(mp["table"], []):
        f = tuple(r.get(mp["from_node"]["properties"][k]["column"], "") for k in sorted(mp["from_node"]["properties"]))
        t = tuple(r.get(mp["to_node"]["properties"][k]["column"], "") for k in sorted(mp["to_node"]["properties"]))
        if all(f) and all(t): pairs_by_rel[rk].add((f, t))
for rk, rel in m.get("relationships", {}).items():
    pairs = pairs_by_rel.get(rk, set())
    for end in ("from", "to"):
        spec = rel[end]
        if "count" in spec and ("min_count" in spec or "max_count" in spec):
            out("BLOCKER", f"{rk}.{end}: both count and min_count/max_count")
        if any((spec.get(c) or 0) < 0 for c in ("count", "min_count", "max_count")):
            out("BLOCKER", f"{rk}.{end}: negative count")
        if spec.get("min_count") is not None and spec.get("max_count") is not None and spec["min_count"] > spec["max_count"]:
            out("BLOCKER", f"{rk}.{end}: min_count exceeds max_count")
    for end, idx in (("from", 0), ("to", 1)):
        spec = rel[end]
        if not any(c in spec for c in ("count", "min_count", "max_count")): continue
        per = collections.Counter(pair[idx] for pair in pairs)
        nodes = identities.get(spec["node"], set())
        lo = spec.get("count", spec.get("min_count")); hi = spec.get("count", spec.get("max_count"))
        bad = [n for n in nodes if (lo is not None and per[n] < lo) or (hi is not None and per[n] > hi)]
        out("BLOCKER" if bad else "COUNT", f"{rk}.{end} ({spec['node']}): expected {lo}..{hi if hi is not None else 'many'}, "
            + (f"{len(bad)} of {len(nodes)} nodes violate it, e.g. {bad[0]}" if bad else f"holds for {len(nodes)} nodes"))

print("done")
