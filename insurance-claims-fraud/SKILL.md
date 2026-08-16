---
name: insurance-claims-fraud
description: Detect insurance claims fraud by modelling claimants, medical professionals, vehicles, and claims as a graph. Provides a graph model, bundled sample data, and Cypher for repeat claimants, unusual medical-professional activity, and vehicles reused across claims.
metadata:
  neo4j-card-title: Insurance Claims Fraud
  neo4j-card-category: Insurance & Risk
  neo4j-card-description: Uncover fraud rings and suspicious claims through the connections between claimants, doctors, vehicles, and claims.
  neo4j-icon-category: risk-detection
---

# Insurance Claims Fraud

Use this skill for insurance fraud analysts and developers investigating claims fraud
(staged accidents, exaggerated injuries, inflated costs, crash-for-cash rings) by exploring
the relationships between claimants, medical professionals, vehicles, and claims.

Source reference:

- <https://neo4j.com/developer/industry-use-cases/insurance/claims-fraud/>

Disclaimer: this is an illustrative, synthetic model for demonstration. Real claims fraud
detection needs validated data, thresholds tuned to the portfolio, and human review before
any decision. Do not present model choices, thresholds, or query behaviour as proven guidance.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own
words — don't recite this file. Convey:

- The core idea: fraudulent claims (staged accidents, exaggerated injuries, inflated repair
  costs) tend to hide in the relationships between parties rather than in any single record —
  the same vehicle across several claims, one doctor tied to an unusual share of high-value
  claims, a claimant filing repeatedly.
- The bundled sample data is synthetic and deliberately seeds each of those patterns, so the
  queries in `QUERIES.md` return results straight away.
- A schema diagram is available to show when explaining the model:
  <https://neo4j.com/developer/industry-use-cases/_images/insurance/insurance-claims-fraud-schema.svg>
- What you can help with: explaining the model, walking through the query patterns (repeat
  claimants, unusual medical-professional activity, reused vehicles), importing the sample
  data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the model or start
importing data.

## Model

- Nodes: `Claimant {name}`, `MedicalProfessional {name}`, `Claim {claimID, date, amountClaimed}`, `Vehicle {VIN}`.
- Relationships: `(Claimant)-[:HAS_CLAIM]->(Claim)`, `(Claim)-[:TREATED_BY]->(MedicalProfessional)`, `(Claimant)-[:OWNS]->(Vehicle)`, `(Vehicle)-[:INVOLVED_IN]->(Claim)`, `(MedicalProfessional)-[:TREATS]->(Claimant)`.
- Full schema, mappings, and sample CSVs are in `GRAPH_MODEL.json` and `sample-data/`; runnable Cypher with expected results is in `QUERIES.md`.

## Operational Constraints

- Prefer the bundled `sample-data/` Import flow. No post-import setup is required — do not improvise indexes or constraints after Import.
- The Graph Data Science queries in `QUERIES.md` require the GDS library and are unproven; flag that before running.
- Thresholds in the queries (claim count, total amount) are illustrative parameters; tune per portfolio.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
