---
name: retail-banking
description: Detect retail banking transaction fraud rings with a Neo4j reference ontology and Cypher query patterns for ring, chronology, and amount-decay checks.
metadata:
  neo4j-card-title: Retail Banking
  neo4j-card-category: Financial Services
  neo4j-card-description: Follow payments through chains of accounts to find money that comes back to where it started.
---

# Retail Banking

Use this skill for retail-banking transaction fraud ring analysis, especially for suspicious circular money movement and APP-fraud style flows.

Source reference:

- <https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/transaction-ring/>

Do not treat this as legal or regulatory advice; use it for graph-modelling and query-pattern guidance. Treat every result as an investigative lead requiring analyst review, not proof of fraud. The bundled sample data is synthetic.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: money moved through a chain of accounts to obscure where it came from and who benefited. No single transaction looks wrong; the shape only appears when you follow the payments and find they come back to where they started. A graph makes that a traversal rather than a self-join, so a ring, the paths into it, and the intermediaries are things you can see.
- The bundled sample data is synthetic: a few months of everyday retail-banking payments — payroll, card spend, supplier settlements, transfers between friends, loan repayments and refunds — with laundering rings and near-misses seeded among them. Everyday activity closes plenty of innocent loops, so each query in turn has genuine rings to keep and look-alikes to discard.
- What you can help with: explaining the reference ontology and why the transaction is a node rather than a relationship, walking through the ring queries from bare cycle detection to chronology and amount decay, importing the sample data or mapping their own payments data onto the reference ontology, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Nodes: `Account {accountNumber}`, `Transaction {transactionId, amount, currency, date}`.
- Relationships: `(Account)-[:PERFORMS]->(Transaction)`, `(Transaction)-[:BENEFITS_TO]->(Account)`.
- The transaction is a node, not a relationship, so it can carry its own amount and timestamp and be traversed from either side. That is what makes the chronology and decay checks expressible.
- The decay query divides each payment's amount by the previous one's and accepts 0.80–1.00, a loss of up to 20% per hop. The source page's version divides the other way round, which accepts growth instead of decay; this package follows the page's stated intent, not its Cypher.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.cypher`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data, and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Party money passes through | `Account` | A stable key per account that payments both leave and arrive at. A ring closes only when the walk returns to the same node, so one real account split across two keys hides the ring |
| Directed transfer | `Transaction` | A node per transfer with exactly one link in from the paying party (`PERFORMS`) and one out to the beneficiary (`BENEFITS_TO`). Transfers stored as direct account-to-account relationships need the patterns rewritten around relationship properties |
| Comparable value and time | `Transaction` (`amount`, `date`) | A positive amount in one shared currency and a true execution timestamp on every transfer. Without them only the structural ring queries apply |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.cypher`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.9+ and Cypher 5, for the quantified path patterns and the chained comparison in the decay query. The two queries headed "(requires APOC)" need `apoc.coll.toSet`; check the procedure exists before offering them. The others need no plugin.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- The hop bounds and the amount-ratio band are literals in the Cypher, not parameters, and they are starting points, not values that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or the **Graph census** and the ring named in `@sample` match it. Then treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Run the checks in order, broad to strict: directed rings, then distinct accounts, then chronology and amount decay. The progression keeps each result explainable and shows which condition removes a ring when data quality is uneven. Then rank candidates by risk context the reference ontology does not hold — velocity, shared identifiers, account age — rather than presenting a ring as a finding.
- Before applying the chronology and ratio checks to the user's data, confirm `amount` is numeric and `date` is a temporal execution timestamp; a posting or value date breaks the chronology test.
- Keep an explicit upper hop bound. Quantifier bounds cannot be parameters, so a configurable depth means generating the query text. An unbounded quantifier over a dense transaction graph is the most likely way these queries become expensive.
- Validate the ratio direction against a known example before trusting results; inverting it silently returns amount-growth rings.
- Amount ratios assume every payment on a ring shares one currency; partial payments and currency conversion invalidate them.
- The bundled sample's rings are seeded deliberately, so a hit rate on it is not a measure of precision on real data.
- Real fraud often branches rather than forming a perfect cycle, and closed loops have legitimate explanations — refunds, treasury sweeps, transfers between a customer's own accounts. A chronological, decaying ring is a stronger lead than a bare cycle, not a conclusion.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
