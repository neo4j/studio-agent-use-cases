#!/usr/bin/env python3
"""Prove a migration preserved meaning: compare a legacy GRAPH_MODEL.json (or a pre-release ONTOLOGY.json
still using extensions.tables / extensions.mappings) with ONTOLOGY.json.

Usage: python3 compare_ontology.py <old GRAPH_MODEL.json or ONTOLOGY.json> <new ONTOLOGY.json>

Compares what a user's database, queries and imports depend on, keyed by label and
relationship type rather than by entity key (keys are allowed to change):
  labels; relationship type + from label + to label; property names and types;
  node keys and existence/uniqueness; descriptions; annotations (aliases, reference,
  one_of, pattern, relationship target counts); table columns; mapping bindings.
Prints CHANGED / ADDED / REMOVED lines, then "EQUIVALENT" or "DIFFERENT".
Exit 0 when equivalent, 1 otherwise. Every difference must be an approved change
in the migration plan. Standard library only.
"""
import json, sys

def load(path):
    m = json.load(open(path, encoding="utf-8"))
    nodes, rels = {}, {}
    label = {}
    for k, n in m.get("nodes", {}).items():
        lab = n.get("label") or (n.get("labels") or {}).get("identifier")
        label[k] = lab
        props = {}
        for pk, pv in (n.get("properties") or {}).items():
            must = pv.get("must_exist", pv.get("mustExist"))
            if pv.get("nullable") is False: must = True
            props[pk] = {"type": pv.get("type"), "key": bool(pv.get("key")),
                         "must_exist": bool(must) or bool(pv.get("key")),
                         "unique": bool(pv.get("unique")) or bool(pv.get("key")),
                         "description": pv.get("description", ""),
                         "one_of": pv.get("one_of"), "pattern": pv.get("pattern"), "reference": pv.get("reference")}
        cons = sorted((c.get("type"), tuple(c.get("properties", []))) for c in (n.get("constraints") or {}).values())
        nodes[lab] = {"props": props, "constraints": cons, "description": n.get("description", ""),
                      "aliases": sorted(n.get("aliases") or []), "reference": n.get("reference")}
    for k, r in m.get("relationships", {}).items():
        sig = (r["type"], label[r["from"]["node"]], label[r["to"]["node"]])
        props = {pk: {"type": pv.get("type"),
                      "must_exist": bool(pv.get("must_exist", pv.get("mustExist"))) or pv.get("nullable") is False,
                      "description": pv.get("description", ""), "one_of": pv.get("one_of"),
                      "pattern": pv.get("pattern"), "reference": pv.get("reference")}
                 for pk, pv in (r.get("properties") or {}).items()}
        counts = lambda t: {c: t.get(c) for c in ("count", "min_count", "max_count") if t.get(c) is not None}
        rels[sig] = {"props": props, "description": r.get("description", ""),
                     "aliases": sorted(r.get("aliases") or []), "reference": r.get("reference"),
                     "from_counts": counts(r["from"]), "to_counts": counts(r["to"])}
    ext = m.get("extensions") or {}
    tables = {}
    # Current names, then the pre-release ONTOLOGY.json names, then legacy GRAPH_MODEL.json root keys.
    for t, tbl in (ext.get("data_source_tables") or ext.get("tables") or m.get("tables") or {}).items():
        cols = [c["name"] for c in tbl["columns"]] if "columns" in tbl else list((tbl.get("fields") or {}).keys())
        tables[t] = sorted(cols)
    maps = ext.get("data_source_mappings") or ext.get("mappings")
    maps = [x for lst in maps.values() for x in lst] if isinstance(maps, dict) else (m.get("mappings") or [])
    bind = set()
    rel_by_key = m.get("relationships", {})
    for mp in maps:
        ty = mp["type"].lower()
        col = lambda d: tuple(sorted((k, v.get("column", v.get("field"))) for k, v in (d or {}).items()))
        if ty in ("node", "nodemapping"):
            bind.add(("NODE", label[mp["node"]], mp["table"], col(mp.get("properties")), tuple(sorted(mp.get("key") or mp.get("keys") or []))))
        else:
            r = rel_by_key[mp["relationship"]]
            sig = (r["type"], label[r["from"]["node"]], label[r["to"]["node"]])
            f = mp.get("from_node") or mp.get("from"); t = mp.get("to_node") or mp.get("to")
            bind.add(("REL", sig, mp["table"], col(f.get("properties")), col(t.get("properties")), col(mp.get("properties"))))
    return nodes, rels, tables, bind

a, b = load(sys.argv[1]), load(sys.argv[2])
diffs = []
def cmp(kind, x, y):
    for k in sorted(set(x) | set(y), key=str):
        if k not in y: diffs.append(f"REMOVED {kind} {k}")
        elif k not in x: diffs.append(f"ADDED {kind} {k}")
        elif x[k] != y[k]:
            if isinstance(x[k], dict) and isinstance(y[k], dict):
                cmp(f"{kind} {k}", x[k], y[k])
            else:
                diffs.append(f"CHANGED {kind} {k}: {x[k]!r} -> {y[k]!r}")
cmp("node", a[0], b[0])
cmp("relationship", a[1], b[1])
cmp("table", a[2], b[2])
for x in sorted(a[3] - b[3], key=str): diffs.append(f"REMOVED mapping {x}")
for x in sorted(b[3] - a[3], key=str): diffs.append(f"ADDED mapping {x}")
print("\n".join(diffs))
print("EQUIVALENT" if not diffs else f"DIFFERENT ({len(diffs)} differences)")
sys.exit(0 if not diffs else 1)
