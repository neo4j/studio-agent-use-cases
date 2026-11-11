#!/usr/bin/env python3
"""Generate a LOAD CSV script from ONTOLOGY.json that mirrors what Aura's Import does with it.

Usage: python3 ontology_to_cypher.py <package-dir> [out.cypher]
Prints the statement count, any fidelity notes, and fails loudly (exit 2) on any mapping shape,
binding or property type it does not recognise. Hardened from the prototype in the v2 brief.

What it mirrors (upx apps/import/src/cypher-runner and the @neo4j/ontology-graph-spec decoder; see
RELATE.md "Import fidelity"):
- Constraints come from the ontology, never from the mapping key: each `key`, `unique` and `must_exist`
  property flag becomes its own single-property constraint, and only a `constraints` entry listing
  several properties makes a composite one. Names follow Import: <props>_<Label>_<suffix>.
- Nodes: MERGE on the mapping key, then SET every other mapped property. Rows whose converted key is
  null are dropped. Only the node's first label is written.
- Relationships: MATCH both endpoints on their key (never created), MERGE the relationship on its
  mapping key (an empty key collapses parallel rows into one), then SET every mapped property.
- Values: an empty cell is null (Import converts '' to null before sending rows); STRING is not
  trimmed; INTEGER/FLOAT/ZONED DATETIME trim first; BOOLEAN is toLower(trim(v)) IN ['1','true','yes'];
  a value that does not convert becomes null, as in Import (a datetime must be ISO-shaped to reach
  datetime(), which would otherwise fail the whole statement).

Not mirrored, reported instead: Import normalises datetimes through JavaScript `Date` (so a value with
no zone is read in the browser's timezone), and deduplicates rows within each ~1 MB chunk.
Standard library only."""
import csv, json, re, sys, pathlib

TYPES = ("STRING", "INTEGER", "FLOAT", "BOOLEAN", "ZONED DATETIME")
NODE_MAPPING_KEYS = {"type", "node", "table", "mode", "key", "properties"}
REL_MAPPING_KEYS = {"type", "relationship", "table", "mode", "key", "properties", "from_node", "to_node"}
ENDPOINT_KEYS = {"label", "properties"}
UTC_ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,3})?Z$")
# Import turns a value JavaScript Date cannot parse into null; datetime() would fail the whole statement
# instead, so only ISO-shaped values reach it. import_check.py reports every non-empty cell that does not
# convert, so the guard hides nothing.
ISO_DATETIME = r"^\\d{4}-\\d{2}-\\d{2}(T\\d{2}:\\d{2}(:\\d{2}(\\.\\d{1,9})?)?)?(Z|[+-]\\d{2}:\\d{2})?$"
SUFFIX = {"key": "key", "unique": "uniq", "must_exist": "propertyExistence",
          "KEY": "key", "UNIQUE": "uniq", "EXISTS": "propertyExistence", "PROPERTY_TYPE": "propertyType"}

# Workarounds RELATE.md records for this Relate version. Each maps an Import constraint kind to
# the statement form Relate accepts, or to None to skip it with a note.
WORKAROUNDS = {}
# Cypherlite 0.13.0, the release before the rename to Relate, keeps a UTF-8 BOM in the first header key
# (Import strips it), so a BOM-prefixed CSV's first column is addressed by its raw key. RELATE.md, import.bom.
BOM_STAYS_IN_FIRST_KEY = True


class ShapeError(Exception):
    pass


def q(name):
    return "`" + name.replace("`", "``") + "`"


def conv(col, typ, alias=None):
    """The Cypher expression Import applies to a CSV cell, with '' already read as null."""
    v = f"row.{q((alias or {}).get(col, col))}"
    if typ not in TYPES:
        raise ShapeError(f"property type {typ!r} is not supported by the generator")
    inner = {"STRING": v, "INTEGER": f"toInteger(trim({v}))", "FLOAT": f"toFloat(trim({v}))",
             "BOOLEAN": f"toLower(trim({v})) IN ['1', 'true', 'yes']",
             "ZONED DATETIME": f"CASE WHEN trim({v}) =~ '{ISO_DATETIME}' THEN datetime(trim({v})) END"}[typ]
    return f"CASE WHEN {v} IS NULL OR {v} = '' THEN null ELSE {inner} END"


def label_of(node):
    return node.get("label") or (node.get("labels") or {}).get("identifier")


def resolve_csv(pkg, table):
    base = pkg / "sample-data"
    hits = [f for f in base.rglob("*.csv") if f.relative_to(base).as_posix() == table] \
        or [f for f in base.rglob("*.csv") if f.name == table]
    if len(hits) != 1:
        raise ShapeError(f"table {table!r} does not resolve to exactly one CSV below sample-data/")
    return hits[0]


