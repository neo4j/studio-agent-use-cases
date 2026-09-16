# Configurable BOM — Cypher

Runnable Cypher for exploring a configurable product structure, resolving a
variant from it, pruning the decisions constraints left open, and costing the
result.

## Prerequisites

- **Neo4j 2025.06 or later, with Cypher 25.** Two queries below open with a
  `CYPHER 25` directive and use query chaining (`NEXT`) and scoped call
  subqueries (`CALL (var) { ... }`); several use quantified path patterns
  (`-[:TYPE]->*`, `-[:TYPE]->{1,8}`) and the negated type predicate
  (`-[r:!RESOLVED_LINK]->`). None of this runs on an earlier version.
- The model in `GRAPH_MODEL.json`, loaded through the Import flow.
- `RESOLVED_LINK` is **not** declared in `GRAPH_MODEL.json` and does not exist
  in a freshly imported database. The queries below create it, and `SKILL.md`
  carries its definition. Every other label, relationship type and property used
  here is in the model.
- `SETUP.md` carries one recommended index. Nothing here fails without it, but
  every query that filters `RESOLVED_LINK` by variant scans without it.
- No APOC or GDS.

**Four of these queries write to the database.** Resolving a variant creates
`RESOLVED_LINK` relationships; pruning, garbage collection and clearing delete
them. None of them touches `Product`, `Assembly`, `ConfigGroup` or `Part`, or
any structural relationship between them — the configurable structure is
read-only throughout, and every write is confined to one variant's links.
Confirm the target database before running any of them.

The intended order for a full resolution is: resolve, then prune, then garbage
collect, then roll up. Rolling up before pruning counts every surviving option,
which is a sum over a superset rather than over a bill of materials.

## Adapting these queries

These queries assume the model in `GRAPH_MODEL.json`. When the user's schema
differs — their own model, a modified one, or a database that predates this
package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`)
   rather than assuming this model applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart
   means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what
   the rewritten query actually does.

The commonest mismatch in this domain is a structure that records a chosen
option directly on the parent rather than as a separate decision node. There is
then no counterpart to the decision role, and the constraint and scoring
patterns have nothing to attach to — the structure describes variants that have
already been resolved elsewhere.

## Explore the configurable structure of a product

```cypher
/*
 * @name           Explore the configurable structure of a product
 * @description    Returns the product's configurable structure as paths:
 *                 required assemblies, fixed parts, and the configuration
 *                 decisions with the options each offers. Reads the structure
 *                 only; ignores any resolved variant.
 * @params         productId - Identifier of the product to explore. Matches
 *                     Product.productId.
 * @prerequisites  None beyond the imported model.
 * @returns        One path per route from the product down through the
 *                 structure, for rendering as a graph.
 * @usage          The first query to run on an unfamiliar catalog: it shows
 *                 the superset of everything the product could contain, before
 *                 any constraint is applied. The depth bound of 8 covers a
 *                 structure nesting assemblies inside options inside
 *                 assemblies; raise it only if the catalog nests deeper than
 *                 the result shows, and lower it when the graph is too large
 *                 to read. Returns paths, not a deduplicated tree, so a part
 *                 used by several assemblies appears on several paths.
 * @tags           structure, exploration, bom, product
 *
 * TODO(review): unproven query
 */
MATCH path = (:Product {productId: $productId})-[:REQUIRES|HAS_PART|HAS_OPTION]->{1,8}()
RETURN path
```

## List the configuration decisions and their options

```cypher
/*
 * @name           List the configuration decisions and their options
 * @description    Returns every configuration decision in the catalog with
 *                 its category, the option property its choices vary along,
 *                 and the options themselves with the value each carries for
 *                 that property.
 * @params         None
 * @prerequisites  None beyond the imported model.
 * @returns        One row per ConfigGroup: configGroupId, category,
 *                 optionProperty, and a list of {optionId, optionValue}.
 * @usage          Use this to build the constraints parameter the resolution
 *                 query takes: the category column supplies each constraint's
 *                 category, optionProperty supplies the property name, and the
 *                 optionValue column shows the exact strings an allow or deny
 *                 list has to match, which are compared by equality and are
 *                 case-sensitive. Two decisions sharing a category are governed
 *                 by one constraint entry, which is how a single constraint
 *                 keeps components that must match in step.
 * @tags           configuration, options, constraints, catalog
 *
 * TODO(review): unproven query
 */
