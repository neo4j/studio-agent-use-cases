---
name: retail-banking
description: Detect retail banking transaction fraud rings with graph models, Neo4j schema design, and Cypher query patterns for ring, chronology, and amount-decay checks.
metadata:
  neo4j-card-title: Retail Banking
  neo4j-card-category: Real-time risk detection
  neo4j-card-description: Spot suspicious entities and hidden paths in real time, and surface coordinated behavior across accounts and devices.
  neo4j-card-icon: FingerPrintIconOutline
---

# Transaction Fraud Ring

Use this skill for retail-banking transaction fraud ring analysis, especially for suspicious circular money movement and APP-fraud style flows.

Source reference:
https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/transaction-ring/

Do not treat this as legal/regulatory advice; use it for graph modeling and query-pattern guidance.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: money moved through a chain of accounts to obscure where it came from and who benefited. No single transaction looks wrong; the shape only appears when you follow the payments and find they come back to where they started. A graph makes that a traversal rather than a self-join, so a ring, the paths into it, and the intermediaries are things you can see.
- The bundled sample data is deliberately minimal — 4 accounts and 4 transactions forming exactly one closed ring, `1 → 2 → 3 → 4 → 1`, with the amount decaying by a constant 0.9 on consecutive days. It is a worked example, not a realistic portfolio: it shows what a ring looks like and how the three queries tighten around it, and it contains no negative cases to test selectivity against.
- What you can help with: explaining the `Account`–`Transaction` model and why the transaction is a node rather than a relationship, walking through the three ring queries from bare cycle detection to chronology and amount decay, importing the sample data or mapping their own payments data onto the model, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the model or start importing data.

## Model

- Nodes: `Account {accountNumber}`, `Transaction {transactionId, amount, currency, date}`.
- Relationships: `(Account)-[:PERFORMS]->(Transaction)`, `(Transaction)-[:BENEFITS_TO]->(Account)`.
- The transaction is a node, not a relationship, so it can carry its own amount and timestamp and be traversed from either side. That is what makes the chronology and decay checks expressible.
- Full schema, mappings, and sample CSVs are in `GRAPH_MODEL.json` and `sample-data/`; runnable Cypher with expected results is in `QUERIES.md`.

## Supporting files

| File                         | Use it for                                                    |
| ---------------------------- | ------------------------------------------------------------- |
| `overview.md`                | What a transaction fraud ring is, and the core objective      |
| `graph-model.md`             | Labels, relationships, and the meaning of each required field |
| `detection-workflow.md`      | The order to run the checks in                                |
| `query-patterns.md`          | Which query to run when, and why each is shaped that way      |
| `QUERIES.md`                 | Runnable Cypher, each with an expected-result comment         |
| `query-templates.md`         | The bare query text, without commentary                       |
| `implementation-guidance.md` | Adapting the model to real payments data                      |
| `caveats.md`                 | Limitations and false-positive modes                          |

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, which is the only route. This package ships no write-based seed; don't offer one, and don't fall back to `LOAD CSV` or a `CREATE` script.
- Clarify intended target database/connection before execution.
- No post-import setup is required — do not improvise indexes, constraints, or labels after Import.
- Requires Neo4j 5.9+ / Cypher 5 for the quantified path patterns and the chained comparison in the decay query.
- The distinct-account filter in queries 2 and 3 of `QUERIES.md` requires APOC (`apoc.coll.toSet`). Check the procedure exists before offering those two; query 1 needs no plugin.
- The sample data holds one positive case and no negative cases. It shows the queries return the ring; it does not show they discriminate. Say so rather than presenting a 4-of-4 hit rate as precision.
- Treat all outputs as investigative leads, not proof of fraud.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (only if requested)
What this detects
Tuning options
Validation approach
```
