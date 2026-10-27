#!/usr/bin/env python3
"""Read-only inventory of an existing package, for MIGRATION.md phase 2.

Usage: python3 inventory.py <package-dir> [--repo-root DIR]

Reports, without changing anything:
  - the ontology file and its format generation
  - required files present or missing
  - every file outside the package format, with a suggested clean-up category
  - legacy markers in each Markdown file
  - QUERIES.md structure (annotation blocks, adapting section) and TESTS.md parity
  - the catalog.json entry against the folder, when the repo root is known
Standard library only.
"""
import json, re, sys, pathlib

args = sys.argv[1:]
root = None
if "--repo-root" in args:
    i = args.index("--repo-root"); root = pathlib.Path(args[i + 1]).resolve(); del args[i:i + 2]
p = pathlib.Path(args[0]).resolve()
if root is None and (p.parent / "catalog.json").is_file():
    root = p.parent
print(f"PACKAGE {p.name}")

# --- ontology file and generation --------------------------------------------------
def generation(path):
    m = json.loads(path.read_text(encoding="utf-8"))
    if "schema" in m and isinstance(m.get("extensions"), dict) and "data_source_tables" in m["extensions"]:
        return f"current (schema {m['schema']})"
    text = path.read_text(encoding="utf-8")
    if re.search(r'"n:\d+"', text) or '"nullable"' in text or re.search(r'"type":\s*"(node|relationship)"', text):
        return "legacy, older dialect (declares version 4.0.0 but predates the alpha.25 shape: positional keys / nullable / lowercase mapping types)"
    if "NodeMapping" in text or "mustExist" in text:
        return "legacy, graph-spec 4.0.0-alpha.25"
    return "unknown"
for name in ("ONTOLOGY.json", "GRAPH_MODEL.json"):
    f = p / name
    if f.is_file():
        print(f"ONTOLOGY-FILE {name}: {generation(f)}")

# --- files -------------------------------------------------------------------------
FORMAT = {"SKILL.md", "ONTOLOGY.json", "QUERIES.md", "human_description.md", "TESTS.md", "SETUP.md"}
REQUIRED = {"SKILL.md", "ONTOLOGY.json", "QUERIES.md", "human_description.md"}
has_csv = any((p / "sample-data").rglob("*.csv")) if (p / "sample-data").is_dir() else False
if has_csv: REQUIRED.add("TESTS.md")
for f in sorted(REQUIRED):
    if not (p / f).is_file():
        print(f"MISSING {f}" + (" (create)" if f != "ONTOLOGY.json" else " (convert GRAPH_MODEL.json)"))

CATEGORY = [
    (r"^GRAPH_MODEL\.json$", "legacy ontology: convert to ONTOLOGY.json, then delete"),
    (r"(graph|data)[-_]?model|schema|ontology", "ontology prose: fold unique meaning into ONTOLOGY.json descriptions, then delete"),
    (r"^index", "index statements: move into SETUP.md, then delete"),
    (r"\.cypher$|quer(y|ies)[-_]?(templates?|patterns?)|^queries\.", "duplicate queries: reconcile with QUERIES.md, then delete"),
    (r"^introduction|^overview|^readme", "intro or overview: fold into SKILL.md intro guidance / human_description.md, then delete"),
    (r"sample[-_]?data\.md|^data", "sample-data description: move into TESTS.md, then delete"),
    (r"caveat|limitation|implementation|guidance", "agent guidance: fold into SKILL.md, or keep as an indexed supporting file if too large"),
    (r"workflow|procedure|playbook", "workflow: keep as an indexed supporting file, or fold into SKILL.md if small"),
]
for f in sorted(x for x in p.iterdir() if x.is_file() and not x.name.startswith(".")):
    if f.name in FORMAT: continue
    cat = next((c for rx, c in CATEGORY if re.search(rx, f.name, re.I)), "unclassified: read it and decide")
    if f.suffix == ".md" and cat.startswith("duplicate queries") and "```cypher" not in f.read_text(encoding="utf-8"):
        cat = "query prose, no Cypher: fold into the matching queries' @description/@usage/@pattern, then delete"
    print(f"EXTRA {f.name} ({f.stat().st_size} bytes): {cat}")
for d in sorted(x for x in p.iterdir() if x.is_dir() and x.name not in ("sample-data",) and not x.name.startswith(".")):
    print(f"EXTRA-DIR {d.name}/: read it and decide")
if (p / "sample-data").is_dir():
    for f in sorted((p / "sample-data").rglob("*")):
        if f.is_file() and f.suffix.lower() != ".csv":
            print(f"EXTRA sample-data/{f.relative_to(p / 'sample-data')}: not a CSV; delete unless it is source data")

# --- legacy markers in Markdown ----------------------------------------------------
MARKERS = [
    (r"GRAPH_MODEL\.json", "names GRAPH_MODEL.json"),
    (r"(?i)\bgraph (data )?model\b|\bdata model\b", "says graph model / data model"),
    (r"neo4j-graph-spec-version", "retired neo4j-graph-spec-version key"),
    (r"neo4j-icon-category", "retired neo4j-icon-category key"),
    (r"TODO\(review\): unproven query", "unproven-query TODO (remove)"),
    (r"(?m)^## Model\s*$", "'## Model' heading (now 'Reference ontology')"),
    (r"INTRODUCTION\.md", "names INTRODUCTION.md"),
    (r"Model assumptions", "'Model assumptions' in Response Shape (now 'Reference ontology assumptions')"),
    (r"(?i)\b(?:the|this|our) model\b", "says 'the model' — check each: rename where it means the reference ontology"),
]
for f in sorted(p.glob("*.md")):
    t = f.read_text(encoding="utf-8")
    for rx, label in MARKERS:
        n = len(re.findall(rx, t))
        if n: print(f"LEGACY {f.name}: {label} x{n}")

