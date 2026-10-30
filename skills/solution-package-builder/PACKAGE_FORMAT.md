# Assistant Sidebar Use Case Format

Use this reference when creating a use-case folder. The folder name becomes `skillId`; it is independent from the semantic `name` in frontmatter.

## Enforced structure

```text
<skillId>/
├── SKILL.md                    # required
├── ONTOLOGY.json               # required — the reference ontology
├── QUERIES.cypher                  # required for packages — runnable Cypher
├── human_description.md        # required — the package explained to a person; rendered as HTML, never loaded
├── TESTS.md                    # required when sample data is bundled — authoring-side only, never loaded
├── SETUP.md                    # optional — post-import statements the queries depend on
└── sample-data/                # optional, but the required location for bundled CSV data
    └── *.csv
```

Sample data is optional at the format level — `ONTOLOGY.json` is required either way — but a use case that bundles none also has nothing to test, and is a reference-ontology template rather than a working demo. `TESTS.md` is required exactly when sample data is present. `human_description.md` is required in both cases.

If the use case bundles sample CSVs for Import, every CSV must be below `sample-data/`.

There is no `INTRODUCTION.md`. The agent introduces the package from guidance inside SKILL.md (an "Introducing this package" section), not from a canned document. `human_description.md` does not reinstate it: it is read by people, not agents, and is never the script for a spoken introduction.

