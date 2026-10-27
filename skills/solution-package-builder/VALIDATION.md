# Package Validation

Run these checks on a generated or edited package before handing it off. Let `<package-path>` be the package folder. Do not rely on a successful build alone: malformed packages are caught and skipped by the registry, so a broken package fails silently by never appearing.

Work through sections 1–6 (including 3b, 5a, 5b, 5c and 5d) and collect every finding — don't stop at the first failure. Then report and resolve findings with the user as described in section 7, and write the handoff described in section 8.

Two failure modes dominate. The first is **inconsistency** between reference ontology, data, and queries. The second, since the TESTS.md split, is **sample-data leakage**: concrete detail about the bundled rows appearing in a file the consuming agent reads, where it becomes a false claim about the user's data. Section 5a checks for it mechanically.

## 1. Structural checks

Required:

```text
<package-path>/SKILL.md
<package-path>/ONTOLOGY.json
<package-path>/QUERIES.md
<package-path>/human_description.md  # required in every package
<package-path>/sample-data/**/*.csv   # optional at the format level; present in any working demo
<package-path>/TESTS.md               # required whenever sample-data CSVs resolve
```

Confirm:

- All required files exist and are non-empty, and every CSV referenced by ONTOLOGY.json sits below `sample-data/` (at any depth — nested subdirectories are legal).
- There is no `GRAPH_MODEL.json`. A package carrying one is in the legacy format, or carries a stale copy beside its `ONTOLOGY.json` — blocker either way; convert per ONTOLOGY_SPEC_FORMAT.md's "Converting a legacy graph model" and remove it.
- There is no `INTRODUCTION.md` — introduction guidance lives inside SKILL.md.
- `TESTS.md` exists whenever the package bundles sample data. A package with resolving CSVs and no TESTS.md has no test oracle and cannot be verified — blocker. A package with no CSVs at all is a reference-ontology template rather than a working demo; TESTS.md is then not required, and that should be a deliberate choice the handoff names.
- `human_description.md` exists, spelled exactly so — lower-case, underscore, `.md`. It is required whether or not the package bundles sample data. Missing is a blocker; a variant spelling is a blocker, because the runtime resolves it by name. Its content is checked in section 5d.
- `TESTS.md` and `human_description.md` are **not** indexed in SKILL.md's Supporting files table, and no agent-facing file instructs the agent to read either. Any mention is worth reviewing; an instruction to load one defeats the split and is a blocker.
- The folder name (`skillId`) is kebab-case and stable.
- Supporting files beyond the required set use only `.md` or `.cypher`, and each is indexed in SKILL.md with a stated purpose so the agent knows when to load it. An unindexed supporting file is a warning: index it, fold it in, or remove it. `TESTS.md` and `human_description.md` are the only exemptions.
- Readable files stay under ~50,000 characters. This is guidance, not an enforced limit — exceeding it is a *warning*, not a blocker — but note that larger files consume more of the consuming agent's context and increase the need for a more powerful model. Report any file over the target with its size and whether annotations, queries, or prose drove the growth, so the user can decide. **`TESTS.md`, `human_description.md` and the sample-data CSVs are exempt** — none reaches the consuming agent, so size costs nothing there. A large TESTS.md is not a finding; a large QUERIES.md usually means material that belongs in TESTS.md has not moved. `human_description.md` has its own length guidance in 5d, which is about the reader, not the context window.
- Paths use forward slashes with no absolute, URL, backslash, empty, `.` or `..` segments.
- No file references a bundled file that does not exist.
- In `neo4j/studio-agent-use-cases`, the package's `catalog.json` entry lists exactly the files in the folder (`scripts/catalog_entry.py <repo-root> <skillId>` prints any difference; no output means none).

```bash
P="<package-path>"

for f in SKILL.md ONTOLOGY.json QUERIES.md human_description.md; do
  test -s "$P/$f" || echo "MISSING: $f"
done

test -e "$P/GRAPH_MODEL.json" && echo "BLOCKER: legacy GRAPH_MODEL.json present"

# Variant spellings of human_description.md — the runtime resolves it by name.
find "$P" -maxdepth 1 -iname 'human*desc*' ! -name 'human_description.md' \
  | grep . && echo "BLOCKER: human_description.md is misnamed"

# Sample data at any depth below sample-data/ requires a TESTS.md.
find "$P/sample-data" -name '*.csv' 2>/dev/null | grep -q . \
  && { test -s "$P/TESTS.md" || echo "BLOCKER: sample data present, TESTS.md missing"; }

# Agent-facing files: any mention of TESTS.md or human_description.md is worth a
# look; an instruction to read one is a blocker. Reviewed by eye — the grep only
# finds candidates.
AGENT_FACING=$(find "$P" -maxdepth 1 -name '*.md' ! -name 'TESTS.md' ! -name 'human_description.md')
rg -n 'TESTS\.md|human_description\.md' $AGENT_FACING | tee /tmp/reserved-mentions.txt
rg -ni 'read|load|see|consult|refer|open' /tmp/reserved-mentions.txt \
  && echo "BLOCKER: an agent-facing file instructs the agent to read a reserved file"

rg -n "TODO\(review\)" "$P"
wc -c "$P"/*.md "$P"/ONTOLOGY.json
```

## 2. Frontmatter and parser checks

- SKILL.md begins with valid YAML frontmatter delimited by `---` and has a non-empty body.
- `name` is kebab-case, 1–64 characters.
- `description` is non-empty, specific, and at most 1024 characters; it should read as trigger text (industry, use cases, capabilities).
- `metadata` values are all strings; `neo4j-card-title`, `neo4j-card-category`, and `neo4j-card-description` are non-empty.
- **`neo4j-card-category` is one of the allowed values, matched exactly** — `Financial Services`, `Insurance`, `Healthcare & Life Sciences`, `Manufacturing`, `Cybersecurity`, `Industry Agnostic`, or the legacy `General`, `Real-time risk detection`, `Supply Chain`. This is a blocker: the destination validates the field against this closed set and drops the whole package when it fails, with no user-visible error. A descriptive-but-unlisted value is the trap — `Investment Banking` reads perfectly and is rejected. Prefer a non-legacy value for new packages.
- **No `neo4j-icon-category` key is present.** The field was removed from every package and is referenced nowhere in the destination; emitting it reintroduces a key nothing consumes.
- **No `neo4j-graph-spec-version` key is present.** It belonged to the legacy format; the spec version now lives in `ONTOLOGY.json`'s `schema` field and is checked in section 3. A leftover key is a blocker, because it asserts a contract the package no longer uses.
- Invalid YAML or missing required metadata rejects the package.

