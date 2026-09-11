# Package Validation

Run these checks on a generated or edited package before handing it off. Let `<package-path>` be the package folder. Do not rely on a successful build alone: malformed packages are caught and skipped by the registry, so a broken package fails silently by never appearing.

Work through sections 1–6 (including 3b, 5a, 5b and 5c) and collect every finding — don't stop at the first failure. Then report and resolve findings with the user as described in section 7, and write the handoff described in section 8.

Two failure modes dominate. The first is **inconsistency** between model, data, and queries. The second, since the TESTS.md split, is **sample-data leakage**: concrete detail about the bundled rows appearing in a file the consuming agent reads, where it becomes a false claim about the user's data. Section 5a checks for it mechanically.

## 1. Structural checks

Required:

```text
<package-path>/SKILL.md
<package-path>/GRAPH_MODEL.json
<package-path>/QUERIES.md
<package-path>/sample-data/**/*.csv   # optional at the format level; present in any working demo
<package-path>/TESTS.md               # required whenever sample-data CSVs resolve
```

Confirm:

- All required files exist and are non-empty, and every CSV referenced by GRAPH_MODEL.json sits below `sample-data/` (at any depth — nested subdirectories are legal).
- There is no `INTRODUCTION.md` — introduction guidance lives inside SKILL.md.
- `TESTS.md` exists whenever the package bundles sample data. A package with resolving CSVs and no TESTS.md has no test oracle and cannot be verified — blocker. A package with no CSVs at all is a model template rather than a working demo; TESTS.md is then not required, and that should be a deliberate choice the handoff names.
- `TESTS.md` is **not** indexed in SKILL.md's Supporting files table, and no agent-facing file instructs the agent to read it. Any mention is worth reviewing; an instruction to load it defeats the split and is a blocker.
- The folder name (`skillId`) is kebab-case and stable.
- Supporting files beyond the required set use only `.md` or `.cypher`, and each is indexed in SKILL.md with a stated purpose so the agent knows when to load it. An unindexed supporting file is a warning: index it, fold it in, or remove it. `TESTS.md` is the sole exemption.
- Readable files stay under ~50,000 characters. This is guidance, not an enforced limit — exceeding it is a *warning*, not a blocker — but note that larger files consume more of the consuming agent's context and increase the need for a more powerful model. Report any file over the target with its size and whether annotations, queries, or prose drove the growth, so the user can decide. **`TESTS.md` and the sample-data CSVs are exempt** — neither reaches the consuming agent, so size costs nothing there. A large TESTS.md is not a finding; a large QUERIES.md usually means material that belongs in TESTS.md has not moved.
- Paths use forward slashes with no absolute, URL, backslash, empty, `.` or `..` segments.
- No file references a bundled file that does not exist.

```bash
P="<package-path>"

for f in SKILL.md GRAPH_MODEL.json QUERIES.md; do test -s "$P/$f" || echo "MISSING: $f"; done

# Sample data at any depth below sample-data/ requires a TESTS.md.
find "$P/sample-data" -name '*.csv' 2>/dev/null | grep -q . \
  && { test -s "$P/TESTS.md" || echo "BLOCKER: sample data present, TESTS.md missing"; }

# Agent-facing files: any mention of TESTS.md is worth a look; an instruction to
# read it is a blocker. Reviewed by eye — the grep only finds candidates.
AGENT_FACING=$(find "$P" -maxdepth 1 -name '*.md' ! -name 'TESTS.md')
rg -n 'TESTS\.md' $AGENT_FACING | tee /tmp/tests-mentions.txt
rg -ni 'read|load|see|consult|refer|open' /tmp/tests-mentions.txt \
  && echo "BLOCKER: an agent-facing file instructs the agent to read TESTS.md"

rg -n "TODO\(review\)" "$P"
wc -c "$P"/*.md "$P"/GRAPH_MODEL.json
```

## 2. Frontmatter and parser checks

