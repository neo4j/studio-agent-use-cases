#!/usr/bin/env python3
"""Find bundled sample-data values in the files the consuming agent reads (VALIDATION.md 5a).

Usage: python3 leak_scan.py <package-dir> [--min-length N]

Collects the values of every CSV column that ONTOLOGY.json maps to a node key, or to a
STRING property with many distinct values (identifier-like: names, addresses, phone
numbers) — low-cardinality columns are domain vocabulary, not seeded detail — and
searches SKILL.md, QUERIES.md, SETUP.md and every supporting
.md/.cypher file for them as whole tokens. TESTS.md and human_description.md are not
scanned (5a and 5d treat them separately), and ONTOLOGY.json's `e.g.` samples are
legitimate, as is a query's `@sample` tag (lines from `@sample` to the next tag or the
end of the comment are skipped). Short values (default under 4 characters) and pure small numbers are
skipped to keep noise down. Every hit is a candidate: read it and decide.
Standard library only.
"""
import csv, json, re, sys, pathlib

args = sys.argv[1:]
min_len = 4
if "--min-length" in args:
    i = args.index("--min-length"); min_len = int(args[i + 1]); del args[i:i + 2]
p = pathlib.Path(args[0])
m = json.loads((p / "ONTOLOGY.json").read_text(encoding="utf-8"))
ext = m.get("extensions") or {}
mappings = [x for lst in (ext.get("data_source_mappings") or {}).values() for x in lst]

def find_csv(name):
    hits = [f for f in (p / "sample-data").rglob("*.csv")
            if f.relative_to(p / "sample-data").as_posix() == name or f.name == name]
    return hits[0] if len(hits) == 1 else None

watched = {}  # value -> "Owner.property"
for mp in mappings:
    if mp["type"] != "NODE": continue
    node = m["nodes"].get(mp["node"], {})
    f = find_csv(mp["table"])
    if f is None: continue
    rows = list(csv.DictReader(f.open(newline="", encoding="utf-8")))
    for prop, pm in (mp.get("properties") or {}).items():
        d = (node.get("properties") or {}).get(prop, {})
        distinct = {(r.get(pm["column"]) or "").strip() for r in rows}
        if not (d.get("key") or (d.get("type") == "STRING" and "one_of" not in d and len(distinct) >= 20)): continue
        for r in rows:
            v = (r.get(pm["column"]) or "").strip()
            if len(v) >= min_len and not re.fullmatch(r"\d{1,4}", v):
                watched.setdefault(v, f"{mp['node']}.{prop}")

targets = [x for x in sorted(p.iterdir())
           if x.is_file() and x.suffix in (".md", ".cypher") and x.name not in ("TESTS.md", "human_description.md")]
hits = 0
def sample_lines(lines):
    skip, inside = set(), False
    for n, line in enumerate(lines, 1):
        if re.match(r"\s*\*?\s*@sample\b", line): inside = True
        elif inside and (re.match(r"\s*\*?\s*@\w+", line) or "*/" in line): inside = False
        if inside: skip.add(n)
    return skip

for t in targets:
    text = t.read_text(encoding="utf-8")
    lines = text.splitlines()
    skip = sample_lines(lines)
    for v, owner in watched.items():
        if v not in text: continue  # fast substring pre-filter
        rx = re.compile(rf"(?<![\w-]){re.escape(v)}(?![\w-])")
        for n, line in enumerate(lines, 1):
            if n not in skip and rx.search(line):
                hits += 1
                print(f"CANDIDATE {t.name}:{n}: {owner} value {v!r}: {line.strip()[:120]}")
print(f"scanned {len(targets)} files for {len(watched)} values; {hits} candidates")
