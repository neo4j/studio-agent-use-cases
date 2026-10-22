# Insurance Claims Fraud — Query Guidance

Cypher for the `insurance-claims-fraud` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database; the Graph Data Science queries create and drop an in-memory projection only.

## Prerequisites

- Neo4j 5.x, Cypher 5. No APOC required. The Graph Data Science section additionally requires the Graph Data Science (GDS) library, which is not available on every target — some Aura tiers do not include it.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology.
- The node keys in `ONTOLOGY.json` make `Claimant.name`, `MedicalProfessional.name`, `Claim.claimID`, and `Vehicle.VIN` unique. `Claim.amountClaimed` is an INTEGER, so the totals below are numeric sums.
- No `SETUP.md` statements are needed, and no query creates a label, relationship type, or property in the database. The GDS projection `fraud-graph` lives only in the GDS graph catalog, in memory, and does not exist until its projection query runs.
- The medical-professional outlier thresholds and the result sizes of the Louvain and PageRank queries are parameters, each with a starting point in `@params`. The other thresholds and limits are literals in the Cypher, and each query's `@usage` says how to change them.
- Queries come in pairs per signal — repeat claimants, medical-professional outliers, reused vehicles — a tabular query and a graph or ranking view, followed by the optional Graph Data Science section.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Claimants with multiple claims

```cypher
/*
 * @name           Claimants with multiple claims
 * @description    Flags claimants who filed more than one claim — the
 *                 simplest repeat-claimant check — by counting HAS_CLAIM
 *                 relationships per claimant.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per claimant with more than one claim: claimant
 *                 (Claimant.name) and numClaims, ordered by numClaims
 *                 descending.
 * @usage          The literal threshold numClaims > 1 is the definition of a
 *                 repeat claimant, not a tuned value. On a large portfolio
 *                 the list is long: raise the literal towards the
 *                 portfolio's upper percentile of claims per claimant until
 *                 the result is reviewable by hand. Claimants are keyed by
 *                 name, so a spelling variant counts as a different
 *                 claimant and splits the count. Frequency alone is a lead,
 *                 not a finding.
 * @tags           repeat-claimant, claimant, claim, frequency
 * @sample         Bundled sample data only: returns 600 rows — 20
 *                 claimants with 10 claims, then 80 with 5 and 500 with 2.
 */
MATCH (c:Claimant)-[:HAS_CLAIM]->(cl:Claim)
WITH c, count(cl) AS numClaims
WHERE numClaims > 1
RETURN c.name AS claimant, numClaims
ORDER BY numClaims DESC
```

## Claim subgraphs of the most frequent repeat claimants

```cypher
/*
 * @name           Claim subgraphs of the most frequent repeat claimants
 * @description    Visualises the claims of the most frequent repeat
 *                 claimants: ranks claimants with more than one claim by
 *                 claim count, keeps the top 20, and re-matches each one's
 *                 HAS_CLAIM paths after the count for Browser or Bloom to
 *                 draw.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths Claimant → Claim, one per claim, for at most 20
 *                 claimants.
 * @usage          Visual, not tabular — use Claimants with multiple claims
 *                 for the counts. The literal LIMIT 20 caps how many
 *                 claimants are drawn and keeps the picture readable; lower
 *                 it if the graph is crowded. Claimants tied on claim count
 *                 at the cut-off are chosen arbitrarily.
 * @tags           visualisation, repeat-claimant, claimant, claim
 * @sample         Bundled sample data only: returns 200 paths — the 20
 *                 claimants with 10 claims each.
 */
MATCH (c:Claimant)-[:HAS_CLAIM]->(:Claim)
WITH c, count(*) AS numClaims
WHERE numClaims > 1
ORDER BY numClaims DESC
LIMIT 20
MATCH path = (c)-[:HAS_CLAIM]->(:Claim)
RETURN path
```

## Medical professionals with unusual patterns