- SKILL.md begins with valid YAML frontmatter delimited by `---` and has a non-empty body.
- `name` is kebab-case, 1–64 characters.
- `description` is non-empty, specific, and at most 1024 characters; it should read as trigger text (industry, use cases, capabilities).
- `metadata` values are all strings; `neo4j-card-title`, `neo4j-card-category`, and `neo4j-card-description` are non-empty.
- **`neo4j-card-category` is one of the allowed values, matched exactly** — `Financial Services`, `Insurance`, `Healthcare & Life Sciences`, `Manufacturing`, `Cybersecurity`, `Industry Agnostic`, or the legacy `General`, `Real-time risk detection`, `Supply Chain`. This is a blocker: the destination validates the field against this closed set and drops the whole package when it fails, with no user-visible error. A descriptive-but-unlisted value is the trap — `Investment Banking` reads perfectly and is rejected. Prefer a non-legacy value for new packages.
- **No `neo4j-icon-category` key is present.** The field was removed from every package and is referenced nowhere in the destination; emitting it reintroduces a key nothing consumes.
- `neo4j-graph-spec-version` is present and non-empty, recording the graph spec the package was built against. A missing value is a blocker — an unversioned package cannot be checked against the schema that will validate it (section 3).
- Invalid YAML or missing required metadata rejects the package.

## 3. Graph model checks

[GRAPH_SPEC_FORMAT.md](GRAPH_SPEC_FORMAT.md) is the contract; its authority is `graph-spec.schema.json`, bundled with this skill. **Validate against that file and nothing else.** Never fetch a schema over the network, and never treat a remote revision as more current — a package's graph model is bound to the spec version this bundle is pinned to, and silently validating against a different one is the failure this rule exists to prevent.

First verify JSON syntax, then validate against the bundled schema. The snippet needs `jsonschema` 4.x or newer — the spec declares draft 2020-12, which 3.x cannot load, and some runners still ship 3.2.0 (`pip install -U jsonschema`):

```bash
P="<package-path>"
S="<skill-path>"   # this skill's own folder, where graph-spec.schema.json sits

node -e 'JSON.parse(require("node:fs").readFileSync(process.argv[1], "utf8"))' "$P/GRAPH_MODEL.json"

test -s "$S/graph-spec.schema.json" \
  || { echo "BLOCKER: bundled graph-spec.schema.json missing from $S"; exit 1; }

python3 -c "
import json, jsonschema
schema = json.load(open('$S/graph-spec.schema.json'))
model  = json.load(open('$P/GRAPH_MODEL.json'))
jsonschema.validate(model, schema)
print('schema OK')
"
```

The schema sets `additionalProperties: false` throughout, so any off-schema key fails here — including superseded fields (`nullable`, the plural `keys`, lowercase mapping types). A schema failure is a blocker.

**Schema validity is necessary, not sufficient.** The schema is generated from the runtime library's own type definitions, and where the library hand-writes a deserializer that departs from its generated form, the schema will happily pass a model the runtime cannot read. The `extensions` container is exactly that case (GRAPH_SPEC_FORMAT.md, Pipeline caveats), and a package that fails this way is not rejected loudly — it is silently dropped from the destination's catalogue. That is why the runtime gate below is mandatory.

### Spec version pin

The package must declare the graph spec it was built against, and it must be the one this bundle carries. A mismatch means the model was authored against a different contract than the schema now validating it — the model may be silently wrong in ways the schema cannot see. **A mismatch is a blocker.**

