# Assistant Sidebar Use Case Format

Use this reference when creating a use-case folder. The folder name becomes `skillId`; it is independent from the semantic `name` in frontmatter.

## Enforced structure

```text
<skillId>/
├── SKILL.md                    # required
├── GRAPH_MODEL.json            # required
├── QUERIES.md                  # required for packages — runnable Cypher
├── TESTS.md                    # required when sample data is bundled — authoring-side only, never loaded
├── SETUP.md                    # optional — post-import statements the queries depend on
└── sample-data/                # optional, but the required location for bundled CSV data
    └── *.csv
```

Sample data is optional at the format level — `GRAPH_MODEL.json` is required either way — but a use case that bundles none also has nothing to test, and is a model template rather than a working demo. `TESTS.md` is required exactly when sample data is present.

If the use case bundles sample CSVs for Import, every CSV must be below `sample-data/`.

There is no `INTRODUCTION.md`. The agent introduces the package from guidance inside SKILL.md (an "Introducing this package" section), not from a canned document.

`TESTS.md` is a reserved filename with a special contract — see [TESTS.md](#testsmd) below. It is the only file in the package the runtime deliberately ignores.

## Identity and metadata

Keep these identifiers distinct:

| Value         | Source                         | Purpose                                           |
| ------------- | ------------------------------ | ------------------------------------------------- |
| `skillId`     | Use-case folder name           | Registry lookup, tool calls, and assistant target |
| `name`        | `SKILL.md` frontmatter         | Semantic Agent Skill name and sample-model naming |
| Card title    | `metadata.neo4j-card-title`    | Human-readable catalog title                      |
| Card category | `metadata.neo4j-card-category` | Catalog grouping, e.g. Healthcare & Life Sciences |
| Card blurb    | `metadata.neo4j-card-description` | One-sentence user-facing value statement       |
| Spec version  | `metadata.neo4j-graph-spec-version` | The graph spec `GRAPH_MODEL.json` was built against |

`neo4j-graph-spec-version` binds the package to a specific graph spec. A model is only meaningful against the spec that defines its fields, and the spec has changed shape within a single format version before — so this value, not `GRAPH_MODEL.json`'s `version`, is what identifies the contract the package was authored under. Validation rejects a package whose value differs from the skill bundle's pin.

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
- No `neo4j-icon-category` key is present.
- `neo4j-graph-spec-version` is required and non-empty, and must equal the spec version the skill bundle is pinned to.
- Markdown after frontmatter must be non-empty.

### The role map

SKILL.md's Model section carries a **conceptual role map**: a small table naming the abstract roles the model's labels play, alongside what a substitute in someone else's schema would have to supply. It exists because the package's value is the analytical patterns, not the labels — and a user who arrives with their own model, or their own database, needs those patterns to survive the rename.

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
  neo4j-graph-spec-version: <the skill bundle's pinned spec version, verbatim>
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

## Model

- <Nodes and relationships in one or two lines each; key properties.>
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is
  in `QUERIES.md`.

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| <Abstract role> | `<Label>` | <The property or connection the pattern depends on> |

When the user's schema differs from this model, map their labels onto
these roles before rewriting anything from `QUERIES.md`. A role with no
counterpart in their data means the patterns resting on it have no
analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through Import only. Never offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative route.
- Confirm before executing anything that writes, and confirm the target database first.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- Treat the `description` annotations in `GRAPH_MODEL.json` — on nodes, relationships, and properties — as the authoritative meaning of each model term when explaining the model, adapting it to user data, or generating Cypher.
- <Name any `SETUP.md` statements and the queries that depend on them, when the package ships one.>
- <State Neo4j, Cypher, APOC, or GDS prerequisites.>
- Clarify the intended target database and connection before execution.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this <detects|optimizes|explains>
Tuning options
Validation approach
```
````

Keep the body short because the active agent receives it directly in its instruction prompt.

## `QUERIES.md` and `SETUP.md`

Every query in `QUERIES.md` — and every statement in `SETUP.md` when the package ships one — opens with an @-annotation block: a Cypher block comment before any logic, carrying @-prefixed key–value metadata per the agent-optimised query annotations RFC.

```cypher
/*
 * @name           Find connected products by customer
 * @description    Returns all products associated with a given customer
 *                 node, traversing up to three relationship hops.
 * @params         customerId - The internal ID of the customer node.
 * @prerequisites  None beyond the imported model.
 * @returns        Product nodes with name, category, and purchase date.
 * @usage          Use when building customer-product recommendation
 *                 context. Widen the traversal depth only as far as the
 *                 result stays reviewable.
 * @tags           customer, product, recommendation
 */
```

Because the block is a comment, it can never execute as part of the query.

Required tags on a **query**: `@name`, `@description`, `@params`, `@prerequisites`, `@returns`, `@usage`, `@tags` — no `@version` (the package versions as a whole). Each parameter gets its own `@params` line, with wrapped text indented past the parameter name so the set stays machine-readable.

Required tags on a **`SETUP.md` statement**: `@name`, `@description`, and `@usage`. The rest only where meaningful — a schema statement usually has no parameters and returns nothing worth describing.

**Annotation blocks are data-agnostic, and so is the rest of QUERIES.md.** The file travels into editors and into customers' databases, and the consuming agent surfaces the block when showing or running a query. A claim about the bundled sample — a row count, a seeded entity name, a threshold justified by "the sample" — is false the moment the data is the user's own, and visibly so. Where a query has a parameter that gates its result, `@params` gives either a starting value with a reason that holds on any dataset ("start at 4 and raise until the result is a reviewable size") or a procedure for deriving one ("take the portfolio's upper quartile and start there") — never a value justified by the bundled rows.

Concrete expected results live in `TESTS.md`, not here. `QUERIES.md` also carries a short "Adapting these queries" section stating the procedure when the user's schema differs: read the live schema, map their labels onto SKILL.md's role map, rewrite, and update the annotation block to match.

The consuming agent treats the annotation block as context, not ground truth — query logic wins on conflict. The create-solution-package skill defines the full authoring rules.

## `TESTS.md`

The test oracle for the bundled sample data, and the one file in the package the runtime never loads.

It exists because the sample data is a means to a quick working demo, not the subject of the package. Expected row counts, seeded ring compositions, background-noise statistics and threshold-sensitivity notes are all genuinely useful — to the engineer curating the package and to an agent verifying it — and all actively harmful in the consuming agent's context, where they read as claims about the user's data.

Contract:

- **Reserved filename**, at the package root. Runtimes implementing this format must not load it and must not surface it to the agent.
- **Exempt from the supporting-file rule.** Every other non-required file must be indexed in SKILL.md with a stated purpose; `TESTS.md` must not be, precisely because the agent should never load it.
- **Exempt from the file-size guidance.** It never consumes the consuming agent's context, so detail is free here. This is the file verbosity belongs in.
- **Required whenever the package bundles sample data.** A package whose CSVs resolve but which ships no `TESTS.md` has no oracle and cannot be verified.

Structure: a "How to run" preamble, the full sample-data profile, then one `##` section per query whose heading matches its `QUERIES.md` heading exactly, so the two files pair mechanically. Each file also has headings the other does not — prerequisites and the adapting section on one side, how-to-run and the profile on the other — and parity is checked over the query headings only.

A query that could not be executed still gets its own `##` section, stating what it was not run against and why. `## Queries not executed` as a single catch-all breaks parity and hides which query is unverified.

Each query section states:

- **Parameters** — the values used for the run.
- **Invariant** — what must hold whatever the data generator produces, expressed in terms of the seeded design ("returns the twelve Ring A claimants and no unseeded claimant"). This is what survives a data regeneration.
- **Observed** — the concrete snapshot: row counts, returned values, the date or data version of the run. Useful and precise, but a snapshot, not a contract.
- **Sensitivity** — optional; what other threshold values do. This is the material that most often bloats QUERIES.md and it belongs here.

Separating invariant from observed is the point of the file. A package whose oracle is nothing but row counts breaks the first time anyone regenerates the CSVs, and the breakage looks like a query fault.

## `GRAPH_MODEL.json`

Use [GRAPH_SPEC_FORMAT.md](GRAPH_SPEC_FORMAT.md) for the complete field-by-field format. Its authority is `graph-spec.schema.json`, bundled with the create-solution-package skill, which sets `additionalProperties: false` at every level — off-schema keys fail validation. That bundled file is the only schema a package is ever validated against; nothing is fetched over the network.

`GRAPH_MODEL.json` is required even when sample CSV files are not bundled. It must:

- Be valid JSON containing an object that validates against the bundled `graph-spec.schema.json`.
- Be accepted by the destination runtime's conversion. This is a required gate, not a courtesy check — see VALIDATION.md §3.
- Use graph-spec format version `4.0.0`, and be built against the spec version the skill bundle is pinned to — recorded in the package's `metadata.neo4j-graph-spec-version`.
- Define nodes, relationships, tables, mappings, and display coordinates, with readable stable keys.
- Mark every node identifier `key: true` (composite keys via an explicit `KEY` constraint), and use `mustExist` — not the removed `nullable` — for required non-key properties.
- Define each query-referenced property with its correct graph type.
- Declare bundled-CSV table fields as `"type": "string"`, keyed by exact CSV headers, each also carrying an explicit `"name"` equal to its key — without it the field name is silently dropped when the model is encoded and the package breaks on load; conversion happens through mappings (`NodeMapping`/`RelationshipMapping`, mode `MERGE`, `key` arrays).
- Carry semantic annotations, all of them in `description` fields: on the spec root, on every node, on every relationship (meaning in the from→to direction, plus multiplicity in both directions), and on every property (unit, encoding, and scope for numeric and coded properties, ending with a `` e.g. `...` `` sample value drawn verbatim from the bundled CSVs). See GRAPH_SPEC_FORMAT.md's Annotations section for the full rules.
- Contain **no `extensions` block anywhere**. The spec schema defines one, but the pinned runtime rejects every encoding of it and drops the whole package — see GRAPH_SPEC_FORMAT.md's Pipeline caveats.

The consuming agent should treat these descriptions as the authoritative meaning of each model term — when explaining the model, adapting queries to user data, or generating new Cypher, its wording must agree with them.

Note that the trailing `` e.g. `...` `` sample values are the one place sample data legitimately reaches the consuming agent. They are there to show the shape of a value, not to describe the user's data, and an agent should read them as such.

### Minimal two-node pattern

Adapt every domain term, filename, property, and mapping. Do not leave angle-bracket placeholders or JSON comments in the finished file.

```json
{
  "version": "4.0.0",
  "name": "Entity Events",
  "description": "Minimal model relating entities to the timestamped events they produce.",
  "nodes": {
    "Entity": {
      "label": "Entity",
      "description": "A tracked subject in the domain; the anchor for event history.",
      "properties": {
        "entityId": {
          "type": "STRING",
          "description": "Unique identifier for the entity. Expected to be stable across source systems. e.g. `entity-1`.",
          "key": true
        }
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
          "mustExist": true
        }
      }
    }
  },
  "relationships": {
    "hasEvent": {
      "type": "HAS_EVENT",
      "description": "Attributes an event to the entity that produced it. Each event belongs to exactly one entity; an entity may produce many events, or none.",
      "from": { "node": "Entity" },
      "to": { "node": "Event" }
    }
  },
  "tables": {
    "entities.csv": {
      "source": "local",
      "fields": {
        "entityId": { "name": "entityId", "type": "string" }
      }
    },
    "events.csv": {
      "source": "local",
      "fields": {
        "eventId": { "name": "eventId", "type": "string" },
        "entityId": { "name": "entityId", "type": "string" },
        "occurredAt": { "name": "occurredAt", "type": "string" }
      }
    }
  },
  "mappings": [
    {
      "type": "NodeMapping",
      "node": "Entity",
      "table": "entities.csv",
      "mode": "MERGE",
      "key": ["entityId"],
      "properties": {
        "entityId": { "field": "entityId" }
      }
    },
    {
      "type": "NodeMapping",
      "node": "Event",
      "table": "events.csv",
      "mode": "MERGE",
      "key": ["eventId"],
      "properties": {
        "eventId": { "field": "eventId" },
        "occurredAt": { "field": "occurredAt" }
      }
    },
    {
      "type": "RelationshipMapping",
      "relationship": "hasEvent",
      "table": "events.csv",
      "mode": "MERGE",
      "key": [],
      "from": {
        "node": "Entity",
        "properties": {
          "entityId": { "field": "entityId" }
        }
      },
      "to": {
        "node": "Event",
        "properties": {
          "eventId": { "field": "eventId" }
        }
      }
    }
  ],
  "display": {
    "nodes": {
      "Entity": { "x": -100, "y": 0 },
      "Event": { "x": 100, "y": 0 }
    }
  }
}
```

Common graph property types in packages include `STRING`, `INTEGER`, `FLOAT`, `BOOLEAN`, `DATE`, and `ZONED DATETIME`; the full set is the spec's `Neo4jType` enum.

Note the annotation shape in the example: `description` on the root, nodes, relationships, and properties; property descriptions ending with a `` e.g. `...` `` value that appears verbatim in the sample CSVs below; the relationship's multiplicity stated in its description in both directions. Every sample value must match a real value in the mapped CSV column — mismatches are validation failures. Note also what the example does *not* contain: any `extensions` block.

## Sample CSV files

Put import-ready files under `sample-data/`. The parser resolves CSV references found in graph-model `tables` keys and `mappings[].table`.

For the minimal example:

`sample-data/entities.csv`

```csv
entityId
entity-1
entity-2
```

`sample-data/events.csv`

```csv
eventId,entityId,occurredAt
event-1,entity-1,2026-01-10T09:00:00Z
event-2,entity-2,2026-01-10T10:00:00Z
```

Resolution rules:

- Only CSV files under `sample-data/` become import samples.
- Basename references such as `events.csv` resolve anywhere below `sample-data/` when unambiguous.
- A relative-path reference must match exactly.
- If some referenced CSVs resolve and others do not, the use case is invalid.
- If no referenced CSV resolves, the use case remains valid but reports no bundled sample data.
- Duplicate basenames are ambiguous unless graph-model references use explicit relative paths.

Prefer a complete, deliberately useful sample over a large dataset. Include rows that make every showcased query return a meaningful result.

The sample data is a means to a quick working demo. It is not the subject of the package, and no file the consuming agent reads should describe it in forensic detail — that description belongs in `TESTS.md`.

## Runtime and integration

### Automatic use-case discovery

In a runtime that implements this format, adding a valid folder to its configured use-case root enables discovery. Typically:

- `SKILL.md` and `GRAPH_MODEL.json` are loaded eagerly.
- `TESTS.md` is never loaded, at any point, by any path.
- An invalid use case is logged and skipped rather than necessarily failing the build.

The active agent receives the use case's `SKILL.md` body.

### Manual selectable-card integration

Do not assume how the destination project registers selectable use cases. When integration is requested:

1. Locate its assistant-target and card registration mechanisms.
2. Register the folder-derived `skillId`.
3. Configure the card title, description, and category.
4. Confirm the category resolves to the intended icon in the destination, which derives one from it.
5. Extend the destination project's focused registry and UI tests.

Do not assume frontmatter metadata automatically creates a selectable tile.

### Sample-data behavior

When every graph-referenced CSV resolves from `sample-data/`, the manifest reports `hasSampleData: true`. The assistant can preview the model and load it into the Import app. That is the only supported route for getting data into the graph. Packages must not ship a write-based data seed, and the assistant will not generate one on request.

Sample data is one of three ways a user reaches a package's queries — the others being their own data mapped through this model, and a database that predates the package entirely. Only the first has a test oracle. The other two are the runtime's responsibility to handle, and the package supports them through the role map and the adapting section rather than through anything sample-specific.
