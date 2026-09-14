---
name: create-solution-package
description: Build a Neo4j industry solution package — a graph model (graph spec JSON), sample CSV data with import mappings, proven Cypher queries, and agent guidance — for Aura's onboarding agent. Use whenever a user wants to create, draft, scaffold, rebuild, or review a solution package, industry use case, or vertical quick start, e.g. "make a package like insurance-claims-fraud for telecoms". The output is a starting point for human curation, not a finished product.
---

# Create a Solution Package

A solution package is an agent skill that Aura's onboarding agent loads to help a user get started with Neo4j in a specific industry. It bundles a graph model, sample data matching that model, proven Cypher queries, and guidance that steers the agent. The same model doubles as a template for the user to map and import their own data via Neo4j's Import tool.

Your job: take the user's raw inputs and produce a complete, consistent draft package. An engineer will curate it — flag anything you're unsure about with `TODO(review):` rather than silently guessing.

Companion skills: [GRAPH_SPEC_FORMAT.md](GRAPH_SPEC_FORMAT.md) is the contract for `GRAPH_MODEL.json` — follow it exactly; its authority is `graph-spec.schema.json`, bundled here. [VALIDATION.md](VALIDATION.md) is the check suite to run before handing off.

**The bundled schema is the only graph spec.** Never fetch one over the network or reason from a remembered version — the bundled file is pinned deliberately, and packages are bound to it. GRAPH_SPEC_FORMAT.md carries the pinned version; every package you build records it.

## Who reads what

This is the constraint that shapes every decision below. A package has two audiences and they need opposite things.

**The consuming agent** receives SKILL.md's body directly in its instruction prompt and loads QUERIES.md when it needs Cypher. Everything it reads costs context, and everything it reads it may repeat to a user whose data is not yours. It needs the model's meaning, the query patterns, and honest caveats — stated so they stay true whatever data is in the database.

**The curating engineer**, and any agent verifying the package, needs the opposite: concrete row counts, the exact composition of the seeded rings, what happens at other thresholds, which query returned what on which day. All of that is real work product and none of it belongs anywhere the consuming agent can read it, because on the user's own data it is not merely useless but wrong.

TESTS.md is where the second audience is served. Keep the line clean and most authoring questions answer themselves.

## Package structure

Six parts, five of them required. Keep packages this small where possible — experience shows it is usually sufficient.

```text
<package-name>/          # kebab-case; the folder name becomes the skillId
├── SKILL.md             # agent guidance: frontmatter + body (see below)
├── GRAPH_MODEL.json     # graph spec per GRAPH_SPEC_FORMAT.md
├── QUERIES.md           # runnable Cypher with @-annotation blocks
├── TESTS.md             # expected results on the sample data — never loaded by the runtime
├── SETUP.md             # optional — post-import statements the queries depend on
└── sample-data/
    └── *.csv            # one CSV per table in GRAPH_MODEL.json
```

A package with no sample data is a model template, not a working demo, and needs no TESTS.md. Assume you are building the working demo unless the user says otherwise.

There is no INTRODUCTION.md. The agent introduces the package from guidance inside SKILL.md (see the template below), not from a canned document.

Complex packages may add supporting files (`.md` or `.cypher` only) when they are justified in explaining the package to the agent and how to use it effectively — for example a multi-step workflow, detailed model rationale, or honest caveats that would bloat SKILL.md (see `identity-validation` for a worked example). Each one must earn its place: add it only when the content is too large or too specialised for SKILL.md or QUERIES.md, and index every one in a "Supporting files" table in SKILL.md stating when the agent should load it. Simple packages need none. Keep each readable file under ~50,000 characters as a working target — this is guidance, not an enforced limit, but larger files consume more of the consuming agent's context and increase the need for a more powerful model, so justify any file that exceeds it and note it in the handoff. Paths must be relative with forward slashes.

`TESTS.md` and the sample-data CSVs are exempt from both rules: neither is indexed in SKILL.md, and neither counts against the size target, because neither reaches the consuming agent.

## Identity and metadata

