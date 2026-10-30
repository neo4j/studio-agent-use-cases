#!/usr/bin/env python3
"""Rebuild one package's entry in studio-agent-use-cases catalog.json from its folder.

Usage: python3 catalog_entry.py <repo-root> <skillId> [--write]

The entry lists every file in the package folder relative to it: files.graph is
ONTOLOGY.json, files.markdown is SKILL.md, and files.skill is every other file.
For an existing entry, files that remain keep their current order, deleted files
are removed and new files are appended (sorted) — so the diff shows only what
changed. A new entry lists sample-data CSVs first, then the remaining files, each
group sorted case-insensitively. Other entries, and the position of this one, are
left untouched. Without --write, prints the diff only (no output: nothing to change).
Standard library only.
"""
import json, sys, pathlib, difflib

args = sys.argv[1:]
write = "--write" in args
args = [a for a in args if a != "--write"]
root, skill_id = pathlib.Path(args[0]).resolve(), args[1]
pkg = root / skill_id
if not pkg.is_dir(): sys.exit(f"no package folder {pkg}")
cat_path = root / "catalog.json"
before = cat_path.read_text(encoding="utf-8")
cat = json.loads(before)

files = sorted(
    (x.relative_to(pkg).as_posix() for x in pkg.rglob("*")
     if x.is_file() and not any(part.startswith(".") for part in x.relative_to(pkg).parts)),
    key=lambda f: (not f.startswith("sample-data/"), f.lower()))
if "ONTOLOGY.json" not in files: sys.exit("package has no ONTOLOGY.json")
if "SKILL.md" not in files: sys.exit("package has no SKILL.md")
if "GRAPH_MODEL.json" in files: sys.exit("package still has GRAPH_MODEL.json; remove it first")
entry = {"skillId": skill_id, "files": {
    "graph": "ONTOLOGY.json",
    "skill": [f for f in files if f not in ("ONTOLOGY.json", "SKILL.md")],
    "markdown": "SKILL.md"}}

skills = cat.setdefault("skills", [])
idx = next((i for i, s in enumerate(skills) if s.get("skillId") == skill_id), None)
if idx is None: skills.append(entry)
else:
    old = skills[idx].get("files", {})
    wanted = entry["files"]["skill"]
    kept = [f for f in old.get("skill", []) if f in wanted]
    entry["files"]["skill"] = kept + [f for f in wanted if f not in kept]
    entry["files"] = {k: entry["files"][k] for k in (list(old) + [k for k in entry["files"] if k not in old]) if k in entry["files"]}
    skills[idx] = entry
after = json.dumps(cat, indent=2, ensure_ascii=False) + "\n"
sys.stdout.writelines(difflib.unified_diff(before.splitlines(True), after.splitlines(True), "catalog.json", "catalog.json"))
if write:
    cat_path.write_text(after, encoding="utf-8")
    print(f"WROTE {cat_path}")