MATCH (cg:ConfigGroup)-[:HAS_OPTION]->(option)
RETURN cg.configGroupId AS configGroupId,
       cg.category      AS category,
       cg.optionProperty AS optionProperty,
       collect({
         optionId:    coalesce(option.partId, option.assemblyId),
         optionValue: option[cg.optionProperty]
       }) AS options
ORDER BY category, configGroupId
```

## Resolve a variant against constraints

```cypher
/*
 * @name           Resolve a variant against constraints
 * @description    Walks the configurable structure from the product to its
 *                 parts, refusing any step out of a configuration decision
 *                 whose option the constraints reject, and records every edge
 *                 that survives on a path reaching a part as a RESOLVED_LINK
 *                 tagged with the variant name. WRITES to the database.
 * @params         productId - Identifier of the product to resolve. Scopes the
 *                     traversal to one product so a catalog holding many is
 *                     not walked.
 *                 idVariant - Name for the variant being resolved. Every
 *                     RESOLVED_LINK written carries it, so several variants can
 *                     coexist in one database. Reuse a value only when
 *                     re-resolving that same variant after clearing it.
 *                 constraints - List of maps, one per decision category:
 *                     {category, properties: [{name, allowList, denyList}]}.
 *                     category is matched against ConfigGroup.category; name is
 *                     the graph property read off each option node. Supply
 *                     allowList, denyList, or both. Omitting a category leaves
 *                     that decision open, to be settled by scoring.
 * @prerequisites  Neo4j 2025.06 or later (Cypher 25: NEXT, quantified path
 *                 patterns, negated relationship type predicate).
 * @returns        Nothing. Its effect is the RESOLVED_LINK relationships it
 *                 merges, which the other queries read.
 * @usage          Run this first, then prune, then garbage collect, then roll
 *                 up. Whether a decision comes out made depends on how tightly
 *                 the constraints bind it: exactly one surviving option is a
 *                 decision made, more than one is a decision left to scoring,
 *                 and none at all is a decision the constraints cannot satisfy
 *                 — which the unsatisfied-requirements query reports. Because
 *                 the filter is applied per step rather than to the finished
 *                 configuration, it prunes as it walks and never enumerates the
 *                 rejected combinations. Clear a variant before re-resolving it
 *                 under different constraints; MERGE is idempotent, so a second
 *                 run under the same constraints changes nothing.
 * @tags           resolution, constraints, variant, write, bom
 *
 * TODO(review): unproven query
 */
CYPHER 25

MATCH path = (:Product {productId: $productId})
  (
    (x)-[r:!RESOLVED_LINK]->(y)
    WHERE NOT (
      x:ConfigGroup
      AND any(cons IN $constraints WHERE
        cons.category = x.category
        AND any(prop IN cons.properties WHERE
          (prop.allowList IS NOT NULL AND NOT y[prop.name] IN prop.allowList)
          OR (prop.denyList IS NOT NULL AND y[prop.name] IN prop.denyList)
        )
      )
    )
  )*
  (:Part)
UNWIND relationships(path) AS rel
RETURN startNode(rel) AS source, rel AS r, endNode(rel) AS target

NEXT

