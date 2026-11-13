#!/usr/bin/env python3
"""Check ONTOLOGY.json annotations against the bundled sample data (VALIDATION.md sections 3, 3b and 4).

Usage: python3 check_annotations.py <package-dir>
Also checks the three rules the schema and the spec library miss but the destination enforces: a constraint
flag repeated across entries of one label or relationship type (duplicate constraint names), repeated
endpoint pairs in a relationship table whose mapping key cannot tell them apart (MERGE collapses them), and,
when the package bundles tables, a property type Import does not support for local CSV imports (DATE above all).
Prints BLOCKER / WARN / NOTE / COUNT lines and ends with "done". Standard library only."""
import csv, json, re, sys, pathlib, collections

p = pathlib.Path(sys.argv[1])
m = json.loads((p / "ONTOLOGY.json").read_text())
out = lambda level, msg: print(f"{level} {msg}")

SAMPLE = re.compile(r"e\.g\. `([^`]+)`\.?\s*$")
NUMERIC_OR_CODED = re.compile(r"^(INTEGER|FLOAT|DATE|ZONED |LOCAL |DURATION|BOOLEAN)")
# The types Import supports for local CSV imports (upx SUPPORTED_CSV_TYPE_OPTIONS_COMPLETED); the rest of the
# Neo4jType enum converts cleanly and is then flagged "Not supported in local imports".
LOCAL_IMPORT_SCALARS = ("STRING", "INTEGER", "FLOAT", "BOOLEAN", "ZONED DATETIME")
LOCAL_IMPORT_TYPES = set(LOCAL_IMPORT_SCALARS) | {f"LIST<{t}>" for t in LOCAL_IMPORT_SCALARS} \
    | {f"VECTOR<{t}>" for t in ("FLOAT", "FLOAT32", "INTEGER", "INTEGER32", "INTEGER16", "INTEGER8")}

# Blocker: extensions anywhere except root data_source_tables/data_source_mappings and node display.
RENAMED = {"tables": "data_source_tables", "mappings": "data_source_mappings"}
for key, val in (m.get("extensions") or {}).items():
    if key in RENAMED:
        out("BLOCKER", f"root extensions.{key} is the pre-release name; rename it to extensions.{RENAMED[key]}")
    elif key not in ("data_source_tables", "data_source_mappings"):
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
tables = (m.get("extensions") or {}).get("data_source_tables") or {}
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

mappings = [x for lst in ((m.get("extensions") or {}).get("data_source_mappings") or {}).values() for x in lst]
if set(((m.get("extensions") or {}).get("data_source_mappings") or {}).keys()) != {"mapping0"}:
    out("BLOCKER", "extensions.data_source_mappings must hold exactly one list, keyed mapping0")

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

# Per-property checks: local-import type, description, length, sample, one_of / pattern.
def check_props(owner, props):
    for prop, d in (props or {}).items():
        if tables and d.get("type") not in LOCAL_IMPORT_TYPES:
            fix = "; store calendar dates as ZONED DATETIME at midnight UTC" if "DATE" in str(d.get("type")) else ""
            out("BLOCKER", f"type {d.get('type')} of {owner}.{prop} is not supported in local imports "
                f"(use {', '.join(LOCAL_IMPORT_SCALARS)}, a LIST<...> of one, or a VECTOR<...>{fix})")
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

# Constraint flags are scoped to a label or relationship type, not to an entry: the same flag on the same
# property in two entries of one type becomes two constraints with one name, and the destination drops the
# package. Property and constraint `name` stay unset (ONTOLOGY_SPEC_FORMAT.md).
flagged = collections.defaultdict(list)
for kind, entities in (("label", m.get("nodes", {})), ("relationship type", m.get("relationships", {}))):
    for k, e in entities.items():
        token = e.get("type") if kind != "label" else (e.get("label") or (e.get("labels") or {}).get("identifier"))
        for prop, d in (e.get("properties") or {}).items():
            if d.get("name"): out("WARN", f"{k}.{prop} sets name {d['name']!r}; packages leave property names unset")
            for flag in ("key", "must_exist", "unique"):
                if d.get(flag) is True: flagged[(kind, token, prop, flag)].append(k)
        for c, cd in (e.get("constraints") or {}).items():
            if cd.get("name"): out("WARN", f"constraint {k}.{c} sets name {cd['name']!r}; packages leave constraint names unset")
for (kind, token, prop, flag), keys in flagged.items():
    if len(keys) > 1:
        out("BLOCKER", f"{flag} on {prop!r} is declared by {len(keys)} entries of {kind} {token!r} ({', '.join(keys)}); "
            "the constraint covers the whole type, so flag it on one entry and state it in the others' descriptions")

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
    # Under MERGE a relationship is identified by its endpoints plus its mapping key, so rows repeating that
    # identity become one relationship: data loss when their property values differ, redundancy when they don't.
    ident_cols = [mp["from_node"]["properties"][k]["column"] for k in sorted(mp["from_node"]["properties"])] \
        + [mp["to_node"]["properties"][k]["column"] for k in sorted(mp["to_node"]["properties"])] \
        + [(mp.get("properties") or {}).get(k, {}).get("column", k) for k in mp.get("key", [])]
    prop_cols = [v["column"] for v in (mp.get("properties") or {}).values()]
    seen = collections.defaultdict(set)
    for r in rows.get(mp["table"], []):
        ident = tuple(r.get(c, "") for c in ident_cols)
        if all(ident[:len(ident_cols) - len(mp.get("key", []))]): seen[ident].add(tuple(r.get(c, "") for c in prop_cols))
    repeated = {i: v for i, v in seen.items() if len(v) > 1}
    rows_by_ident = collections.Counter(tuple(r.get(c, "") for c in ident_cols) for r in rows.get(mp["table"], []))
    duplicates = [i for i, n in rows_by_ident.items() if n > 1 and i not in repeated]
    if repeated:
        out("BLOCKER", f"{rk}: {len(repeated)} endpoint pairs in {mp['table']} repeat with different property values under "
            f"key {mp.get('key', [])}, e.g. {next(iter(repeated))}; MERGE keeps one per pair — set the mapping key "
            "to the property that tells parallel relationships apart")
    if duplicates:
        out("WARN", f"{rk}: {len(duplicates)} endpoint pairs in {mp['table']} repeat with identical values; they merge into one relationship")
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