```cypher
/*
 * @name           Medical professionals with unusual patterns
 * @description    Surfaces medical professionals who are outliers by claim
 *                 volume or by total value claimed, counting TREATED_BY
 *                 relationships and summing Claim.amountClaimed per
 *                 professional.
 * @params         minClaims - Number of claims a professional must exceed to
 *                     be flagged on volume. Integer. Start at twice the
 *                     portfolio's median claims per professional, then
 *                     raise it until the result is reviewable by hand.
 *                 minTotal - Total amountClaimed, in whole currency units,
 *                     a professional must exceed to be flagged on value.
 *                     Integer. Start at twice the portfolio's median total
 *                     per professional, and tune it the same way.
 * @prerequisites  Claim.amountClaimed loaded as an INTEGER, so the sum is
 *                 numeric.
 * @returns        One row per professional above either threshold:
 *                 medicalProfessional (MedicalProfessional.name),
 *                 claimCount, and totalAmount (summed amountClaimed, in
 *                 whole currency units), ordered by totalAmount descending.
 * @usage          A professional above either threshold is returned. The
 *                 starting points use the median because it is not pulled
 *                 up by the outliers being looked for, as a high
 *                 percentile can be when outliers are more than a few
 *                 percent of professionals; the factor of two has no
 *                 strong prior behind it. Compute the medians with
 *                 percentileCont(…, 0.5) over the per-professional counts
 *                 and totals, and read Medical professionals ranked by
 *                 total claim value to keep each threshold between the
 *                 bulk of professionals and the outliers. Thresholds set
 *                 too low flag every busy professional. totalAmount
 *                 assumes a single-currency portfolio. A busy clinic and a
 *                 fraudulent one look alike from the outside, so an
 *                 outlier is a lead for review.
 * @tags           medical-professional, outlier, claim-value, claim-volume
 * @sample         Bundled sample data only: $minClaims = 150, $minTotal =
 *                 3000000 returns 3 rows — Dr. Ruth Butler (200 claims,
 *                 8135003), Dr. Jason Brown (200, 8001365), and Dr. Eric
 *                 Robinson (200, 7701383).
 */
MATCH (m:MedicalProfessional)<-[:TREATED_BY]-(cl:Claim)
WITH m, count(cl) AS claimCount, sum(cl.amountClaimed) AS totalAmount
WHERE claimCount > $minClaims OR totalAmount > $minTotal
RETURN m.name AS medicalProfessional, claimCount, totalAmount
ORDER BY totalAmount DESC
```

## Medical professionals ranked by total claim value

```cypher
/*
 * @name           Medical professionals ranked by total claim value
 * @description    Threshold-free ranking of medical professionals by the
 *                 total value claimed across the claims they are attached
 *                 to, with claim count alongside.
 * @params         None
 * @prerequisites  Claim.amountClaimed loaded as an INTEGER, so the sum is
 *                 numeric.
 * @returns        Up to 10 rows: medicalProfessional
 *                 (MedicalProfessional.name), claimCount, and totalAmount
 *                 (summed amountClaimed, in whole currency units), ordered
 *                 by totalAmount descending.
 * @usage          Run it first, to see the spread before choosing the
 *                 thresholds for Medical professionals with unusual
 *                 patterns: outliers show as a gap between the leading rows
 *                 and the rest. The literal LIMIT 10 sets how many are
 *                 shown; raise it to see where the bulk of professionals
 *                 sits. It ranks rather than filters, so it stays
 *                 meaningful as the portfolio grows.
 * @tags           medical-professional, ranking, claim-value
 * @sample         Bundled sample data only: returns 10 rows, led by Dr.
 *                 Ruth Butler (200 claims, 8135003), Dr. Jason Brown (200,
 *                 8001365), and Dr. Eric Robinson (200, 7701383); the other
 *                 seven have 93–94 claims and totals from 848139 down to
 *                 788452.
 */
MATCH (m:MedicalProfessional)<-[:TREATED_BY]-(cl:Claim)
RETURN m.name AS medicalProfessional,
       count(cl) AS claimCount,
       sum(cl.amountClaimed) AS totalAmount
ORDER BY totalAmount DESC
LIMIT 10
```

## Potential "crash for cash" scams