MERGE (source)-[rl:RESOLVED_LINK {idVariant: $idVariant, relType: type(r)}]->(target)
SET rl.qty = r.qty
```

## Show a resolved bill of materials

```cypher
/*
 * @name           Show a resolved bill of materials
 * @description    Returns every RESOLVED_LINK belonging to one variant as
 *                 paths, for rendering the resolved structure as a graph.
 * @params         idVariant - Name of the variant to show, as supplied when it
 *                     was resolved.
 * @prerequisites  The variant has been resolved.
 * @returns        One path per resolved link.
 * @usage          Run it after resolving and again after pruning: the
 *                 difference between the two is exactly what scoring decided.
 *                 A decision node with more than one outgoing link is still
 *                 open; one with exactly one is settled. Returns nothing at all
 *                 when the variant name does not match one that was resolved,
 *                 which is worth checking before reading anything into an empty
 *                 result.
 * @tags           bom, variant, visualisation
 *
 * TODO(review): unproven query
 */
MATCH p = ()-[:RESOLVED_LINK {idVariant: $idVariant}]->()
RETURN p
```

## Prune undecided decisions by scoring

```cypher
/*
 * @name           Prune undecided decisions by scoring
 * @description    Repeatedly finds configuration decisions that still have
 *                 more than one surviving option and no undecided decision
 *                 beneath them, totals cost and weight over each option's whole
 *                 sub-branch, scores the options, and deletes the links to all
 *                 but the best. Works bottom-up, so a nested decision is
 *                 settled before the decision that contains it. WRITES to the
 *                 database.
 * @params         idVariant - Name of the variant to prune, as supplied when it
 *                     was resolved.
 *                 scoring - List of {field, factor} maps, where field is cost
 *                     or weight and factor weights it. The option with the
 *                     highest total score is kept, so use negative factors to
 *                     minimise. The ratio between factors is an exchange rate
 *                     between the fields: {cost, -1.0} with {weight, -50.0}
 *                     says you would spend fifty units of currency to save a
 *                     kilogram. Set it from what the product is worth, not from
 *                     the numbers in the catalog.
 *                 maxIterations - Upper bound on the bottom-up passes. One pass
 *                     settles one layer of nesting, so set it to at least the
 *                     depth of decisions nested inside options; 10 covers a
 *                     deeply nested structure and costs nothing when resolution
 *                     converges sooner.
 * @prerequisites  Neo4j 2025.06 or later (Cypher 25: NEXT, scoped call
 *                 subqueries, quantified path patterns). The variant has been
 *                 resolved.
 * @returns        Nothing. Its effect is the RESOLVED_LINK relationships it
 *                 deletes.
 * @usage          Only needed when constraints left a decision open; a fully
 *                 constrained variant is unchanged by it. Scoring compares
 *                 whole sub-branches, not single components, so an option that
 *                 is dearer in isolation can still win by what it brings with
 *                 it — and the reverse, which is the usual reason a result
 *                 surprises. Deleting a link can strand the links below it;
 *                 run the garbage collector afterwards. Read the chosen options
 *                 before trusting the totals: scoring always picks something,
 *                 including when neither option was really acceptable.
 * @tags           scoring, optimisation, pruning, variant, write
 *
 * TODO(review): unproven query
 */
CYPHER 25