| Value         | Source                         | Purpose                                  |
| ------------- | ------------------------------ | ---------------------------------------- |
| `skillId`     | Package folder name            | Registry lookup and assistant target     |
| `name`        | SKILL.md frontmatter           | Semantic skill name; may equal `skillId` |
| Card title    | `metadata.neo4j-card-title`    | Human-readable catalog title             |
| Card category | `metadata.neo4j-card-category` | Catalog grouping — a closed set; see PACKAGE_FORMAT.md for the allowed values |
| Card blurb    | `metadata.neo4j-card-description` | One-sentence user-facing value statement |
| Spec version  | `metadata.neo4j-graph-spec-version` | The graph spec the model was built against — copy the pin from GRAPH_SPEC_FORMAT.md verbatim |

Parser contract for SKILL.md: begins with YAML frontmatter delimited by `---`; `name` is 1–64 chars matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`; `description` is non-empty, specific, and at most 1024 characters (it is the trigger text — state the industry, the use cases, and the capabilities); all `metadata` values are strings and the `neo4j-card-*` fields are non-empty; `neo4j-graph-spec-version` is present and equals the pin in GRAPH_SPEC_FORMAT.md; the Markdown body after frontmatter is non-empty.

## Inputs to gather

Ask for whatever is missing, but don't block — draft and flag instead:

1. **Industry links** — pages explaining the industry and use cases (neo4j.com/developer/industry-use-cases/ pages are ideal). Fetch and read them; they drive the use cases, terminology, and caveats.
2. **Graph model** — ideally graph-spec JSON. From a description or diagram, build the spec yourself and mark it `TODO(review)`.
3. **Sample Cypher** — proven queries. If none provided, draft a small set from the use cases and mark each `TODO(review): unproven query`.

Also confirm: package name (kebab-case), a one-line industry qualifier, and the primary use cases (3–5).

## Build order

Each artifact constrains the next — build in this order.

### 1. GRAPH_MODEL.json

Follow [GRAPH_SPEC_FORMAT.md](GRAPH_SPEC_FORMAT.md) exactly, and build against the bundled `graph-spec.schema.json` — read it if you need to settle a question the format doc leaves open, and never substitute a remote or remembered version. Record its pinned version in the package's `metadata.neo4j-graph-spec-version` when you write SKILL.md at step 6. Every property a query will touch must exist with the correct graph type; every node identifier is marked `key: true` (composite keys via an explicit `KEY` constraint); every CSV is declared in `tables` and bound in `mappings` (`NodeMapping`/`RelationshipMapping`, mode `MERGE`, `key` arrays); every node gets display coordinates.

**Annotate the model as you build it, not afterwards.** The spec root, every node, every relationship, and every property gets a `description` — and all annotation lives there. Numeric and coded property descriptions end with a `` e.g. `...` `` sample value (backfilled verbatim from the CSVs in step 2). Descriptions are the semantic contract the sample data and queries must satisfy, and they travel into the user's database with the model — they are what a downstream agent reasons from. Relationship descriptions state what the connection means in the from→to direction and its multiplicity in both directions; where one relationship type is reused between node pairs, each entry's description states its distinct meaning. **Never write an `extensions` block** — the pinned runtime rejects every encoding of it and silently drops the whole package. GRAPH_SPEC_FORMAT.md's Annotations section has the full rules.

**Descriptions you inferred need the user's confirmation.** Source material rarely defines meaning down to the property level — a source page will name `dosage` on a prescription without saying per-administration or per-day, mg or mL. Use the full context you have (the domain, the model structure, the use cases, the queries you plan) to draft the most reasonable reading, then put the uncertain ones to the user before generating sample data:

- Batch the uncertain descriptions into one prompt: for each, state the property (or relationship), your proposed description (with unit/encoding/scope), and why you chose that reading.
- Invite overrides explicitly — the user can accept all, or reply with corrections in their own words, which you then apply verbatim in spirit.
- Definitional glosses that follow directly from the label and model structure don't need confirmation. Units, encodings, scopes, and code systems that the source doesn't state always do.
- If the user is unavailable or defers, keep your best guess and mark it `TODO(review): inferred description` — never present an unconfirmed stipulation as settled.

This confirmation happens at step 1 deliberately: once CSVs and queries exist, a wrong reading is baked into data and thresholds, not just prose.

### 2. sample-data/ CSVs

One CSV per table in the spec. Headers must match the table's field keys exactly, including case — the Import tool depends on it. **Deliberately seed the patterns the queries detect**: a fraud package contains an actual ring, a routing package contains a reachable route. Size the data so results are meaningful rather than trivial (working packages range from tens of rows to a few thousand), and keep signal rows distinguishable from a realistic non-matching background. A query that returns zero rows against the sample data is a broken package.

The data must also satisfy the model's annotations: every value conforms to its property's confirmed `description` (unit, encoding, scope), and any multiplicity claim stated in a relationship description holds. Once the CSVs exist, backfill each property description's trailing `` e.g. `...` `` with a real value taken verbatim from the mapped column.

Keep a working note of what you seeded as you go — ring composition, deliberate background noise, the counts each pattern produces. That note becomes TESTS.md at step 4. Do not put it in QUERIES.md.

### 3. QUERIES.md

The agent runs these as-is when the schema matches and rewrites them when it doesn't, so correctness beats cleverness — and everything in the file must stay true on data that isn't yours.

- Open with a short preamble: prerequisites in one place (Neo4j/Cypher version, APOC or GDS needs). **No sample-data profile** — row counts, seeded signals and noise statistics go in TESTS.md.
- Follow it with a short **"Adapting these queries"** section — see below.
- One `##` heading per query, simplest first, each with a fenced ```` ```cypher ```` block.
- **Every query opens with an @-annotation block** — a Cypher block comment (`/* ... */`) before any query logic, so it can never execute, carrying @-prefixed key–value annotations:

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
   *                 result stays reviewable — three hops reaches most
   *                 catalogues without fanning out to everything.
   * @tags           customer, product, recommendation
   */
  MATCH (c:Customer {id: $customerId})-[*1..3]-(p:Product)
  RETURN p.name, p.category, p.purchaseDate
  ```

  Required tags: `@name` (matching the `##` heading), `@description`, `@params`, `@prerequisites`, `@returns` (the shape of the result), `@usage` (constraints and tuning guidance), `@tags`. Omit `@version` — the package versions as a whole. The set is extensible per the RFC; add a new @tag only when it earns its place.

  **`@params` is one line per parameter**, starting at the parameter name, with any wrapped text indented past it. A second parameter that begins at the same indent as the first one's continuation lines is unparseable — no checker can tell it from a fourth line of prose. Write `None` when the query takes none.

  ```text
   * @params         minClaims - Minimum claims filed. Integer. Start at 4 and
   *                     raise until the result is reviewable by hand.
   *                 minExposure - Minimum summed value across those claims.
   ```