```cypher
/*
 * @name           Potential "crash for cash" scams
 * @description    Identifies vehicles involved in more than one claim — the
 *                 staged-accident signal — by counting INVOLVED_IN
 *                 relationships per vehicle.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per vehicle involved in more than one claim:
 *                 vehicle (Vehicle.VIN) and claimCount, ordered by
 *                 claimCount descending.
 * @usage          The literal threshold claimCount > 1 flags any repeat
 *                 involvement. A vehicle can feature in more than one
 *                 genuine incident, so on a large portfolio raise the
 *                 literal until the result is reviewable and look hardest
 *                 at the highest counts. Relies on VIN being recorded
 *                 consistently: a missing or mistyped VIN splits one
 *                 vehicle into several.
 * @tags           crash-for-cash, vehicle, staged-accident, claim
 * @sample         Bundled sample data only: returns 100 rows, each with
 *                 claimCount 6.
 */
MATCH (v:Vehicle)-[:INVOLVED_IN]->(cl:Claim)
WITH v, count(cl) AS claimCount
WHERE claimCount > 1
RETURN v.VIN AS vehicle, claimCount
ORDER BY claimCount DESC
```

## Claim subgraphs of vehicles involved in more than one claim

```cypher
/*
 * @name           Claim subgraphs of vehicles involved in more than one claim
 * @description    Visualises the claims linked to vehicles involved in more
 *                 than one claim: ranks those vehicles by claim count,
 *                 keeps the top 10, and returns each one's INVOLVED_IN
 *                 paths for Browser or Bloom to draw.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths Vehicle → Claim, one per claim, for at most 10
 *                 vehicles.
 * @usage          Visual, not tabular — use Potential "crash for cash"
 *                 scams for the full list. The literal LIMIT 10 keeps the
 *                 picture readable; drop it to draw every vehicle involved
 *                 in more than one claim. Vehicles tied on claim count at
 *                 the cut-off are chosen arbitrarily.
 * @tags           visualisation, crash-for-cash, vehicle, claim
 * @sample         Bundled sample data only: returns 60 paths — 10 of the
 *                 100 vehicles with 6 claims each; which 10 is not fixed.
 */
MATCH (v:Vehicle)-[:INVOLVED_IN]->(:Claim)
WITH v, count(*) AS claimCount
WHERE claimCount > 1
ORDER BY claimCount DESC
LIMIT 10
MATCH path = (v)-[:INVOLVED_IN]->(:Claim)
RETURN path
```

## Graph Data Science (optional)

The queries in this section require the Graph Data Science (GDS) library, which is not available on every target — some Aura tiers do not include it. Confirm GDS is installed before offering them.

Run them in order: project the `fraud-graph` first, then the Louvain and PageRank queries in either order, and drop the projection last. The projection is an in-memory copy held in the GDS graph catalog; nothing in this section writes to the database. Projecting under a name that already exists fails, so drop an existing `fraud-graph` before projecting again.

## Project the fraud-graph

```cypher
/*
 * @name           Project the fraud-graph
 * @description    Builds the in-memory GDS projection 'fraud-graph' over
 *                 all four node labels and the HAS_CLAIM, TREATED_BY, OWNS,
 *                 and INVOLVED_IN relationships, each projected undirected.
 * @params         None
 * @prerequisites  GDS library installed. No projection named fraud-graph
 *                 already in the GDS graph catalog.
 * @returns        One row describing the projection, including its node
 *                 and relationship counts. GDS counts each undirected
 *                 relationship once in each direction.
 * @usage          Run before the Louvain and PageRank queries, and drop the
 *                 projection afterwards to release its memory. TREATS is
 *                 not projected, so the algorithms see claim-borne links
 *                 only.
 * @tags           gds, projection
 * @sample         Bundled sample data only: projects 13550 nodes and 39000
 *                 relationships (19500 relationships, each counted in both
 *                 directions).
 */
CALL gds.graph.project(
  'fraud-graph',
  ['Claimant', 'MedicalProfessional', 'Claim', 'Vehicle'],
  {
    HAS_CLAIM:   { orientation: 'UNDIRECTED' },
    TREATED_BY:  { orientation: 'UNDIRECTED' },
    OWNS:        { orientation: 'UNDIRECTED' },
    INVOLVED_IN: { orientation: 'UNDIRECTED' }
  }
)
```

## Louvain communities in the fraud-graph