s = (p / "SKILL.md").read_text(encoding="utf-8") if (p / "SKILL.md").is_file() else ""
if s:
    secs = re.findall(r"(?m)^## (.+)$", s)
    print(f"SKILL-SECTIONS {secs}")
    if "Reference ontology" not in secs and "Model" not in secs:
        print("SKILL no ontology section")
    if not re.search(r"(?m)^\|\s*Role\s*\|", s):
        print("SKILL no role map")
    if "Supporting files" in secs:
        print("SKILL has a Supporting files table — re-check every entry after clean-up")

# --- QUERIES.md and TESTS.md -------------------------------------------------------
q = (p / "QUERIES.md").read_text(encoding="utf-8") if (p / "QUERIES.md").is_file() else ""
if q:
    blocks = re.findall(r"```cypher\n(.*?)```", q, re.S)
    schema_stmt = re.compile(r"\s*(CREATE|DROP|SHOW)\s+(CONSTRAINT|INDEX|CONSTRAINTS|INDEXES)", re.I)
    strip = lambda b: re.sub(r"(?m)^\s*//.*$\n?", "", re.sub(r"(?s)^\s*/\*.*?\*/", "", b))
    queries = [b for b in blocks if not schema_stmt.match(strip(b))]
    annotated = sum(1 for b in queries if re.match(r"\s*/\*.*?@name", b, re.S))
    print(f"QUERIES {len(queries)} queries ({len(blocks) - len(queries)} constraint/index statements), {annotated} with an @-annotation block")
    if "## Adapting these queries" not in q:
        print("QUERIES no 'Adapting these queries' section")
    for h in re.findall(r"(?m)^## (.+)$", q):
        sec = q.split(f"## {h}", 1)[1].split("\n## ", 1)[0]
        n = sum(1 for b in re.findall(r"```cypher\n(.*?)```", sec, re.S) if not schema_stmt.match(strip(b)))
        if n > 1: print(f"QUERIES heading holds {n} queries (split to one per heading): {h}")
setup_text = (p / "SETUP.md").read_text(encoding="utf-8") if (p / "SETUP.md").is_file() else ""
for name, text in (("QUERIES", q), ("SETUP", setup_text)):
    code = "\n".join(re.findall(r"```cypher\n(.*?)```", text, re.S))
    writes = sorted(set(re.findall(r"(?:SET|MERGE|CREATE)\s+[^\n]*?:(\w+)", code)) - {"CONSTRAINT", "INDEX"})
    props = sorted(set(re.findall(r"\bSET\s+\w+\.(\w+)", code)))
    if writes: print(f"{name} writes labels/types {writes} — check each is declared or defined in SKILL.md")
    if props: print(f"{name} writes properties {props} — check each is declared and mapped, or defined in SKILL.md")
    qh = set(re.findall(r"(?m)^## (.+)$", q))
    t = (p / "TESTS.md").read_text(encoding="utf-8") if (p / "TESTS.md").is_file() else ""
    if t:
        th = set(re.findall(r"(?m)^## (.+)$", t))
        skip = {"Prerequisites", "Adapting these queries", "How to run", "Sample-data profile"}
        for h in sorted((qh - th) - skip): print(f"TESTS no section for query heading: {h}")
        for h in sorted((th - qh) - skip): print(f"TESTS section with no query: {h}")

# --- SETUP.md and descriptions -----------------------------------------------------
if (p / "SETUP.md").is_file():
    st = (p / "SETUP.md").read_text(encoding="utf-8")
    n = len(re.findall(r"```cypher", st)); a = len(re.findall(r"```cypher\n\s*/\*.*?@name", st, re.S))
    print(f"SETUP {n} statements, {a} with an @-annotation block")
    if re.search(r"(?i)CREATE\s+CONSTRAINT[^`]*IS\s+(NODE\s+)?KEY", st): print("SETUP contains node-key constraints (remove: Import creates them)")
for name in ("ONTOLOGY.json", "GRAPH_MODEL.json"):
    f = p / name
    if f.is_file():
        hits = re.findall(r"(?i)\b(?:the|this) model\b|\bgraph model\b|\bdata model\b", f.read_text(encoding="utf-8"))
        if hits: print(f"LEGACY {name}: 'model' wording in descriptions x{len(hits)}")

# --- catalog.json ------------------------------------------------------------------
if root and (root / "catalog.json").is_file():
    cat = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    entry = next((s for s in cat.get("skills", []) if s.get("skillId") == p.name), None)
    if entry is None:
        print("CATALOG no entry for this package")
    else:
        files = entry.get("files", {})
        listed = set(files.get("skill", [])) | {files.get("graph"), files.get("markdown")}
        actual = {x.relative_to(p).as_posix() for x in p.rglob("*") if x.is_file() and not any(part.startswith(".") for part in x.relative_to(p).parts)}
        for f in sorted(listed - actual - {None}): print(f"CATALOG lists missing file: {f}")
        for f in sorted(actual - listed): print(f"CATALOG omits file: {f}")
        print(f"CATALOG files.graph = {files.get('graph')!r}")
print("done")