- **The whole file is data-agnostic, not just the annotation blocks.** No row counts, no seeded-entity names, no thresholds justified by the bundled data, anywhere in QUERIES.md. The file travels with the package into editors and customers' databases, and the Solution Agent's show/run tooling surfaces annotation blocks to help the user understand a query — a sample-data claim is false the moment the data is the user's own, and conspicuously so.
- **Every parameter that gates a result needs a starting point, stated data-agnostically.** A threshold with no suggested value is unusable without opening the test file. Give either a concrete value justified by what the parameter does — "start at 4 and raise until the result is a reviewable size" — or a procedure for deriving one where no number could transfer between datasets: "take the portfolio's upper quartile of claims per professional and start there". Both travel; "4 returns the seeded ring" does not.

  The trap here is subtler than a row count, and no grep catches it. A justification can be phrased data-agnostically and still be a fact about your generator: "start at 4, which clears ordinary household size" sounds like domain knowledge, but if you picked 4 because your noise generator caps legitimate groups at 3, it is the seed talking. Test each one by asking whether you would write the same sentence having never seen the CSVs. If not, either find the real domain reason or say plainly that the value is a starting point with no strong prior behind it. The tuned value, and the honest note about where it came from, go in TESTS.md.
- Reference only labels, relationship types, directions, and properties defined in GRAPH_MODEL.json.
- **Annotation blocks inherit the model's vocabulary.** When `@description`, `@params`, or `@usage` explains a property or relationship, use the wording, unit, scope, and direction from its GRAPH_MODEL.json `description` — never a paraphrase that could drift (if the model says dose per administration in milligrams, the annotation doesn't say "daily dosage"). The model's descriptions, the query annotations, and the queries themselves must read as one coherent artifact.
- Bound every variable-length traversal.
- Mark anything not executed against a live database with a literal `TODO(review): unproven query` line inside the annotation block, and isolate optional APOC/GDS material in its own clearly labelled section.
- **Design rationale is not query material.** Why the model diverges from a published source page, why a query differs from the one on that page — that is a line or two in SKILL.md's Model section, or a supporting rationale file if it genuinely needs more. It does not belong between the queries.
- End with the node-key constraints implied by GRAPH_MODEL.json (`key: true` properties and any composite `KEY` constraints), framed as a schema reference. Import creates them from GRAPH_MODEL.json, so they are there to verify the expected schema, not to build it. Section prose introduces them; the individual statements need no annotation blocks.

