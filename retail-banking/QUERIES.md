# Retail Banking — Query Guidance

Cypher for the `retail-banking` use case. Every query references only labels, relationship types, and properties defined in `GRAPH_MODEL.json`. The `//` comments before each query state its purpose, inputs, prerequisites, and the expected result against the bundled `sample-data/` so they act as a lightweight test oracle.

Prerequisites for every query below:

- Neo4j 5.9+ / Cypher 5. The ring queries use quantified path patterns (`{3,6}`, `*`), and the decay query uses a chained comparison (`0.80 <= x <= 1.00`).
- Queries 2 and 3 require APOC (`apoc.coll.toSet`). Query 1 needs no plugin.
- The graph is loaded via the bundled sample-data Import (`GRAPH_MODEL.json`), which is the only route data takes into the graph.
- Node-key constraints on `Account.accountNumber` and `Transaction.transactionId` are created by Import, so every anchored lookup is an index seek rather than a label scan.

Sample-data profile: 4 accounts (`1`–`4`) and 4 transactions forming exactly one closed directed ring, `1 → 2 → 3 → 4 → 1`. Amounts decay by a constant factor of 0.9 (1000.00, 900.00, 810.00, 729.00 GBP) on consecutive days from 2023-10-24 to 2023-10-27. The dataset is deliberately minimal: it contains one positive case and no negative cases, so it proves each query returns the ring and does not demonstrate selectivity.

> TODO(verify): the expected-result counts below are derived from the sample CSVs by inspection and have not been executed against a live database. Confirm them on a freshly imported instance and remove this note.

## 0. Graph census

```cypher
// Purpose: confirm the import landed before running anything else, and supply a real anchor.
// Inputs: none.
// Expected: 1 row — accounts 4, transactions 4.
MATCH (a:Account)
WITH count(a) AS accounts
MATCH (t:Transaction)
RETURN accounts, count(t) AS transactions;
```

## 1. Directed ring (basic)

```cypher
// Purpose: first pass — prove directed cycles of 3 to 6 account hops exist at all.
// Inputs: none. Every account is tried as the ring's starting point.
// Prerequisites: none beyond Neo4j 5.9+.
// Expected: 4 paths against the sample data. The ring is 4 hops long, so only a
//   4-repetition match closes back on the start; each of the 4 accounts yields the
//   same ring rotated to start at itself. Repetition counts 3, 5, and 6 land on a
//   different account and match nothing.
MATCH path =
  (start:Account)
  (()-[:PERFORMS]->()-[:BENEFITS_TO]->()){3,6}
  (start)
RETURN path;
```

## 2. Directed ring with distinct accounts

```cypher
// Purpose: drop rings that revisit an intermediate account, which are usually
//   legitimate back-and-forth activity rather than layering.
// Inputs: none.
// Prerequisites: APOC (apoc.coll.toSet).
// Expected: 4 paths — the same 4 as query 1. Every account in the sample ring is
//   distinct, so this filter removes nothing here. On real data it is the filter
//   that does the most work.
MATCH path =
  (start:Account)
  ((source)-[:PERFORMS]->(tx)-[:BENEFITS_TO]->(target)){3,6}
  (start)
WHERE size(apoc.coll.toSet(source)) = size(source)
RETURN path;
```

## 3. Chronological and amount-decay ring

```cypher
// Purpose: the strongest of the three — require the ring to move forward in time
//   and lose a consistent slice of value at each hop, the signature of a cut being
//   taken at every step.
// Inputs: none. The 0.80–1.00 ratio band is the parameter to retune on real data.
// Prerequisites: APOC (apoc.coll.toSet).
// Expected: 1 path against the sample data — the ring anchored at account 1.
//   Amounts decay 1000 → 900 → 810 → 729 (a constant 0.9) on ascending dates, so
//   only the rotation starting at the largest amount satisfies the band the whole
//   way round; closing from 729 back to 1000 is a ratio of 1.37 and fails.
//   This is the query to show when explaining why direction and ordering matter.
MATCH path =
  (start:Account)-[:PERFORMS]->(firstTx)
  (
    (previousTx)-[:BENEFITS_TO]->(middleAccount)-[:PERFORMS]->(nextTx)
    WHERE previousTx.date < nextTx.date
      AND 0.80 <= nextTx.amount / previousTx.amount <= 1.00
  )*
  (lastTx)-[:BENEFITS_TO]->(start)
WHERE size(apoc.coll.toSet([start] + middleAccount)) = size([start] + middleAccount)
RETURN path;
```

## Tuning

- The ratio band and the `{3,6}` hop bound are the two levers. Widen the band and you catch more layering but also ordinary commerce; widen the hop bound and cost grows quickly.
- Quantifier bounds are literals. Cypher rejects a parameter inside `{1,n}`, so a configurable depth means generating the query text, not passing a parameter.
- Always keep an explicit upper hop bound in production. An unbounded quantifier over a dense transaction graph is the most likely way these queries become expensive.
- Validate the ratio direction against a known example before trusting results. Inverting it silently returns amount-_growth_ rings, which look plausible and mean something different.
- Without APOC, queries 2 and 3 lose their distinctness filter. Rewrite it with `size(apoc.coll.toSet(x)) = size(x)` replaced by a `reduce`-based check, or accept the duplicates and filter downstream.

## Constraints

The node-key constraints below are created automatically when the sample data is loaded via the Import app from `GRAPH_MODEL.json`, which is the only route data takes into the graph. They are listed here as a schema reference and to verify what the import produced:

```cypher
// Node-key constraints matching GRAPH_MODEL.json. Schema reference; Import creates these.
CREATE CONSTRAINT accountNumber_Account_key IF NOT EXISTS
  FOR (a:Account) REQUIRE a.accountNumber IS NODE KEY;
CREATE CONSTRAINT transactionId_Transaction_key IF NOT EXISTS
  FOR (t:Transaction) REQUIRE t.transactionId IS NODE KEY;
```