## 3. Reference ontology checks

[ONTOLOGY_SPEC_FORMAT.md](ONTOLOGY_SPEC_FORMAT.md) is the contract; its authority is `ontology-graph-spec.schema.json`, bundled with this skill. **Validate against that file and nothing else.** Never fetch a schema over the network, and never treat a remote revision as more current — a package's reference ontology is bound to the spec version this bundle is pinned to, and silently validating against a different one is the failure this rule exists to prevent.

First verify JSON syntax, then validate against the bundled schema. The snippet needs `jsonschema` 4.x or newer — the spec declares draft 2020-12, which 3.x cannot load, and some runners still ship 3.2.0 (`pip install -U jsonschema`):

```bash
P="<package-path>"
S="<skill-path>"   # this skill's own folder, where ontology-graph-spec.schema.json sits

node -e 'JSON.parse(require("node:fs").readFileSync(process.argv[1], "utf8"))' "$P/ONTOLOGY.json"

test -s "$S/ontology-graph-spec.schema.json" \
  || { echo "BLOCKER: bundled ontology-graph-spec.schema.json missing from $S"; exit 1; }

python3 -c "
import json, jsonschema
schema = json.load(open('$S/ontology-graph-spec.schema.json'))
model  = json.load(open('$P/ONTOLOGY.json'))
jsonschema.Draft202012Validator(schema).validate(model)
print('schema OK')
"
```

The schema sets `additionalProperties: false` throughout, so any off-schema key fails here — including every field of the legacy graph-spec format (`mustExist`, `nullable`, root `tables`/`mappings`/`display`, table `fields`, `NodeMapping`/`RelationshipMapping`, `field` references) and a missing `schema` or `id`. A schema failure is a blocker.

**Schema validity is necessary, not sufficient.** The schema is generated from the spec library's own type definitions; it cannot express the library's semantic rules (below), and it cannot tell you whether the destination runtime reads the file. A package that the runtime cannot read is not rejected loudly — it is silently dropped from the destination's catalogue. That is why the spec-library check and the runtime gate below are both required.

### Spec version pin

The package's `schema` URI must name the spec this bundle carries. A mismatch means the reference ontology was authored against a different contract than the schema now validating it — it may be silently wrong in ways the schema cannot see. **A mismatch is a blocker**, and so is a leftover `neo4j-graph-spec-version` key in SKILL.md, which belongs to the retired format.

```bash
P="<package-path>"
S="<skill-path>"

# The bundle's pin — the single source of truth, declared in ONTOLOGY_SPEC_FORMAT.md.
PINNED=$(sed -n 's/^ontology-graph-spec-version: *//p' "$S/ONTOLOGY_SPEC_FORMAT.md" | head -1)

# The package's declaration: the version segment of ONTOLOGY.json's schema URI.
DECLARED=$(python3 -c "
import json, re, sys
s = json.load(open('$P/ONTOLOGY.json')).get('schema', '')
m = re.fullmatch(r'https://neo4j\.com/docs/ontology-graph-spec/([^/]+)/schema\.json', s.strip())
print(m.group(1) if m else '')
")

if   [ -z "$PINNED"   ]; then echo "BLOCKER: no ontology-graph-spec-version pin found in $S/ONTOLOGY_SPEC_FORMAT.md"
elif [ -z "$DECLARED" ]; then echo "BLOCKER: $P/ONTOLOGY.json has no well-formed ontology graph spec schema URI"
elif [ "$PINNED" != "$DECLARED" ]; then
  echo "BLOCKER: spec version mismatch — package declares '$DECLARED', bundle is pinned to '$PINNED'"
else
  echo "spec version OK: $DECLARED"
fi

awk '/^---$/ { n++; next } n == 1' "$P/SKILL.md" | grep -q 'neo4j-graph-spec-version' \
  && echo "BLOCKER: SKILL.md still declares the retired neo4j-graph-spec-version"
```

Resolving a mismatch is a decision for the user, never a silent edit. Either the package predates a spec update and needs migrating to the pinned version, or the pin itself is wrong. Do not "fix" it by rewriting the package's `schema` URI to match the bundle — that asserts a migration that has not happened.

Then inspect consistency the schema cannot see:

