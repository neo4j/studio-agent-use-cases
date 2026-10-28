#!/usr/bin/env python3
"""Convert a legacy GRAPH_MODEL.json to ONTOLOGY.json (ontology graph spec 1.0.0).

Usage: python3 convert_legacy.py <package-dir> [--schema-uri URI]

Structural conversion only, per ONTOLOGY_SPEC_FORMAT.md "Converting a legacy graph model".
Handles both legacy dialects found in packages:
  - graph-spec 4.0.0-alpha.25: mustExist, NodeMapping/RelationshipMapping, readable keys
  - older: nullable, lowercase "node"/"relationship" mappings, positional keys (n:0, r:1)
It never invents annotations (one_of, pattern, counts, aliases, reference) and never
deletes GRAPH_MODEL.json. Legacy extensions (sample, cardinality) are reported, not
carried over: their meaning belongs in descriptions and target counts, set by hand.

Writes <package-dir>/ONTOLOGY.json and prints a conversion log. Exit 1 on anything it
cannot convert safely. Standard library only.
"""
import csv, json, re, sys, pathlib

SCHEMA_URI = "https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json"
args = sys.argv[1:]
if "--schema-uri" in args:
    i = args.index("--schema-uri"); SCHEMA_URI = args[i + 1]; del args[i:i + 2]
if len(args) != 1:
    sys.exit(__doc__)
p = pathlib.Path(args[0]).resolve()
src = p / "GRAPH_MODEL.json"
if not src.is_file():
    sys.exit(f"no GRAPH_MODEL.json in {p}")
m = json.loads(src.read_text(encoding="utf-8"))
log = []
def note(msg): log.append(msg)
def fail(msg): print("\n".join(log)); sys.exit(f"CANNOT CONVERT: {msg}")

ALLOWED_PROP = {"type", "description", "key", "unique", "must_exist", "dimension", "one_of", "pattern", "reference"}

# --- readable keys -----------------------------------------------------------------
def label_of(n):
    return n.get("label") or (n.get("labels") or {}).get("identifier")
node_keys = {}
for k, n in m.get("nodes", {}).items():
    lab = label_of(n)
    if not lab: fail(f"node {k} has no label")
    node_keys[k] = lab if re.fullmatch(r"n:\d+", k) else k
if len(set(node_keys.values())) != len(node_keys):
    fail("two node definitions share a label; give them readable keys by hand")

def camel(s):
    parts = re.split(r"[^A-Za-z0-9]+", s.lower())
    return parts[0] + "".join(x.title() for x in parts[1:])
rels = m.get("relationships", {})
types = [r["type"] for r in rels.values()]
rel_keys = {}
for k, r in rels.items():
    if not re.fullmatch(r"r:\d+", k):
        rel_keys[k] = k; continue
    if types.count(r["type"]) == 1:
        new = camel(r["type"])
    else:
        f = node_keys[r["from"]["node"]]; t = node_keys[r["to"]["node"]]
        ty = camel(r["type"])
        new = f[0].lower() + f[1:] + ty[0].upper() + ty[1:] + t
    rel_keys[k] = new
if len(set(rel_keys.values())) != len(rel_keys):
    fail("generated relationship keys collide; name them by hand")
for old, new in list(node_keys.items()) + list(rel_keys.items()):
    if old != new: note(f"KEY {old} -> {new}")

# --- properties --------------------------------------------------------------------
def prop(owner, pk, d):
    out = {}
    for k, v in d.items():
        if k == "mustExist": out["must_exist"] = v
        elif k == "nullable":
            if v is False: out["must_exist"] = True
            else: note(f"DROPPED {owner}.{pk}.nullable: {v} (optional is the default; nothing to carry over)")
        elif k == "extensions":
            note(f"DROPPED {owner}.{pk}.extensions {sorted(v)} — restate as description text / counts by hand")
        elif k == "name":
            note(f"DROPPED {owner}.{pk}.name (packages leave property names unset)")
        elif k in ALLOWED_PROP: out[k] = v
        else: fail(f"unknown property field {owner}.{pk}.{k}")
    if out.get("key") and (out.get("must_exist") or out.get("unique")):
        out.pop("must_exist", None); out.pop("unique", None)
        note(f"FIXED {owner}.{pk}: key implies must_exist/unique; removed the redundant flags")
    return out

o = {"schema": SCHEMA_URI, "id": p.name, "version": "1"}
if m.get("name"): o["name"] = m["name"]
if m.get("description"): o["description"] = m["description"]
o["nodes"] = {}; o["relationships"] = {}
display = (m.get("display") or {}).get("nodes", {})
for k, n in m.get("nodes", {}).items():
    nk = node_keys[k]
    nn = {}
    for f, v in n.items():
        if f in ("label", "labels", "description", "constraints", "aliases", "reference"): nn[f] = v
        elif f == "properties": nn[f] = {pk: prop(nk, pk, pv) for pk, pv in v.items()}
        elif f == "indexes":
            if v: note(f"DROPPED {nk}.indexes {sorted(v)} — move index statements to SETUP.md")
        elif f == "extensions":
            if v: note(f"DROPPED {nk}.extensions {sorted(v)}")
        elif f == "name": note(f"DROPPED {nk}.name (packages leave node names unset)")
        else: fail(f"unknown node field {nk}.{f}")
    if k in display:
        nn["extensions"] = {"display": {"x": display[k]["x"], "y": display[k]["y"]}}
    else:
        note(f"MISSING display for node {nk} — add extensions.display by hand")
    o["nodes"][nk] = nn