```cypher
/*
 * @name           Louvain communities in the fraud-graph
 * @description    Runs Louvain community detection over the fraud-graph to
 *                 reveal clusters of related claimants, medical
 *                 professionals, claims, and vehicles, and summarises each
 *                 community by its size and by how many members carry each
 *                 label.
 * @params         limit - Maximum number of communities returned, largest
 *                     first. Start at 10 for a reviewable list; raise it to
 *                     reach smaller communities.
 * @prerequisites  GDS library installed; the fraud-graph projection from
 *                 Project the fraud-graph.
 * @returns        One row per community, at most $limit: communityId, size
 *                 (members), and claimants, professionals, claims, and
 *                 vehicles (members with each label), ordered by size
 *                 descending.
 * @usage          Louvain is not deterministic: community IDs are arbitrary
 *                 labels that change between runs, and boundaries can
 *                 shift too, so compare compositions rather than IDs. With
 *                 $limit at least the number of communities, the sizes and
 *                 each label column sum to the projected node counts. A
 *                 community whose claims outnumber its vehicles or its
 *                 claimants concentrates the reused-vehicle or
 *                 repeat-claimant signal; to list its members, filter the
 *                 stream on its communityId within the same run. A
 *                 community is a lead for review, not a ring.
 * @tags           gds, community-detection, louvain, ring
 * @sample         Bundled sample data only: $limit = 10 returns 10
 *                 communities, each with claimants, professionals, claims,
 *                 and vehicles summing to its size; community IDs and
 *                 compositions vary between runs.
 */
CALL gds.louvain.stream('fraud-graph')
YIELD nodeId, communityId
WITH communityId, gds.util.asNode(nodeId) AS member
WITH communityId,
     count(*) AS size,
     sum(CASE WHEN member:Claimant THEN 1 ELSE 0 END) AS claimants,
     sum(CASE WHEN member:MedicalProfessional THEN 1 ELSE 0 END) AS professionals,
     sum(CASE WHEN member:Claim THEN 1 ELSE 0 END) AS claims,
     sum(CASE WHEN member:Vehicle THEN 1 ELSE 0 END) AS vehicles
RETURN communityId, size, claimants, professionals, claims, vehicles
ORDER BY size DESC
LIMIT $limit
```

## PageRank centrality in the fraud-graph

```cypher
/*
 * @name           PageRank centrality in the fraud-graph
 * @description    Runs PageRank over the fraud-graph to highlight highly
 *                 connected, potentially central entities.
 * @params         limit - Maximum number of nodes returned, highest score
 *                     first. Start at 20 for a reviewable list; raise it to
 *                     look past the top-scoring label.
 * @prerequisites  GDS library installed; the fraud-graph projection from
 *                 Project the fraud-graph.
 * @returns        At most $limit rows: node (the node itself) and score,
 *                 ordered by score descending.
 * @usage          Scores grow with the number of claim links reaching a
 *                 node, and each medical professional is attached to many
 *                 claims, so professionals score highest by construction:
 *                 compare a node's score with others of the same label
 *                 rather than across labels. To rank one label, filter the
 *                 streamed nodes by label before the ORDER BY and LIMIT.
 * @tags           gds, centrality, pagerank
 * @sample         Bundled sample data only: $limit = 20 returns 20 medical
 *                 professionals; the three highest scores belong to Dr.
 *                 Jason Brown, Dr. Eric Robinson, and Dr. Ruth Butler.
 */
CALL gds.pageRank.stream('fraud-graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId) AS node, score
ORDER BY score DESC
LIMIT $limit
```

## Drop the fraud-graph projection

```cypher
/*
 * @name           Drop the fraud-graph projection
 * @description    Removes the fraud-graph projection from the GDS graph
 *                 catalog, releasing its memory.
 * @params         None
 * @prerequisites  GDS library installed; the fraud-graph projection
 *                 exists.
 * @returns        One row describing the dropped projection.
 * @usage          Run last, after the Louvain and PageRank queries. Fails
 *                 when no projection named fraud-graph exists.
 * @tags           gds, projection, clean-up
 */
CALL gds.graph.drop('fraud-graph')
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
CREATE CONSTRAINT name_Claimant_key IF NOT EXISTS
  FOR (c:Claimant) REQUIRE c.name IS NODE KEY;
CREATE CONSTRAINT name_MedicalProfessional_key IF NOT EXISTS
  FOR (m:MedicalProfessional) REQUIRE m.name IS NODE KEY;
CREATE CONSTRAINT claimID_Claim_key IF NOT EXISTS
  FOR (cl:Claim) REQUIRE cl.claimID IS NODE KEY;
CREATE CONSTRAINT VIN_Vehicle_key IF NOT EXISTS
  FOR (v:Vehicle) REQUIRE v.VIN IS NODE KEY;
```
