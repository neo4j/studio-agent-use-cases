# Ontology Graph Spec Format

This file defines how to write a package's `ONTOLOGY.json`: the package's **reference ontology**, expressed in the **ontology graph spec**. It covers the node, relationship and property definitions, their semantic annotations, the source tables and import mappings, and the layout used to draw the ontology.

**Terminology.** The format is the *ontology graph spec*. A document written in it is an *ontology*, and the one a package ships is its *reference ontology*. Users, older packages and older tooling say "graph model", "model" or "data model" for the reference ontology, and "graph spec" for the format — understand all of them, but write "reference ontology" yourself. "Schema" is reserved for the live database (`db.schema.visualization()`, `SHOW CONSTRAINTS`) and for the JSON Schema file below; it is never a name for the reference ontology.

**What the word does not claim.** A reference ontology here is a set of typed node, relationship and property definitions whose meaning is carried by descriptions, with structural constraints. It is not OWL or RDF, supports no reasoning or inference, and has no T-Box/A-Box split; queries are not "axioms". Never describe a package's ontology in those terms.

**Authority:** `ontology-graph-spec.schema.json`, bundled with this skill, is the contract. It is the *sole* authority for the format — never fetch, consult, or validate against any other copy of the spec, and never treat a remote revision as more current. The bundled file overrides any other description of the format, including older revisions of this file. It sets `additionalProperties: false` at every level: any key not defined in it is a validation failure.

**Pinned version.** A package's reference ontology is bound to the spec it was built against. This bundle is pinned to:

```text
ontology-graph-spec-version: 1.0.0
```

That line is the single source of truth for the pin. Every package this skill builds declares the matching spec through the `schema` field of its `ONTOLOGY.json` — `https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json` — and VALIDATION.md treats a package whose `schema` names a different version as a blocker.