UNWIND range(1, $maxIterations) AS _
CALL (_) {

  // Decisions still open, with no still-open decision beneath them.
  MATCH (cf:ConfigGroup)
  WHERE count{ (cf)-[:RESOLVED_LINK {idVariant: $idVariant}]->() } > 1
    AND NOT EXISTS {
      (cf)-[:RESOLVED_LINK {idVariant: $idVariant}]->+(cfBelow:ConfigGroup)
      WHERE count{ (cfBelow)-[:RESOLVED_LINK {idVariant: $idVariant}]->() } > 1
    }
  RETURN cf

  NEXT

  // Total cost and weight over each option's whole sub-branch.
  MATCH path = (leaf)<-[rs:RESOLVED_LINK {idVariant: $idVariant}]-*(opt)
      <-[optLink:RESOLVED_LINK {idVariant: $idVariant}]-(cf)
  WHERE NOT EXISTS { (leaf)-[:RESOLVED_LINK {idVariant: $idVariant}]->() }
  WITH cf, optLink, opt, leaf, reduce(acc = 1, r IN rs | acc * coalesce(r.qty, 1)) AS times
  WITH cf, optLink, opt, leaf, {cost: leaf.cost * times, weight: leaf.weight * times} AS vals
  WITH cf, optLink, opt, collect(vals) AS valsList
  WITH cf, optLink, opt, reduce(acc = {cost: 0.0, weight: 0.0}, vals IN valsList |
      {cost: acc.cost + vals.cost, weight: acc.weight + vals.weight}) AS vals

  // Score, then detach every option but the best.
  UNWIND $scoring AS fieldFactor
  WITH cf, optLink, opt, vals[fieldFactor.field] * fieldFactor.factor AS score
  WITH cf, optLink, opt, sum(score) AS score
  ORDER BY cf, score DESC
  WITH cf, collect(optLink) AS optLinks
  UNWIND optLinks[1..] AS delOptLink
  DELETE delOptLink

}
```

## Remove resolved links detached from the product

```cypher
/*
 * @name           Remove resolved links detached from the product
 * @description    Deletes RESOLVED_LINK relationships for one variant that are
 *                 no longer reachable from the product, which is what pruning
 *                 a decision leaves behind beneath the options it discarded.
 *                 WRITES to the database.
 * @params         idVariant - Name of the variant to tidy, as supplied when it
 *                     was resolved.
 * @prerequisites  The variant has been resolved.
 * @returns        Nothing. Its effect is the RESOLVED_LINK relationships it
 *                 deletes.
 * @usage          Run after every pruning pass. Skipping it leaves the links
 *                 beneath discarded options in place, and because the rollup
 *                 walks down from the product it will not count them — but the
 *                 resolved bill of materials will still show them, so the
 *                 picture and the totals disagree. Deletes only links whose
 *                 source has no remaining route back to a product, so it is
 *                 safe to run repeatedly and harmless on a variant that needed
 *                 no pruning.
 * @tags           cleanup, pruning, variant, write
 *
 * TODO(review): unproven query
 */
MATCH ()<-[r:RESOLVED_LINK {idVariant: $idVariant}]-(x)
WHERE NOT EXISTS { (x)<-[:RESOLVED_LINK {idVariant: $idVariant}]-*(:Product) }
DELETE r
```

## Roll up weight and cost of a resolved variant

```cypher
/*
 * @name           Roll up weight and cost of a resolved variant
 * @description    Totals the weight and cost of a resolved variant by finding
 *                 every part at the bottom of the resolved structure,
 *                 multiplying its per-unit values by the quantities on the path
 *                 from the product down to it, and summing.
 * @params         idVariant - Name of the variant to total, as supplied when it
 *                     was resolved.
 * @prerequisites  The variant has been resolved, pruned to a single option per
 *                 decision, and garbage collected.
 * @returns        One row: weightKg and cost, rounded to two decimals. Weight
 *                 is in kilograms and cost in the catalog's base currency,
 *                 following Part.weight and Part.cost.
 * @usage          Only meaningful on a fully pruned variant — run it while a
 *                 decision is still open and it totals every surviving option
 *                 at once, giving a figure for a superset rather than for a
 *                 bill of materials. Check the unsatisfied-requirements query
 *                 before quoting the result: an over-constrained variant still
 *                 totals cleanly, and the number it gives is for an incomplete
 *                 product. A relationship carrying no quantity counts as one.
 * @tags           rollup, cost, weight, variant, bom
 *
 * TODO(review): unproven query
 */
MATCH path = (leaf)<-[rs:RESOLVED_LINK {idVariant: $idVariant}]-*(:Product)
WHERE NOT EXISTS { (leaf)-[:RESOLVED_LINK {idVariant: $idVariant}]->() }
WITH leaf, reduce(acc = 1, r IN rs | acc * coalesce(r.qty, 1)) AS times
WITH leaf, {cost: leaf.cost * times, weight: leaf.weight * times} AS vals
WITH collect(vals) AS valsList
WITH reduce(acc = {cost: 0.0, weight: 0.0}, vals IN valsList |
     {cost: acc.cost + vals.cost, weight: acc.weight + vals.weight}) AS vals