- `id` equals the package folder name; `version` is set (it is the document's revision label, distinct from the pinned spec version checked above).
- Node and relationship keys are readable and stable (label-based for nodes, camelCase for relationships); every key referenced by relationships and mappings exists.
- Every node has exactly one `key: true` property (or a composite `KEY` constraint instead); `key: true` is never combined with `unique`/`must_exist` on the same property.
- `extensions.data_source_mappings` holds exactly one list, `mapping0`. Mappings use `"type": "NODE"` / `"RELATIONSHIP"` with `mode: "MERGE"`; each node mapping's `key` array matches its node's `key: true` property, or the properties of its composite `KEY` constraint.
- Every mapping table exists in `extensions.data_source_tables`; every mapped `column` exists in that table's `columns`; every mapped property exists on its node or relationship.
- Every relationship mapping's `from_node.label` and `to_node.label` equal the labels of the relationship's `from.node` and `to.node`, and endpoint columns resolve to node identifiers.
- **Every declared node and every declared relationship has a mapping.** This is a blocker, and the runtime gate will not catch it: a reference ontology that decodes cleanly can still be unimportable. Import treats the reference ontology as an import job definition and demands a source table for every declared entity, a column for every property, and an ID column for every relationship endpoint; anything unmapped is flagged `Must be specified` and the import definition cannot be cleared without hand-editing the file. The usual cause is a relationship a query creates rather than loads — a resolution or selection edge, a computed similarity, an algorithm-written link. Those must not be declared at all; they belong in SKILL.md (see ONTOLOGY_SPEC_FORMAT.md, "Declare only what Import can load", and §6 below). The fix is never to invent a CSV to make one mappable.

```bash
python3 - "<package-path>" <<'PY'
import json, sys, pathlib
m = json.loads((pathlib.Path(sys.argv[1]) / "ONTOLOGY.json").read_text())
maps = [x for lst in (m.get("extensions", {}).get("data_source_mappings") or {}).values() for x in lst]
mn = {x.get("node") for x in maps if x.get("type") == "NODE"}
mr = {x.get("relationship") for x in maps if x.get("type") == "RELATIONSHIP"}
for n in m.get("nodes", {}):
    if n not in mn: print(f"BLOCKER unmapped node: {n}")
for r, d in m.get("relationships", {}).items():
    if r not in mr: print(f"BLOCKER unmapped relationship: {r} ({d.get('type')})")
PY
```

Every `BLOCKER` line is either an entity whose mapping was forgotten — add it —
or a query-created entity that should never have been declared — delete it from
the reference ontology and document it in SKILL.md. Decide which by asking whether any CSV
could supply it. There is no third case.
- Table entries use `source: "local"`, keys equal to the exact CSV filenames, and `columns` listing every CSV header **in header order**, each `"type": "string"`; graph property types are correct for query behaviour (numeric comparisons on numeric types, temporal operations on temporal types). Checked mechanically in 3b.
- Every node has `extensions.display` with `x`/`y`. Checked mechanically in 3b.
- Valid JSON only: no comments, trailing commas, or unresolved placeholders.

### The spec-library check (required when available)

The spec library — the code the schema is generated from — runs semantic rules the schema cannot express: a relationship target with both `count` and `min_count`/`max_count`, negative counts or `min_count` above `max_count`, a property with both `one_of` and `pattern`, a node, relationship or property `description` over 1,024 characters, a label containing `:` or `=`, constraint and index coherence, and mapping dependency cycles. Run it from a checkout of [neo4j/graph-spec](https://github.com/neo4j/graph-spec) at the commit named in ONTOLOGY_SPEC_FORMAT.md's provenance line — a different commit is a different contract. This is tooling, not the spec: the bundled schema stays the authority for structure.

```bash
G="<path-to-graph-spec-checkout>"   # at the pinned commit
P="<package-path>"

mkdir -p "$G/go/cmd/validatefile"
cat > "$G/go/cmd/validatefile/main.go" <<'EOF'
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/neo4j/graph-spec/go/model"
	"github.com/neo4j/graph-spec/go/validation"
)

func main() {
	b, err := os.ReadFile(os.Args[1])
	if err != nil { panic(err) }
	var m model.GraphModel
	if err := json.Unmarshal(b, &m); err != nil { fmt.Println("DECODE FAILED:", err); os.Exit(2) }
	issues, err := validation.Validate(m)
	if err != nil { fmt.Println("VALIDATE ERROR:", err); os.Exit(2) }
	if len(issues) == 0 { fmt.Println("SPEC LIBRARY OK"); return }
	for _, i := range issues { fmt.Printf("BLOCKER %s at %s: %s\n", i.Code, i.Path, i.Message) }
	os.Exit(1)
}
EOF
(cd "$G/go" && go run ./cmd/validatefile "$P/ONTOLOGY.json")
rm -rf "$G/go/cmd/validatefile"
```

The library needs a Go toolchain at the version its `go.mod` names and a Linux or Apple-silicon host (it embeds a native library). If module downloads fail behind a proxy, `GOPROXY=direct` usually works. Issue paths use the library's internal ids (`nodes.node1.properties.node1_property0`), not the package's readable keys — locate the element by its position in the file. If no toolchain is available, say so in the handoff: "spec library not run" is a finding to report. 3b's script covers the count, `one_of`/`pattern`, description-length and label-token rules in the meantime, but not constraint, index or mapping-dependency coherence.

### The runtime gate (required)

**A reference ontology that has not been decoded by the destination runtime is not validated.** Schema validation and every eyeball check above can pass on a package that the destination silently drops. Run this gate on every package, every time; a package that has not been through it does not ship, and "no runtime available to test against" is a finding to report, not a reason to skip.

For Aura/upx, the destination is `graphSpecJsonToDataModelAndVisualisation` — the same call the app's package registry makes — or whatever replaces it when upx adopts the ontology graph spec; use the call the registry actually makes. Drop a temporary test into a checked-out upx repo and run it:

```bash
U="<path-to-upx-checkout>"
P="<package-path>"

cat > "$U/commons/ui/src/assistant-sidebar/skills/tmp-runtime-gate.test.ts" <<EOF
import { readFileSync } from 'node:fs';
import { graphSpecJsonToDataModelAndVisualisation } from '@nx/import-shared/sample-models';
import { describe, expect, it } from 'vitest';

describe('runtime gate', () => {
  it('decodes', () => {
    let result = 'DECODE OK';
    try {
      const { dataModel } = graphSpecJsonToDataModelAndVisualisation(readFileSync('$P/ONTOLOGY.json', 'utf8'));

      // Decoding without throwing is not enough: the encode step can drop content silently.
      // Assert the output is coherent — every table field keeps a name, and every mapping
      // points at a field that exists under that name.
      const dm = dataModel;
      const schema = dm.dataSourceSchema ?? dm.graphMappingRepresentation?.dataSourceSchema;
      const tables = schema?.tableSchemas ?? [];
      const problems = [];
      const declared = new Set();
      for (const table of tables) {
        for (const [index, field] of (table.fields ?? []).entries()) {
          if (typeof field.name !== 'string' || field.name === '') {
            problems.push(\`table "\${table.name ?? '?'}" field #\${index} encoded with no name: \${JSON.stringify(field)}\`);
          } else {
            declared.add(field.name);
          }
        }
      }
      for (const mapping of dm.graphMappingRepresentation?.nodeMappings ?? []) {
        for (const pm of mapping.propertyMappings ?? []) {
          if (pm.fieldName !== undefined && !declared.has(pm.fieldName)) {
            problems.push(\`mapping references undeclared field "\${pm.fieldName}"\`);
          }
        }
      }
      if (problems.length > 0) result = \`ENCODE LOSSY: \${problems.join('; ')}\`;
    } catch (error) {
      result = \`DECODE FAILED: \${error instanceof Error ? error.message : String(error)}\`;
    }
    expect(result).toBe('DECODE OK');
  });
});
EOF

(cd "$U" && pnpm exec vitest run commons/ui/src/assistant-sidebar/skills/tmp-runtime-gate.test.ts 2>&1 | grep -E 'DECODE|Tests ')
rm -f "$U/commons/ui/src/assistant-sidebar/skills/tmp-runtime-gate.test.ts"
```

Note the assertion is written to surface the *message*, not just a pass/fail — a failing run prints the runtime's own diagnosis (`Unknown Extension type. Keys: [type, value]`, `Missing required labels at …`, `Version must be specified`, `Unable to determine version from schema`), which is what tells you which rule the reference ontology broke. A runtime that has not yet adopted the ontology graph spec fails on the `schema` field or the `extensions` layout; that is case 3 below, not a package defect. Delete the temp file afterwards: it lives in someone else's repo.

The gate covers the reference ontology's decode *and* the coherence of what it encodes — a decode that throws nothing can still produce a lossy result, which is exactly how a table-field `name` defect reached production under the legacy format. It does not cover the package's SKILL.md frontmatter, card metadata, or CSV resolution; those are checked separately by the destination's own package parser, and sections 1, 2 and 4 stand in for that.

A gate that passes is still not proof of a working package. It proves the reference ontology survives the destination's decode and encode with its column names intact; it says nothing about whether those names match the bundled CSVs (section 4) or whether the data supports the queries (sections 5 and 5c).

**If the runtime rejects a schema-valid reference ontology, stop.** Report it to the user with the exact error; do not strip fields until it passes. There are three explanations, and they call for different responses:

1. **The reference ontology breaks a documented rule.** Fix it.
2. **The schema and the runtime disagree at the same pinned version** — as the typed extension values did at the previous pin. Fix the *pipeline* (this skill), not just the one package, so the next package does not repeat it.
3. **The runtime and the pin are on different spec versions** — either way round. If the runtime is ahead, raise it as a spec-update decision: replace `ontology-graph-spec.schema.json`, update the pin and provenance in ONTOLOGY_SPEC_FORMAT.md, re-validate and migrate every existing package. If the runtime is behind, the package waits for the runtime. Never edit a reference ontology to fit an unpinned runtime.

Do not assume (3) without evidence: the first real failure under the legacy format was a (2).

Until upx adopts the ontology graph spec, expect every package built by this skill to fail the gate as case 3 — on the `schema` field or the `extensions` layout. Run the gate anyway, record the exact error, and report it in the handoff as "runtime gate failed: destination predates the pinned spec". The package is not shippable until the destination catches up, but every other check still runs and still has to pass.

## 3b. Annotation checks

Annotations are tested content, not decoration — check them against the same consistency standard as everything else:

- The root has a non-empty `name` and `description`.
- Every node, every relationship, and every property (node and relationship) has a non-empty, specific `description` of at most 1,024 characters. A description that only restates the name ("the dosage") is a warning: it gives an agent nothing.
- Every numeric, temporal, or coded property's description states its unit, encoding, or scope (per-what, measured how, which code system).
- Relationship descriptions read in the from→to direction and state multiplicity both ways; where one relationship type is reused between node pairs, each entry's description states its distinct meaning.
- Descriptions are worded normatively ("expected to carry…") where the reference ontology doubles as a template for user data.
- **The only `extensions` are root `data_source_tables` and `data_source_mappings` and node `display`** — a blocker, not a style note. `custom` at any level, `indexes`, or an extension on a property, relationship, constraint or table is outside this pipeline's partial adoption of the spec.
- Every property description carrying a sample ends with a `` e.g. `<value>`. `` clause, and that `<value>` appears **verbatim** in the mapped CSV column — checked mechanically below. A sample absent from the data is a blocker: either the sample or the data is wrong.
- Sample values illustrate the *shape* of a value, not the dataset. A sample that only makes sense as a claim about the bundled rows (a seeded ring member's identifier chosen because it is a ring member) is a warning — pick an unremarkable value instead. This is the one place sample data legitimately reaches the consuming agent, and it should carry no signal beyond format.
- Stated units and encodings are consistent with the CSV value ranges (a "milligrams" property whose values run 0.001–0.9 is probably grams). An enumeration stated only in prose ("one of `https`, `http`, `ssh`") belongs in `one_of` where the set is closed; until it is moved, check by eye that it matches the values present.
- **Value restrictions hold and are the domain's.** No property has both `one_of` and `pattern`; every mapped value is in `one_of` or fully matches `pattern` (checked below); the sample is an allowed value. By eye: a `one_of` list is the domain's complete closed set, not the distinct values the generator happened to emit, and no `pattern` encodes the package's own identifier scheme — either would reject a user's legitimate data. Each is a warning.
- **Counts hold.** Every relationship target's `count`/`min_count`/`max_count` holds for every node at that end in the sample data (checked below), and the prose multiplicity in the description says the same thing. A count the data violates is a blocker; prose and counts that disagree is a blocker.
- **Aliases and references are sourced.** Every `reference` is a real URL that was actually read — a fabricated or unverified one is a blocker. Every alias is an industry term from the source material, not a spelling variant, the label itself, or one organisation's private vocabulary — warning.
- The optional `name` fields on nodes, properties, relationships and constraints are unset — root `name` only.
- Inferred annotations the user has not confirmed are marked `TODO(review): inferred description` — an unmarked, unconfirmed stipulation is a warning.

The bundled script `scripts/check_annotations.py` resolves every mapping to its CSV column and checks the extensions allow-list, display coordinates, the root `id`, table columns against CSV headers, descriptions, samples, value restrictions, endpoint labels, and counts:

```bash
python3 "<skill-path>/scripts/check_annotations.py" "<package-path>"
```

Any `BLOCKER` line stops the build: fix the reference ontology or the data, and do not proceed to the runtime gate. The `COUNT` lines show each count claim and the number of nodes it was tested against; a count tested against zero nodes means the node's mapping or identity columns did not resolve, which is itself a finding. Prose multiplicity has no fixed form — read each relationship description and confirm it says what the counts say.

## 4. CSV and mapping checks

For every CSV referenced in `extensions.data_source_tables` or a mapping's `table`:

- The file resolves unambiguously below `sample-data/` (basename match, or exact relative path; duplicate basenames need explicit paths).
- The header row exactly matches the table's `columns` names, in order, including case (checked in 3b).
- Every row has the expected column count; values with delimiters, quotes, or newlines are CSV-escaped.
- Identifier columns are present. Rows may repeat a node key — mode `MERGE` merges them into one node — but every mapped node property must then carry the same value on every row sharing that key; conflicting values make the imported property nondeterministic.
- Every non-empty relationship endpoint value resolves to a node row. An empty endpoint value creates no relationship — a legitimate pattern for chain ends (e.g. a last encounter with no `NEXT`) — but should be deliberate, not accidental.
- Dates, numbers, and booleans convert cleanly to their declared graph property types.
- Values conform to their property's confirmed annotations — unit, encoding and scope in the `description`, and `one_of` or `pattern` (cross-check with section 3b).
- The deliberately seeded signal patterns described in **TESTS.md's** sample-data profile actually exist in the data.

A package where only some referenced CSVs resolve is invalid.

## 5. Query checks

For QUERIES.md (and any supporting `.cypher` file):

- The preamble states prerequisites in one place. It does **not** profile the sample data — row counts and seeded signals belong in TESTS.md.
- An **"Adapting these queries"** section appears near the top: read the live schema, map onto SKILL.md's role map, rewrite, update the annotation block. Missing section is a finding.
- Every query opens with a `/* @... */` annotation block **before any query logic** (a Cypher block comment, so it can never execute), carrying the required tags: `@name` matching the query's `##` heading, `@description`, `@params`, `@prerequisites`, `@returns`, `@usage`, `@tags`. No `@version`. A missing block or missing required tag is a finding.
- **`@sample`, where present:** at most one per query; opens with the literal `Bundled sample data only:`; gives a value for every `$parameter` the query takes; every value it names exists in the bundled CSVs (an anchor that does not exist is a blocker — it sends the agent's smoke test to a false alarm); and it agrees with the query's TESTS.md section — parameters, row count and named results. Disagreement is a blocker: one of the two is stale.
- `@params` matches the query's actual parameters exactly: every `$parameter` in the Cypher appears in `@params` with its meaning, and `@params` names nothing the query doesn't use (`None` for parameterless queries). Mechanically checkable — do it mechanically.
- `@params` is **one line per parameter**, each starting at the parameter name, with wrapped text indented past it. A second parameter beginning at the same indent as the first one's continuation lines is unparseable and defeats the check above — finding.
- Every parameter that gates a result set carries a **starting point with a data-agnostic justification**: either a concrete value justified by what the parameter does, or a stated procedure for deriving one where no number transfers between datasets ("take the portfolio's upper quartile"). A gating threshold with neither is a finding — the query is unusable without opening TESTS.md. A threshold justified by the sample is a leak, caught in 5a.
- Labels, relationship types, directions, and properties match ONTOLOGY.json exactly — **with one exception: entities the queries themselves create.** A relationship type or label that a bundled query writes has no source data, cannot be mapped, and therefore must not be declared in the reference ontology at all (§3, and ONTOLOGY_SPEC_FORMAT.md's "Declare only what Import can load"). For each of those, confirm all four of: it is genuinely written by a bundled query and not merely missing from the reference ontology; it is absent from `extensions.data_source_tables` and `extensions.data_source_mappings` as well as `relationships`; SKILL.md carries its full definition (§6); and QUERIES.md's prerequisites say it does not exist in a freshly imported database. A query-referenced entity that is undeclared *and* undocumented is a blocker — that is the drift this rule exists to catch, and it looks identical to the legitimate case until you check which query writes it.
- Annotation blocks use the reference ontology's vocabulary: where `@description`, `@params`, or `@usage` explains a property or relationship, its wording, unit, scope, allowed values, and direction agree with that element's ONTOLOGY.json annotations. An annotation that contradicts the reference ontology is a blocker — the two are one contract.
- Variable-length traversals have explicit bounds; thresholds and limits are called out in `@usage` as tunable, in general terms.
- No per-query schema-drift prose. The adapting section states the procedure once; repeating it per query is boilerplate. An optional `@pattern` tag on a query whose shape isn't recoverable from its Cypher is fine — on every query it is padding, and a warning.
- No design rationale between the queries (why the reference ontology departs from a source page, why a query differs from a published one). That belongs in SKILL.md's Reference ontology section or a supporting rationale file.
- APOC or GDS use is confined to a clearly labelled section with prerequisites stated — or, where the queries must run in a stated order, each APOC/GDS query is labelled in place in its heading and `@prerequisites`.
- The node-key constraints implied by ONTOLOGY.json (`key: true` properties and composite `KEY` constraints) appear at the end as a reference for checking the live database, introduced by section prose; the individual statements need no annotation blocks.

Running the queries against a database is manual testing, outside this skill's scope. Do not import data or run queries as part of validation, and do not mark queries as unproven. The checks above are static: read every query against ONTOLOGY.json and against the seeded design TESTS.md describes, and confirm by reading the CSVs that each query's pattern is present in the data — a query whose pattern the data cannot produce is a blocker whether or not anyone runs it.

## 5a. Sample-data leakage checks

Everything the consuming agent reads must stay true on data that is not yours. Scan SKILL.md, QUERIES.md, SETUP.md and any supporting file — outside `@sample` tags, which are labelled as describing the bundled sample only — for:

- Row counts, totals, or "N rows" claims of any kind.
- Identifiers that only exist in the bundled CSVs — seeded entity IDs, names, addresses, account numbers.
- Thresholds or limits justified by the bundled data ("4 returns the seeded ring", "tuned to the sample profile").
- Statistical claims about the dataset ("no false positives", "the largest legitimate group is 3").
- Any sentence that would read as false, or as a lie, if the reader's database held their own data.

The mechanical version: `scripts/leak_scan.py` takes the values of every key column and every identifier-like text column (names, addresses, phone numbers — any STRING column with many distinct values) from the CSVs and searches the agent-facing files for them. Each hit is a candidate; a seeded identifier, name or value in an agent-facing file is a blocker unless it is the general mention 5a permits.

```bash
P="<package-path>"
AGENT_FACING=$(find "$P" -maxdepth 1 -name '*.md' ! -name 'TESTS.md' ! -name 'human_description.md')

python3 "<skill-path>/scripts/leak_scan.py" "$P"
# A hit is acceptable only when the value is a domain constant the query logic
# needs — a known placeholder or sentinel it filters on (`none@none.com`,
# `999-999-9999`) — rather than an entity from the data. List accepted hits
# in the handoff.

# Row-count claims, digits and words. Extend the noun list to this package's domain.
# "one" is excluded deliberately: "One row per qualifying claimant" is the standard
# @returns idiom and would swamp the result.
NUM='[0-9]+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozen'
NOUN='rows?|records?|nodes?|claims?|claimants?|incidents?|groups?|rings?|professionals?'
rg -ni "\b($NUM)\s+($NOUN)\b" $AGENT_FACING

# Explicit references to the bundled data.
rg -ni 'bundled sample|sample[- ]data|seeded|synthetic (rows|dataset)' $AGENT_FACING
```

**The greps are the easy half.** They catch counts and identifiers. They cannot catch a
justification that is phrased data-agnostically and is nonetheless a fact about the
generator — "start at 4, which clears ordinary household size" reads as domain knowledge
but is a leak if 4 was chosen because the noise generator caps legitimate groups at 3.
Read every `@params` starting value and every `@usage` threshold claim by hand and apply
the test: *would the author write this sentence having never seen the CSVs?* If the honest
answer is no, it is a leak however it is worded. Cross-check against the TESTS.md
sensitivity notes, which should say where each shipped value actually came from.

Three hit classes are correct and expected. SKILL.md's "Introducing this package" section
may describe the sample *in general terms* ("synthetic data that deliberately seeds the
patterns the queries look for"); QUERIES.md's prerequisites may name the bundled CSVs as
one of the things that can be imported. Both say the sample exists and what it is for, and
neither may quantify it, name anything in it, or imply the reader's database contains it.
The third is a query's `@sample` tag, which may name and quantify the sample because it is
labelled as describing nothing else (`leak_scan.py` skips it). The same values anywhere
else — a Cypher comment, an example `:param` line, the query's prose — are leaks.

A leak is a blocker where it makes a factual claim (counts, identifiers, statistics) and a warning where it is merely a stale framing.

`human_description.md` is excluded from the scan above because it is held to a stricter rule and checked separately in 5d: it may not mention the sample data at all, in any terms, so the two expected hit classes above do not apply to it.

## 5b. Post-import setup checks

When `SETUP.md` exists:

- It contains **no node-key constraints** — Import creates those from ONTOLOGY.json's key definitions, and recreating them (or `UNIQUE` variants) conflicts with the existing `KEY` constraints. This is the single most common setup mistake.
- Only statements that a bundled query actually depends on (or a clearly optional section); nothing speculative.
- One statement per ```` ```cypher ```` block; required statements first; recommended and optional ones clearly marked.
- Every statement opens with a `/* @... */` annotation block: `@name`, `@description`, and `@usage` naming the dependent queries and the effect if skipped.
- The file opens with the agent rules: explain before running, confirm the target, caveat results if declined.
- SKILL.md's Operational Constraints reference SETUP.md with its statement count.
- Any statement duplicated in QUERIES.md as a reference template says so in both places, with a run-once instruction.
- TESTS.md's "How to run" names the SETUP.md statements the queries depend on.

When `SETUP.md` is absent:

- SKILL.md states explicitly that no post-import setup is required.
- No query template depends on schema Import doesn't create — cross-check every index, label, and property the queries touch against ONTOLOGY.json and the import behaviour. A dependency with no home is a blocker: add SETUP.md or fix the query.

## 5c. TESTS.md checks

TESTS.md is the oracle. It is never loaded by the runtime, so it is exempt from the size target and free to be as concrete as the work requires — but it must be complete and it must pair with QUERIES.md.

- A "How to run" preamble for the manual tester: disposable database required, CSVs imported through the Import flow from ONTOLOGY.json, and any SETUP.md statements that must run first.
- A sample-data profile: row counts per label and relationship type, the seeded signals in full, and the deliberate background noise. This is the material removed from QUERIES.md — confirm it actually landed here rather than being deleted.
- **Heading parity with QUERIES.md.** Every query's `##` heading has an identically titled `##` section in TESTS.md, and vice versa. Mechanically checkable — do it mechanically.
- Every query section states its **Parameters** and an **Invariant**. A section with expected counts but no invariant is a finding: it breaks on the next data regeneration and the breakage looks like a query fault.
- Invariants are expressed in terms of the seeded design ("returns the twelve Ring A claimants and no unseeded claimant"), not as bare counts. A bare row count is an observation, not an invariant.
- Any **Expected** counts are derivable from the bundled CSVs, and agree with them.
- No `TODO(review): unproven query` lines anywhere, and no "queries not executed" section — testing is manual and outside package creation. Remove any left over from older packages.

Both files carry headings the other does not — prerequisites and the adapting section on one side, how-to-run and the profile on the other, plus any APOC/GDS section heading and the closing node-key constraints section. Exclude those, then compare what remains; the exclusion lists are per-package, so edit them to match.

```bash
P="<package-path>"
Q_SKIP='^## (Prerequisites|Adapting these queries|Graph Data Science.*|Node-key constraints.*)$'
T_SKIP='^## (How to run|Sample-data profile)$'

rg -N '^## ' "$P/QUERIES.md" | grep -Ev "$Q_SKIP" | sort > /tmp/q-headings.txt
rg -N '^## ' "$P/TESTS.md"   | grep -Ev "$T_SKIP" | sort > /tmp/t-headings.txt

if ! diff -q /tmp/q-headings.txt /tmp/t-headings.txt >/dev/null; then
  echo "FINDING: unpaired query headings"
  comm -23 /tmp/q-headings.txt /tmp/t-headings.txt | sed 's/^/  no TESTS.md section: /'
  comm -13 /tmp/q-headings.txt /tmp/t-headings.txt | sed 's/^/  no QUERIES.md query: /'
fi

# Every TESTS.md query section states Parameters and an Invariant, and names the
# offending section when it does not.
awk -v skip="$T_SKIP" '
  /^## / { if ($0 ~ skip) { cur = ""; next }
           cur = $0; order[++n] = cur; hasP[cur] = 0; hasI[cur] = 0 }
  cur && /Parameters/ { hasP[cur] = 1 }
  cur && /Invariant/  { hasI[cur] = 1 }
  END { for (i = 1; i <= n; i++) {
          if (!hasP[order[i]]) print "FINDING: no Parameters in " order[i]
          if (!hasI[order[i]]) print "FINDING: no Invariant in "  order[i]
        } }
' "$P/TESTS.md"
```

## 5d. human_description.md checks

The only file in the package written for a human reader, and the only one nothing downstream verifies — no schema rejects it, no query fails against it, no agent reads it back. Check it by eye as well as by grep, and say in the handoff that it still needs a human read.

**Structure**

- An `#` heading whose text matches `metadata.neo4j-card-title` in SKILL.md, followed by a one- or two-sentence lead.
- Exactly two `##` sections, titled `Overview` and `Ontology`, in that order. A third `##` section is a finding — the structure is fixed so every package's page reads the same way.
- Overview covers the industry and, in a table, the problem statements against what the reference ontology makes answerable.
- Ontology opens with a short orienting paragraph, then carries tables for entities, properties, relationships, and relationship properties. The last is omitted entirely when no relationship carries a property — an empty table or an "N/A" row is a finding.
- Small paragraphs, bullet summaries, and tables throughout. A paragraph running past roughly six lines is a finding in this file.

**Completeness against the reference ontology** — the check that matters most, because a reader uses these tables to decide whether the reference ontology fits their data:

- Every node label in ONTOLOGY.json appears in the entities table.
- Every node property appears in the properties table, with its graph type.
- Every relationship entry appears in the relationships table. Where one relationship type joins more than one pair of nodes, **each pair has its own row** with its own meaning — one row per type is a finding, since the type name alone does not distinguish them.
- Every relationship property appears, with its graph type.
- No table names anything the reference ontology does not define.
- Meanings agree with the reference ontology's `description` annotations — plain-Englished and shortened, never contradicted, and never restated with a different unit, scope or direction. This is the same consistency rule as section 6's, applied to a file a customer may read.

**Terminology**

- The file calls it the **reference ontology**. `graph model`, `graph data model`, `data model` and `schema` must not appear as names for it — blocker. The same rule applies to every file in the package, and is checked package-wide in section 6.

**Exclusions** — none of the following may appear:

- Filenames or paths of any kind: `ONTOLOGY.json`, `QUERIES.md`, `SKILL.md`, `TESTS.md`, `SETUP.md`, `sample-data/`.
- Cypher, JSON, or any fenced code block. Inline code formatting on label, relationship and property names is expected and fine.
- Any mention of the sample data, in any terms — counts, seeded entities, or a general "bundled synthetic dataset". Stricter than 5a: the file is about the industry and the ontology, and the data is out of scope.
- Instructions addressed to an agent: "the agent can help you", response shapes, operational constraints, "when the user first opens this package".

**Length** — aim for a page a reader gets through in two or three minutes, roughly 400–900 words outside the Ontology tables. Over that is a warning, and usually means the file is explaining Neo4j rather than the domain.

```bash
P="<package-path>"
H="$P/human_description.md"

# Section structure: expect exactly "## Overview" then "## Ontology".
rg -N '^## ' "$H"

# H1 must match the card title in SKILL.md's frontmatter.
rg -N -m1 '^# ' "$H"
rg -N 'neo4j-card-title:' "$P/SKILL.md"

# Banned terminology for the reference ontology.
rg -ni 'graph model|graph data model|data model|\bschema\b' "$H" \
  && echo "BLOCKER: human_description.md must say reference ontology"

# Filenames, paths, and code blocks.
rg -n 'ONTOLOGY\.json|GRAPH_MODEL\.json|QUERIES\.md|SKILL\.md|TESTS\.md|SETUP\.md|sample-data|\.csv' "$H" \
  && echo "FINDING: human_description.md names a package file"
rg -n '^```' "$H" && echo "FINDING: code block in human_description.md"

# Any mention of the sample data at all.
rg -ni 'sample|synthetic|seeded|bundled|dataset|row' "$H" \
  && echo "FINDING: human_description.md refers to the bundled data"

# Agent-directed language.
rg -ni 'the agent|the user first opens|response shape|operational constraint' "$H" \
  && echo "FINDING: agent-directed language in human_description.md"

# Every label and relationship type in the reference ontology appears in the file.
python3 - "$P" <<'PY'
import json, re, sys, pathlib
p = pathlib.Path(sys.argv[1])
m = json.loads((p / "ONTOLOGY.json").read_text())
h = (p / "human_description.md").read_text()
for label, node in m.get("nodes", {}).items():
    if node.get("label", label) not in h:
        print(f"FINDING: node {node.get('label', label)} missing from human_description.md")
    for prop in node.get("properties", {}):
        if not re.search(rf"\b{re.escape(prop)}\b", h):
            print(f"FINDING: property {label}.{prop} missing from human_description.md")
for key, rel in m.get("relationships", {}).items():
    if rel["type"] not in h:
        print(f"FINDING: relationship {rel['type']} missing from human_description.md")
    for prop in rel.get("properties", {}):
        if not re.search(rf"\b{re.escape(prop)}\b", h):
            print(f"FINDING: relationship property {rel['type']}.{prop} missing")
types = [r["type"] for r in m.get("relationships", {}).values()]
for t in set(types):
    if types.count(t) > 1:
        print(f"CHECK BY EYE: {t} joins {types.count(t)} node pairs — expect that many rows")
PY

wc -w "$H"
```

The greps over-report by design. `schema` may appear legitimately in a domain sense, `row` inside an unrelated word, a label name may coincide with ordinary prose. Read each hit rather than acting on the count — and read the whole file once straight through, which is the only check that catches a page that is accurate and still unreadable.

## 6. SKILL.md content and terminology checks

- The body is terse and agent-facing, with no duplicated runnable queries.
- An "Introducing this package" section exists and is guidance for the agent to phrase its own introduction — not verbatim copy to recite. It covers the core idea, the sample data and what it is for, what the agent can help with, and a next step. It describes the sample in general terms and does not quantify it (see 5a).
- The section describing the ontology is headed **Reference ontology**, not "Model".
- A **role map** exists in the Reference ontology section: one row per abstract role, naming the label that plays it in the reference ontology and what a substitute in another database would have to supply.
  - Every role maps to a label that exists in ONTOLOGY.json.
  - Every label the queries depend on structurally is covered by some role. A pattern resting on an unmapped label cannot be rewritten by the consuming agent — finding.
  - The third column states a requirement, not a restatement ("a value-keyed node several parties can converge on", not "an address").
  - The map has roles, not a row per node label. A map the same length as the node list is the reference ontology restated — warning.
  - It is followed by the instruction to map the user's labels onto the roles before rewriting, and to say plainly when a role has no counterpart.
- Any image URL is real or marked `TODO(review)` — never fabricated.
- Operational constraints cover write confirmation, target-database confirmation, that `@params` starting values are starting points rather than universal defaults, package-specific gotchas (versions, plugins, tuning), and — when any query carries `@sample` — the rule that `@sample` is used only when the connected database holds the bundled sample.
- Terminology, units, allowed values, directions, and identifiers are consistent across SKILL.md, QUERIES.md, ONTOLOGY.json, and the CSVs — with ONTOLOGY.json's annotations (nodes, relationships, and properties) as the reference vocabulary the other files must agree with.
- The Reference ontology section summarises rather than redefines: the authoritative meanings live in ONTOLOGY.json's annotations, and SKILL.md says so.
- SKILL.md instructs the consuming agent to treat those annotations as authoritative when explaining the reference ontology or generating Cypher, and tells it that users may say "model", "graph model", "data model" or "ontology" for the same thing.
- **Package-wide terminology.** Every package file, TESTS.md included, calls the ontology the reference ontology. "Graph model", "graph data model", "data model" or a bare "model" used as its name, and any mention of `GRAPH_MODEL.json` or `neo4j-graph-spec-version`, is a finding — and a blocker in `human_description.md`. "Schema" is correct only for the live database. Equally a finding: describing the reference ontology in OWL, RDF, reasoning, T-Box/A-Box or "axiom" terms.

```bash
P="<package-path>"
# Candidates only — read each hit. "model" is legitimate in other senses
# (a pricing model, a risk model); "schema" is legitimate for the live database.
rg -ni 'graph model|graph data model|data model|\bthe model\b|this model|GRAPH_MODEL|neo4j-graph-spec-version' \
  "$P" --glob '*.md'
rg -ni '\bOWL\b|\bRDF\b|t-box|a-box|axiom|inference|reasoner' "$P" --glob '*.md'
```

The package's own terminology line ("users may say model, graph model…") is an expected hit.

- **Any query-created relationship or label is fully defined in the Reference ontology section**, because ONTOLOGY.json cannot define it (§3, §5). The definition names the node pairs or labels it connects, every property with its graph type, which queries write it and which remove it, and states that it is absent from a freshly imported database and absent from ONTOLOGY.json by design. A package whose queries write an entity that SKILL.md does not define leaves the consuming agent unable to explain or adapt those queries — blocker. A one-line mention is not a definition.
- SKILL.md instructs the consuming agent to keep each query's `/* @... */` annotation block with the query when showing or running it, to treat it as context rather than ground truth (Cypher logic wins on conflict), and to update annotations when adapting a query.
- Limitations are stated honestly: data-quality assumptions, performance traps, false-positive sources, and the boundary between analytical leads and domain conclusions — stated as properties of the technique, not of the bundled dataset.

## 7. Reporting issues and agreeing fixes

Validation findings are decisions for the user, not silent patches. After completing sections 1–6:

1. **Classify** each finding: *blocker* (package would be rejected, fails schema validation or the spec-library check, declares a spec version other than the bundle's pin or none at all, a query's pattern cannot be produced by the bundled data, an agent-facing file makes a false claim about the user's data, `human_description.md` is missing or misnamed, or it calls the ontology anything but the reference ontology) or *warning* (works but weakens quality — vague description, untuned threshold, oversized agent-facing file).
2. **Report** them together in one summary. For each finding give: the file and location, what's wrong, why it matters, and a concrete proposed fix. Where more than one fix is reasonable, present the options with a recommendation rather than choosing silently.
3. **Ask** before applying fixes that change meaning — reference ontology changes, description changes, data regeneration, threshold changes, renames. Mechanical corrections (a typo'd field name that must match a CSV header, invalid JSON syntax, a stray row count that belongs in TESTS.md) may be fixed directly and reported.
4. **Re-run** the affected checks after fixes, and repeat until no blockers remain.

Example report shape:

```text
Blockers (3)
1. QUERIES.md §3 references Claim.amount; ONTOLOGY.json defines amountClaimed.
   Fix: rename in the query (recommended) or add the property to the reference ontology.
2. ONTOLOGY.json fails schema validation: property "vin" uses "mustExist"
   (legacy field). Fix: replace with must_exist (mechanical — fixed, please confirm).
3. QUERIES.md §7 @usage says "returns the 12 seeded ring members" — a sample-data
   claim in an agent-facing file. Fix: move the count to TESTS.md and restate the
   guidance as "raise until the group size is improbable for the portfolio in hand"
   (mechanical — fixed, please confirm).

Warnings (2)
4. Prescription.dosageMg description was inferred, not confirmed
   (TODO(review): inferred description). Options: (a) confirm with domain owner,
   (b) accept the stated reading. Recommend (a).
5. SKILL.md role map has nine rows for nine node labels — the reference ontology restated
   rather than a role map. Fix: collapse to the four or five roles the queries
   actually depend on.
```

## 8. Handoff

The handoff summary must name:

- Files created or changed.
- Checks actually run, including whether ONTOLOGY.json validated against the bundled `ontology-graph-spec.schema.json`, **the ontology graph spec version its `schema` field declares and that it matches the bundle's pin**, whether the spec-library check ran and passed, whether the destination runtime or registry test accepted it. Queries are not run; say so, and point the tester at TESTS.md.
- Every remaining `TODO(review):` with its path — calling out `inferred description` items the user has not yet confirmed.
- Any agent-facing file over the ~50,000-character guidance size, with what drove it. (TESTS.md, human_description.md and the CSVs are exempt and need no mention.)
- That `human_description.md` covers every node, relationship and property the reference ontology defines, and that **it still needs a human read** — nothing downstream validates its prose, so the handoff must say so rather than implying the automated checks cleared it.
- Any assumption that still requires domain-owner review.
