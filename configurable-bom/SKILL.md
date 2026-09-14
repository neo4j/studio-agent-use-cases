---
name: configurable-bom
description: Manufacturing product design and engineering. Models a configurable product as a superset of assemblies, fixed parts and explicit configuration decisions, then resolves a single buildable variant from it. Use for configure-to-order and engineer-to-order product structures, option and variant management, constraint-driven configuration with allow and deny lists, multi-factor scoring of the branches constraints leave open, cost and weight rollups over a resolved bill of materials, and detecting over-constrained specifications that cannot be built. Provides a graph model for products, assemblies, configuration groups and parts, sample data for a configurable product with nested options, and Cypher for exploring the structure, resolving variants, pruning by score, costing the result and reporting unsatisfiable requirements.
metadata:
  neo4j-card-title: Configurable Bill of Materials
  neo4j-card-category: Manufacturing
  neo4j-card-description: Resolve a single buildable product variant from a configurable bill of materials by applying constraints, scoring the options that remain, and rolling up cost and weight.
  neo4j-graph-spec-version: 4.0.0-alpha.25
---

# Configurable Bill of Materials

Use this skill for manufacturing product design and engineering teams working
with configure-to-order or engineer-to-order products: structures where the
bill of materials is not a fixed list but a superset of possibilities, from
which one buildable variant has to be resolved against customer requirements,
engineering rules, and compliance obligations.

Source references:

- <https://neo4j.com/developer/industry-use-cases/manufacturing/product-design-and-engineering/configurable-bom/>

The bundled data is synthetic. Resolved variants are
engineering analysis, not release-to-manufacture decisions: a scored result is a
recommended branch, not a validated build, and nothing here substitutes for
design review, supplier qualification, or conformity assessment. Where a
configuration is described as compliant, that is a property of the constraints
someone wrote, not a regulatory judgement.

## Introducing this package

When the user first opens this package, greet them with a short introduction in
your own words — don't recite this file. Convey:

- The core idea: a configurable product is a superset, not a list. Every
  variant a customer could order is present at once, and the work is pruning it
  down to one — applying rules that rule options out, choosing between the
  options no rule settles, and knowing when the rules contradict each other.
  Graph traversal prunes as it walks, so invalid combinations are never
  enumerated; the alternative is generating combinations and testing them.
- What the sample data contains: one configurable product with nested
  configuration decisions, synthetic, deliberately built so that the constraint
  scenarios the queries demonstrate — a tightly specified variant, a loosely
  specified one that needs scoring, and a contradictory one — are all reachable
  from the same structure.
- What you can help with: explaining the model, walking through the resolution
  pattern, importing the sample data or their own, and running Cypher once a
  database is connected.

End with a clear next step, such as asking whether they'd like to explore the
structure or start importing data.

## Model

- `Product` is the configurable end product and the root every resolution starts
  from. `Assembly` groups fixed parts and further decisions, and is reusable —
  it may sit beneath the product or be offered as an option. `Part` is a leaf
  and the only node carrying `cost` and `weight`, so every rollup is a sum over
  parts.
- `ConfigGroup` is the pivot of the whole model: a decision point holding two or
  more interchangeable options. Its `category` is what constraints are matched
  against, and its `optionProperty` names the property on each option node whose
  value the constraint compares. Constraints are scoped by category, not by
  property name — two decisions may vary along the same property and be governed
  independently.
- `REQUIRES` and `HAS_PART` carry `qty`, the number needed per one of the parent.
  Rollups multiply these along the path, so a quantity above a decision
  multiplies everything chosen beneath it.
- `RESOLVED_LINK` is written by the resolution queries, never imported. It
  mirrors a structural edge and tags it with a variant name, so many resolved
  variants coexist over one structure without copying it. How many leave a
  decision is the whole diagnostic: exactly one is a decision made, more than
  one is a decision still open to scoring, none at all is a decision the
  constraints could not satisfy.