RETURN round(vals.weight, 2) AS weightKg, round(vals.cost, 2) AS cost
```

## Find configuration decisions the constraints could not satisfy

```cypher
/*
 * @name           Find configuration decisions the constraints could not satisfy
 * @description    Returns the paths to configuration decisions that the
 *                 resolved variant reaches but never resolves — decisions whose
 *                 every option the constraints rejected.
 * @params         productId - Identifier of the product the variant was
 *                     resolved for. Matches Product.productId.
 *                 idVariant - Name of the variant to check, as supplied when it
 *                     was resolved.
 * @prerequisites  The variant has been resolved.
 * @returns        One path per unsatisfied decision, from the product down to
 *                 the decision node, showing which branch of the structure the
 *                 contradiction sits in.
 * @usage          This is the over-constrained check, and it should be run
 *                 before any result is reported: the rollup and the resolved
 *                 bill of materials both return perfectly well on an incomplete
 *                 variant, so an empty result here is what makes them
 *                 trustworthy. A returned decision names the category whose
 *                 allow or deny list is impossible to satisfy — widen that
 *                 list, or accept that the product cannot be built to that
 *                 specification. Run it on a variant that was never resolved
 *                 and it returns nothing, because nothing was reached; that is
 *                 not the same as a satisfiable configuration.
 * @tags           constraints, diagnostics, over-constrained, variant
 *
 * TODO(review): unproven query
 */
MATCH path = (:Product {productId: $productId})-[:RESOLVED_LINK {idVariant: $idVariant}]->*(x)
             -[:REQUIRES]->(y:ConfigGroup)
WHERE NOT EXISTS { (x)-[:RESOLVED_LINK {idVariant: $idVariant}]->(y) }
RETURN path
```

## Clear a resolved variant

```cypher
/*
 * @name           Clear a resolved variant
 * @description    Deletes every RESOLVED_LINK belonging to one variant,
 *                 returning the database to its imported state as far as that
 *                 variant is concerned. WRITES to the database.
 * @params         idVariant - Name of the variant to clear, as supplied when it
 *                     was resolved.
 * @prerequisites  None beyond the imported model.
 * @returns        Nothing. Its effect is the RESOLVED_LINK relationships it
 *                 deletes.
 * @usage          Run before re-resolving a variant under different
 *                 constraints: resolution merges links rather than replacing
 *                 them, so re-running over an existing variant adds the new
 *                 result to the old one and the two become indistinguishable.
 *                 Touches only links carrying this variant name, so other
 *                 variants and the whole configurable structure are unaffected.
 *                 On a variant with very many links, wrap the delete in
 *                 CALL { ... } IN TRANSACTIONS to avoid one large transaction.
 * @tags           cleanup, variant, reset, write
 *
 * TODO(review): unproven query
 */
MATCH ()-[r:RESOLVED_LINK {idVariant: $idVariant}]->()
DELETE r
```

## Node-key constraints (schema reference)

The Import flow creates these from the key definitions in `GRAPH_MODEL.json`.
They are listed here so the expected schema can be verified against a live
database — `SHOW CONSTRAINTS` should report all four — not so they can be
created by hand. There are no constraints on `RESOLVED_LINK`, and no definition
of it in the model either: it is written by the queries above rather than
imported.

```cypher
CREATE CONSTRAINT product_key IF NOT EXISTS
FOR (n:Product) REQUIRE n.productId IS NODE KEY;

CREATE CONSTRAINT assembly_key IF NOT EXISTS
FOR (n:Assembly) REQUIRE n.assemblyId IS NODE KEY;

CREATE CONSTRAINT config_group_key IF NOT EXISTS
FOR (n:ConfigGroup) REQUIRE n.configGroupId IS NODE KEY;

CREATE CONSTRAINT part_key IF NOT EXISTS
FOR (n:Part) REQUIRE n.partId IS NODE KEY;
```