#### The "Adapting these queries" section

A dozen lines or so near the top of QUERIES.md, stating the procedure once for the whole package rather than repeating it per query:

```markdown
## Adapting these queries

These queries assume the model in `GRAPH_MODEL.json`. When the user's
schema differs — their own model, a modified one, or a database that
predates this package — the queries are patterns to rebuild, not Cypher
to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`)
   rather than assuming this model applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no
   counterpart means the pattern below it has no analogue — say so
   rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe
   what the rewritten query actually does.
```

That is the whole investment. Do not add per-query rewrite prose: it is boilerplate against a capable agent, and it costs context on every query to say what one section says once. The exception, used sparingly, is a query whose analytical shape genuinely isn't recoverable from its Cypher — there, add `@pattern` (the schema-independent shape in one line) to the annotation block. Most queries don't need it.

### 4. TESTS.md

Everything concrete about the bundled sample data, in one file the runtime never loads.

Write it immediately after QUERIES.md, from the working note kept at step 2 and the results of actually running the queries. It is the oracle VALIDATION.md checks against and the reference an engineer curating the package needs, and it is exempt from the size target — detail is free here, because none of it reaches the consuming agent.

Structure:

- **How to run** — that a disposable database is required, that the CSVs import through the Import flow from GRAPH_MODEL.json first, and any SETUP.md statements that must run before the queries.
- **Sample-data profile** — row counts per label and relationship type, the deliberately seeded signals in full, and the deliberate background noise that keeps any single query from being a clean detector. Say why key choices were made where the data drove them.
- **One `##` section per query, heading matching QUERIES.md exactly** so the two files pair mechanically.

Each query section carries:

| Field | Content |
| ----- | ------- |
| Parameters | The values used for this run. |
| Invariant | What must hold whatever the generator produces, in terms of the seeded design: "returns the twelve Ring A claimants and no unseeded claimant". |
| Observed | The concrete snapshot — row counts, returned values, date or data version of the run. |
| Sensitivity | Optional. What other threshold values do, and where the signal stops separating from the noise. |

**Distinguishing invariant from observed is the point of the file.** An oracle made only of row counts breaks the first time anyone regenerates the CSVs, and the breakage looks like a query fault rather than a stale expectation. The invariant is the contract; the observed numbers are evidence for it.

Sensitivity is also where you are honest about where a shipped threshold came from. If the value in `@params` was reverse-engineered from the seed, say so here, next to the value the honest derivation would have given. That admission is useful to the next engineer and would be misleading to a customer — which is the whole reason these are two files.

A query you could not execute still gets its own `##` section, saying what it was not run against and why, and carries the matching `TODO(review): unproven query` in its QUERIES.md annotation block. Do not collect them under one "queries not executed" heading — that breaks heading parity and hides which query is unverified.

### 5. SETUP.md (only when needed)

If any query depends on schema or derived data the Import flow does not create — a fulltext or point index, a query-applied label — put the minimal statements in SETUP.md. Most packages need none.

