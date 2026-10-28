---
name: insurance-claims-fraud
description: Detect insurance claims fraud by modelling claimants, medical professionals, vehicles, and claims as a graph. Provides a reference ontology, bundled sample data, and Cypher for repeat claimants, unusual medical-professional activity, and vehicles reused across claims.
metadata:
  neo4j-card-title: Insurance Claims Fraud
  neo4j-card-category: Insurance
  neo4j-card-description: Uncover fraud rings and suspicious claims through the connections between claimants, doctors, vehicles, and claims.
---

# Insurance Claims Fraud

Use this skill for insurance fraud analysts and developers investigating claims fraud
(staged accidents, exaggerated injuries, inflated costs, crash-for-cash rings) by exploring
the relationships between claimants, medical professionals, vehicles, and claims.

Source reference:

- <https://neo4j.com/developer/industry-use-cases/insurance/claims-fraud/>

Disclaimer: this is an illustrative reference ontology with synthetic data, for demonstration.
Real claims fraud detection needs validated data, thresholds tuned to the portfolio, and human
review before any decision. Treat query results as leads for an investigator, never as a
determination of fraud, and do not present design choices, thresholds, or query behaviour as
proven guidance.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own
words — don't recite this file. Convey:

- The core idea: fraudulent claims (staged accidents, exaggerated injuries, inflated repair
  costs) tend to hide in the relationships between parties rather than in any single record —
  the same vehicle across several claims, one doctor tied to an unusual share of high-value
  claims, a claimant filing repeatedly.
- The bundled sample data is synthetic and deliberately seeds each of those patterns, so the
  queries in `QUERIES.md` return results straight away.
- A diagram of the reference ontology is available to show when explaining it:
  <https://neo4j.com/developer/industry-use-cases/_images/insurance/insurance-claims-fraud-schema.svg>
- What you can help with: explaining the reference ontology, walking through the query
  patterns (repeat claimants, unusual medical-professional activity, reused vehicles),
  importing the sample data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference
ontology or start importing data.

## Reference ontology

- Nodes: `Claimant {name}`, `MedicalProfessional {name}`, `Claim {claimID, date, amountClaimed}`, `Vehicle {VIN}`.
- Relationships: `(Claimant)-[:HAS_CLAIM]->(Claim)`, `(Claim)-[:TREATED_BY]->(MedicalProfessional)`, `(Claimant)-[:OWNS]->(Vehicle)`, `(Vehicle)-[:INVOLVED_IN]->(Claim)`, `(MedicalProfessional)-[:TREATS]->(Claimant)`.
- Every claim has exactly one claimant, one vehicle and one medical professional, so the fraud signals are concentrations: many claims on one claimant, one vehicle, or one professional. A professional's link to a claim (`TREATED_BY`) is held apart from their care link to a person (`TREATS`) so the two can be compared.
- `Claimant` and `MedicalProfessional` are keyed by name, so identity is expected to be resolved before import; `Claim.date` is an ISO `YYYY-MM-DD` string rather than a temporal type; `Claim.amountClaimed` is whole currency units in a single-currency portfolio.
- The labels, relationships and properties follow the source page. Its queries were corrected here: its repeat-claimant graph view dropped `path` in an aggregating `WITH` and would not compile, so the path is re-matched after the count; and its professional thresholds (more than 1 claim, or a total above 5000) suit a four-row demo, so the outlier query is paired with a threshold-free ranking.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything. The Graph Data Science queries build an in-memory projection, `fraud-graph`, which never reaches the database.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases` and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Doctor` often names the user's equivalent label), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Party | `Claimant` | A resolved identity that files claims and owns assets, so repeat filing counts against one node rather than spelling variants |
| Financial event | `Claim` | One node per claim, carrying a numeric amount and linked to exactly one party, one asset and one professional |
| Shared asset | `Vehicle` | A node keyed on a value that outlives owners and plates (a VIN), so several claims can converge on it |
| Supporting professional | `MedicalProfessional` | A resolved identity attached to claims, so claim count and summed value concentrate on it |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.x and Cypher 5; no APOC. The Graph Data Science queries require the GDS library, which is not available on every target (for example, some Aura tiers) — check before offering them, and run them in order: project `fraud-graph`, then Louvain or PageRank, then drop the projection.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of an `@sample` anchor (for example a medical professional it names) finds it. Then use it as a smoke test of the import, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- The repeat-claimant and vehicle queries keep their thresholds and limits as literals in the Cypher; they are starting points too, so tune them per portfolio as each query's `@usage` describes. For medical professionals, read the threshold-free ranking before setting `$minClaims` and `$minTotal`.
- Repeat claims, high-value concentration on a professional, and a vehicle in several claims each have innocent explanations — a busy clinic and a fraudulent one look alike from the outside. Present every result as a lead for an investigator, never as a finding.
- Totals of `Claim.amountClaimed` assume a single-currency portfolio. Convert `Claim.date` with `date()` before any date arithmetic.
- The Louvain query summarises each community by size and members per label, and the PageRank query is capped; both take `$limit`. Louvain community IDs are arbitrary and change between runs, so compare compositions, never IDs.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