def header_alias(pkg, table):
    """{column: key LOAD CSV sees} for a CSV whose header starts with a BOM, else {}."""
    f = resolve_csv(pkg, table)
    raw = f.read_bytes()[:4096]
    if not (BOM_STAYS_IN_FIRST_KEY and raw.startswith(b"\xef\xbb\xbf")):
        return {}
    first = next(csv.reader([raw[3:].decode("utf-8", "replace").splitlines()[0]]))[0]
    return {first: "\ufeff" + first}


def load(pkg):
    pkg = pathlib.Path(pkg)
    o = json.loads((pkg / "ONTOLOGY.json").read_text(encoding="utf-8"))
    ext = o.get("extensions") or {}
    lists = ext.get("data_source_mappings") or {}
    if set(lists) != {"mapping0"}:
        raise ShapeError("extensions.data_source_mappings must hold exactly one list, keyed mapping0")
    return pkg, o, lists["mapping0"], ext.get("data_source_tables") or {}


def check_shapes(pkg, o, maps, tables):
    """Fail loudly on anything outside the two mapping shapes and five types the generator handles."""
    notes, seen = [], {}
    nodes, rels = o.get("nodes", {}), o.get("relationships", {})
    for i, m in enumerate(maps):
        where = f"mapping0[{i}]"
        kind = m.get("type")
        allowed = {"NODE": NODE_MAPPING_KEYS, "RELATIONSHIP": REL_MAPPING_KEYS}.get(kind)
        if allowed is None:
            raise ShapeError(f"{where}: mapping type {kind!r} is not NODE or RELATIONSHIP")
        extra = set(m) - allowed
        if extra:
            raise ShapeError(f"{where}: unrecognised mapping keys {sorted(extra)}")
        if m.get("mode", "MERGE") != "MERGE":
            notes.append(f"NOTE {where}: mode {m['mode']!r} is ignored by Import, which always MERGEs")
        entity = m.get("node") if kind == "NODE" else m.get("relationship")
        if entity in seen:
            raise ShapeError(f"{where}: {entity!r} is mapped twice; Import loads only the last mapping")
        seen[entity] = m
        decl = (nodes if kind == "NODE" else rels).get(entity)
        if decl is None:
            raise ShapeError(f"{where}: {kind.lower()} {entity!r} is not declared in the ontology")
        props = decl.get("properties") or {}
        for p, b in (m.get("properties") or {}).items():
            if not isinstance(b, dict) or set(b) != {"column"}:
                raise ShapeError(f"{where}: binding for {entity}.{p} is {b!r}; only {{'column': ...}} is supported")
            if p not in props:
                raise ShapeError(f"{where}: {entity}.{p} is mapped but not declared")
            if props[p].get("type") not in TYPES:
                raise ShapeError(f"{where}: {entity}.{p} has type {props[p].get('type')!r}; supported: {', '.join(TYPES)}")
        unmapped = set(props) - set(m.get("properties") or {})
        if unmapped:
            raise ShapeError(f"{where}: {entity} declares unmapped properties {sorted(unmapped)}; Import refuses to run")
        for k in m.get("key") or []:
            if k not in (m.get("properties") or {}):
                raise ShapeError(f"{where}: key {k!r} of {entity} is not among its mapped properties")
        if kind == "NODE" and not m.get("key"):
            raise ShapeError(f"{where}: node {entity} has no mapping key; Import refuses to run")
        if kind == "RELATIONSHIP":
            for end, side in (("from", m.get("from_node")), ("to", m.get("to_node"))):
                if not isinstance(side, dict) or set(side) - ENDPOINT_KEYS:
                    raise ShapeError(f"{where}: {end}_node has an unrecognised shape {side!r}")
                want = label_of(nodes.get(decl[end]["node"], {}))
                if side.get("label") != want:
                    raise ShapeError(f"{where}: {end}_node.label {side.get('label')!r} != {want!r}")
                for p, b in side["properties"].items():
                    if set(b) != {"column"}:
                        raise ShapeError(f"{where}: {end}_node binding {b!r} is not a plain column")
        tbl = m.get("table")
        if tbl not in tables:
            raise ShapeError(f"{where}: table {tbl!r} is not declared in data_source_tables")
        f = resolve_csv(pkg, tbl)
        with f.open(newline="", encoding="utf-8-sig") as fh:
            header = [h.strip() for h in next(csv.reader(fh))]
        cols = [b["column"] for b in (m.get("properties") or {}).values()]
        if kind == "RELATIONSHIP":
            cols += [b["column"] for s in (m["from_node"], m["to_node"]) for b in s["properties"].values()]
        missing = sorted(set(cols) - set(header))
        if missing:
            raise ShapeError(f"{where}: columns {missing} are not in {tbl}'s header")
    for kind, entities in (("node", nodes), ("relationship", rels)):
        for k in entities:
            if k not in seen:
                raise ShapeError(f"{kind} {k!r} has no mapping; Import flags it 'Must be specified'")
    return notes