```bash
P="<package-path>"
S="<skill-path>"

# The bundle's pin — the single source of truth, declared in GRAPH_SPEC_FORMAT.md.
PINNED=$(sed -n 's/^graph-spec-version: *//p' "$S/GRAPH_SPEC_FORMAT.md" | head -1)

# The package's declaration, from SKILL.md's frontmatter block only.
DECLARED=$(awk '/^---$/ { n++; next } n == 1' "$P/SKILL.md" \
           | sed -n 's/.*neo4j-graph-spec-version: *//p' | tr -d "\"' " | head -1)

if   [ -z "$PINNED"   ]; then echo "BLOCKER: no graph-spec-version pin found in $S/GRAPH_SPEC_FORMAT.md"
elif [ -z "$DECLARED" ]; then echo "BLOCKER: $P/SKILL.md declares no neo4j-graph-spec-version"
elif [ "$PINNED" != "$DECLARED" ]; then
  echo "BLOCKER: spec version mismatch — package declares '$DECLARED', bundle is pinned to '$PINNED'"
else
  echo "spec version OK: $DECLARED"
fi
```

Resolving a mismatch is a decision for the user, never a silent edit. Either the package predates a spec update and needs migrating to the pinned version, or the pin itself is wrong. Do not "fix" it by rewriting the package's declared version to match the bundle — that asserts a migration that has not happened.

Then inspect consistency the schema cannot see:

- `version` is `"4.0.0"` (the format version — distinct from the pinned spec version checked above).
- Node and relationship keys are readable and stable (label-based for nodes, camelCase for relationships); every key referenced by relationships, mappings, and display exists.
- Every node has exactly one `key: true` property (or a composite `KEY` constraint instead); `key: true` is never combined with `unique`/`mustExist` on the same property.
- `mustExist` (not the old `nullable`) marks required non-key properties.
- Mappings use `"type": "NodeMapping"` / `"RelationshipMapping"` with `mode: "MERGE"`; each node mapping's `key` array matches its node's `key: true` property.
- Every mapping table exists in `tables`; every mapping field exists in that table's `fields`; every mapped property exists on its node or relationship.
- Relationship mapping directions match their relationship definitions, and endpoint fields resolve to node identifiers.
- Table entries use `source: "local"`, keys equal to the exact CSV filenames, and fields declared `"type": "string"` keyed by exact CSV headers; graph property types are correct for query behaviour (numeric comparisons on numeric types, temporal operations on temporal types).
- **Every table field sets `"name"` to its own key** — checked mechanically in 3b. The importer data model holds table fields as an array, so a field-map key with no `name` is dropped on encode and the package fails to load; a `name` that disagrees with its key leaves mappings pointing at a field the schema does not declare. Neither case throws, so the runtime gate will not find it.
- `display.nodes` has `x`/`y` for every node.
- Valid JSON only: no comments, trailing commas, or unresolved placeholders.

### The runtime gate (required)

**A model that has not been decoded by the destination runtime is not validated.** Schema validation and every eyeball check above can pass on a package that the destination silently drops. Run this gate on every package, every time; a package that has not been through it does not ship, and "no runtime available to test against" is a finding to report, not a reason to skip.

For Aura/upx, the destination is `graphSpecJsonToDataModelAndVisualisation` — the same call the app's package registry makes. Drop a temporary test into a checked-out upx repo and run it:

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
      const { dataModel } = graphSpecJsonToDataModelAndVisualisation(readFileSync('$P/GRAPH_MODEL.json', 'utf8'));

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

Note the assertion is written to surface the *message*, not just a pass/fail — a failing run prints the runtime's own diagnosis (`Unknown Extension type. Keys: [type, value]`, `Missing required labels at …`, `Version must be specified`), which is what tells you which rule the model broke. Delete the temp file afterwards: it lives in someone else's repo.

The gate covers the graph model's decode *and* the coherence of what it encodes — a decode that throws nothing can still produce a lossy model, which is exactly how the table-field `name` defect reached production. It does not cover the package's SKILL.md frontmatter, card metadata, or CSV resolution; those are checked separately by the destination's own package parser, and sections 1, 2 and 4 stand in for that.

A gate that passes is still not proof of a working package. It proves the model survives the destination's decode and encode with its field names intact; it says nothing about whether those names match the bundled CSVs (section 4) or whether the data supports the queries (sections 5 and 5c).