- Design rationale: the model follows the source page, with three deliberate
  departures. Property names are camelCase throughout (`idVariant`, `relType`,
  `wheelSize`) rather than the page's snake_case, matching Neo4j convention.
  `optionProperty` is a single string rather than the page's list, because each
  decision in this model varies along exactly one attribute and the queries take
  property names from their constraint parameter rather than from the node. The
  resolution query is scoped to one `productId`, which the page's version is not,
  so it does not walk a catalog holding many products.
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is in
  `QUERIES.md`.
- Treat the model's `description` annotations as the authoritative meaning of
  each term — quote them when explaining the model, rely on them when adapting
  queries to the user's own data, and never contradict them.

### Roles

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| Configurable root | `Product` | A single node the whole structure hangs from, so a resolution has one place to start and one scope |
| Composition node | `Assembly` | A node that groups components and further decisions, reachable from more than one parent so it can be reused rather than copied per variant |
| Decision point | `ConfigGroup` | A node standing between a parent and its alternatives, carrying the value constraints are matched on. Without one, the choices are already made in the data and there is nothing to constrain, score, or report as unsatisfied |
| Alternative | option nodes reached by `HAS_OPTION` | A node carrying the attribute an allow or deny list compares, readable by property name, with two or more alternatives per decision |
| Costed leaf | `Part` | A node carrying the numeric measures a rollup sums, stated per unit rather than per parent |
| Quantity | `qty` on `REQUIRES` and `HAS_PART` | A multiplier on the edge rather than on the node, so the same component counts differently under different parents |
| Selection record | `RESOLVED_LINK` | A per-variant marker written onto the edge, so resolutions coexist without duplicating the structure |

When the user's schema differs from this model, map their labels onto these
roles before rewriting anything from `QUERIES.md`. A role with no counterpart in
their data means the patterns resting on it have no analogue — say so plainly
rather than forcing a fit. The decision point is the one to check first: a
structure that records the chosen option directly on its parent describes
variants already resolved elsewhere, and none of the constraint or scoring
patterns apply to it.

## Operational Constraints

- **Neo4j 2025.06 or later, with Cypher 25.** The resolve and prune queries use
  query chaining (`NEXT`) and scoped call subqueries, and several use quantified
  path patterns. They do not parse on earlier versions — check the server version
  before offering them, and say plainly that the package needs a newer server
  rather than rewriting them into something weaker. No APOC or GDS.
- Data loads through the bundled `sample-data/` Import flow, and only through
  it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a
  `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and
  confirm with the user before running anything that writes.
- **Four queries write.** Resolving creates `RESOLVED_LINK`; pruning, garbage
  collection and clearing delete it. None touches the configurable structure,
  so the blast radius is one variant — say so when asking for confirmation,
  and name the variant.
- Right after a sample-data import, offer the statement in `SETUP.md` — 1
  statement, 0 required, 1 recommended. Explain it before running; if the user
  declines it, say that results are unaffected and only speed changes, and do
  not raise it again.
- **Run the queries in order: resolve, prune, garbage collect, roll up.** A
  rollup taken before pruning totals every surviving option at once and is a
  figure for a superset, not for a bill of materials. It returns without
  complaint, so nothing but the ordering protects against it.
- **Check for unsatisfied decisions before reporting any result.** An
  over-constrained variant still produces a clean resolved structure and a clean
  rollup, for a product that cannot be built. The unsatisfied-requirements query
  is what makes the other two trustworthy; run it and say what it returned.
- **Clear a variant before re-resolving it.** Resolution merges rather than
  replaces, so re-running under new constraints unions the two results with no
  way to tell them apart afterwards.
- Scoring always chooses something. It ranks whole sub-branches, not single
  components, so an option dearer in isolation can win on what it brings with
  it. Where one alternative is better on every scored field, no choice of
  factors will select another — that needs a constraint, not a weight.
- Queries open with a `/* @... */` annotation block. Keep the block with the
  query when showing or running it — it exists to help the user understand the
  query — and treat it as context, not ground truth: on any conflict, the Cypher
  logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that
  fit any dataset. The scoring factors in particular are an exchange rate
  between cost and weight that belongs to the product, not to the catalog. Read
  the result and retune before presenting anything as a finding.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this resolves or surfaces
Tuning options
Validation approach
```
