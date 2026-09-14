# Graph Spec JSON Format

This skill is used to create a package's `GRAPH_MODEL.json` which describes the graph schema, CSV-to-graph mappings, source tables, visual layout, and semantic annotations for a use case.

**Authority:** `graph-spec.schema.json`, bundled with this skill, is the contract. It is the *sole* authority for the format — never fetch, consult, or validate against any other copy of the graph spec, and never treat a remote revision as more current. The bundled file overrides any other description of the format, including older revisions of this file. It sets `additionalProperties: false` at every level: any key not defined below is a validation failure, so nothing off-schema survives.

**Pinned version.** A package's graph model is bound to the graph spec it was built against. This bundle is pinned to:

```text
graph-spec-version: 4.0.0-alpha.25
```

That line is the single source of truth for the pin. Every package this skill builds records the same value in its SKILL.md `metadata.neo4j-graph-spec-version`, and VALIDATION.md treats a package whose recorded value differs as a blocker.

Do not change the pin as a side effect of any other work. Moving to a newer spec is a separate, deliberate exercise: replace `graph-spec.schema.json`, update the line above, then re-validate and migrate every existing package against the new schema. The format version inside a model (`version: "4.0.0"`, below) is *not* a substitute — it has stayed constant across many incompatible revisions, so it cannot identify what a package was built against.

The graph model is not only a structural contract — it is the primary semantic artifact an agent reasons over. It is the only package artifact that crosses into the user's database via Import, so meaning carried only in SKILL.md prose or query annotations is lost at exactly the moment it becomes most useful: when a user has mapped their own data onto the template and an agent is working from the resulting schema. Annotate the model per the [Annotations](#annotations-for-agent-reasoning) section.

## Top-level shape

```json
{
  "version": "4.0.0",
  "name": "Prescription Safety",
  "description": "Relates patients, prescriptions, and clinicians to surface over-prescription patterns.",
  "nodes": {},
  "relationships": {},
  "tables": {},
  "mappings": [],
  "display": {
    "nodes": {}
  }
}
```

| Field           | Purpose                                                            |
| --------------- | ------------------------------------------------------------------ |
| `version`       | Graph-spec *format* version. Use `"4.0.0"`. This is not the pin — see Pinned version above. |
| `name`          | Human-readable model name.                                         |
| `description`   | One or two sentences: the domain, and what the model answers.      |
| `nodes`         | Node definitions keyed by readable stable IDs.                     |
| `relationships` | Relationship definitions keyed by readable stable IDs.             |
| `tables`        | Input table definitions and their available fields.                |
| `mappings`      | Rules mapping table fields to nodes and relationships.             |
| `display`       | Visual coordinates used when presenting the model graphically.     |

**Entity keys are readable.** Key each node by its label (`"Prescription"`) and each relationship by a descriptive camelCase ID (`"prescribedBy"`). These keys connect definitions to mappings and display data, and readable keys make every cross-reference self-explanatory to agents. Keep them stable.

## Nodes

Each node entry needs:

- A readable stable key, normally equal to its label
- A `label` (single-label shorthand) — or `labels: {identifier, implied, optional}` for multi-label nodes; packages normally use `label`
- A `description` — the human/agent explanation of what the node represents
- Property definitions, with `key: true` on the identifier

```json
{
  "Prescription": {
    "label": "Prescription",
    "description": "An authorisation to dispense a specific medication to a patient, issued by a clinician.",
    "properties": {
      "prescriptionId": {
        "type": "STRING",
        "description": "Unique identifier for the prescription. Expected to be stable across refills.",
        "key": true
      },
      "dosageMg": {
        "type": "FLOAT",
        "description": "Dose per administration in milligrams. Not a daily total and not a free-text sig. e.g. `250`."
      }
    }
  }
}
```

### Node properties

The key in `properties` is the Neo4j property name.