**If the runtime rejects a schema-valid model, stop.** Report it to the user with the exact error; do not strip fields until it passes. There are three explanations, and they call for different responses:

1. **The model breaks a documented rule.** Fix the model.
2. **The schema and the runtime disagree at the same pinned version** — the `extensions` case. Fix the *pipeline* (this skill), not just the one package, so the next package does not repeat it.
3. **The runtime has moved past the pin.** Raise it as a spec-update decision: replace `graph-spec.schema.json`, update the pin in GRAPH_SPEC_FORMAT.md, re-validate and migrate every existing package. Never edit a model to fit an unpinned runtime.

Do not assume (3). It was the only explanation this document previously offered, and the first real failure was a (2).

## 3b. Annotation checks

Annotations are tested model content, not decoration — check them against the same consistency standard as everything else:

- The spec root has a non-empty `name` and `description`.
- Every node, every relationship, and every property (node and relationship) has a non-empty, specific `description`. A description that only restates the name ("the dosage") is a warning: it gives an agent nothing.
- Every numeric, temporal, or coded property's description states its unit, encoding, or scope (per-what, measured how, which code system).
- Relationship descriptions read in the from→to direction; where one relationship type is reused between node pairs, each entry's description states its distinct meaning.
- Descriptions are worded normatively ("expected to carry…") where the model doubles as a template for user data.
- **No `extensions` key appears anywhere in the model** — this is a blocker, not a style note. The pinned runtime rejects every encoding of the extensions container and drops the whole package, so a model carrying one cannot load at all. See GRAPH_SPEC_FORMAT.md's Pipeline caveats for why the bundled schema nonetheless permits it.
- Every property description carrying a sample ends with a `` e.g. `<value>`. `` clause, and that `<value>` appears **verbatim** in the mapped CSV column — check mechanically, not by eye. A sample absent from the data is a blocker: either the sample or the data is wrong.
- Sample values illustrate the *shape* of a value, not the dataset. A sample that only makes sense as a claim about the bundled rows (a seeded ring member's identifier chosen because it is a ring member) is a warning — pick an unremarkable value instead. This is the one place sample data legitimately reaches the consuming agent, and it should carry no signal beyond format.
- Stated units and encodings are consistent with the CSV value ranges (a "milligrams" property whose values run 0.001–0.9 is probably grams); stated enumerations match the distinct values actually present.
- Every multiplicity claim in a relationship description holds in the sample data (count endpoint occurrences per node). Prose claims are still checkable claims — read each relationship description and test what it asserts.
- The optional `name` fields on nodes, properties, and relationships are unset — root `name` only. Table fields are the exception: each one must set `name` to its own key (see section 3), and the scan below treats a missing or mismatched value as a blocker.
- Inferred descriptions the user has not confirmed are marked `TODO(review): inferred description` — an unmarked, unconfirmed stipulation is a warning.

```bash
node -e '
const SAMPLE = /e\.g\. `([^`]+)`\.?\s*$/;
const NUMERIC_OR_CODED = /^(INTEGER|FLOAT|DATE|ZONED |LOCAL |DURATION|BOOLEAN)/;
const m = JSON.parse(require("node:fs").readFileSync(process.argv[1], "utf8"));

// Blocker: the extensions container is unreadable by the pinned runtime, at any depth.
(function scan(o, path) {
  if (o === null || typeof o !== "object") return;
  for (const [k, v] of Object.entries(o)) {
    if (k === "extensions") console.log(`BLOCKER extensions block at ${path}`);
    scan(v, `${path}.${k}`);
  }
})(m, "$");

// Blocker: a table field without a name equal to its key is dropped or misdeclared on encode.
for (const [t, tbl] of Object.entries(m.tables ?? {})) {
  for (const [k, f] of Object.entries(tbl.fields ?? {})) {
    if (f.name === undefined) console.log(`BLOCKER table field has no name: ${t}.${k}`);
    else if (f.name !== k) console.log(`BLOCKER table field name != key: ${t}.${k} declares name "${f.name}"`);
  }
}

if (!m.name || !m.description) console.log("WARN root missing name/description");

const checkProps = (owner, props) => {
  for (const [p, def] of Object.entries(props ?? {})) {
    if (!def.description) { console.log(`WARN no description: ${owner}.${p}`); continue; }
    const hasSample = SAMPLE.test(def.description);
    if (NUMERIC_OR_CODED.test(def.type ?? "") && !hasSample)
      console.log(`WARN no "e.g. \`...\`" sample: ${owner}.${p} (${def.type})`);
    if (hasSample) console.log(`SAMPLE ${owner}.${p} = ${def.description.match(SAMPLE)[1]}`);
  }
};

for (const [id, n] of Object.entries(m.nodes ?? {})) {
  if (!n.description) console.log(`WARN no description: node ${id}`);
  checkProps(id, n.properties);
}
for (const [id, r] of Object.entries(m.relationships ?? {})) {
  if (!r.description) console.log(`WARN no description: relationship ${id} (${r.type})`);
  checkProps(id, r.properties);
}
' "<package-path>/GRAPH_MODEL.json"
```

Any `BLOCKER` line stops the build: fix the model, do not proceed to the runtime gate. Both blockers this scan raises — the extensions container and table-field names — are invisible to the gate, so the scan is the only thing standing between them and a package that installs but does not work.

The `SAMPLE` lines are the input to the verbatim check. Confirming each one needs the mapping resolved (property → mapping field → CSV column); script that per package alongside the endpoint-resolution checks in section 4. Multiplicity claims are prose and have no fixed form — read each relationship description and test what it asserts against endpoint counts.

## 4. CSV and mapping checks

For every CSV referenced in `tables` or `mappings[].table`:

- The file resolves unambiguously below `sample-data/` (basename match, or exact relative path; duplicate basenames need explicit paths).
- Headers exactly match the table's field keys, including case.
- Every row has the expected column count; values with delimiters, quotes, or newlines are CSV-escaped.
- Identifier fields are present. Rows may repeat a node key — mode `MERGE` merges them into one node — but every mapped node property must then carry the same value on every row sharing that key; conflicting values make the imported property nondeterministic.
- Every non-empty relationship endpoint value resolves to a node row. An empty endpoint value creates no relationship — a legitimate pattern for chain ends (e.g. a last encounter with no `NEXT`) — but should be deliberate, not accidental.
- Dates, numbers, and booleans convert cleanly to their declared graph property types.
- Values conform to their property's confirmed `description` — unit, encoding, scope, and any stated enumeration (cross-check with section 3b).
- The deliberately seeded signal patterns described in **TESTS.md's** sample-data profile actually exist in the data.

A package where only some referenced CSVs resolve is invalid.

## 5. Query checks

For QUERIES.md (and any supporting `.cypher` file):

- The preamble states prerequisites in one place. It does **not** profile the sample data — row counts and seeded signals belong in TESTS.md.
- An **"Adapting these queries"** section appears near the top: read the live schema, map onto SKILL.md's role map, rewrite, update the annotation block. Missing section is a finding.
- Every query opens with a `/* @... */` annotation block **before any query logic** (a Cypher block comment, so it can never execute), carrying the required tags: `@name` matching the query's `##` heading, `@description`, `@params`, `@prerequisites`, `@returns`, `@usage`, `@tags`. No `@version`. A missing block or missing required tag is a finding.
- `@params` matches the query's actual parameters exactly: every `$parameter` in the Cypher appears in `@params` with its meaning, and `@params` names nothing the query doesn't use (`None` for parameterless queries). Mechanically checkable — do it mechanically.
- `@params` is **one line per parameter**, each starting at the parameter name, with wrapped text indented past it. A second parameter beginning at the same indent as the first one's continuation lines is unparseable and defeats the check above — finding.
- Every parameter that gates a result set carries a **starting point with a data-agnostic justification**: either a concrete value justified by what the parameter does, or a stated procedure for deriving one where no number transfers between datasets ("take the portfolio's upper quartile"). A gating threshold with neither is a finding — the query is unusable without opening TESTS.md. A threshold justified by the sample is a leak, caught in 5a.
- Labels, relationship types, directions, and properties match GRAPH_MODEL.json exactly.
- Annotation blocks use the model's vocabulary: where `@description`, `@params`, or `@usage` explains a property or relationship, its wording, unit, scope, and direction agree with that element's GRAPH_MODEL.json `description`. An annotation that contradicts a model description is a blocker — the two are one contract.
- Variable-length traversals have explicit bounds; thresholds and limits are called out in `@usage` as tunable, in general terms.
- No per-query schema-drift prose. The adapting section states the procedure once; repeating it per query is boilerplate. An optional `@pattern` tag on a query whose shape isn't recoverable from its Cypher is fine — on every query it is padding, and a warning.
- No design rationale between the queries (why the model departs from a source page, why a query differs from a published one). That belongs in SKILL.md's Model section or a supporting rationale file.
- APOC or GDS use is confined to a clearly labelled section with prerequisites stated.
- The node-key constraints implied by GRAPH_MODEL.json (`key: true` properties and composite `KEY` constraints) appear at the end as a schema reference, introduced by section prose; the individual statements need no annotation blocks.

Best validation, when a disposable database is available:

1. Import the bundled CSVs.
2. Run every query with the parameters its TESTS.md section states.
3. Confirm each satisfies the **Invariant** in its TESTS.md section, and note any drift from **Observed**. Every query must return the deliberately seeded pattern, and stricter queries return subsets of broader ones.
4. Mark any query you could not execute with a `TODO(review): unproven query` line inside its annotation block, and list it in TESTS.md with the reason.

An invariant that fails is a blocker. An observed count that has drifted while the invariant still holds is not a bug — it means the data was regenerated. Update the observed figures and say so in the handoff.

Never run imports or writes without explicit user confirmation and a confirmed disposable target.

## 5a. Sample-data leakage checks

Everything the consuming agent reads must stay true on data that is not yours. Scan SKILL.md, QUERIES.md, SETUP.md and any supporting file for:

- Row counts, totals, or "N rows" claims of any kind.
- Identifiers that only exist in the bundled CSVs — seeded entity IDs, names, addresses, account numbers.
- Thresholds or limits justified by the bundled data ("4 returns the seeded ring", "tuned to the sample profile").
- Statistical claims about the dataset ("no false positives", "the largest legitimate group is 3").
- Any sentence that would read as false, or as a lie, if the reader's database held their own data.

The mechanical version: pull the identifier-shaped tokens out of the CSVs and grep the agent-facing files for them.

```bash
P="<package-path>"
AGENT_FACING=$(find "$P" -maxdepth 1 -name '*.md' ! -name 'TESTS.md')

# Every field of every CSV, at any depth, stripped of CRs and quotes.
# Adapt the identifier pattern to this package's own key format.
find "$P/sample-data" -name '*.csv' -exec cat {} + \
  | tr -d '\r' | tr ',' '\n' | tr -d '"' \
  | grep -Eo '^[A-Z]{2,}-[0-9]+$' | sort -u > /tmp/seeded-ids.txt

if [ -s /tmp/seeded-ids.txt ]; then
  rg -nF -f /tmp/seeded-ids.txt $AGENT_FACING \
    && echo "BLOCKER: seeded identifier in an agent-facing file"
else
  echo "NOTE: identifier pattern matched nothing — adapt it to this package's key format"
fi

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

Two hit classes are correct and expected. SKILL.md's "Introducing this package" section
may describe the sample *in general terms* ("synthetic data that deliberately seeds the
patterns the queries look for"); QUERIES.md's prerequisites may name the bundled CSVs as
one of the things that can be imported. Both say the sample exists and what it is for.
Neither may quantify it, name anything in it, or imply the reader's database contains it.

A leak is a blocker where it makes a factual claim (counts, identifiers, statistics) and a warning where it is merely a stale framing.

## 5b. Post-import setup checks

When `SETUP.md` exists:

- It contains **no node-key constraints** — Import creates those from GRAPH_MODEL.json's key definitions, and recreating them (or `UNIQUE` variants) conflicts with the existing `KEY` constraints. This is the single most common setup mistake.
- Only statements that a bundled query actually depends on (or a clearly optional section); nothing speculative.
- One statement per ```` ```cypher ```` block; required statements first; recommended and optional ones clearly marked.
- Every statement opens with a `/* @... */` annotation block: `@name`, `@description`, and `@usage` naming the dependent queries and the effect if skipped.
- The file opens with the agent rules: explain before running, confirm the target, caveat results if declined.
- SKILL.md's Operational Constraints reference SETUP.md with its statement count.
- Any statement duplicated in QUERIES.md as a reference template says so in both places, with a run-once instruction.
- TESTS.md's "How to run" names the SETUP.md statements the queries depend on.

When `SETUP.md` is absent:

- SKILL.md states explicitly that no post-import setup is required.
- No query template depends on schema Import doesn't create — cross-check every index, label, and property the queries touch against GRAPH_MODEL.json and the import behaviour. A dependency with no home is a blocker: add SETUP.md or fix the query.

## 5c. TESTS.md checks

TESTS.md is the oracle. It is never loaded by the runtime, so it is exempt from the size target and free to be as concrete as the work requires — but it must be complete and it must pair with QUERIES.md.

- A "How to run" preamble: disposable database required, CSVs imported through the Import flow from GRAPH_MODEL.json, and any SETUP.md statements that must run first.
- A sample-data profile: row counts per label and relationship type, the seeded signals in full, and the deliberate background noise. This is the material removed from QUERIES.md — confirm it actually landed here rather than being deleted.
- **Heading parity with QUERIES.md.** Every query's `##` heading has an identically titled `##` section in TESTS.md, and vice versa. Mechanically checkable — do it mechanically.
- Every query section states its **Parameters** and an **Invariant**. A section with observed numbers but no invariant is a finding: it breaks on the next data regeneration and the breakage looks like a query fault.
- Invariants are expressed in terms of the seeded design ("returns the twelve Ring A claimants and no unseeded claimant"), not as bare counts. A bare row count is an observation, not an invariant.
- **Observed** figures carry a date or data version, so a later reader can tell whether they are stale.
- A query that could not be executed still has **its own** `##` section, saying what it was not run against and why, and carries the matching `TODO(review): unproven query` in its QUERIES.md annotation block. The two must agree. A single catch-all "queries not executed" heading is a finding: it breaks parity and hides which query is unverified.

Both files carry headings the other does not — prerequisites and the adapting section on one side, how-to-run and the profile on the other, plus any APOC/GDS section heading and the closing schema reference. Exclude those, then compare what remains; the exclusion lists are per-package, so edit them to match.

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

## 6. SKILL.md content checks

- The body is terse and agent-facing, with no duplicated runnable queries.
- An "Introducing this package" section exists and is guidance for the agent to phrase its own introduction — not verbatim copy to recite. It covers the core idea, the sample data and what it is for, what the agent can help with, and a next step. It describes the sample in general terms and does not quantify it (see 5a).
- A **role map** exists in the Model section: one row per abstract role, naming the label that plays it in this model and what a substitute in another schema would have to supply.
  - Every role maps to a label that exists in GRAPH_MODEL.json.
  - Every label the queries depend on structurally is covered by some role. A pattern resting on an unmapped label cannot be rewritten by the consuming agent — finding.
  - The third column states a requirement, not a restatement ("a value-keyed node several parties can converge on", not "an address").
  - The map has roles, not a row per node label. A map the same length as the node list is the model restated — warning.
  - It is followed by the instruction to map the user's labels onto the roles before rewriting, and to say plainly when a role has no counterpart.
- Any image URL is real or marked `TODO(review)` — never fabricated.
- Operational constraints cover write confirmation, target-database confirmation, that `@params` starting values are starting points rather than universal defaults, and package-specific gotchas (versions, plugins, tuning).
- Terminology, units, directions, and identifiers are consistent across SKILL.md, QUERIES.md, GRAPH_MODEL.json, and the CSVs — with GRAPH_MODEL.json's `description` annotations (nodes, relationships, and properties) as the reference vocabulary the other files must agree with.
- The Model section summarises rather than redefines: the authoritative meanings live in the model's descriptions, and SKILL.md says so.
- SKILL.md instructs the consuming agent to treat the model's descriptions as authoritative when explaining the model or generating Cypher.
- SKILL.md instructs the consuming agent to keep each query's `/* @... */` annotation block with the query when showing or running it, to treat it as context rather than ground truth (Cypher logic wins on conflict), and to update annotations when adapting a query.
- Limitations are stated honestly: data-quality assumptions, performance traps, false-positive sources, and the boundary between analytical leads and domain conclusions — stated as properties of the technique, not of the bundled dataset.

## 7. Reporting issues and agreeing fixes

Validation findings are decisions for the user, not silent patches. After completing sections 1–6:

1. **Classify** each finding: *blocker* (package would be rejected, fails schema validation, declares a spec version other than the bundle's pin or none at all, a query fails or violates its invariant, or an agent-facing file makes a false claim about the user's data) or *warning* (works but weakens quality — vague description, untuned threshold, unproven query, oversized agent-facing file).
2. **Report** them together in one summary. For each finding give: the file and location, what's wrong, why it matters, and a concrete proposed fix. Where more than one fix is reasonable, present the options with a recommendation rather than choosing silently.
3. **Ask** before applying fixes that change meaning — schema changes, description changes, data regeneration, threshold changes, renames. Mechanical corrections (a typo'd field name that must match a CSV header, invalid JSON syntax, a stray row count that belongs in TESTS.md) may be fixed directly and reported.
4. **Re-run** the affected checks after fixes, and repeat until no blockers remain.

Example report shape:

```text
Blockers (3)
1. QUERIES.md §3 references Claim.amount; GRAPH_MODEL.json defines amountClaimed.
   Fix: rename in the query (recommended) or add the property to the model.
2. GRAPH_MODEL.json fails schema validation: property "vin" uses "nullable"
   (superseded field). Fix: replace with mustExist (mechanical — fixed, please confirm).
3. QUERIES.md §7 @usage says "returns the 12 seeded ring members" — a sample-data
   claim in an agent-facing file. Fix: move the count to TESTS.md and restate the
   guidance as "raise until the group size is improbable for the portfolio in hand"
   (mechanical — fixed, please confirm).

Warnings (2)
4. Prescription.dosageMg description was inferred, not confirmed
   (TODO(review): inferred description). Options: (a) confirm with domain owner,
   (b) accept the stated reading. Recommend (a).
5. SKILL.md role map has nine rows for nine node labels — the model restated
   rather than a role map. Fix: collapse to the four or five roles the queries
   actually depend on.
```

## 8. Handoff

The handoff summary must name:

- Files created or changed.
- Checks actually run, including whether GRAPH_MODEL.json validated against the bundled `graph-spec.schema.json`, **the graph spec version the package declares and that it matches the bundle's pin**, whether the destination runtime or registry test accepted it, and whether queries were executed against a database.
- For queries that were executed: whether each satisfied its TESTS.md invariant, and whether observed figures were refreshed.
- Every remaining `TODO(review):` with its path — calling out `inferred description` items the user has not yet confirmed.
- Any query not executed against sample data, cross-checked against TESTS.md's list of the same.
- Any agent-facing file over the ~50,000-character guidance size, with what drove it. (TESTS.md and CSVs are exempt and need no mention.)
- Any assumption that still requires domain-owner review.