def constraints(o):
    """Import's constraint statements, in its order: per node entity, then per relationship entity."""
    out = []
    for kind, entities in (("node", o.get("nodes", {})), ("relationship", o.get("relationships", {}))):
        for ent_id, e in entities.items():
            token = label_of(e) if kind == "node" else e["type"]
            specs = [(flag, [p]) for p, d in (e.get("properties") or {}).items()
                     for flag in ("key", "unique", "must_exist") if d.get(flag) is True]
            specs += [(c["type"], list(c["properties"])) for c in (e.get("constraints") or {}).values()]
            for flag, props in specs:
                out.append(constraint_statement(kind, token, flag, props, ent_id))
    return out


def constraint_statement(kind, token, flag, props, ent_id):
    name = "_".join(props + [token, SUFFIX[flag]]).replace(" ", "_")
    pat = f"(n:{q(token)})" if kind == "node" else f"()-[n:{q(token)}]-()"
    tup = "(" + ", ".join(f"n.{q(p)}" for p in props) + ")"
    if flag in ("key", "KEY"):
        req = f"{tup} IS {'NODE' if kind == 'node' else 'RELATIONSHIP'} KEY"
    elif flag in ("must_exist", "EXISTS"):
        if len(props) != 1:
            raise ShapeError(f"{ent_id}: an existence constraint takes one property, got {props}")
        req = f"n.{q(props[0])} IS NOT NULL"
    else:  # UNIQUE, and PROPERTY_TYPE, which Import turns into a uniqueness constraint
        req = f"{tup} IS UNIQUE"
    kind_name = {"key": "key", "KEY": "key", "unique": "unique", "UNIQUE": "unique",
                 "must_exist": "exists", "EXISTS": "exists", "PROPERTY_TYPE": "unique"}[flag]
    stmt = f"CREATE CONSTRAINT {q(name)} IF NOT EXISTS\nFOR {pat}\nREQUIRE {req};"
    note = "Import emits PROPERTY_TYPE as IS UNIQUE" if flag == "PROPERTY_TYPE" else ""
    return {"kind": "constraint", "entity": ent_id, "constraint": f"{kind}-{kind_name}", "name": name,
            "cypher": stmt, "note": note}


def node_statement(pkg, o, m):
    node = o["nodes"][m["node"]]
    props, label = node["properties"], label_of(node)
    path = resolve_csv(pkg, m["table"]).relative_to(pkg / "sample-data").as_posix()
    al = header_alias(pkg, m["table"])
    keyed = {k: conv(m["properties"][k]["column"], props[k]["type"], al) for k in m["key"]}
    sets = [f"n.{q(p)} = {conv(b['column'], props[p]['type'], al)}"
            for p, b in m["properties"].items() if p not in m["key"]]
    cy = (f"LOAD CSV WITH HEADERS FROM 'file:///{path}' AS row\n"
          f"WITH row WHERE " + " AND ".join(f"{e} IS NOT NULL" for e in keyed.values()) + "\n"
          f"MERGE (n:{q(label)} {{" + ", ".join(f"{q(k)}: {e}" for k, e in keyed.items()) + "})"
          + (f"\nSET " + ",\n    ".join(sets) if sets else "") + ";")
    return {"kind": "node", "entity": m["node"], "label": label, "table": m["table"], "cypher": cy}


