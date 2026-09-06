---
name: regulatory-dependency-mapping
description: Investment banking and financial services regulatory compliance. Maps a regulator's handbook — standards, sections and the cross-references between them — onto the obligations, controls, systems, business services and accountable owners a firm operates against it. Use for regulatory change impact assessment (what breaks if this rule changes), control coverage and gap analysis, finding overlapping obligations across rulebooks and jurisdictions, single-point-of-failure analysis across shared systems, operational resilience dependency mapping for important business services, and control testing backlog triage. Provides a graph model, import-ready sample data, and Cypher for hierarchy traversal, cross-reference and blast-radius analysis, coverage scoring, and optional GDS centrality and community detection over the citation graph.
metadata:
  neo4j-card-title: Regulatory Dependency Mapping
  neo4j-card-category: Financial Services
  neo4j-card-description: Trace a regulatory change through cross-referenced handbook sections to the obligations, controls, systems, services and owners it actually reaches.
---

# Regulatory Dependency Mapping

Use this skill for compliance, risk and operational-resilience teams in
investment banking and financial services who need to know what a regulatory
change reaches, where control coverage is thin, and which shared systems
concentrate compliance risk across rulebooks.

Source references:

- <https://neo4j.com/developer/industry-use-cases/finserv/investment-banking/regulatory-dependency-mapping/>

The bundled sample data is synthetic. Section identifiers and rule references
imitate the shape of published handbook material but are not real regulatory
text, and nothing in the data describes a real firm. Everything these queries
return is an analytical lead for a compliance professional to verify — not a
compliance determination, a legal opinion, or evidence of a breach. Never
present a coverage gap as a confirmed breach, or a blast radius as a complete
impact assessment: both depend entirely on how thoroughly the firm's own
obligation and control registers have been mapped.

## Introducing this package

When the user first opens this package, greet them with a short introduction
in your own words — don't recite this file. Convey:

- Regulatory dependency mapping is hard because a rulebook is a graph, not a
  list. One section cross-references another, obligations derive from
  sections, controls satisfy several obligations at once, and services run on
  shared systems — so the real question ("what does this change actually
  touch?") is several joins deep and falls apart in a spreadsheet.
- The sample data is synthetic, and it deliberately seeds the patterns the
  bundled queries look for: a recent change to a heavily cross-referenced
  section, obligations left short of full control coverage, a shared platform
  that a disproportionate amount of the control estate rests on, and controls
  doing duty under more than one rulebook at once.
- What you can help with: explaining the model, walking through the query
  patterns, importing the sample data or mapping their own, and running Cypher
  once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the
model or start importing data.

## Model

- `Standard` — a published handbook or sourcebook, with its regulator and
  jurisdiction. `Section` — one addressable unit of regulatory text, with the
  in-force date of its current wording, which is what change analysis filters
  on.
- `DEPENDS_ON` builds the handbook hierarchy: `Section` → `Standard` for
  top-level sections only, `Section` → `Section` from child to parent for
  everything deeper. `RELATED` records a cross-reference from the citing
  section to the cited one, carrying the specific rule referenced.
- `Obligation` — a requirement the firm extracted from exactly one section
  (`DERIVED_FROM`), scored for inherent risk. `Control` — what the firm
  operates to meet it (`SATISFIES`, carrying assessed coverage as a
  percentage), with a last-tested date and effectiveness score.
- `BusinessService` — what the firm delivers, with a resilience classification
  and impact tolerance, `GOVERNED_BY` obligations. `System` — what services
  and controls run on. `BusinessUnit` is `ACCOUNTABLE_FOR` both obligations
  and services, which are separate accountabilities and often different units.
- `DEPENDS_ON` is reused for the operational layer too: `BusinessService` →
  `System` and `System` → `System`, the latter expected to be acyclic.
- The source page models only `Standard`, `Section`, `DEPENDS_ON` and
  `RELATED`. Everything from `Obligation` onwards is an extension, added
  because the source scenario is explicitly about mapping regulations onto
  products, services, processes and systems — which its own data model stops
  short of. The regulatory layer keeps the source's structure unchanged —
  `Standard`, `Section`, and the reuse of `DEPENDS_ON` for hierarchy alongside
  `RELATED` for cross-references — with three additions and one rename:
  `Standard` gains `title`, `regulator` and `jurisdiction` so that overlap
  across regimes is answerable, and the source's `last_updated` is
  `lastUpdated`, typed as a `DATE` rather than the source demo's `datetime`.
- The source page shows both GDS `stream` and `write` execution modes; this
  package ships only `stream`, so the analytics never mutate a database the
  user has not agreed to change.
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is in
  `QUERIES.md`.
- Treat the model's `description` annotations as the authoritative meaning of
  each term — quote them when explaining the model, rely on them when adapting
  queries to the user's own data, and never contradict them. Two scale
  directions catch people out and are worth stating explicitly: risk and
  effectiveness run 1–5 with 5 as the extreme, while `System.tier` runs 1–3
  with 1 as the most critical.

### Roles

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| Regulatory corpus | `Standard` | A node every text unit resolves back to, so that "which rulebook is this from" is answerable — without it, overlap and concentration across regimes cannot be counted |
| Regulatory text unit | `Section` | An addressable node that nests into a hierarchy, cites its peers, and carries a date its current wording took effect |
| Requirement | `Obligation` | A node traceable to exactly one text unit, so a change to the text has a defined set of consequences |
| Assurance activity | `Control` | A node linkable to many requirements at once, carrying a coverage share and a date it was last verified |
| Consequence bearer | `BusinessService` | Something the business would notice failing, connected to the requirements that constrain it |
| Shared resource | `System` | A node several consequence bearers converge on, and which depends on other such nodes, so failure propagates |
| Accountable party | `BusinessUnit` | A named owner reachable from both requirements and consequence bearers, so findings have someone to go to |

When the user's schema differs from this model, map their labels onto these
roles before rewriting anything from `QUERIES.md`. A role with no counterpart
in their data means the patterns resting on it have no analogue — say so
plainly rather than forcing a fit. There is one role per label here because
the model is a chain of layers and each layer plays a genuinely different part
in the patterns; read the third column, not the second, when matching a user's
schema. A common partial fit is a firm that
has a regulatory hierarchy and an obligation register but no control-to-system
mapping: the change-impact and coverage patterns work, the concentration and
resilience patterns do not.

## Supporting files

| File | Load when |
| ---- | --------- |
| `QUERIES.md` | The user wants to run, see, or adapt Cypher. |
| `SETUP.md` | Right after a sample-data import, or when a date-filtered query is slow on a large graph. |

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through
  it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or
  a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and
  confirm with the user before running anything that writes.
- After a sample-data import, offer the statements in `SETUP.md` — 2
  statements, 0 required, both recommended range indexes for the two
  date-filtered queries. Explain each before running; if the user declines
  one, name the affected query and note that its results stay correct but it
  will scan rather than seek. Do not improvise any other index or constraint:
  the node-key constraints come from `GRAPH_MODEL.json` via Import.
- Queries open with a `/* @... */` annotation block. Keep the block with the
  query when showing or running it — it exists to help the user understand the
  query — and treat it as context, not ground truth: on any conflict, the
  Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults
  that fit any dataset. Read the result and retune before presenting anything
  as a finding.
- Cypher will not accept a parameter as the bound of a variable-length
  pattern. Eight queries carry traversal depths as literals in the Cypher, and
  each says so in its annotation block; tuning any of them means editing the
  query. Never widen one silently — citation and dependency graphs fan out
  fast, and an unbounded traversal on a full handbook will not return. Note
  the converse risk too: five queries reach a `Section` back to its `Standard`
  through a bounded hop, so a section nested deeper than that bound is
  silently excluded rather than flagged. If the user's handbook nests deeper
  than the model's three levels, raise those bounds before trusting any
  result that groups by standard.
- The four GDS queries need the GDS plugin 2.x, which is absent on some Aura
  tiers and many self-managed installs. Check with `RETURN gds.version()`
  before offering them, and fall back to the plain-Cypher queries, which cover
  the same ground — the inbound-citation ranking substitutes for PageRank.
  Project the graph before running them and drop the projection afterwards.
- Honest limitations to state when presenting results: coverage percentages
  are the firm's own assessments, not measurements, so a fully-covered
  obligation is only as trustworthy as the mapping exercise behind it; an
  obligation with no control may be genuinely uncontrolled or simply
  unmapped, and the graph cannot distinguish them; a blast radius is bounded
  by how completely cross-references were captured, so it is a floor on the
  impact, never a ceiling; and control effectiveness scores describe the
  control as it was at its last test and do not decay, which is exactly why
  the overdue-testing query exists.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