`TESTS.md` and `human_description.md` are reserved filenames with special contracts — see [TESTS.md](#testsmd) and [human_description.md](#human_descriptionmd) below. They are the two files in the package the runtime deliberately keeps away from the agent, for opposite reasons: one is too specific to the bundled data to be safe, the other is written for a human reader and would be pure context cost.

## Identity and metadata

Keep these identifiers distinct:

| Value         | Source                         | Purpose                                           |
| ------------- | ------------------------------ | ------------------------------------------------- |
| `skillId`     | Use-case folder name           | Registry lookup, tool calls, and assistant target |
| `name`        | `SKILL.md` frontmatter         | Semantic Agent Skill name and sample naming       |
| Card title    | `metadata.neo4j-card-title`    | Human-readable catalog title                      |
| Card category | `metadata.neo4j-card-category` | Catalog grouping, e.g. Healthcare & Life Sciences |
| Card blurb    | `metadata.neo4j-card-description` | One-sentence user-facing value statement       |
| Ontology id   | `ONTOLOGY.json` `id`           | Equal to `skillId`                                |
| Spec version  | `ONTOLOGY.json` `schema`       | The ontology graph spec the reference ontology was built against |

The `schema` URI in `ONTOLOGY.json` (`https://neo4j.com/docs/ontology-graph-spec/<version>/schema.json`) binds the package to a specific ontology graph spec. A reference ontology is only meaningful against the spec that defines its fields, so validation rejects a package whose `schema` version differs from the skill bundle's pin. `ONTOLOGY.json`'s `version` is the document's own revision label and says nothing about the spec. There is no spec-version key in SKILL.md metadata: the older `neo4j-graph-spec-version` key is retired, and emitting it is a validation failure.

The folder name and frontmatter `name` may match, but they do not have to. Both should be stable kebab-case identifiers where applicable.

`neo4j-card-category` is a closed set — the destination rejects anything outside it, and the package is dropped from the catalog. All allowed values are:

```text
Financial Services
Insurance
Healthcare & Life Sciences
Manufacturing
Cybersecurity
Industry Agnostic
General                      # legacy
Real-time risk detection     # legacy
Supply Chain                 # legacy
```

Match the case and spelling exactly. The first six come from the [industry use-case taxonomy](https://neo4j.com/developer/industry-use-cases/) and are the ones to choose from; the three marked legacy are retained only for packages that predate the taxonomy and are flagged for removal in the destination's own source — do not pick one for a new package. A plausible-sounding value that is not on this list is the failure mode to watch for: "Investment Banking" is not a category, "Financial Services" is.

There is no `neo4j-icon-category`. It was removed from every package and is referenced nowhere in the destination; the card icon is derived from `neo4j-card-category`. Do not emit it — an unknown metadata key is a validation failure.

Choose the category that best represents the card, and never invent a value — an unlisted one is rejected and the package is silently dropped rather than flagged. The card's icon is derived from the category, so no separate icon metadata is needed, though a selectable card may still require manual UI configuration in the destination.

## `SKILL.md`

### Parser contract

- Must begin with YAML frontmatter delimited by `---`.
- `name` must be 1–64 characters and match `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- `description` must be non-empty and at most 1024 characters.
- `metadata` values must be strings.
- All three `neo4j-card-*` fields — `title`, `category`, `description` — are required and non-empty, and `category` must be one of the allowed values above, matched exactly.
- No `neo4j-icon-category` or `neo4j-graph-spec-version` key is present.
- Markdown after frontmatter must be non-empty.

### The role map

SKILL.md's Reference ontology section carries a **conceptual role map**: a small table naming the abstract roles the reference ontology's labels play, alongside what a substitute in someone else's data would have to supply. It exists because the package's value is the analytical patterns, not the labels — and a user who arrives with their own ontology, or their own database, needs those patterns to survive the rename.

Keep it to one row per role, roles a user could plausibly recognise in their own data, and no row that merely repeats a label. Five or six rows is typical; a map with a row per node is not a map.

### Template

````markdown
---
name: <semantic-kebab-case-name>
description: <What this use case helps with and the graph/query capabilities it provides.>
metadata:
  neo4j-card-title: <Short title>
  neo4j-card-category: <one of the allowed values, verbatim>
  neo4j-card-description: <Concise user-facing value statement.>
---

# <Use Case Title>

Use this skill for <audience, domain, and focused use case>.

Source references:

- <https://authoritative-source.example/use-case>

<Add an appropriate domain disclaimer, or omit it when unnecessary.>

## Introducing this package

<Guidance for the agent to phrase its own short introduction: the core
idea, the sample data and its seeded patterns, what the agent can help
with, and a clear next step. Direction, not a script.>

## Reference ontology

- <Nodes and relationships in one or two lines each; key properties.>
- The full reference ontology, with its import mappings, is in
  `ONTOLOGY.json`; runnable Cypher is in `QUERIES.cypher`.
- Call it the reference ontology. Users may say "model", "graph model",
  "data model" or "ontology" — treat these as the same thing.

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| <Abstract role> | `<Label>` | <The property or connection the pattern depends on> |

When the user's database differs from the reference ontology, map their
labels onto these roles before rewriting anything from `QUERIES.cypher`. A role with no
counterpart in their data means the patterns resting on it have no
analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through Import only. Never offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative route.
- Confirm before executing anything that writes, and confirm the target database first.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — imported in this conversation, or its `@sample` anchor found by lookup — as starting parameters and a smoke test of the import. Otherwise ignore it, and never present it as an expectation of the user's data.
- Treat the annotations in `ONTOLOGY.json` — `description` on nodes, relationships, and properties, plus `aliases`, `one_of`, `pattern` and relationship counts — as the authoritative meaning of each term when explaining the reference ontology, adapting it to user data, or generating Cypher.
- <Name any `SETUP.md` statements and the queries that depend on them, when the package ships one.>
- <State Neo4j, Cypher, APOC, or GDS prerequisites.>
- Clarify the intended target database and connection before execution.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this <detects|optimizes|explains>
Tuning options
Validation approach
```
````

Keep the body short because the active agent receives it directly in its instruction prompt.

## `QUERIES.cypher` and `SETUP.md`

Every query in `QUERIES.cypher` — and every statement in `SETUP.md` when the package ships one — opens with an @-annotation block: a Cypher block comment before any logic, carrying @-prefixed key–value metadata per the agent-optimised query annotations RFC.

```cypher
/*
 * @name           Find connected products by customer
 * @description    Returns all products associated with a given customer
 *                 node, traversing up to three relationship hops.
 * @params         customerId - The internal ID of the customer node.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Product nodes with name, category, and purchase date.
 * @usage          Use when building customer-product recommendation
 *                 context. Widen the traversal depth only as far as the
 *                 result stays reviewable.
 * @tags           customer, product, recommendation
 */
```

Because the block is a comment, it can never execute as part of the query.

Required tags on a **query**: `@name`, `@description`, `@params`, `@prerequisites`, `@returns`, `@usage`, `@tags` — no `@version` (the package versions as a whole). Optional: `@pattern`, and `@sample` — concrete parameter values valid on the bundled sample and what the query returns with them, always opening `Bundled sample data only:`. Each parameter gets its own `@params` line, with wrapped text indented past the parameter name so the set stays machine-readable.

Required tags on a **`SETUP.md` statement**: `@name`, `@description`, and `@usage`. The rest only where meaningful — a schema statement usually has no parameters and returns nothing worth describing.

**Annotation blocks are data-agnostic, and so is the rest of QUERIES.cypher — except `@sample`.** The file travels into editors and into customers' databases, and the consuming agent surfaces the block when showing or running a query. An unlabelled claim about the bundled sample — a row count, a seeded entity name, a threshold justified by "the sample" — is false the moment the data is the user's own, and visibly so. `@sample` is the labelled exception: it exists so the agent can smoke-test a sample import and start from a valid anchor, it must agree with TESTS.md, and the package's SKILL.md tells the agent to use it only when the connected database holds the sample. Where a query has a parameter that gates its result, `@params` gives either a starting value with a reason that holds on any dataset ("start at 4 and raise until the result is a reviewable size") or a procedure for deriving one ("take the portfolio's upper quartile and start there") — never a value justified by the bundled rows.

Concrete expected results live in `TESTS.md`, not here. `QUERIES.cypher` is valid Cypher: prose and headings are `//` comments, queries are bare statements without code fences, and every statement ends in `;`. It also carries a short "Adapting these queries" section stating the procedure when the user's schema differs: read the live schema, map their labels onto SKILL.md's role map, rewrite, and update the annotation block to match.

The consuming agent treats the annotation block as context, not ground truth — query logic wins on conflict. The create-solution-package skill defines the full authoring rules.

## `TESTS.md`

The test oracle for the bundled sample data, and the one file in the package the runtime never loads.

It exists because the sample data is a means to a quick working demo, not the subject of the package. Expected row counts, seeded ring compositions, background-noise statistics and threshold-sensitivity notes are all genuinely useful — to the engineer curating the package and to an agent verifying it — and all actively harmful in the consuming agent's context, where they read as claims about the user's data.

Contract:

- **Reserved filename**, at the package root. Runtimes implementing this format must not load it and must not surface it to the agent.
- **Exempt from the supporting-file rule.** Every other non-required file must be indexed in SKILL.md with a stated purpose; `TESTS.md` must not be, precisely because the agent should never load it.
- **Exempt from the file-size limit.** It never consumes the consuming agent's context, so detail is free here. This is the file verbosity belongs in.
- **Required whenever the package bundles sample data.** A package whose CSVs resolve but which ships no `TESTS.md` has no oracle and cannot be verified.

Structure: a "How to run" preamble, the full sample-data profile, then one `##` section per query whose heading matches the text of its `QUERIES.cypher` `// ##` heading exactly, so the two files pair mechanically. Each file also has headings the other does not — prerequisites and the adapting section on one side, how-to-run and the profile on the other — and parity is checked over the query headings only.

Every query gets its own `##` section; a shared catch-all heading breaks parity. TESTS.md is written from the seeded design, not from a database run — testing against a database is manual and outside package creation.

Each query section states:

- **Parameters** — the values the tester should use.
- **Invariant** — what must hold whatever the data generator produces, expressed in terms of the seeded design ("returns the twelve Ring A claimants and no unseeded claimant"). This is what survives a data regeneration.
- **Expected** — optional; concrete expectations derivable from the CSVs, such as the seeded entities and counts the query should return. Useful and precise, but a snapshot of this dataset, not a contract.
- **Sensitivity** — optional; what other threshold values should do. This is the material that most often bloats QUERIES.cypher and it belongs here.

Separating invariant from expected counts is the point of the file. A package whose oracle is nothing but row counts breaks the first time anyone regenerates the CSVs, and the breakage looks like a query fault.

## `human_description.md`

The package explained to a person: clean Markdown, rendered as HTML in a UI, read by a human being deciding whether this package addresses their problem. No agent reads it at any point.

It exists because every other file in the package is written for a machine or for the engineer maintaining it. A reader arriving at a catalog card has nowhere to go for the plain-language account — what the industry is, what the problem is, and what the reference ontology actually holds — and the frontmatter blurb is one sentence.

Contract:

- **Reserved filename**, lower-case with an underscore, at the package root. Runtimes implementing this format must not load it into the agent's context and must not surface it to the agent.
- **Required**, whether or not the package bundles sample data. A reference-ontology template still needs explaining.
- **Exempt from the supporting-file rule.** Like `TESTS.md`, it must not be indexed in `SKILL.md` — the agent should never load it.
- **Exempt from the file-size limit**, for the same reason, though it has a practical length of its own: a page a reader gets through in two or three minutes.
- **Reference ontology.** Like every file in the package, it calls the ontology the *reference ontology* — never "graph model", "data model" or "schema".
- **No filenames, no Cypher, no JSON, no agent instructions, and no sample data** — not counts, not seeded entities, not a general mention. The reader sees a rendered page, not a directory, and the bundled data is out of scope for it. This is stricter than the rule on `SKILL.md`, which permits a general mention of the sample.

Structure — an `#` heading carrying the card title, a one- or two-sentence lead, then exactly two `##` sections:

- **Overview** — the industry in a few short paragraphs, then the problem statements and what the reference ontology makes answerable, as a table.
- **Ontology** — a short paragraph on the shape of it, then a table each for entities, properties, relationships, and relationship properties (the last omitted when no relationship carries one).

The Ontology tables must cover every node, relationship and property the reference ontology defines, with meanings drawn from its own `description` annotations and plain-Englished, never contradicted. Where one relationship type joins more than one pair of nodes, each pair gets its own row. The trailing `` e.g. `...` `` sample values in the property descriptions are dropped: they are sample data.

Favour small paragraphs, bullet summaries, and tables throughout. The create-solution-package skill defines the full authoring rules and carries a template.

## `ONTOLOGY.json`

Use [ONTOLOGY_SPEC_FORMAT.md](ONTOLOGY_SPEC_FORMAT.md) for the complete field-by-field format. Its authority is `ontology-graph-spec.schema.json`, bundled with the create-solution-package skill, which sets `additionalProperties: false` at every level — off-schema keys fail validation. That bundled file is the only schema a package is ever validated against; nothing is fetched over the network.

`ONTOLOGY.json` holds the package's **reference ontology**. It is required even when sample CSV files are not bundled. It must:

- Be valid JSON containing an object that validates against the bundled `ontology-graph-spec.schema.json`.
- Be accepted by the destination runtime's conversion. This is a required gate, not a courtesy check — see VALIDATION.md §3.
- Set `schema` to the ontology graph spec URI for the version the skill bundle is pinned to, `id` to the package's `skillId`, and `version` to the document's revision label.
- Define nodes, relationships, `extensions.data_source_tables`, `extensions.data_source_mappings` (one list, `mapping0`), and `extensions.display` coordinates on every node, with readable stable keys.
- Carry no other `extensions` — no `custom` at any level, no `indexes`, nothing on properties or relationships.
- Mark every node identifier `key: true` (composite keys via an explicit `KEY` constraint), and use `must_exist` for required non-key properties.
- Put each `key`, `must_exist` or `unique` flag on **one entry per relationship type or label**. The flags become database constraints scoped to the type, named from type and property, so the same flag on two entries of a reused type produces duplicate constraint names and the destination drops the package. State the requirement in prose on the other entries.
- Give a relationship mapping a `key` naming the distinguishing property wherever its table holds several rows for the same endpoint pair (parallel relationships); with `key: []`, `MERGE` collapses them into one.
- Define each query-referenced property with its correct graph type.
- Declare every bundled CSV in `extensions.data_source_tables` with `columns` listed in header order, each `name` equal to the header exactly and each `"type": "string"`; conversion happens through mappings (`NODE`/`RELATIONSHIP`, mode `MERGE`, `key` arrays, `column` references).
- Carry semantic annotations: a `description` on the root, on every node, on every relationship (meaning in the from→to direction, plus multiplicity in both directions), and on every property (unit, encoding, and scope for numeric and coded properties, ending with a `` e.g. `...` `` sample value drawn verbatim from the bundled CSVs); `one_of` or `pattern` where the domain fixes a property's values; relationship target counts matching the prose multiplicity; and `aliases` and `reference` where the source material supports them. See ONTOLOGY_SPEC_FORMAT.md's Annotations section for the full rules.
- **Declare only nodes and relationships that have a mapping.** Import reads the reference ontology as an import job definition and requires a source table, property columns, and endpoint ID columns for everything declared; an unmapped entity leaves the import definition in an error state the user cannot clear. A relationship or label a bundled query creates rather than loads therefore has no place in `ONTOLOGY.json` — document it in `SKILL.md` instead. See ONTOLOGY_SPEC_FORMAT.md's "Declare only what Import can load".

The consuming agent should treat these annotations as the authoritative meaning of each term — when explaining the reference ontology, adapting queries to user data, or generating new Cypher, its wording must agree with them.

Note that the trailing `` e.g. `...` `` sample values are the one place sample data legitimately reaches the consuming agent. They are there to show the shape of a value, not to describe the user's data, and an agent should read them as such.

Packages built before the ontology graph spec ship a `GRAPH_MODEL.json` in the older graph-spec format. ONTOLOGY_SPEC_FORMAT.md's "Converting a legacy graph model" maps every old field to its replacement.

### Minimal two-node pattern

Adapt every domain term, filename, property, and mapping. Do not leave angle-bracket placeholders or JSON comments in the finished file.

```json
{
  "schema": "https://neo4j.com/docs/ontology-graph-spec/1.0.0/schema.json",
  "id": "entity-events",
  "version": "1",
  "name": "Entity Events",
  "description": "Minimal reference ontology relating entities to the timestamped events they produce.",
  "nodes": {
    "Entity": {
      "label": "Entity",
      "description": "A tracked subject in the domain; the anchor for event history.",
      "aliases": ["Subject"],
      "properties": {
        "entityId": {
          "type": "STRING",
          "description": "Unique identifier for the entity. Expected to be stable across source systems. e.g. `entity-1`.",
          "key": true
        }
      },
      "extensions": {
        "display": { "x": -100, "y": 0 }
      }
    },
    "Event": {
      "label": "Event",
      "description": "A single occurrence attributed to one entity at a point in time.",
      "properties": {
        "eventId": {
          "type": "STRING",
          "description": "Unique identifier for the event. e.g. `event-1`.",
          "key": true
        },
        "occurredAt": {
          "type": "ZONED DATETIME",
          "description": "Moment the event occurred, ISO 8601 with timezone. e.g. `2026-01-10T09:00:00Z`.",
          "must_exist": true
        },
        "channel": {
          "type": "STRING",
          "description": "Channel through which the event was recorded: online (web), in person at a branch (branch), or by telephone (phone). e.g. `web`.",
          "one_of": ["web", "branch", "phone"]
        }
      },
      "extensions": {
        "display": { "x": 100, "y": 0 }
      }
    }
  },
  "relationships": {
    "hasEvent": {
      "type": "HAS_EVENT",
      "description": "Attributes an event to the entity that produced it. Each event belongs to exactly one entity; an entity may produce many events, or none.",
      "from": { "node": "Entity" },
      "to": { "node": "Event", "count": 1 }
    }
  },
  "extensions": {
    "data_source_tables": {
      "entities.csv": {
        "source": "local",
        "columns": [
          { "name": "entityId", "type": "string" }
        ]
      },
      "events.csv": {
        "source": "local",
        "columns": [
          { "name": "eventId", "type": "string" },
          { "name": "entityId", "type": "string" },
          { "name": "occurredAt", "type": "string" },
          { "name": "channel", "type": "string" }
        ]
      }
    },
    "data_source_mappings": {
      "mapping0": [
        {
          "type": "NODE",
          "node": "Entity",
          "table": "entities.csv",
          "mode": "MERGE",
          "key": ["entityId"],
          "properties": {
            "entityId": { "column": "entityId" }
          }
        },
        {
          "type": "NODE",
          "node": "Event",
          "table": "events.csv",
          "mode": "MERGE",
          "key": ["eventId"],
          "properties": {
            "eventId": { "column": "eventId" },
            "occurredAt": { "column": "occurredAt" },
            "channel": { "column": "channel" }
          }
        },
        {
          "type": "RELATIONSHIP",
          "relationship": "hasEvent",
          "table": "events.csv",
          "mode": "MERGE",
          "key": [],
          "from_node": {
            "label": "Entity",
            "properties": {
              "entityId": { "column": "entityId" }
            }
          },
          "to_node": {
            "label": "Event",
            "properties": {
              "eventId": { "column": "eventId" }
            }
          }
        }
      ]
    }
  }
}
```

Common graph property types in packages include `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `DATE`, and `ZONED DATETIME`; the full set is the spec's `Neo4jType` enum.

Note the annotation shape in the example: `description` on the root, nodes, relationships, and properties; property descriptions ending with a `` e.g. `...` `` value that appears verbatim in the sample CSVs below; a closed value set as `one_of`; an industry synonym as an alias; and the relationship's multiplicity stated in its description in both directions and as counts on its targets — every event has exactly one `HAS_EVENT` (`to.count: 1`), while an entity's zero-or-more is the unconstrained default, so `from` carries no count. Every sample value must match a real value in the mapped CSV column — mismatches are validation failures. Note also which extensions the example carries — `tables`, `mappings` and node `display` — and that it carries no others.

## Sample CSV files

Put import-ready files under `sample-data/`. The parser resolves CSV references found in the reference ontology's `extensions.data_source_tables` keys and mapping `table` values.

For the minimal example:

`sample-data/entities.csv`

```csv
entityId
entity-1
entity-2
```

`sample-data/events.csv`

```csv
eventId,entityId,occurredAt,channel
event-1,entity-1,2026-01-10T09:00:00Z,web
event-2,entity-2,2026-01-10T10:00:00Z,branch
```

Resolution rules:

- Only CSV files under `sample-data/` become import samples.
- Basename references such as `events.csv` resolve anywhere below `sample-data/` when unambiguous.
- A relative-path reference must match exactly.
- If some referenced CSVs resolve and others do not, the use case is invalid.
- If no referenced CSV resolves, the use case remains valid but reports no bundled sample data.
- Duplicate basenames are ambiguous unless the reference ontology's table references use explicit relative paths.

Prefer a complete, deliberately useful sample over a large dataset. Include rows that make every showcased query return a meaningful result.

The sample data is a means to a quick working demo. It is not the subject of the package, and no file the consuming agent reads should describe it in forensic detail — that description belongs in `TESTS.md`.

## Runtime and integration

### Automatic use-case discovery

In a runtime that implements this format, adding a valid folder to its configured use-case root enables discovery. Typically:

- `SKILL.md` and `ONTOLOGY.json` are loaded eagerly, and the reference ontology is converted to an Import model while the catalogue loads.
- `TESTS.md` is never loaded, at any point, by any path.
- `human_description.md` is never loaded into the agent's context either. It is available to the UI for rendering, and to it alone.
- Every other file is read on demand through a tool that refuses any file over 50,000 characters, so a longer QUERIES.cypher, SETUP.md, ONTOLOGY.json or supporting file is unreadable to the agent.
- An invalid use case is logged and skipped rather than failing the build — and "invalid" includes a reference ontology the runtime cannot convert to an Import model (a duplicate constraint name, an encoding it cannot read). The package simply disappears from the catalogue, which is why VALIDATION.md's runtime gate runs the same two steps.

The active agent receives the use case's `SKILL.md` body.

### Manual selectable-card integration

Do not assume how the destination project registers selectable use cases. When integration is requested:

1. Locate its assistant-target and card registration mechanisms.
2. Register the folder-derived `skillId`.
3. Configure the card title, description, and category.
4. Confirm the category resolves to the intended icon in the destination, which derives one from it.
5. Extend the destination project's focused registry and UI tests.

Do not assume frontmatter metadata automatically creates a selectable tile.

### The package repository

In `neo4j/studio-agent-use-cases`, every package also has an entry in the root `catalog.json` listing its files: `files.graph` is `ONTOLOGY.json`, `files.markdown` is `SKILL.md`, and `files.skill` is every other file in the folder — sample-data CSVs first, then the rest, each group sorted case-insensitively. `scripts/catalog_entry.py` in the create-solution-package skill builds the entry from the folder; a new or changed package updates it in the same pull request.

### Sample-data behavior

When every CSV the reference ontology references resolves from `sample-data/`, the manifest reports `hasSampleData: true`. The assistant can preview the reference ontology and load it into the Import app. That is the only supported route for getting data into the graph. Packages must not ship a write-based data seed, and the assistant will not generate one on request.

Sample data is one of three ways a user reaches a package's queries — the others being their own data mapped through the reference ontology, and a database that predates the package entirely. Only the first has a test oracle. The other two are the runtime's responsibility to handle, and the package supports them through the role map and the adapting section rather than through anything sample-specific.
