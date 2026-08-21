# Claims Fraud — Query Guidance

Cypher for the `insurance-claims-fraud` use case. Every query references only labels,
relationship types, and properties defined in `GRAPH_MODEL.json`. The `//` comments before
each query state its purpose, inputs, prerequisites, and the expected result against the
bundled `sample-data/` so they act as a lightweight test oracle.

Prerequisites for this section: Neo4j 5.x / Cypher 5, and the bundled sample data imported
(Claimant, MedicalProfessional, Claim, Vehicle with HAS_CLAIM, TREATED_BY, OWNS,
INVOLVED_IN, TREATS). No APOC required. The GDS section below additionally requires the
Graph Data Science library.

Sample-data profile (synthetic, seeded): 4,000 claimants, 50 medical professionals,
4,500 vehicles, 5,000 claims. Deliberately seeded fraud signals: 600 claimants with more
than one claim, 3 medical professionals handling only high-value claims, and 100 vehicles
each reused across 6 claims (crash-for-cash). Thresholds in the queries below are tuned to
this profile — the source page's demo thresholds (`> 1`, `> 5000`) match its four-row demo
and would flag almost everything at this volume.

## 1. Claimants with multiple claims

```cypher
// Purpose: flag claimants who filed more than one claim (a possible red flag).
// Inputs: none. Prerequisites: Claimant-[:HAS_CLAIM]->Claim imported.
// Expected (sample data): 600 rows; the top claimants have numClaims = 10, then 5, then 2.
MATCH (c:Claimant)-[:HAS_CLAIM]->(cl:Claim)
WITH c, count(cl) AS numClaims
WHERE numClaims > 1
RETURN c.name AS claimant, numClaims
ORDER BY numClaims DESC
```

```cypher
// Purpose: graph view of the claims belonging to the most prolific repeat claimants.
// Note: corrected from the source page, where `path` was dropped by the aggregating WITH
// and would not compile; here the path is re-matched after the count. A LIMIT keeps the
// visualisation readable at this data volume.
// Expected (sample data): the claim subgraphs of the highest-frequency claimants (up to 10 claims each).
MATCH (c:Claimant)-[:HAS_CLAIM]->(:Claim)
WITH c, count(*) AS numClaims
WHERE numClaims > 1
ORDER BY numClaims DESC
LIMIT 20
MATCH path = (c)-[:HAS_CLAIM]->(:Claim)
RETURN path
```

## 2. Medical professionals with unusual patterns

```cypher
// Purpose: surface medical professionals who are clear outliers by claim volume or total value.
// Inputs: thresholds tuned to THIS sample — the median doctor handles ~94 claims / ~£0.85M
//   total, so > 150 claims OR > £3M isolates the outliers. Retune for your portfolio; the
//   source page's > 1 / > 5000 would return every doctor at this volume.
// Prerequisites: Claim-[:TREATED_BY]->MedicalProfessional imported; amountClaimed is numeric.
// Expected (sample data): 3 rows (the seeded fraudulent doctors), each claimCount 200 and
//   totalAmount roughly £7.7M–£8.1M. The next-highest doctor sits at ~94 claims / ~£0.85M.
MATCH (m:MedicalProfessional)<-[:TREATED_BY]-(cl:Claim)
WITH m, count(cl) AS claimCount, sum(cl.amountClaimed) AS totalAmount
WHERE claimCount > 150 OR totalAmount > 3000000
RETURN m.name AS medicalProfessional, claimCount, totalAmount
ORDER BY totalAmount DESC
```

```cypher
// Purpose: threshold-free ranking of medical professionals by exposure — robust as data grows.
// Inputs: LIMIT only. Prerequisites: as above.
// Expected (sample data): the 3 fraudulent doctors head the list (~£8M each, 200 claims),
//   followed by a long tail of ~£0.85M / ~94-claim doctors.
MATCH (m:MedicalProfessional)<-[:TREATED_BY]-(cl:Claim)
RETURN m.name AS medicalProfessional,
       count(cl) AS claimCount,
       sum(cl.amountClaimed) AS totalAmount
ORDER BY totalAmount DESC
LIMIT 10
```

## 3. Potential "crash for cash" scams

```cypher
// Purpose: identify vehicles appearing in more than one claim (a staged-accident signal).
// Inputs: none. Prerequisites: Vehicle-[:INVOLVED_IN]->Claim imported.
// Expected (sample data): 100 rows, each with claimCount = 6 (the seeded crash-for-cash
//   vehicles). The other 4,400 vehicles appear in exactly one claim and are excluded.
MATCH (v:Vehicle)-[:INVOLVED_IN]->(cl:Claim)
WITH v, count(cl) AS claimCount
WHERE claimCount > 1
RETURN v.VIN AS vehicle, claimCount
ORDER BY claimCount DESC
```

```cypher
// Purpose: graph view of claims linked to vehicles involved in more than one claim.
// A LIMIT keeps the visualisation readable; drop it to see all 100 reused vehicles.
// Expected (sample data): up to 10 shared vehicles, each fanning out to 6 claims.
MATCH (v:Vehicle)-[:INVOLVED_IN]->(:Claim)
WITH v, count(*) AS claimCount
WHERE claimCount > 1
ORDER BY claimCount DESC
LIMIT 10
MATCH path = (v)-[:INVOLVED_IN]->(:Claim)
RETURN path
```

## 4. Graph Data Science (advanced, optional)

These require the Graph Data Science (GDS) library, which is not available on every target
(for example, some Aura tiers). They have not been executed against the sample data.

```cypher
// TODO(review): unproven query — requires GDS. Purpose: build an in-memory projection.
// Prerequisites: GDS installed; sample data imported.
// Expected: returns the projected node and relationship counts for 'fraud-graph'.
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

```cypher
// TODO(review): unproven query — requires GDS and the 'fraud-graph' projection above.
// Purpose: community detection to reveal clusters of related claimants, doctors, and vehicles.
// Expected: one (nodeId, communityId) row per projected node; the John Doe / Dr. House /
// VIN-12345 cluster should fall in a single community given the shared claims.
CALL gds.louvain.stream('fraud-graph')
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId) AS node, communityId
ORDER BY communityId ASC
```

```cypher
// TODO(review): unproven query — requires GDS and the 'fraud-graph' projection above.
// Purpose: PageRank to highlight highly connected (potentially central) entities.
// Expected: a score per projected node, highest for the most connected entities.
CALL gds.pageRank.stream('fraud-graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId) AS node, score
ORDER BY score DESC
```

```cypher
// TODO(review): unproven query — requires GDS. Remember to release the projection.
CALL gds.graph.drop('fraud-graph')
```

## Constraints

The node-key constraints below are created automatically when the sample data is loaded via
the Import app from `GRAPH_MODEL.json`, which is the only route data takes into the graph.
They are listed here as a schema reference and to verify what the import produced:

```cypher
// Node-key constraints matching GRAPH_MODEL.json.
CREATE CONSTRAINT name_Claimant_key IF NOT EXISTS
  FOR (c:Claimant) REQUIRE c.name IS NODE KEY;
CREATE CONSTRAINT name_MedicalProfessional_key IF NOT EXISTS
  FOR (m:MedicalProfessional) REQUIRE m.name IS NODE KEY;
CREATE CONSTRAINT claimID_Claim_key IF NOT EXISTS
  FOR (cl:Claim) REQUIRE cl.claimID IS NODE KEY;
CREATE CONSTRAINT VIN_Vehicle_key IF NOT EXISTS
  FOR (v:Vehicle) REQUIRE v.VIN IS NODE KEY;
```