- **Never include node-key constraints.** Import creates them from GRAPH_MODEL.json's key definitions; recreating them (or `UNIQUE` variants) conflicts with the existing `KEY` constraints. Constraints belong at the end of QUERIES.md as a schema reference.
- One statement per ```` ```cypher ```` block — the agent runs one statement per call.
- Each statement opens with the same `/* @... */` annotation block as QUERIES.md queries: `@name`, `@description` (what the statement creates and why), and `@usage` naming the dependent queries and the effect if skipped (fails outright vs. silently degraded results). `@params`/`@returns`/`@tags` only where meaningful.
- Order required statements first; mark recommended and optional ones clearly. Keep the total to a handful — a growing SETUP.md means the package is over-engineered.
- Open the file with the agent rules: explain each statement before running it, confirm the target database, and if the user declines a statement, name the affected queries and caveat their results for the rest of the conversation.

### 6. SKILL.md

Terse and agent-facing — the onboarding agent receives the body directly in its instruction prompt.

The one new piece of thinking here is the **role map**. The package's durable value is its analytical patterns, not its labels, and a user who arrives with their own schema needs those patterns to survive the rename. The roles fall out of writing the queries: each is an abstract part some node plays in the patterns — the party, the financial event, the shared attribute — and the third column states what a substitute in someone else's model would have to supply for the pattern to work at all.

Keep it to roles a user could recognise in their own data. Five or six rows is typical. A row per node label is not a map, it is the model restated.

Skeleton:

````markdown
---
name: <kebab-case-name>
description: <Industry, use cases, and capabilities — the trigger text.>
metadata:
  neo4j-card-title: <Short title>
  neo4j-card-category: <one of PACKAGE_FORMAT.md's allowed values, verbatim>
  neo4j-card-description: <One-sentence value statement.>
  neo4j-graph-spec-version: <the pin from GRAPH_SPEC_FORMAT.md, verbatim>
---

# <Use Case Title>

Use this skill for <audience, domain, and focused use cases>.

Source references:

- <https://authoritative-source.example/use-case>

<Domain disclaimer: synthetic data, results are analytical leads requiring
human review, not <clinical|legal|dispatch|...> conclusions.>

## Introducing this package

When the user first opens this package, greet them with a short
introduction in your own words — don't recite this file. Convey:

- <The core idea: the problem, and why connected data helps — one or two
  specifics from the domain.>
- <What the sample data contains, that it is synthetic, and that it
  deliberately seeds the patterns the bundled queries look for.>
- What you can help with: explaining the model, walking through the query
  patterns, importing the sample data or their own, and running Cypher
  once a database is connected.

End with a clear next step, such as asking whether they'd like to explore
the model or start importing data.

## Model

- <Nodes and relationships in one or two lines each; key properties.
  Summarise — the authoritative definitions are the `description`
  annotations in `GRAPH_MODEL.json`, on relationships as well as nodes
  and properties.>
- <One or two lines of design rationale where the model departs from the
  source material, and why.>
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is
  in `QUERIES.md`.
- Treat the model's `description` annotations as the authoritative meaning
  of each term — quote them when explaining the model, rely on them when
  adapting queries to the user's own data, and never contradict them.

### Roles

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| <Abstract role> | `<Label>` | <The property or connection the patterns depend on> |

When the user's schema differs from this model, map their labels onto
these roles before rewriting anything from `QUERIES.md`. A role with no
counterpart in their data means the patterns resting on it have no
analogue — say so plainly rather than forcing a fit.

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only
  through it. Never ship or offer a write-based data seed, a `LOAD CSV`
  statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing,
  and confirm with the user before running anything that writes.
- <Either: "Right after a sample-data import, offer the statements in
  `SETUP.md` — N statements, M required. Explain each before running; if
  the user declines one, name the affected queries and caveat their
  results thereafter." Or: "No post-import setup is required — do not
  improvise indexes or constraints after Import.">
- Queries open with a `/* @... */` annotation block. Keep the block with
  the query when showing or running it — it exists to help the user
  understand the query — and treat it as context, not ground truth: on
  any conflict, the Cypher logic wins. When adapting a query, update its
  annotations to match.
- Starting parameter values in `@params` are starting points, not
  defaults that fit any dataset. Read the result and retune before
  presenting anything as a finding.
- <Package-specific gotchas: version needs, APOC/GDS dependencies,
  traversal rules, threshold tuning.>

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this <detects|optimizes|surfaces>
Tuning options
Validation approach
```
````

Notes on the introduction guidance: it is direction, not a script — trust the agent to phrase it. Include a real model-image URL as an extra bullet only if one exists; never fabricate one. Keep the whole section under ten lines. Note that it describes the sample data in general terms only — the introduction is spoken to a user who may be about to import something else entirely.

**Do not index TESTS.md in SKILL.md.** Every other non-required file gets a Supporting files entry; TESTS.md deliberately does not, because the agent must never load it.

## Validate and hand off

Run [VALIDATION.md](VALIDATION.md) in full. Inconsistency between model, data, and queries is the most common failure — and annotations widen that check: descriptions, sample values, query annotations, and CSVs must all tell the same story. The second most common failure is now sample-data detail leaking into a file the consuming agent reads; check QUERIES.md and SKILL.md for it specifically.

Your handoff summary must list every remaining `TODO(review):` with its path (including `inferred description` items the user hasn't confirmed), every query not executed against sample data, whether the model validated against the bundled schema and was accepted by the destination runtime, the graph spec version the package declares, and any assumption that needs domain-owner review.
