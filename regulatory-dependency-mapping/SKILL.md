---
name: regulatory-dependency-mapping
description: Investment banking regulatory compliance and change management. Models a regulator's handbook as a graph — standards, the hierarchy of sections beneath them, and the cross-references sections make to one another — so that the dependencies between rules become queryable. Use for regulatory change impact assessment (which other text does this amendment reach), identifying which sections are most expensive to change, sweeping for sections whose text has recently taken effect, prioritising a change backlog by how heavily the changed text is cited, and finding where one sourcebook depends on another. Provides a graph model, import-ready synthetic sample data, and Cypher for hierarchy traversal, citation analysis, blast-radius impact assessment, and optional GDS PageRank and connected-component analytics over the citation graph.
metadata:
  neo4j-card-title: Regulatory Dependency Mapping
  neo4j-card-category: Investment Banking
  neo4j-card-description: Trace a regulatory change through cross-referenced handbook sections to every other rule it reaches.
---

# Regulatory Dependency Mapping

Use this skill for compliance, regulatory-change and risk teams in investment
banking who need to know which parts of a rulebook a proposed or announced
amendment actually reaches, which text is most expensive to change, and where
one sourcebook leans on another.

Source references:

- <https://neo4j.com/developer/industry-use-cases/finserv/investment-banking/regulatory-dependency-mapping/>

The bundled sample data is synthetic. Standard codes, section identifiers,
titles and rule references imitate the shape of published handbook material
but are not real regulatory text. Everything these queries return is an
analytical lead for a compliance professional to verify — not a compliance
determination, a legal opinion, or advice on whether a firm meets its
obligations. A blast radius is bounded by how completely cross-references were
captured in the first place, so treat it as a floor on the impact, never a
ceiling, and never present it as a complete impact assessment.

## Introducing this package

When the user first opens this package, greet them with a short introduction
in your own words — don't recite this file. Convey:

- A rulebook is a graph, not a list. Sections nest into chapters and cite each
  other across chapters and across sourcebooks, so the question that matters
  when a rule changes — what else does this touch? — is several hops deep and
  falls apart in a spreadsheet or a PDF search.
- The sample data is synthetic, spans more than one sourcebook, and
  deliberately seeds the patterns the bundled queries look for: a recently
  changed section that a lot of other text leans on, a chain of citations that
  only shows up if you follow more than one hop, and citations that cross from
  one sourcebook into another.
- What you can help with: explaining the model, walking through the query
  patterns, importing the sample data or mapping their own handbook, and
  running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the
model or start importing data.

## Model

- `Standard` — a published handbook or sourcebook, identified by its code.
  `Section` — one addressable unit of regulatory text, carrying its published
  title and the in-force date of its current wording, which is the property
  change analysis filters on.
- `DEPENDS_ON` builds the hierarchy and is reused for both levels of it:
  `Section` → `Standard` for top-level sections only, and `Section` →
  `Section` from child to parent for everything deeper. A section therefore
  carries one or the other, never both, and deeper sections reach their
  standard by chaining through their parents.
- `RELATED` records a cross-reference from the citing section to the cited
  one, carrying `subsection` — the specific rule inside the cited section that
  is being relied on. Two sections that cite each other carry one `RELATED`
  each way.
- The model is deliberately the source page's, unextended: two labels, two
  relationship types. The source's business-impact scenario invites nodes for
  products, services and systems, and this package does not add them — the
  citation graph on its own answers the change-impact questions, and a
  narrower model is a cleaner template for a user mapping their own handbook.
  One departure: the source page names the change date `last_update` in its
  field list and `last_updated` in its demo Cypher, and this model uses
  `lastUpdated`, typed as a `DATE` rather than the demo's `datetime`.
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is in
  `QUERIES.md`.
- Treat the model's `description` annotations as the authoritative meaning of
  each term — quote them when explaining the model, rely on them when adapting
  queries to the user's own data, and never contradict them.

### Roles

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| Regulatory corpus | `Standard` | A node every text unit resolves back to, so that "which rulebook is this from" is answerable — without it, dependency between corpora cannot be counted |
| Regulatory text unit | `Section` | An addressable node that nests into a hierarchy, cites its peers, and carries a date on which its current wording took effect |

Two relationship roles matter as much as the labels, and both turn on
direction rather than on a node: **containment**, read child to parent, which
the hierarchy queries chain to reach a corpus; and **citation**, read citing
to cited, which every impact and centrality pattern follows backwards to find
what a change reaches. A schema that merges the two into one relationship
type, or that stores citations without a direction, cannot support those
patterns at all.

When the user's schema differs from this model, map their labels onto these
roles before rewriting anything from `QUERIES.md`. A role with no counterpart
in their data means the patterns resting on it have no analogue — say so
plainly rather than forcing a fit.

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through
  it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or
  a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and
  confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints
  after Import. The node-key constraints on `Standard.id` and `Section.id`
  come from `GRAPH_MODEL.json`; `QUERIES.md` repeats them at the end purely so
  the expected schema can be confirmed with `SHOW CONSTRAINTS`.
- Queries open with a `/* @... */` annotation block. Keep the block with the
  query when showing or running it — it exists to help the user understand the
  query — and treat it as context, not ground truth: on any conflict, the
  Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults
  that fit any dataset. Read the result and retune before presenting anything
  as a finding.
- **Traversal depth cannot be parameterised.** Cypher requires a literal bound
  on a variable-length pattern, so there is no `$maxDepth` to pass; tuning a
  depth means editing the query. This matters more than it sounds: a bound of
  N returns the pattern to depth N and silently omits anything deeper, with
  nothing in the result indicating truncation. Most queries walk up to a
  `Standard` in four hops, which suits a chapter/section/subsection handbook —
  before trusting any result on an unfamiliar rulebook, check how deep it
  nests, and raise the literals if it nests deeper. Say so when presenting
  results from a handbook you have not checked.
- The four GDS queries need the GDS plugin 2.x, absent on some Aura tiers and
  many self-managed installs. Check with `RETURN gds.version()` before
  offering them, and otherwise fall back to the plain-Cypher queries, where
  the inbound-citation ranking substitutes for PageRank. Project the graph
  before running them and drop the projection afterwards — a GDS projection
  survives client disconnection and holds memory until dropped.
- Honest limitations to state when presenting results: the graph knows only
  the cross-references someone captured, so a section with no citations may be
  genuinely standalone or simply unmapped and the query cannot tell the two
  apart; connected-component grouping is fragile, since a single bridging
  citation can fuse most of a handbook into one component; and PageRank scores
  are relative within a single run, so they rank text but do not measure it.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
