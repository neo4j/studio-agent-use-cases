---
name: patient-journey
description: Model and analyze patient journeys through a healthcare system with Neo4j — longitudinal care pathways, comorbidity, treatment-pattern queries across patients, encounters, diagnoses, and more.
metadata:
  neo4j-card-title: Patient Journey
  neo4j-card-category: Healthcare & Life Sciences
  neo4j-card-description: Map longitudinal care pathways and discover comorbidities across a connected clinical graph.
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
- What you can help with: explaining the reference ontology, walking through the query patterns from a single patient to population-level comorbidity analysis, importing the sample data or mapping their own EHR, FHIR, or OMOP data onto the reference ontology, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Nodes: `Patient {id, name, birthDate}`, `Encounter {id, date, type}`, `Observation {id, code, description, value, units}`, `Condition {code, description}`, `Drug {code, name}`, `Provider {id, name}`, `Speciality {name}`, `Organisation {id, name, address}`.
- Relationships: `(Patient)-[:HAS_ENCOUNTER]->(Encounter)`, `(Encounter)-[:NEXT]->(Encounter)`, `(Encounter)-[:HAS_OBSERVATION]->(Observation)`, `(Encounter)-[:DIAGNOSED]->(Condition)`, `(Encounter)-[:PRESCRIBED]->(Drug)`, `(Encounter)-[:ATTENDED_BY]->(Provider)`, `(Provider)-[:HAS_SPECIALITY]->(Speciality)`, `(Provider)-[:BELONGS_TO]->(Organisation)`.
- Nothing clinical attaches to a patient directly: observations, diagnoses, prescriptions and the attending provider all hang off the `Encounter`, which gives every fact a date and a context. `Condition` and `Drug` are shared — one node per standardised code — so patients meet at them, and that meeting is the comorbidity and co-prescription signal.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases` and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Person` or `Visit` often names the user's equivalent label), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Subject of care | `Patient` | A stable key, reaching every clinical fact only through care episodes |
| Care episode | `Encounter` | A date, a link to exactly one subject, and — for pathways — an explicit successor link in date order |
| Shared clinical concept | `Condition`, `Drug` | One node per standardised code that many episodes point at; local or per-row codes break every cross-patient pattern |
| Episode measurement | `Observation` | A node owned by exactly one episode, carrying a code, a value and a unit |
| Care deliverer | `Provider` | Exactly one per episode, so workload and delivery can be counted |
| Delivery context | `Speciality`, `Organisation` | A grouping above the deliverer that providers converge on |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.x and Cypher 5; no APOC or GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of the `@sample` anchor (for example its `$patientId`) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Anchor on node keys (`Patient.id`, `Condition.code`, `Drug.code`, `Provider.id`), never on names or descriptions — names are not unique and are not indexed. Offer real anchors from the **Available anchors** query rather than inventing IDs.
- `Condition` and `Drug` nodes are shared across patients by standardised code (SNOMED CT / RxNorm in the sample); comorbidity and co-prescription queries depend on this. If source data uses local codes, nodes will not merge and cross-patient queries silently under-count.
- `Observation.value` is stored as a string to hold mixed measurement types; cast with `toFloat(o.value)` for numeric comparisons, and read the unit from `Observation.units`.
- Bound every `NEXT` chain traversal with an explicit maximum depth.
- Distinguish same-encounter co-occurrence (the condition-anchored and network queries) from same-patient co-occurrence (the patient-anchored comorbidity query) whenever you report a comorbidity.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
