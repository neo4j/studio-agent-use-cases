---
name: retail-banking
description: Detect retail banking transaction fraud rings with graph models, Neo4j schema design, and Cypher query patterns for ring, chronology, and amount-decay checks.
metadata:
  neo4j-card-title: Retail Banking
  neo4j-card-category: Financial Services
  neo4j-card-description: Spot suspicious entities and hidden paths in real time, and surface coordinated behavior across accounts and devices.
  neo4j-icon-category: risk-detection
---

# Transaction Fraud Ring

Use this skill for retail-banking transaction fraud ring analysis, especially for suspicious circular money movement and APP-fraud style flows.

Source reference:
https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/transaction-ring/

Do not treat this as legal/regulatory advice; use it for graph modeling and query-pattern guidance.

## Operational Constraints

For runnable examples:

- Clarify intended target database/connection before execution.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (only if requested)
What this detects
Tuning options
Validation approach
```
