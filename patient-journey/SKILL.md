---
name: patient-journey
description: Model and analyze patient journeys through a healthcare system with Neo4j — longitudinal care pathways, comorbidity, treatment-pattern queries across patients, encounters, diagnoses, and more.
metadata:
  neo4j-card-title: Patient Journey
  neo4j-card-category: Healthcare & Life Sciences
  neo4j-card-description: Map longitudinal care pathways and discover comorbidities across a connected clinical graph.
  neo4j-icon-category: healthcare-lifesciences
---

# Patient Journey

Use this skill for healthcare patient-journey analysis: mapping individual care pathways, discovering comorbidities across a patient population, understanding provider–patient relationships, and querying longitudinal clinical data modelled as a graph.

Source reference:

- <https://github.com/jarasch/field-industry-use-cases/blob/main/modules/ROOT/pages/life-sciences/medical-care/patient-journey.adoc>

This is a graph-modelling and query-pattern aid, not clinical guidance. Treat query results as analytical leads, not clinical diagnoses or regulatory conclusions. The bundled sample data is synthetic (Synthea, Massachusetts, seed 100) and does not represent real patients.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: a patient's history is scattered across encounters, lab results, prescriptions, diagnoses, and the providers and facilities that delivered care. A graph represents those connections directly — traverse from a patient along their sequence of encounters, out to the conditions diagnosed, drugs prescribed, and measurements taken at each one, instead of stitching records together with joins.
- The bundled sample data is synthetic (Synthea, Massachusetts) with overlapping conditions such as hypertension and type 2 diabetes — enough to demonstrate single-patient pathways and cross-patient comorbidity patterns.
- What you can help with: explaining the model, walking through the query patterns from a single patient to population-level comorbidity analysis, importing the sample data or adapting the model to their own EHR, FHIR, or OMOP data, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the model or start importing data.

## Model

- Nodes: `Patient {id, name, birthDate}`, `Encounter {id, date, type}`, `Observation {id, code, description, value, units}`, `Condition {code, description}`, `Drug {code, name}`, `Provider {id, name}`, `Speciality {name}`, `Organisation {id, name, address}`.
- Relationships: `(Patient)-[:HAS_ENCOUNTER]->(Encounter)`, `(Encounter)-[:NEXT]->(Encounter)`, `(Encounter)-[:HAS_OBSERVATION]->(Observation)`, `(Encounter)-[:DIAGNOSED]->(Condition)`, `(Encounter)-[:PRESCRIBED]->(Drug)`, `(Encounter)-[:ATTENDED_BY]->(Provider)`, `(Provider)-[:HAS_SPECIALITY]->(Speciality)`, `(Provider)-[:BELONGS_TO]->(Organisation)`.
- Full schema, mappings, and sample CSVs are in `GRAPH_MODEL.json` and `sample-data/`; runnable Cypher with expected results is in `QUERIES.md`.

## Operational Constraints

For runnable examples:

- Prefer the bundled `sample-data/` Import flow. Offer any write-based Cypher only after explicit confirmation that database writes are wanted.
- Clarify the intended target database and connection before executing anything.
- `Condition` and `Drug` nodes are shared across patients by standardised code (SNOMED CT / RxNorm); comorbidity queries depend on this. If source data uses local codes, nodes will not merge and cross-patient queries return misleading results.
- `Observation.value` is stored as a string to hold mixed measurement types; cast with `toFloat(o.value)` for numeric comparisons.
- Bound every `NEXT` chain traversal with an explicit maximum depth.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
