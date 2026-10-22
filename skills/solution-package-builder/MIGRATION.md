# Updating an Existing Package

Use this file when the request is to update, migrate, upgrade or clean up an existing package — "use /create-solution-package to update patient-journey to the latest package spec". The result is one branch and one pull request against `neo4j/studio-agent-use-cases`, carrying a package that passes VALIDATION.md and contains nothing the current format does not define.

An update is not a rebuild. A new package fails by being incomplete; an update fails by being destructive — dropping curated content, renaming what users depend on, or quietly rewriting queries that work. Every rule below exists to prevent one of those.

## Rules

1. **Preserve, don't regenerate.** Descriptions, query logic, thresholds, caveats and design rationale were curated by a person. Keep their wording unless a format rule forces a change, and then make the smallest edit that satisfies the rule. Never redraft a section because you could write it better.
2. **Names are stable.** The package folder (`skillId`), labels, relationship types, relationship directions, property names, property types and node keys do not change. Users' databases, saved queries and agents built from the package depend on them. A change to any of them is a breaking change: it needs explicit approval, and the PR says so in its own section. Entity keys inside `ONTOLOGY.json` (`n:0` → `Identity`) are internal and may change freely.
3. **Sample data is stable.** Do not regenerate or edit CSVs. If the data contradicts a new annotation, ask whether to change the data or the annotation — never quietly do either.
4. **Mechanical changes are made; meaning changes are asked.** Use VALIDATION.md §7's split. Format conversion, terminology, moving sample-data detail into TESTS.md and removing retired keys are mechanical. New `one_of`, `pattern`, counts, aliases or references, edited descriptions, changed Cypher, and anything breaking are meaning changes: propose them in the plan.
5. **Nothing is deleted without a destination.** Every file removed has a row in the content map saying where each part of its content went, or why that part was dropped (a duplicate of what text, or obsolete because of what).
6. **Clean packages.** Everything outside the package format is folded in and deleted. A file survives as a supporting file only when its content is too large or too specialised for SKILL.md or QUERIES.md (SKILL.md's rule for supporting files) — and then it is indexed in SKILL.md's Supporting files table.
7. **Idempotent.** Running an update on a package that is already current produces no changes: report "already current", list anything VALIDATION.md still flags, and open no PR.
8. **One package per branch and PR.** Never batch packages; each one is tested on its own.
9. **No query runs.** Testing against a database is manual and outside this skill (as for new packages). Do not import data or run queries, and do not mark queries as unproven. TESTS.md is what the tester works from.

## Tools

The `scripts/` folder beside this file does the mechanical work. Use them rather than converting by hand — a script is repeatable and a hand conversion is not. All are standard-library Python 3.

| Script | Does |
| ------ | ---- |
| `inventory.py <package-dir>` | Read-only. Ontology format generation, missing files, every file outside the format with a suggested clean-up category, legacy markers in each Markdown file, QUERIES.md/TESTS.md structure, and catalog.json drift. |
| `convert_legacy.py <package-dir>` | Writes `ONTOLOGY.json` from `GRAPH_MODEL.json` (either legacy dialect). Structural only: it renames positional entity keys, converts fields and mappings, and logs every key rename and every dropped field. It never invents annotations and never deletes the legacy file. |
| `compare_ontology.py <old> <new>` | Proves the conversion kept meaning: labels, relationship type + direction, property names, types, keys, existence, descriptions, table columns and mapping bindings, compared by label and type rather than entity key. Exit 0 and `EQUIVALENT`, or a list of differences. |
| `check_annotations.py <package-dir>` | VALIDATION.md §3b against the bundled CSVs. |
| `catalog_entry.py <repo-root> <skillId> [--write]` | Rebuilds the package's `catalog.json` entry from the folder. |

## Phase 1: Locate

1. Resolve `<source>`. A bare name (`patient-journey`) is a folder in `neo4j/studio-agent-use-cases`; a GitHub URL names it directly; a local path is a checkout. Anything else — a zip, a folder outside the repo — ask where the package lives in the repo before going further, because the deliverable is a PR.
2. Work in a clone of `neo4j/studio-agent-use-cases`. Fetch `origin` (fetching changes nothing in the working tree, so it belongs here, before assessment) and record `origin/main`'s commit as the base — the report cites it, and every "base commit" below means it. Choose the branch name now, but create the branch only after approval in Phase 4: `<prefix>/migrate-<skillId>` when the user's own branches in the repo share a prefix (`git branch -r` and recent merged PRs show it, e.g. `ian/`), otherwise `migrate/<skillId>`.
3. Read every file in the package in full: SKILL.md, the ontology file, QUERIES.md, every supporting file, TESTS.md and SETUP.md if present, human_description.md, and the CSV headers. Folding content in requires knowing all of it; skimming loses exactly the sentences that make a package good.

## Phase 2: Assess

Change nothing yet.

1. Run `inventory.py`. It names the ontology generation, what is missing, every extra file and every legacy marker.
2. Run VALIDATION.md against the package as it stands and collect every finding. On a legacy package most findings are expected; they become plan items.
3. Run `convert_legacy.py` on a scratch copy of the package (not the branch) and `compare_ontology.py` on its output. It must print `EQUIVALENT`. A conversion that is not equivalent, or that refuses to convert, is a blocker to resolve in the plan before anything else.
4. Build the **content map**: for each file that will be deleted, list each distinct piece of its content — a rule, a caveat, a query, a definition, a sample-data fact — and its destination.

| Kind of file | Typical examples | Destination of its content |
| ------------ | ---------------- | -------------------------- |
| Legacy ontology | `GRAPH_MODEL.json` | `ONTOLOGY.json` via the converter |
| Ontology prose | `graph-model.md`, `data-model.md` | Meaning per element → that element's `description` in ONTOLOGY.json (within 1,024 characters); design rationale → SKILL.md's Reference ontology section; anything already in a description → dropped as duplicate |
| Duplicate queries | `queries.cypher`, `query-templates.md`, `query-patterns.md` | Queries not in QUERIES.md → added to QUERIES.md with annotation blocks; queries already there → dropped as duplicate; pattern descriptions → that query's `@usage` or `@pattern` |
| Index statements | `indexes.cypher` | SETUP.md, one annotated statement per block, only those a query depends on |
| Intro or overview | `INTRODUCTION.md`, `overview.md` | Agent-facing points → SKILL.md "Introducing this package" guidance; reader-facing explanation → human_description.md, where it is not already there |
| Sample-data description | `sample-data.md`, profile prose in QUERIES.md or SKILL.md | TESTS.md's sample-data profile |
| Per-query sample expectations | `// Expected against sample data: …` comments, example `:param` lines with seeded values | That query's `@sample` tag (and its TESTS.md section, which must agree); the comment or `:param` line is then removed from the Cypher block |
| Agent guidance | `caveats.md`, `implementation-guidance.md`, "Key rules" sections | SKILL.md Operational Constraints or Reference ontology section; large and specialised → kept as a supporting file |
| Workflow | `resolution-workflow.md`, `detection-workflow.md` | Small → SKILL.md; large and specialised → kept as an indexed supporting file |
| Obsolete material | content describing retired format features | Dropped, with the reason |

**Fold or keep.** Fold by default. Keep a file as a supporting file only when both hold: its remaining content — the characters of its content-map rows whose destination is not "dropped" — is over roughly 3,000 characters, and the consuming agent needs it only for a specific task (so loading it on demand saves context on every other turn). A file that is mostly duplication folds even when it is long. Record the decision and the remaining size in the file table; near the threshold, say so and let the user decide.

**Prose between queries** in QUERIES.md or a duplicate query file goes where its kind belongs: about one query → that query's `@description`, `@usage` or `@pattern`; design rationale → SKILL.md's Reference ontology section; sample-data detail → TESTS.md; procedure across queries → SKILL.md or the retained workflow file.

When two files say different things about the same subject, the content map says so; resolving the conflict is a meaning change for the plan.

## Phase 3: Plan, then stop for approval

Present one plan and wait. Do not start the branch's changes until the user approves it; they may approve all of it, or correct parts in their own words.

The plan contains:

- **Source**: repo, base commit, package, ontology generation.
- **File table**: one row per file in the package and per file to be created — keep, convert, rewrite to format, create, or delete — with the reason.
- **Content map**: from Phase 2, for every deletion.
- **Ontology**: the converter's key renames (internal), anything it dropped and where that meaning goes, and description edits (terminology, folded prose, length) shown as before/after.
- **Proposed annotations**: `one_of`, `pattern`, relationship counts, aliases and references, batched the way SKILL.md step 1 batches inferred descriptions — each with its reason and the source it comes from. A `reference` needs a URL you have read in this session; the package's own Source references in SKILL.md qualify once read, and if you cannot read them, propose no references and say so. Source URLs themselves stay in SKILL.md's Source references list — the root of ONTOLOGY.json has no `reference` field. Counts and value lists must hold in the bundled CSVs; `check_annotations.py` on the scratch copy proves it before you propose them.
- **Queries**: which queries gain annotation blocks, which come in from duplicate files, which sample-data claims move to TESTS.md. Cypher is unchanged; any query that looks wrong is listed separately as a proposed fix, never folded silently into the migration.
- **TESTS.md**: created or restructured, and what the invariants are derived from.
- **Breaking changes**: normally "none". Anything else is listed with its impact.
- **catalog.json**: the entry diff from `catalog_entry.py` (without `--write`), run against a scratch copy of the repo root holding `catalog.json` and the package in its planned end state.
- **Validation findings**: every Phase 2 VALIDATION.md finding, each with the plan item that resolves it or the reason it stays.
- **Conflicts and decisions**: contradictions the content map found, heading splits and their new names, and anything else the user must choose.

## Phase 4: Execute

On the branch, in this order — each step constrains the next, as in a new build.

1. **Ontology.** Run `convert_legacy.py` in the package folder; run `compare_ontology.py GRAPH_MODEL.json ONTOLOGY.json` and require `EQUIVALENT`; then `git rm GRAPH_MODEL.json`. Fold ontology prose into descriptions, apply the approved annotations, replace "model" terminology inside descriptions, and keep each description within 1,024 characters. Re-run `compare_ontology.py` against the legacy file from the base commit (`git show <base>:<skillId>/GRAPH_MODEL.json`): the only differences allowed are the approved description edits and the approved annotations.
2. **CSVs.** Untouched, unless the plan approved a change.
3. **QUERIES.md.** Bring it to the format in SKILL.md step 3: a prerequisites preamble, the "Adapting these queries" section, an @-annotation block on every query, the data-agnostic sweep (sample-data claims move to TESTS.md), APOC/GDS material in its own section, and the node-key constraints reference at the end. Add the queries the content map brings in. Keep every query's Cypher byte-for-byte; the annotation block goes above it. Remove every `TODO(review): unproven query`. Comments inside the Cypher block are the one exception to byte-for-byte: a comment or `:param` line carrying sample-data expectations moves into the query's `@sample` tag (VALIDATION.md 5a), and the Phase 5 comparison ignores comments, so it still proves the logic unchanged. Three cases need a rule:
   - **A heading that holds more than one query** is split into one `##` heading per query. Each resulting heading must describe its own query: the first query keeps the original heading only if it still does, otherwise every part gets a new name from what it does, in the same style. Record every new heading in the plan; TESTS.md follows the new headings.
   - **Run order.** When the package says its queries must run in order, keep that order. Satisfy the APOC/GDS rule by labelling those queries in place — "(requires APOC)" in the heading and in `@prerequisites` — rather than moving them into a separate section.
   - **Literal thresholds.** Where a threshold is written into the Cypher as a literal rather than a `$parameter`, do not parameterise it: `@params` says `None` (or lists only the real parameters), and `@usage` names each literal threshold, what it controls, and a data-agnostic starting point for changing it. Parameterising is a query change — propose it in the plan as an optional fix.
4. **SETUP.md.** Absorb index statements from deleted files; annotate each statement; no node-key constraints. Delete SETUP.md if nothing a query depends on is left in it, and say so in SKILL.md.
5. **TESTS.md.** Create or restructure it per SKILL.md step 4, from the CSVs and the seeded design they show: How to run, the sample-data profile (absorbing any sample-data file or profile prose), and one section per query with Parameters, Invariant and, where derivable from the CSVs, Expected. Sections that recorded execution status ("not executed", "status of these expectations") are removed; editing notes worth keeping go into the profile.
6. **SKILL.md.** Re-shape it onto the current template, keeping its domain content: frontmatter without retired keys; "Introducing this package" guidance absorbing overview material; a **Reference ontology** section with the summary, design rationale, terminology line and a **role map** (new for most legacy packages — derive the roles from the queries, as SKILL.md step 6 describes); definitions of any query-created entities; a Supporting files table listing only retained files; Operational Constraints absorbing caveats and guidance, with the template's standard bullets present; Response Shape.
7. **human_description.md.** Terminology, completeness against ONTOLOGY.json (every node, relationship and property), and the exclusions in SKILL.md step 7. It is otherwise preserved, like everything else.
8. **Clean-up.** `git rm` every file the content map deletes. Then search the package for every deleted filename — no file may reference one — and for every legacy marker `inventory.py` reported.
9. **Catalog.** `python3 <skill-path>/scripts/catalog_entry.py <repo-root> <skillId> --write`.

## Phase 5: Validate

Run VALIDATION.md in full, then these migration checks:

- `inventory.py` reports no `MISSING`, no `LEGACY` lines (a "the model" hit is acceptable only where it means something other than the reference ontology — a pricing model, a risk model), and no `EXTRA` except retained supporting files indexed in SKILL.md. Every label, type or property it reports as written by a query is declared and mapped, or defined in SKILL.md.
- `compare_ontology.py` against the base commit's legacy file shows only approved differences.
- Every query in the base commit's QUERIES.md and duplicate query files is either in the new QUERIES.md with identical Cypher, or recorded in the content map as a duplicate:

```bash
python3 - "<repo-root>" "<skillId>" "<base-commit>" <<'PY'
import re, subprocess, sys, pathlib
root, skill, base = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def bodies(text):
    out = set()
    for b in re.findall(r"```cypher\n(.*?)```", text, re.S) or ([text] if "```" not in text else []):
        for stmt in re.split(r";\s*\n", re.sub(r"(?s)/\*.*?\*/", "", b)):
            s = re.sub(r"(?m)^\s*//.*$", "", stmt).strip()
            if s: out.add(re.sub(r"\s+", " ", s))
    return out
names = subprocess.run(["git", "-C", root, "ls-tree", "--name-only", f"{base}:{skill}"], capture_output=True, text=True).stdout.split()
old = set()
for n in names:
    if not (n.endswith(".md") or n.endswith(".cypher")): continue
    text = subprocess.run(["git", "-C", root, "show", f"{base}:{skill}/{n}"], capture_output=True, text=True).stdout
    if n.endswith(".cypher") or "```cypher" in text:
        old |= bodies(text)
new = bodies((root / skill / "QUERIES.md").read_text()) | bodies((root / skill / "SETUP.md").read_text() if (root / skill / "SETUP.md").is_file() else "")
for q in sorted(old - new): print("NOT CARRIED OVER (must be a duplicate or an approved change):", q[:120])
for q in sorted(new - old): print("NEW OR CHANGED (must be an approved addition or fix):", q[:120])
PY
```

  Statements are compared whitespace-normalised and without comments, across every Markdown file with Cypher blocks and every `.cypher` file in the base commit (SETUP.md and index files included). Every line printed must match a content-map row or an approved plan item.
- `leak_scan.py` (VALIDATION.md 5a) shows no seeded value left in an agent-facing file outside `@sample` tags. Legacy packages often carry seeded identifiers and expected results in query comments and example parameters; they become the query's `@sample`, or move to TESTS.md where they are not about one query. Hits inside unchanged Cypher are acceptable only when the value is a domain constant the logic needs (a placeholder or sentinel it filters on); list them in the PR as accepted.
- No file references a deleted file, `GRAPH_MODEL.json`, or `INTRODUCTION.md`.

## Phase 6: Pull request

1. Commit in three steps so the review reads in order: the ontology conversion (`ONTOLOGY.json` added, `GRAPH_MODEL.json` removed); the documents brought to format (SKILL.md, QUERIES.md, SETUP.md, TESTS.md, human_description.md); the clean-up (deleted files and `catalog.json`).
2. Push the branch and open a pull request against `main`, titled `Migrate <skillId> to the current package format`. If you cannot push or open the PR from this environment, produce the branch as a patch plus the PR description, and give the user the commands to push and open it.
3. The PR description is the migration report:
   - **Summary**: source commit, ontology generation before and after, one line on what changed.
   - **Files**: created, rewritten, deleted — with the content map for every deletion.
   - **Ontology**: entity-key renames (internal, not breaking), annotations added, description edits.
   - **Queries**: annotation blocks added, queries brought in from deleted files, confirmation that existing Cypher is unchanged, and any proposed query fixes (approved ones applied, the rest listed).
   - **Breaking changes**: normally "None — labels, relationship types, directions, properties and keys are unchanged".
   - **Checks run**: VALIDATION.md results, `compare_ontology.py` output, the spec-library check, and the runtime gate result — including, until the destination adopts the ontology graph spec, the expected failure on `schema`/`extensions` and the exact error.
   - **Manual testing**: point the tester at TESTS.md.
   - **Remaining `TODO(review)`** items, with paths.
   - **For the reviewer**: human_description.md and every folded section need a human read.