def rel_statement(pkg, o, m):
    rel = o["relationships"][m["relationship"]]
    rprops = rel.get("properties") or {}
    path = resolve_csv(pkg, m["table"]).relative_to(pkg / "sample-data").as_posix()
    ends, guards, al = [], [], header_alias(pkg, m["table"])
    for var, end, side in (("source", "from", m["from_node"]), ("target", "to", m["to_node"])):
        node = o["nodes"][rel[end]["node"]]
        node_map = next(x for x in o["extensions"]["data_source_mappings"]["mapping0"]
                        if x["type"] == "NODE" and x["node"] == rel[end]["node"])
        # Import keeps only the endpoint properties that belong to the endpoint node's mapping key.
        used = {p: b for p, b in side["properties"].items() if p in node_map["key"]}
        if not used:
            raise ShapeError(f"{m['relationship']}: {end}_node binds none of {rel[end]['node']}'s key {node_map['key']}")
        exprs = {p: conv(b["column"], node["properties"][p]["type"], al) for p, b in used.items()}
        guards += [f"{e} IS NOT NULL" for e in exprs.values()]
        ends.append(f"MATCH ({var}:{q(label_of(node))} {{" + ", ".join(f"{q(p)}: {e}" for p, e in exprs.items()) + "})")
    mp = m.get("properties") or {}
    rkey = ("{" + ", ".join(f"{q(k)}: {conv(mp[k]['column'], rprops[k]['type'], al)}" for k in m["key"]) + "}") if m["key"] else ""
    sets = [f"r.{q(p)} = {conv(b['column'], rprops[p]['type'], al)}" for p, b in mp.items()]
    cy = (f"LOAD CSV WITH HEADERS FROM 'file:///{path}' AS row\n"
          f"WITH row WHERE " + " AND ".join(guards) + "\n" + "\n".join(ends) + "\n"
          f"MERGE (source)-[r:{q(rel['type'])}{(' ' + rkey) if rkey else ''}]->(target)"
          + (f"\nSET " + ",\n    ".join(sets) if sets else "") + ";")
    return {"kind": "relationship", "entity": m["relationship"], "type": rel["type"], "table": m["table"],
            "from": label_of(o["nodes"][rel["from"]["node"]]), "to": label_of(o["nodes"][rel["to"]["node"]]),
            "cypher": cy}


def fidelity_notes(pkg, o, maps):
    """Cases where LOAD CSV cannot reproduce Import's JavaScript-side handling of the data."""
    notes = []
    for m in maps:
        decl = o["nodes"][m["node"]] if m["type"] == "NODE" else o["relationships"][m["relationship"]]
        props = decl.get("properties") or {}
        dt_cols = [(p, b["column"]) for p, b in (m.get("properties") or {}).items()
                   if props[p]["type"] == "ZONED DATETIME"]
        if not dt_cols:
            continue
        flagged = set()
        with resolve_csv(pkg, m["table"]).open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                for p, c in dt_cols:
                    v = (r.get(c) or "").strip()
                    if c not in flagged and v and not UTC_ISO.match(v):
                        flagged.add(c)
                        notes.append(f"NOTE {m['table']}.{c}: {v!r} is not a UTC ISO instant; Import reads it through "
                                     "JavaScript Date (no zone = browser time zone) and LOAD CSV may disagree")
    return notes


def generate(pkg):
    pkg, o, maps, tables = load(pkg)
    notes = check_shapes(pkg, o, maps, tables)
    stmts = constraints(o)
    for c in stmts:
        alt = WORKAROUNDS.get(c["constraint"], c["cypher"])
        if alt is None:
            c["skipped"] = f"workaround: {c['constraint']} constraints are not created on Relate (RELATE.md)"
        elif callable(alt):
            c["cypher"], c["note"] = alt(c)
    stmts += [node_statement(pkg, o, m) for m in maps if m["type"] == "NODE"]
    stmts += [rel_statement(pkg, o, m) for m in maps if m["type"] == "RELATIONSHIP"]
    return stmts, notes + fidelity_notes(pkg, o, maps)


def render(stmts, notes, pkg_name):
    head = [f"// import.cypher for {pkg_name}: generated by ontology_to_cypher.py, mirroring Aura Import.",
            "// Run each statement on its own with --load-csv-dir <package>/sample-data."]
    head += [f"// {n}" for n in notes]
    body = []
    for s in stmts:
        if s.get("skipped"):
            body.append("// SKIPPED (" + s["skipped"] + ")\n// " + s["cypher"].replace("\n", "\n// "))
        else:
            body.append(("// " + s["note"] + "\n" if s.get("note") else "") + s["cypher"])
    return "\n".join(head) + "\n\n" + "\n\n".join(body) + "\n"


if __name__ == "__main__":
    pkg = pathlib.Path(sys.argv[1])
    try:
        stmts, notes = generate(pkg)
    except ShapeError as e:
        print(f"ERROR {e}")
        sys.exit(2)
    if len(sys.argv) > 2:
        pathlib.Path(sys.argv[2]).write_text(render(stmts, notes, pkg.resolve().name), encoding="utf-8")
    kinds = {}
    for s in stmts:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"{len(stmts)} statements: " + ", ".join(f"{v} {k}" for k, v in kinds.items()))
    for n in notes:
        print(n)