for k, r in rels.items():
    rk = rel_keys[k]
    rr = {}
    for f, v in r.items():
        if f in ("type", "description", "aliases", "reference"): rr[f] = v
        elif f in ("from", "to"):
            if "node" not in v: fail(f"relationship {rk}.{f} has no node reference")
            rr[f] = {"node": node_keys[v["node"]]}
            if set(v) - {"node", "label", "property"}: fail(f"unknown target field in {rk}.{f}")
        elif f == "properties": rr[f] = {pk: prop(rk, pk, pv) for pk, pv in v.items()}
        elif f in ("constraints", "indexes"):
            if v: note(f"DROPPED {rk}.{f} {sorted(v)}")
        elif f == "extensions":
            if v: note(f"DROPPED {rk}.extensions {sorted(v)} — restate cardinality as target counts and prose")
        elif f == "name": note(f"DROPPED {rk}.name")
        else: fail(f"unknown relationship field {rk}.{f}")
    o["relationships"][rk] = rr

# --- tables ------------------------------------------------------------------------
def header(table):
    hits = [f for f in (p / "sample-data").rglob("*.csv")
            if f.relative_to(p / "sample-data").as_posix() == table or f.name == table]
    if len(hits) != 1: return None
    with hits[0].open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh), None)
tables = {}
for t, tbl in m.get("tables", {}).items():
    names = list((tbl.get("fields") or {}).keys())
    h = header(t)
    if h is not None and sorted(h) == sorted(names):
        cols = h
    elif h is not None:
        cols = h
        note(f"TABLE {t}: legacy fields {sorted(set(names) ^ set(h))} differ from the CSV header; columns taken from the header")
    else:
        cols = names
        note(f"TABLE {t}: CSV not found below sample-data/; columns kept in legacy order")
    for extra in set(tbl) - {"source", "fields", "primaryKeys", "foreignKeys", "extensions"}:
        fail(f"unknown table field {t}.{extra}")
    tables[t] = {"source": tbl.get("source", "local"), "columns": [{"name": c, "type": "string"} for c in cols]}

# --- mappings ----------------------------------------------------------------------
def pmap(d): return {k: {"column": v["field"]} for k, v in (d or {}).items()}
maps = []
for mp in m.get("mappings", []):
    ty = mp.get("type", "").lower()
    mode = mp.get("mode", "MERGE")
    if "mode" not in mp: note(f"MAPPING {mp.get('node') or mp.get('relationship')}: no mode in legacy file; set MERGE")
    if ty in ("nodemapping", "node"):
        nk = node_keys[mp["node"]]
        key = mp.get("key", mp.get("keys"))
        if not key:
            key = [pk for pk, pv in o["nodes"][nk].get("properties", {}).items() if pv.get("key")]
            note(f"MAPPING {nk}: no key array in legacy file; derived {key} from key: true")
        maps.append({"type": "NODE", "node": nk, "table": mp["table"], "mode": mode,
                     "key": key, "properties": pmap(mp.get("properties"))})
    elif ty in ("relationshipmapping", "relationship"):
        rk = rel_keys[mp["relationship"]]
        x = {"type": "RELATIONSHIP", "relationship": rk, "table": mp["table"], "mode": mode,
             "key": mp.get("key", []),
             "from_node": {"label": label_of(m["nodes"][mp["from"]["node"]]), "properties": pmap(mp["from"].get("properties"))},
             "to_node": {"label": label_of(m["nodes"][mp["to"]["node"]]), "properties": pmap(mp["to"].get("properties"))}}
        if mp.get("properties"): x["properties"] = pmap(mp["properties"])
        maps.append(x)
    else:
        fail(f"unsupported mapping type {mp.get('type')!r}")
o["extensions"] = {"data_source_tables": tables, "data_source_mappings": {"mapping0": maps}}

# --- faithful but not accepted by the destination: warn, never fix (both are meaning changes) ---------------
flags = {}
for kind, entities in (("label", o["nodes"]), ("type", o["relationships"])):
    for k, e in entities.items():
        token = e.get("type") if kind == "type" else label_of(e)
        for pk, pv in (e.get("properties") or {}).items():
            for flag in ("key", "must_exist", "unique"):
                if pv.get(flag): flags.setdefault((kind, token, pk, flag), []).append(k)
for (kind, token, pk, flag), keys in flags.items():
    if len(keys) > 1:
        note(f"WARN {flag} on {pk} repeats across {len(keys)} entries of {kind} {token} ({', '.join(keys)}): "
             "duplicate constraint names; keep it on one entry and move it to prose on the others")
def rows(table):
    hits = [f for f in (p / "sample-data").rglob("*.csv")
            if f.relative_to(p / "sample-data").as_posix() == table or f.name == table]
    if len(hits) != 1: return []
    with hits[0].open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
for x in maps:
    if x["type"] != "RELATIONSHIP" or x["key"]: continue
    cols = [v["column"] for v in x["from_node"]["properties"].values()] + [v["column"] for v in x["to_node"]["properties"].values()]
    seen = {}
    for r in rows(x["table"]):
        seen[tuple(r.get(c, "") for c in cols)] = seen.get(tuple(r.get(c, "") for c in cols), 0) + 1
    repeated = sum(1 for n in seen.values() if n > 1)
    if repeated:
        note(f"WARN {x['relationship']}: {repeated} endpoint pairs repeat in {x['table']} under an empty key; "
             "MERGE will collapse them — set the mapping key to the property that tells them apart")

out = p / "ONTOLOGY.json"
out.write_text(json.dumps(o, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("\n".join(log))
print(f"WROTE {out}")