Provenance of the bundled copy: `ontology-graph-spec.schema.json` from [neo4j/ontology-graph-spec](https://github.com/neo4j/ontology-graph-spec) release `v0.10.0` (commit `6c3ce42c12027225cf56f13a6347227bcdc2fbb7`, 27 October 2026), SHA-256 `1b0fa49e8a0793c2f5bc3ec02245309c766f1a994cb10af6bedb599064ab0458`. On that date it was byte-identical to the copy published at the `schema` URI above. The same release is on npm as `@neo4j/ontology-graph-spec@0.10.0`, and that is the library VALIDATION.md's spec-library check runs:

```text
ontology-graph-spec-release: v0.10.0
```

Two version numbers are in play and they are not the same thing. `1.0.0` is the version of the format, carried in the `schema` URI; it has not changed while the format was being finalised, so it cannot tell two revisions of the schema apart. `v0.10.0` is the release of the repository and its libraries, and together with the hash it identifies exactly what this bundle carries. The published copy behind the URI follows the latest release, so it can move ahead of this bundle without notice — that is why the bundled file, never the URI, is what packages are validated against.

The destination runtime embeds its own release of the same library, and it can lag this pin. At the time of writing upx embeds `@neo4j/ontology-graph-spec@0.9.1`, whose schema differs from `v0.10.0` only in lacking property `aliases`: it accepts them and silently drops them on decode. Find the embedded release in the destination's dependency catalogue (for upx, `@neo4j/ontology-graph-spec` in `pnpm-workspace.yaml`) before relying on anything newer than it — see [Pipeline caveats](#pipeline-caveats).

Refreshing the copy is a deliberate exercise, never a side effect of other work: replace the file, update the provenance line and the release line, re-run the spec-library check with the matching npm release, then re-validate every existing package against it.

The reference ontology is not only a structural contract — it is the primary semantic artefact an agent reasons over. It is the only package artefact that crosses into the user's database via Import, so meaning carried only in SKILL.md prose or query annotations is lost at exactly the moment it becomes most useful: when a user has mapped their own data onto the template and an agent is working from the result. Annotate it per the [Annotations](#annotations-for-agent-reasoning) section.

## Partial adoption

This pipeline follows the spec's structure exactly but adopts only part of it. The rules below are the whole of what packages use; anything the spec allows that is not described here stays out.

| Area | Packages use | Packages do not use |
| ---- | ------------ | ------------------- |
| Root | `schema`, `id`, `version`, `name`, `description`, `nodes`, `relationships`, `extensions` | — |
| Nodes | `label`, `description`, `aliases`, `reference`, `properties`, `constraints` (composite keys and additional requirements), `extensions.display` | `labels` (unless multi-label), `extensions.indexes`, `extensions.custom` |
| Properties | `type`, `description`, `key`, `must_exist`, `unique`, `one_of`, `pattern`, `aliases`, `reference`, `dimension` (vectors only) | `name`, `extensions` |
| Relationships | `type`, `description`, `aliases`, `reference`, `from`/`to` with `node` and `count`/`min_count`/`max_count`, `properties` | `constraints`, `extensions` |
| Root `extensions` | `data_source_tables`, `data_source_mappings` | `custom` |

**Extensions are allowed in exactly three places**, because the spec moved import and layout data there and a package cannot load its sample data without them: root `extensions.data_source_tables`, root `extensions.data_source_mappings`, and each node's `extensions.display`. No other `extensions` key is written anywhere — no `custom` at any level, no `indexes`, and no extension on a property, relationship, constraint, label set, table, column or foreign key.

## Top-level shape

```json
{
  "schema": "https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json",
  "id": "prescription-safety",
  "version": "1",
  "name": "Prescription Safety",
  "description": "Relates patients, prescriptions, and clinicians to surface over-prescription patterns.",
  "nodes": {},
  "relationships": {},
  "extensions": {
    "data_source_tables": {},
    "data_source_mappings": {
      "mapping0": []
    }
  }
}
```

| Field           | Purpose |
| --------------- | ------- |
| `schema`        | Required. The spec URI, `https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json` — the version segment must equal the pin above. |
| `id`            | Required. The package's `skillId` (its folder name), in kebab-case. |
| `version`       | Required. The ontology document's own revision label — not the spec version. Start at `"1"` and increment when the reference ontology changes. |
| `name`          | Human-readable name of the reference ontology. |
| `description`   | One or two sentences: the domain, and what the reference ontology answers. |
| `nodes`         | Node definitions keyed by readable stable IDs. |
| `relationships` | Relationship definitions keyed by readable stable IDs. |
| `extensions`    | `data_source_tables` and `data_source_mappings` only — see [Tables](#tables) and [Mappings](#mappings). |

**Entity keys are readable.** Key each node by its label (`"Prescription"`) and each relationship by a descriptive camelCase ID (`"prescribedBy"`). These keys connect definitions to mappings, and readable keys make every cross-reference self-explanatory to agents. Keep them stable.

## Nodes

Each node entry needs:

- A readable stable key, normally equal to its label
- A `label` (single-label shorthand) — or `labels: {identifier, implied, optional}` for multi-label nodes; packages normally use `label`. A label may not contain `:` or `=`.
- A `description` — what the entity is in the domain
- Property definitions, with `key: true` on the identifier
- `extensions.display` coordinates
- Optionally `aliases` and `reference` — see [Aliases and references](#aliases-and-references)

```json
{
  "Prescription": {
    "label": "Prescription",
    "description": "An authorisation to dispense a specific medication to a patient, issued by a clinician.",
    "aliases": ["Medication order", "Script"],
    "properties": {
      "prescriptionId": {
        "type": "STRING",
        "description": "Unique identifier for the prescription. Expected to be stable across refills. e.g. `RX-1001`.",
        "key": true
      },
      "dosageMg": {
        "type": "FLOAT",
        "description": "Dose per administration in milligrams. Not a daily total and not a free-text sig. e.g. `250`."
      },
      "route": {
        "type": "STRING",
        "description": "Route of administration, as a lower-case route name. e.g. `oral`.",
        "one_of": ["oral", "intravenous", "intramuscular", "subcutaneous", "topical", "inhaled"]
      }
    },
    "extensions": {
      "display": { "x": -100, "y": 0 }
    }
  }
}
```

### Node properties

The key in `properties` is the Neo4j property name. Leave the property's own `name` unset: the spec uses it only for a database name that differs from the key, and packages always key a property by its database name.

- `type` — a value from the spec's `Neo4jType` enum, limited by what Import can load; see [Property types Import can load](#property-types-import-can-load). Match types to query behaviour: numeric comparisons require numeric types, temporal operations temporal types.
- `description` — required by this pipeline on every property; see [Annotations](#annotations-for-agent-reasoning).
- `key: true` — marks the node's single-property identifier. It implies existence and uniqueness (a node key), so do **not** combine it with `unique` or `must_exist`. Exactly one property per node carries it — or none, when the node's identity is a composite `KEY` constraint, in which case the node mapping's `key` lists that constraint's properties.
- `must_exist` / `unique` — for non-key requirements. `must_exist: true` means the property is required. (Older revisions spelled this `mustExist`, and older still `nullable` with the inverted sense; neither exists in the spec.) `key`, `must_exist` and `unique` each expand into a database constraint scoped to the label or relationship type, not to the entry — where a label or type is declared by more than one entry, see [Constraint flags on shared labels and types](#constraint-flags-on-shared-labels-and-types).
- `one_of` / `pattern` — value restrictions; see [Value restrictions](#value-restrictions). Never both on one property.
- `aliases` / `reference` — see [Aliases and references](#aliases-and-references).
- `dimension` — only for `VECTOR<...>` types.
- A **sample value** in the `description`, as a trailing `` e.g. `...` `` clause taken verbatim from the mapped CSV column. See [Annotations](#annotations-for-agent-reasoning).

### Property types Import can load

A package with bundled CSVs is loaded by Import as a local CSV import, and Import supports only some of the spec's types there. **Every node and relationship property uses one of:**

- `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `ZONED DATETIME`;
- their list forms `LIST<STRING>`, `LIST<INTEGER>`, `LIST<FLOAT>`, `LIST<BOOLEAN>`, `LIST<ZONED DATETIME>`;
- `VECTOR<...>` (with `dimension`).

Everything else the enum offers is out. `DATE`, `LOCAL DATETIME`, `LOCAL TIME`, `ZONED TIME`, `DURATION`, `POINT` and their lists are valid against the schema, pass the spec library and convert cleanly to an Import model — and Import then flags every such property "Not supported in local imports", leaving the import job unrunnable. `UUID`, `ANY` and the sized scalars (`INTEGER8/16/32`, `FLOAT32`, and their lists; the sized `VECTOR<...>` forms are fine) fail earlier, in the conversion itself. This is the destination's rule (upx's `SUPPORTED_CSV_TYPE_OPTIONS_COMPLETED`), not a modelling preference.

**Calendar dates are `ZONED DATETIME` at midnight UTC.** A date of birth, an origination date or a published date is typed `ZONED DATETIME`, its CSV column carries `2025-10-08T00:00:00Z` rather than `2025-10-08`, and its description says that only the calendar date carries meaning and the time is always midnight UTC — so the `e.g.` sample is the full `2025-10-08T00:00:00Z`. Queries follow from the type:

- Compare with `datetime(...)`: `WHERE l.originationDate >= datetime('2025-01-01')` or `datetime($from)`. A `ZONED DATETIME` ordered against a `date(...)` is `null` (and equal to one is `false`), so the filter silently drops every row rather than raising an error.
- Date arithmetic and bucketing use `duration.inDays(...)`, `date.truncate(...)` or `.year`/`.month` on the datetime value directly.
- Values shown to a user are wrapped in `date()` — `RETURN date(l.originationDate) AS originationDate` — so the padding time never reaches the answer.

A point, a duration or any other unsupported value either becomes one of these types (a `POINT` as two `FLOAT` properties, a `DURATION` as an `INTEGER` count of a stated unit) or is computed by a post-import setup query and documented in SKILL.md like any other query-created property ([Declare only what Import can load](#declare-only-what-import-can-load)).

### Value restrictions

`one_of` and `pattern` state what values a property is expected to hold. They are claims about the domain, written for the user's data as much as the bundled sample, so the test for each is: *would this restriction still be right on a real customer's data?*

- **`one_of`** — the complete list of allowed values for a `STRING` property whose values come from a closed set the domain defines (values are compared as exact text, so do not use it on numeric, boolean or temporal properties): a status lifecycle, a route of administration, a channel. List every legitimate value, not just the ones the sample uses — a list derived from the CSVs is a fact about the generator, not the domain. Use it only when the set is genuinely closed; an open-ended category (merchant type, product line) gets a description, not a list.
- **`pattern`** — a regular expression every value must match in full, anchored with `^` and `$`, for a property whose format is set by an external standard: an ICD-10 code, an IBAN, a LEI, an ISO 3166 country code. Keep to syntax common to Java, JavaScript, Go (RE2) and Python regular expressions: character classes, quantifiers, groups and alternation — no lookaround, no backreferences, no named groups, no flags. **Never write a pattern for the package's own identifier scheme** (`EP-001`, `RX-1001`): a user mapping their own data onto the template has their own identifiers, and the pattern would declare them invalid.
- A property carries `one_of` or `pattern`, never both — the spec library rejects the combination.
- Every value in the mapped CSV column satisfies the restriction (VALIDATION.md §3b checks this mechanically), and the trailing `` e.g. `...` `` sample is one of the allowed values.
- A restriction you inferred rather than read from the source is a stipulation: put it to the user with the other uncertain descriptions (SKILL.md, step 1).

### Node constraints and indexes

`key: true` covers the standard single-property node identifier. Use the `constraints` block only for composite keys or additional requirements:

```json
"constraints": {
  "flight_leg_key": {
    "type": "KEY",
    "properties": ["flightNo", "departureDate"]
  }
}
```

A constraint applies to the node it is declared on; it carries no `label` of its own (older revisions had one, and the schema no longer allows it). Constraint types: `EXISTS`, `KEY`, `PROPERTY_TYPE`, `UNIQUE`. Prefer a single-property key — composite keys break the Import flow — and use a surrogate derived key where the natural identity is composite. Write no `extensions.indexes`: the Import pipeline is not known to create indexes from the reference ontology, so index needs belong in `SETUP.md` where the agent applies them with consent.

## Relationships

Each relationship entry needs:

- A readable stable key, e.g. `"prescribedBy"`
- A Neo4j relationship `type`
- A `description` — required by this pipeline: what the connection means, read in the from→to direction, with its multiplicity in both directions
- `from` and `to` targets referencing node keys, carrying multiplicity counts where the domain fixes them
- Optional relationship properties (same shape as node properties, including `description`)
- Optionally `aliases` and `reference`
- Source data behind it — see [Declare only what Import can load](#declare-only-what-import-can-load)

```json
{
  "prescribedBy": {
    "type": "PRESCRIBED_BY",
    "description": "Links a prescription to the clinician who authorised it. Exactly one clinician per prescription; a clinician may authorise many prescriptions, or none.",
    "from": { "node": "Prescription", "count": 1 },
    "to": { "node": "Clinician" },
    "properties": {
      "confidence": {
        "type": "FLOAT",
        "description": "Extraction confidence from the source system, 0.0–1.0. e.g. `0.92`.",
        "must_exist": true
      }
    }
  }
}
```

- `from.node` and `to.node` reference keys in `nodes`. A relationship may connect two different node definitions or a node definition to itself. (The spec also allows a label-only target via `label`; packages use `node` references.)
- **Relationship descriptions are core spec fields — always write one.** When the same relationship `type` string is reused between different node pairs, each reuse is its own entry with its own key and its own description stating that instance's distinct meaning.
- Write no relationship `constraints` and no `extensions`, for the same reasons as nodes.

### Constraint flags on shared labels and types

`key`, `must_exist` and `unique` are shorthand for database constraints, and a database constraint belongs to a label or a relationship type — not to one entry in `ONTOLOGY.json`. The destination names each one from the type, the property and the kind (`road_ref_ROAD_propertyExistence`), so two entries that share a type and flag the same property produce two constraints with the same name. The destination rejects that with `graph-spec contains duplicate constraint name "…"` while converting the reference ontology to an Import model, and because it converts at registration, the whole package silently disappears from the catalogue.

The usual cause is a relationship type reused between node pairs (`ROAD` city→city, city→station, station→city; `REQUIRES` product→assembly and assembly→config group), each entry faithfully carrying the same `must_exist` flags. The rule:

- **Flag each property on exactly one entry per label or type.** Choose the entry that best represents the type and put the flag there; it already constrains every relationship of that type in the database.
- **State the requirement in the other entries' descriptions instead** — "Expected on every `ROAD` relationship." — so an agent reading any entry still learns it.
- The same applies to a label declared by more than one node entry (multi-label nodes sharing an `identifier`), though packages rarely have one.

Neither the schema nor the spec library catches this; `check_annotations.py` and the runtime gate do (VALIDATION.md §3).

### Multiplicity

Multiplicity is stated twice, and the two must agree: in prose in the `description`, where an agent reads it, and as counts on the targets, where a tool can check it.

**The counts on a target describe the node at that end:** how many relationships of this entry each node at that end has.

| On | Field | Means |
| -- | ----- | ----- |
| `from` | `count: 1` | Every from-node has exactly one of these relationships. |
| `from` | `min_count`/`max_count` | Every from-node has between min and max of them. |
| `to` | `count: 1` | Every to-node has exactly one of these relationships. |
| `to` | `min_count`/`max_count` | Every to-node has between min and max of them. |

In the example, every prescription has exactly one `PRESCRIBED_BY` (`from.count: 1`); a clinician has zero or more, which is the unconstrained default, so `to` carries no count. Rules:

- `count` or a `min_count`/`max_count` range on a target, never both; no negative values; `min_count` never exceeds `max_count`. The spec library rejects all three.
- Omit a bound the domain does not fix. An omitted `max_count` means "many"; `min_count: 0` adds nothing and is omitted. A target with nothing to say carries no count fields at all.
- **State counts only where the domain makes them true**, worded as an expectation of the user's data — "every claim is filed by exactly one claimant" — not as a measurement of the sample. A count is a checkable claim: the bundled data must satisfy it (VALIDATION.md §3b), and an agent working from a user's imported data will rely on it.
- The prose in the `description` states the same multiplicity, in both directions, in plain language. Where the two disagree, the package is defective.
- Some counts hold by construction — a `to.count: 1` where every to-node and its one relationship are created from the same CSV row. State them anyway when the domain fixes them: the count documents the domain for a user's own data, and the data check only proves the bundled rows agree.

### Declare only what Import can load

**Every node and every relationship a reference ontology declares must have a mapping.** The
Import tool treats the reference ontology as the definition of an import job, not as a
description of a graph: it requires a source table for each declared entity, a
column for each of its properties, and an ID column for each endpoint of a
relationship. Anything declared without those is not ignored — it is flagged
`Must be specified`, and the import definition stays in an error state that the
user cannot clear without editing the reference ontology by hand.

This makes one category of modelling impossible, and it is a category packages
reach for naturally: **a relationship, label or property created by a query rather than
loaded from data.** (A property a query writes onto a declared node — a computed
point, a score — is the same case: declaring it would demand a source column.) A resolution or selection edge written per run, a scored
link, a `SIMILAR_TO` computed by an algorithm, a cluster label applied by a
workflow — none of these have source data, none can be mapped, and declaring
them breaks the import outright.

The rule:

- If it comes from a CSV, declare it and map it.
- If a query creates it, **do not declare it in the reference ontology.** Document it in
  SKILL.md instead, in enough detail for the consuming agent to use it: the
  node pairs or labels it connects (or, for a property, the label it sits on), its properties with their types, and which
  queries write it and which remove it. State plainly that it does not exist in
  a freshly imported database.
- Never invent a CSV to make a query-created entity mappable. Seeding it at
  import time pre-computes the very thing the package's queries are there to
  demonstrate.

This is a deliberate, documented exception to VALIDATION.md §5's rule that every
label, relationship type and property a query references resolves in
`ONTOLOGY.json` — the one case where the query is right and the reference ontology is
silent. VALIDATION.md §3 checks for unmapped entities, and §6 checks that
SKILL.md carries the definition.

> Verified in the Import tool against a package that declared six query-created
> relationships: all six showed `Must be specified` on the source table, on
> every property column, and on both node ID columns. The behaviour was
> confirmed for relationships; nodes were not separately tested, so treat the
> node half of this rule as the safe assumption rather than as an observation.

## Aliases and references

Both are optional. Both are claims an agent will repeat to a user, so the standard is the same as for descriptions: write them from the source material, and never invent them.

- **`aliases`** (nodes, relationships and properties) — other names the industry uses for the same concept: `Claimant` → `["Policyholder", "Insured party"]`, `Encounter` → `["Visit", "Episode of care"]`, a property `birthDate` → `["Date of birth"]`. They let an agent recognise the concept when a user, or a user's own schema, names it differently, so they support mapping a user's labels and columns onto the reference ontology. Use terms from the source pages or established industry usage. An expansion of an abbreviated label is an alias (`DOB` → `["Date of birth"]`); spelling or case variants, the label itself, and one organisation's private vocabulary are not — customer vocabulary cannot be generated, and an alias that only fits one customer misleads every other. Aliases you are unsure of go to the user with the uncertain descriptions at step 1.
  - **Property aliases are new in release `v0.10.0`**, and a destination embedding an older library ignores them: upx at `0.9.1` accepts the field and drops it on decode, so a property alias reaches the agent reading `ONTOLOGY.json` but not the user's database. Until the destination's embedded release is `0.10.0` or later, a property synonym that a downstream consumer must see also goes in the property's `description`.
- **`reference`** (nodes, relationships, properties) — a URI for an external resource that defines the concept: a standard or code system, a regulatory definition, or the industry use-case page the package is built from (a page under `https://neo4j.com/developer/industry-use-cases/`). Every `reference` must be a real, reachable URL you have actually read. Never construct a plausible-looking URL; omit the field instead. One URI per element.

## Tables

`extensions.data_source_tables` describes each CSV used by a mapping:

```json
{
  "prescriptions.csv": {
    "source": "local",
    "columns": [
      { "name": "prescriptionId", "type": "string" },
      { "name": "clinicianId", "type": "string" },
      { "name": "dosageMg", "type": "string" },
      { "name": "route", "type": "string" },
      { "name": "confidence", "type": "string" }
    ]
  }
}
```

- The table key is the exact CSV filename and must match the `table` value used by mappings.
- `source` is `"local"` for bundled CSV input.
- `columns` lists every CSV column **in header order**, each `name` equal to the header exactly, including case, with no duplicates and no empty names. Declare every column `"type": "string"` — the mapped property's type converts values to graph types.
- The spec's richer column facets (`size`, `suggested`, `supported`, `nullable`) and table keys (`primary_keys`, `foreign_keys`) describe RDBMS sources; omit them for bundled CSVs.
- Include endpoint columns used only to connect relationships, even when they do not become graph properties.

If sample CSVs are bundled, place them under `sample-data/`. Keep table references unambiguous.

## Mappings

`extensions.data_source_mappings` is a map of named mapping lists. Packages carry exactly one list, keyed `"mapping0"` — the key the spec library itself assigns when it converts an Import data model — and every mapping goes in it. Each mapping is a discriminated union on `type`: `"NODE"` or `"RELATIONSHIP"` (also `"QUERY"`, which packages do not use). Leave the optional mapping `id`, `depends_on` and `match_label` unset.

### Node mappings

```json
{
  "type": "NODE",
  "node": "Prescription",
  "table": "prescriptions.csv",
  "mode": "MERGE",
  "key": ["prescriptionId"],
  "properties": {
    "prescriptionId": { "column": "prescriptionId" },
    "dosageMg": { "column": "dosageMg" },
    "route": { "column": "route" }
  }
}
```

- `node` references a key in `nodes`; `table` references a key in `extensions.data_source_tables`.
- `mode` is `"MERGE"` for packages — rows may repeat a key and merge into one node.
- `key` (an array) lists the graph properties that identify the node; it matches the property marked `key: true`.
- Every mapped graph property must exist on the node; every referenced `column` must exist in the table.

### Relationship mappings

```json
{
  "type": "RELATIONSHIP",
  "relationship": "prescribedBy",
  "table": "prescriptions.csv",
  "mode": "MERGE",
  "key": [],
  "from_node": {
    "label": "Prescription",
    "properties": {
      "prescriptionId": { "column": "prescriptionId" }
    }
  },
  "to_node": {
    "label": "Clinician",
    "properties": {
      "clinicianId": { "column": "clinicianId" }
    }
  },
  "properties": {
    "confidence": { "column": "confidence" }
  }
}
```

- `relationship` references a key in `relationships`.
- `from_node` and `to_node` identify the endpoint nodes **by label** — the `label` of the node definitions the relationship's `from.node` and `to.node` point at. Their `properties` map each endpoint node's key property to the column carrying its value.
- Top-level `properties` map relationship properties; omit when the relationship has none.
- Every non-empty endpoint value in sample data must resolve to a mapped node.
- **`key` decides which rows become one relationship.** With mode `MERGE` and `key: []`, Import identifies a relationship by its endpoints alone, so every row joining the same two nodes merges into one relationship and only one row's properties survive. That is right when the table holds one row per pair. When the domain has **parallel relationships** — several of the same type between the same two nodes, told apart by a property (a charging site's `top-up` and `full` options, modelled as two `CHARGE` self-loops) — set `key` to that property: `"key": ["tier"]`. The spec library turns a relationship mapping's `key` into Import's relationship key properties, which control merging only; it does not create a database constraint, so do not also mark the property `key: true` (on a relationship that would demand it be unique across every relationship of the type). VALIDATION.md §4 checks every relationship table for repeated endpoint pairs.

## Display

Each node carries its position in the ontology visualisation as `extensions.display`, with `x` and `y` required:

```json
"extensions": {
  "display": { "x": -100, "y": 0 }
}
```

The spec makes `display` optional; this pipeline requires it on every node, spread far enough apart to make labels and relationship directions readable. Leave `colour` and `custom` unset — node colour is assigned by the rendering application.

## Annotations for agent reasoning

Annotations give the reference ontology its meaning: they define terms, not just structure. Agents downstream — Aura's onboarding agent, tool-generating agents working from the imported data — rely on them to interpret properties correctly, choose the right traversals, and explain results. Treat them as first-class content, not documentation garnish.

### Where annotations live

| Level        | Field         | Carries |
| ------------ | ------------- | ------- |
| Root         | `name`, `description` | Domain, and what the reference ontology answers |
| Node         | `description`, `aliases`, `reference` | What the entity is in the domain; other industry names; an external definition |
| Property     | `description`, `one_of`/`pattern`, `aliases`, `reference` | Meaning, unit/encoding/scope, and a trailing sample value; allowed values; other names; an external definition |
| Relationship | `description`, target counts, `aliases`, `reference` | Meaning in the from→to direction and multiplicity both ways; the same multiplicity as counts; other names; an external definition |

**`description` carries the meaning.** The structured fields restate parts of it in checkable form; they never replace it. A property with `one_of` still says in its description what the values mean, and a relationship with counts still states its multiplicity in prose. No annotation goes in `extensions`.

**Length limits.** The spec library rejects any node, relationship or property `description` over **1,024 characters**, and a root `description` over 64 KiB. Write descriptions that are complete and dense, not long: one to three sentences is typical.

**The sample-value convention.** A property description that carries a sample ends with a final clause:

```text
e.g. `250`.
```

A single backticked literal, taken **verbatim** from the mapped CSV column, as the last clause of the description. The fixed form keeps it mechanically checkable — VALIDATION.md §3b extracts it with `` /e\.g\. `([^`]+)`\.?\s*$/ `` and compares it against the column — so this is a convention with a test behind it, not a formatting preference. One value only; do not list alternatives.

Populate `name` at the root only. Nodes and relationships have no `name` field; a property's `name` is only for a database name that differs from its key, which never happens in a package; and a constraint's `name` would override the name the destination derives for it. The spec library's `missing_property_name` rule (in its `consistentSchema` set) mirrors an Import-UI requirement and fires on every property left in this shorthand form — VALIDATION.md §3 explains why that one rule is filtered.

### Authoring rules

1. **Author annotations with the reference ontology, before the sample data.** A description, value restriction or count is a contract the CSVs and queries must then satisfy — write it first and generate data that conforms. Annotating after the data is written produces rationalisations, not specifications.
2. **Annotations are normative for a template.** Packages double as templates for the user's own data, so word descriptions as expectations — "Dose per administration in milligrams" asserts what the property is expected to carry — rather than as claims about data you have never seen. The same holds for `one_of`, `pattern` and counts.
3. **Every node, every relationship, and every property gets a `description`.** Nodes: what the entity is in the domain. Relationships: what the connection means in the from→to direction and its multiplicity both ways — and where one relationship type is reused, each entry's description states its distinct meaning. Properties: what the value means; and for every numeric, temporal, or coded property, also its **unit, encoding, and scope** (per-what? measured how? which code system?). "The dosage" is not a description; "Dose per administration in milligrams" is.
4. **End every numeric and coded property's description with a sample value**, and do the same anywhere prose alone leaves ambiguity. Take the value verbatim from the mapped CSV column — a sample is only trustworthy because it is mechanically true of the data. A description plus a real sample exposes wrong readings immediately (a `dosage` described as milligrams ending `` e.g. `1 tab PO BID`. `` is visibly broken).
5. **Confidence is not uniform — tier it, and keep the human in the loop.** Definitional glosses derivable from the label, the structure, and the queries are low-risk. Units, encodings, scopes, value lists, patterns and counts are stipulations: when the source material does not state them, you are choosing a reading, and the build process must surface that choice to the user for confirmation (see SKILL.md's human-in-the-loop rules). Aliases and references come from sources or not at all. Provenance, authority, governance, and customer vocabulary cannot be generated — mark them `TODO(review):` if a package needs them; never invent them.
6. **Keep annotations consistent with everything else.** The same wording, units, allowed values, and directions must appear in the reference ontology's annotations, the `@description`/`@params`/`@usage` annotation blocks of QUERIES.md, and SKILL.md's Reference ontology section. A query annotation that contradicts the reference ontology is a package defect.

### Pipeline caveats

- The bundled schema validates structure, so run a JSON Schema validation against it — but **schema validity does not prove the destination runtime accepts the file**. The destination decodes the reference ontology with its own embedded release of the spec library and then converts it to an Import model, and it does both while registering the package: a throw at either step drops the package from the catalogue with nothing but a log line. Three ways this has bitten packages already:
  - the runtime could not read an encoding the schema documented (the typed extension values at the old `4.0.0-alpha.25` pin, and the node `display` extension before upx adopted the ontology graph spec);
  - the runtime enforces a rule the schema and the library do not — duplicate constraint names from flags repeated across entries of one type (see [Constraint flags on shared labels and types](#constraint-flags-on-shared-labels-and-types));
  - the runtime embeds an older release than the pin and silently drops what it does not know (property `aliases` under `0.9.1`).

  Only the runtime gate in VALIDATION.md §3 proves the destination reads the file. It is a blocker, not an optional extra. If a schema-valid file is rejected, stop and raise it with the user rather than stripping fields silently.
- The spec library carries semantic checks the schema cannot express — count conflicts, `one_of` with `pattern`, description length, label tokens, mapping keys, column names. VALIDATION.md §3 runs it with the npm release that matches the pin; no toolchain beyond Node is needed.
- The sample-value convention and the requirement that prose multiplicity matches the counts are this pipeline's own. Nothing but this pipeline validates them — which makes VALIDATION.md §3b the only thing standing between a plausible-looking annotation and a false one.

## Converting a legacy graph model

Packages built before this pin ship a `GRAPH_MODEL.json` in the older graph-spec format. Convert it with `scripts/convert_legacy.py` and prove the result with `scripts/compare_ontology.py`, as part of the whole-package procedure in [MIGRATION.md](MIGRATION.md) — never by hand-editing the legacy file. The table records what the script does, for review.

| Legacy `GRAPH_MODEL.json` | `ONTOLOGY.json` |
| ------------------------- | --------------- |
| `version: "4.0.0"` | `schema: "https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json"`, `version: "1"`, and `id` set to the package folder name |
| `metadata.neo4j-graph-spec-version` in SKILL.md | Removed — the `schema` field declares the spec |
| `mustExist` (or older `nullable: false`) | `must_exist: true` |
| Root `tables` | `extensions.data_source_tables` |
| Table `fields` map (`{ "col": { "name": "col", "type": "string" } }`) | Table `columns` array, in CSV header order (`[{ "name": "col", "type": "string" }]`) |
| `primaryKeys`, `foreignKeys` | Omitted for CSV tables (`primary_keys`, `foreign_keys` if ever needed) |
| Root `mappings` array | `extensions.data_source_mappings.mapping0` |
| `"type": "NodeMapping"` (or older `"node"`) | `"type": "NODE"` |
| `"type": "RelationshipMapping"` (or older `"relationship"`) | `"type": "RELATIONSHIP"` |
| Relationship mapping `from` / `to` with `node` | `from_node` / `to_node` with the endpoint node's `label` |
| `{ "field": "col" }` in property mappings | `{ "column": "col" }` |
| `matchLabel` | `match_label` (packages leave it unset) |
| `display.nodes.<key>` | `nodes.<key>.extensions.display` |
| `extensions.sample` | Trailing `` e.g. `...` `` in the property description |
| `extensions.cardinality` | Target `count`/`min_count`/`max_count`, plus prose in the description |
| Relationship target `property` | Removed |
| Positional keys (`n:0`, `r:1`) | Readable keys (label for nodes, camelCase for relationships) |

The script also renames positional entity keys (`n:0` → the node's label; `r:0` → the relationship type in camelCase, prefixed and suffixed with its node labels where one type joins several pairs), and drops legacy `indexes` and `extensions`, logging each so their meaning can be moved by hand. It warns — it does not fix — on the two things a faithful conversion carries over but the destination will not accept: a constraint flag repeated across entries of one relationship type or label (legacy files routinely set `mustExist` on every reuse of a type), and a relationship table with repeated endpoint pairs under an empty mapping `key`. Both are meaning changes for the migration plan; see [Constraint flags on shared labels and types](#constraint-flags-on-shared-labels-and-types) and [Relationship mappings](#relationship-mappings).

**Pre-release `ONTOLOGY.json`.** A package converted before the spec renamed its root extensions carries `extensions.tables` and `extensions.mappings`. That shape fails the bundled schema; the fix is the rename alone — `tables` → `data_source_tables`, `mappings` → `data_source_mappings` — with nothing else touched, proved by `compare_ontology.py` against the file before the rename (it reads both names). `inventory.py` reports this generation separately from the legacy `GRAPH_MODEL.json` ones.

## Authoring order

1. Define node keys, labels, and identifiers.
2. Write the root `schema`, `id`, `version`, `name` and `description`.
3. Add node descriptions and properties (with descriptions and `key: true` identifiers), plus any `one_of`/`pattern` the domain fixes. Type every property — node and relationship — from the set Import can load locally; a calendar date is `ZONED DATETIME` at midnight UTC, never `DATE` (see [Property types Import can load](#property-types-import-can-load)).
4. Define relationship keys, types, directions, and properties, with descriptions stating meaning and multiplicity and target counts matching that prose. Decide for each one whether source data exists for it; a relationship a query will create belongs in SKILL.md, not here. Where a type is reused between node pairs, put each `must_exist`/`unique` flag on one entry only and state it in prose on the others.
5. Add `aliases` and `reference` where the source material supports them.
6. Draft the property descriptions' sample-value intents — and confirm uncertain descriptions, value restrictions, counts and aliases with the user now, before data exists to rationalise.
7. Define the CSV tables and their columns in header order.
8. Add node mappings (`NODE`, mode `MERGE`, `key`) to `extensions.data_source_mappings.mapping0`.
9. Add relationship mappings and endpoint lookups, with a `key` naming the distinguishing property wherever the domain has parallel relationships between the same two nodes.
10. Add `extensions.display` coordinates to every node.
11. Create sample CSVs that satisfy the descriptions, value restrictions, and counts — then set each description's trailing `` e.g. `...` `` verbatim from the generated column.
12. Check every query-referenced label, type, direction, and property against the reference ontology, and every query annotation block against the descriptions. Anything a query references that the reference ontology does not define must be a query-created entity documented in SKILL.md — if it is not, one of the two is wrong.
13. Run the VALIDATION.md §3 checks, including the spec-library check and the runtime gate. A reference ontology that has never been through the runtime gate is not finished, however clean it looks.

## Consistency checklist

- The file validates against the bundled `ontology-graph-spec.schema.json` — no off-schema keys anywhere.
- `schema` is `https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json`, its version segment equal to this bundle's pin; `id` equals the package folder name; `version` is set.
- The root has a `name` and `description`.
- Node and relationship keys are readable and stable; every key referenced by relationships and mappings exists.
- Every node, every relationship, and every property has a non-empty, specific `description` of at most 1,024 characters; numeric, temporal, and coded properties state unit, encoding, or scope.
- Exactly one `key: true` property per node (or a composite `KEY` constraint instead), never combined with `unique`/`must_exist` on the same property.
- Every node and relationship property is typed `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN` or `ZONED DATETIME`, a `LIST<...>` of one of those, or a `VECTOR<...>` — the types Import supports for local CSV imports. Calendar dates are `ZONED DATETIME` values at midnight UTC (`2025-10-08T00:00:00Z`) whose descriptions say only the date carries meaning; queries compare them with `datetime(...)` and display them through `date()`.
- No `key`, `must_exist` or `unique` flag on a property is repeated across entries that share a relationship type or label.
- `name` is set at the root only — not on properties or constraints.
- Every property description carrying a sample ends with `` e.g. `<value>`. ``, and that value appears verbatim in the mapped CSV column.
- No property has both `one_of` and `pattern`; every mapped CSV value satisfies the restriction; no `pattern` encodes the package's own identifier scheme.
- Every relationship target uses `count` or a `min_count`/`max_count` range, not both; every count holds in the sample data and agrees with the prose in the description.
- Every `reference` is a real URL that was read; every alias comes from source material.
- **The only `extensions` keys are root `data_source_tables` and `data_source_mappings` and node `display`.** No `custom`, no `indexes`, nothing on properties or relationships.
- The reference ontology has passed the VALIDATION.md §3 runtime gate, not just schema validation.
- Mappings live in the single list `extensions.data_source_mappings.mapping0`, use `"type": "NODE"` / `"RELATIONSHIP"`, `mode: "MERGE"`, and `key` arrays; node-mapping `key` matches the `key: true` property.
- Every mapping table exists in `extensions.data_source_tables`; every mapped `column` exists in its table; every mapped property exists on its node or relationship.
- **Every declared node and every declared relationship has a mapping** — nothing is declared that Import cannot load. Query-created relationships and labels are documented in SKILL.md instead of being declared here.
- Every relationship mapping's `from_node.label` and `to_node.label` match the labels of the relationship's `from.node` and `to.node`, and endpoint columns resolve to node identifiers.
- A relationship table with more than one row for the same endpoint pair has a mapping `key` naming the property that tells those rows apart.
- Every query label, relationship type, direction, and property exists in the reference ontology, and query annotation blocks agree with its descriptions.
- Every bundled CSV header row matches its table's `columns` names, in order.
- Every node has `extensions.display` coordinates.
- The file contains valid JSON with no comments, trailing commas, or unresolved placeholders.