- `type` — a value from the spec's `Neo4jType` enum. Common in packages: `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `DATE`, `ZONED DATETIME`, `POINT`. The enum also covers `LIST<...>`, `VECTOR<...>` (with `dimension`), sized numerics (`INTEGER8/16/32`, `FLOAT32`), `DURATION`, times, and `UUID`. Match types to query behaviour: numeric comparisons require numeric types, temporal operations temporal types.
- `description` — required by this pipeline on every property; see [Annotations](#annotations-for-agent-reasoning).
- `key: true` — marks the node's single-property identifier. It implies existence and uniqueness (a node key), so do **not** combine it with `unique` or `mustExist`. Exactly one property per node carries it.
- `mustExist` / `unique` — for non-key requirements. `mustExist: true` means the property is required (this replaces the old `nullable` field, with inverted sense — there is no `nullable` in the spec).
- `dimension` — only for `VECTOR<...>` types.
- A **sample value** in the `description`, as a trailing `` e.g. `...` `` clause taken verbatim from the mapped CSV column. See [Annotations](#annotations-for-agent-reasoning).

**Do not write an `extensions` block.** The spec schema defines one, but the pinned runtime cannot read any encoding of it — see [Pipeline caveats](#pipeline-caveats).

### Node constraints and indexes

`key: true` covers the standard single-property node identifier. Use the `constraints` block only for composite keys or additional requirements:

```json
"constraints": {
  "flight_leg_key": {
    "type": "KEY",
    "label": "FlightLeg",
    "properties": ["flightNo", "departureDate"]
  }
}
```

Constraint types: `EXISTS`, `KEY`, `PROPERTY_TYPE`, `UNIQUE`. Leave `indexes` empty: the Import pipeline is not known to create them from the model, so index needs belong in `SETUP.md` where the agent applies them with consent.

## Relationships

Each relationship entry needs:

- A readable stable key, e.g. `"prescribedBy"`
- A Neo4j relationship `type`
- A `description` — required by this pipeline: what the connection means, read in the from→to direction
- `from` and `to` targets referencing node keys
- Optional relationship properties (same shape as node properties, including `description`)
- Any multiplicity expectation stated **in the `description`**, not as an extension

```json
{
  "prescribedBy": {
    "type": "PRESCRIBED_BY",
    "description": "Links a prescription to the clinician who authorised it. Exactly one clinician per prescription; a clinician may authorise many prescriptions, or none.",
    "from": { "node": "Prescription" },
    "to": { "node": "Clinician" },
    "properties": {
      "confidence": {
        "type": "FLOAT",
        "description": "Extraction confidence from the source system, 0.0–1.0. e.g. `0.92`.",
        "mustExist": true
      }
    }
  }
}
```

- `from.node` and `to.node` reference keys in `nodes`. A relationship may connect two different node definitions or a node definition to itself. (The spec also allows label-only targets via `label`/`property`; packages use `node` references.)
- **Relationship descriptions are core spec fields — always write one.** When the same relationship `type` string is reused between different node pairs, each reuse is its own entry with its own key and its own description stating that instance's distinct meaning.
- **Multiplicity goes in the `description`**, in prose, stated in both directions — "Exactly one clinician per prescription; a clinician may authorise many prescriptions, or none." State it only when the sample data actually satisfies it: cardinality is a checkable claim, not decoration, and VALIDATION.md §3b checks it against the bundled rows whether it is written in prose or not.
- Leave relationship `constraints` and `indexes` empty for the same reasons as nodes.

## Tables

`tables` describes each CSV used by a mapping:

```json
{
  "prescriptions.csv": {
    "source": "local",
    "fields": {
      "prescriptionId": { "name": "prescriptionId", "type": "string" },
      "clinicianId": { "name": "clinicianId", "type": "string" },
      "dosageMg": { "name": "dosageMg", "type": "string" }
    }
  }
}
```

- The table key is the exact CSV filename and must match the `table` value used by mappings.
- `source` is `"local"` for bundled CSV input.
- Each field key must match the CSV header exactly, including case. Declare CSV fields as `"type": "string"` — the mapping's target property converts values to graph types.
- **Every field must also carry an explicit `"name"` equal to its own key.** This is the one place the optional `name` is mandatory, and omitting it fails silently: the importer data model represents table fields as an *array*, so the field-map key has nowhere to live and is simply dropped — the field encodes as `{ "sample": "", "recommendedType": … }` with no name at all, and the package breaks when loaded. A `name` that differs from its key is worse than none: the schema still declares the field under the wrong name while mappings go on referencing the key, leaving a dangling reference. The runtime gate cannot catch either case — neither throws.
- The spec's richer field facets (`size`, `suggested`, `supported`) and table keys (`primaryKeys`, `foreignKeys`) describe RDBMS sources; omit them for bundled CSVs.
- Include endpoint fields used only to connect relationships, even when they do not become graph properties.

If sample CSVs are bundled, place them under `sample-data/`. Keep table references unambiguous.

## Mappings

Mappings are a discriminated union on `type`: `"NodeMapping"`, `"RelationshipMapping"` (also `"QueryMapping"` and `"LabelMapping"`, which packages do not use).

### Node mappings

```json
{
  "type": "NodeMapping",
  "node": "Prescription",
  "table": "prescriptions.csv",
  "mode": "MERGE",
  "key": ["prescriptionId"],
  "properties": {
    "prescriptionId": { "field": "prescriptionId" },
    "dosageMg": { "field": "dosageMg" }
  }
}
```

- `node` references a key in `nodes`; `table` references a key in `tables`.
- `mode` is `"MERGE"` for packages — rows may repeat a key and merge into one node.
- `key` (an array — the old `keys` name is gone) lists the graph properties that identify the node; it matches the property marked `key: true`.
- Every mapped graph property must exist on the node; every referenced field must exist in the table.

### Relationship mappings

```json
{
  "type": "RelationshipMapping",
  "relationship": "prescribedBy",
  "table": "prescriptions.csv",
  "mode": "MERGE",
  "key": [],
  "from": {
    "node": "Prescription",
    "properties": {
      "prescriptionId": { "field": "prescriptionId" }
    }
  },
  "to": {
    "node": "Clinician",
    "properties": {
      "clinicianId": { "field": "clinicianId" }
    }
  },
  "properties": {
    "confidence": { "field": "confidence" }
  }
}
```

- `relationship` references a key in `relationships`; `from.node`/`to.node` must agree with the relationship definition.
- Endpoint `properties` map each node's key property to the table field carrying its value.
- Top-level `properties` map relationship properties; omit when the relationship has none.
- Every non-empty endpoint value in sample data must resolve to a mapped node.

## Display

`display.nodes` positions node definitions in the model visualisation, keyed by node keys, with `x` and `y` required:

```json
{
  "display": {
    "nodes": {
      "Prescription": { "x": -100, "y": 0 },
      "Clinician": { "x": 100, "y": 0 }
    }
  }
}
```

`display` is optional in the spec but required by this pipeline: add coordinates for every node, spread far enough apart to make labels and relationship directions readable.

## Annotations for agent reasoning

Annotations give the graph model ontological weight: they define terms, not just structure. Agents downstream — Aura's onboarding agent, tool-generating agents working from the imported schema — rely on them to interpret properties correctly, choose the right traversals, and explain results. Treat them as first-class model content, not documentation garnish.

### Where annotations live

| Level        | Field         | Carries                                                        |
| ------------ | ------------- | -------------------------------------------------------------- |
| Spec root    | `name`, `description` | Domain, and what the model answers                     |
| Node         | `description` | What the entity is in the domain                               |
| Property     | `description` | Meaning, unit/encoding/scope, and a trailing sample value      |
| Relationship | `description` | Meaning in the from→to direction, and multiplicity both ways   |

**Everything lives in `description`. Packages never write an `extensions` block.**

The spec schema does define `extensions` as an open container of typed values, and earlier revisions of this pipeline used it for two keys, `sample` and `cardinality`. That is no longer permitted — the pinned runtime cannot read the container in any form (see [Pipeline caveats](#pipeline-caveats)). Both annotations moved into `description`, which the runtime carries intact and which reaches the consuming agent by the same path it always did.

**The sample-value convention.** A property description that carries a sample ends with a final clause:

```text
e.g. `250`.
```

A single backticked literal, taken **verbatim** from the mapped CSV column, as the last clause of the description. The fixed form keeps it mechanically checkable — VALIDATION.md §3b extracts it with `` /e\.g\. `([^`]+)`\.?\s*$/ `` and compares it against the column — so this is a convention with a test behind it, not a formatting preference. One value only; do not list alternatives.

**The multiplicity convention.** Relationship descriptions state expected multiplicity in prose, in both directions, after the meaning sentence. There is no fixed form to match — §3b checks the *claim* against endpoint counts in the sample data, so write it plainly and make it true.

The optional `name` fields on nodes, properties, and relationships stay unset — readable entity keys and labels already carry the names; populate `name` and `description` at the root only. Table fields are the exception and are not covered by this rule: every entry under `tables.*.fields` must set `name` to its own key, for the reasons given in the Tables section above.

### Authoring rules

1. **Author annotations with the model, before the sample data.** A description is a contract the CSVs and queries must then satisfy — write it first and generate data that conforms. Annotating after the data is written produces rationalisations, not specifications.
2. **Descriptions are normative for template models.** Packages double as templates for the user's own data, so word descriptions as expectations — "Dose per administration in milligrams" asserts what the property is expected to carry — rather than as claims about data you have never seen.
3. **Every node, every relationship, and every property gets a `description`.** Nodes: what the entity is in the domain. Relationships: what the connection means in the from→to direction — and where one relationship type is reused, each entry's description states its distinct meaning. Properties: what the value means; and for every numeric, temporal, or coded property, also its **unit, encoding, and scope** (per-what? measured how? which code system?). "The dosage" is not a description; "Dose per administration in milligrams" is.
4. **End every numeric and coded property's description with a sample value**, and do the same anywhere prose alone leaves ambiguity. Take the value verbatim from the mapped CSV column — a sample is only trustworthy because it is mechanically true of the data. A description plus a real sample exposes wrong readings immediately (a `dosage` described as milligrams ending `` e.g. `1 tab PO BID`. `` is visibly broken).
5. **Confidence is not uniform — tier it, and keep the human in the loop.** Definitional glosses derivable from the label, the model structure, and the queries are low-risk. Units, encodings, and scopes are stipulations: when the source material does not state them, you are choosing a reading, and the build process must surface that choice to the user for confirmation (see SKILL.md's human-in-the-loop rules). Provenance, authority, governance, and customer vocabulary cannot be generated at all — mark them `TODO(review):` if a package needs them; never invent them.
6. **Keep annotations consistent with everything else.** The same wording, units, and directions must appear in the model descriptions, the `@description`/`@params`/`@usage` annotation blocks of QUERIES.md, and SKILL.md's Model section. A query annotation that contradicts a model description is a package defect.

### Pipeline caveats

- The bundled schema validates structure, so run a JSON Schema validation against it — but **schema validity does not prove the destination runtime accepts the file**, and the two can disagree at the *same* pinned version. The schema is generated from the runtime library's own type definitions, so where the library hand-writes a custom deserializer that departs from its generated form, the schema documents an encoding the library will not read. Version drift is therefore only one explanation for a rejection; a same-version schema/runtime disagreement is another, and the `extensions` defect below is a live instance. Always confirm with the runtime gate in VALIDATION.md §3 — it is a blocker, not an optional extra — and if a schema-valid model is rejected, stop and raise it with the user rather than stripping fields silently.

- **Known defect: `extensions` is unusable at the pinned version.** The schema says an extension value is `{"type": "String", "value": "..."}`. The runtime's `ExtensionValueSerializer` instead dispatches on the *presence of a key named after the type* (`String`, `Boolean`, `Long`, `Double`, `List`, `Map`), so it rejects the documented form with `Unknown Extension type. Keys: [type, value]` and drops the whole package. Its encoder emits a third form, `{"value": "..."}`, which its own decoder also rejects — so no encoding survives a round trip. **Write no `extensions` block anywhere in the model.** Do not "fix" this by emitting the hybrid the deserializer happens to accept: that form contradicts the published schema and would break again the moment the library is corrected. If a future spec bump fixes the round trip, reintroducing extensions is a deliberate exercise — re-validate every existing package, and only after the §3 runtime gate passes with them present.

- The sample value and multiplicity conventions are this pipeline's own, expressed in `description` prose. They are not spec-defined fields, so nothing but this pipeline validates them — which makes VALIDATION.md §3b the only thing standing between a plausible-looking annotation and a false one.

## Authoring order

1. Define node keys, labels, and identifiers.
2. Write the spec-root `name` and `description`.
3. Add node descriptions and properties (with descriptions and `key: true` identifiers).
4. Define relationship keys, types, directions, and properties, with descriptions stating meaning and multiplicity.
5. Draft the property descriptions' sample-value intents — and confirm uncertain descriptions with the user now, before data exists to rationalise.
6. Define the CSV tables and exact field names.
7. Add node mappings (`NodeMapping`, mode `MERGE`, `key`).
8. Add relationship mappings and endpoint lookups.
9. Add display coordinates.
10. Create sample CSVs that satisfy the descriptions, samples, and multiplicity claims — then set each description's trailing `` e.g. `...` `` verbatim from the generated column.
11. Check every query-referenced label, type, direction, and property against the model, and every query annotation block against the descriptions.
12. Run the VALIDATION.md §3 runtime gate. A model that has never been through it is not finished, however clean it looks.

## Consistency checklist

- The file validates against the bundled `graph-spec.schema.json` — no off-schema keys anywhere.
- `version` is `"4.0.0"`, and the package's SKILL.md records a `neo4j-graph-spec-version` equal to this bundle's pin (above) verbatim.
- The spec root has a `name` and `description`.
- Node and relationship keys are readable and stable; every key referenced by mappings and display exists.
- Every node, every relationship, and every property has a non-empty, specific `description`; numeric, temporal, and coded properties state unit, encoding, or scope.
- Exactly one `key: true` property per node (or a composite `KEY` constraint instead), never combined with `unique`/`mustExist` on the same property.
- `mustExist` is used for required non-key properties — the old `nullable` field never appears.
- Every property description carrying a sample ends with `` e.g. `<value>`. ``, and that value appears verbatim in the mapped CSV column.
- Every multiplicity claim in a relationship description holds in the sample data.
- **No `extensions` key appears anywhere in the file** — not on properties, relationships, nodes, tables, or display entries.
- The model has passed the VALIDATION.md §3 runtime gate, not just schema validation.
- Mappings use `"type": "NodeMapping"` / `"RelationshipMapping"`, `mode: "MERGE"`, and `key` arrays; node-mapping `key` matches the `key: true` property.
- Every mapping table exists in `tables`; every mapped field exists in its table; every mapped property exists on its node or relationship.
- Every relationship mapping direction matches its relationship definition, and endpoint fields resolve to node identifiers.
- Every query label, relationship type, direction, and property exists in the graph spec, and query annotation blocks agree with model descriptions.
- Every bundled CSV header matches the corresponding table fields.
- Every node has `display` coordinates.
- The file contains valid JSON with no comments, trailing commas, or unresolved placeholders.
