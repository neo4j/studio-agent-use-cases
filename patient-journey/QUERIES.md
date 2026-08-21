# Patient Journey — Query Guidance

Cypher for the `patient-journey` use case. Every query references only labels, relationship types, and properties defined in `GRAPH_MODEL.json`. The `//` comments before each query state its purpose, inputs, prerequisites, and the expected result against the bundled `sample-data/` so they act as a lightweight test oracle.

Prerequisites in one place:

- Neo4j 5.x, Cypher 5. No APOC or GDS required.
- The graph is loaded via the bundled sample-data Import (`GRAPH_MODEL.json`).
- KEY constraints from `GRAPH_MODEL.json` ensure `Patient.id`, `Encounter.id`, `Observation.id`, `Condition.code`, `Drug.code`, `Provider.id`, `Speciality.name`, and `Organisation.id` are unique, so every anchored lookup below is an index seek rather than a label scan.

Sample-data profile: 3,000 patients, 5,000 encounters, and 5,000 observations over a fixed vocabulary of 8 conditions, 6 drugs, 4 providers, and 4 organisations. Aggregate/global expected results below are for this seed and scale with the data; per-patient results for the documented sample IDs are stable.

Anchors are **parameters**, never hardcoded IDs. Before running an anchored query, either ask the user which entity they want or offer them a real anchor from query 0 (Available anchors). Do not invent IDs. To test in Neo4j Browser or cypher-shell, set the sample parameters first:

```text
:param patientId     => 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'   // Gerardo Covarrubias
:param conditionCode => '59621000'                               // Hypertension
:param providerId    => 'e2edaa6b-9fea-3a37-8581-df6a8b8f64f5'   // Wilton Pollich
:param limit         => 50                                       // cap for graph/viz results
```

Sections: A — point and tabular queries (0–7); B — graph/visualisation queries (G1–G5), which return nodes, relationships, and paths to render.

## A. Point & tabular queries

### 0. Available anchors

```cypher
// Purpose: enumerate valid anchor values so the agent never has to guess or hardcode one.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 3012 rows — 3000 patients, 8 conditions, 4 providers.
MATCH (p:Patient)
RETURN 'patient' AS Kind, p.id AS Id, p.name AS Label
UNION
MATCH (c:Condition)
RETURN 'condition' AS Kind, c.code AS Id, c.description AS Label
UNION
MATCH (pr:Provider)
RETURN 'provider' AS Kind, pr.id AS Id, pr.name AS Label;
```

### 1. Model sanity check — node counts by label

```cypher
// Purpose: confirm the model loaded and shared nodes merged correctly.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 3000 Patient, 5000 Encounter, 5000 Observation, 8 Condition,
//   6 Drug, 4 Provider, 1 Speciality, 4 Organisation. A Condition count far larger than
//   the number of distinct SNOMED codes means conditions were imported per-row instead of
//   shared — comorbidity queries (4, 5) will then return misleading results.
MATCH (n)
RETURN labels(n)[0] AS Label, count(*) AS Count
ORDER BY Count DESC;
```

### 2. Patient's prescribed drugs

```cypher
// Purpose: first-pass validation that PRESCRIBED relationships exist for a known patient —
//   every drug prescribed to one patient across their journey.
// Inputs: $patientId — ask the user, or offer a patient from query 0 (sample: Gerardo Covarrubias).
// Prerequisites: graph loaded; $patientId set.
// Expected against sample data ($patientId = Gerardo): 1 row with 2 distinct drugs —
//   "Clopidogrel 75 MG Oral Tablet" and "Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray".
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:PRESCRIBED]->(d:Drug)
RETURN p.name AS Name, collect(DISTINCT d.name) AS `Prescribed Drugs`;
```

### 3. Patient's diagnosed conditions

```cypher
// Purpose: validate DIAGNOSED relationships and that SNOMED-coded Condition nodes are populated —
//   all conditions diagnosed across one patient's journey.
// Inputs: $patientId — ask the user, or offer a patient from query 0 (sample: Gerardo Covarrubias).
// Prerequisites: graph loaded; $patientId set.
// Expected against sample data ($patientId = Gerardo): 1 row with 4 distinct conditions —
//   Hypertension, Coronary Heart Disease, Dyspnea (finding), Cough (finding).
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition)
RETURN p.name AS Name, collect(DISTINCT c.description) AS Conditions;
```

### 4. Comorbidities of other patients who share a condition with a given patient

```cypher
// Purpose: core cross-patient pattern — requires Condition nodes to be shared by code.
// Inputs: $patientId — ask the user, or offer a patient from query 0 (sample: Gerardo Covarrubias).
// Prerequisites: graph loaded; $patientId set; the same SNOMED code must appear for >1 patient.
// Expected against sample data ($patientId = Gerardo): population-scale and non-empty. Diabetes
//   mellitus type 2 (44054006) ranks highest (~690 patients on the shipped seed), followed by other
//   conditions co-occurring across everyone who shares one of Gerardo's diagnoses. Exact counts are
//   data-dependent. If this returns zero rows, conditions did not merge on code — check query 1.
MATCH
    (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition),
    (c)<-[:DIAGNOSED]-(:Encounter)<-[:HAS_ENCOUNTER]-(other:Patient)-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE c <> c2
RETURN c2.code AS Code, c2.description AS Description, count(DISTINCT other) AS PatientCount
ORDER BY PatientCount DESC;
```

### 5. Comorbidities associated with a condition

```cypher
// Purpose: condition-centric aggregate for clinical decision support — conditions co-occurring
//   at the same encounter.
// Inputs: $conditionCode — ask the user, or offer a condition from query 0 (sample: 59621000 = Hypertension).
// Prerequisites: graph loaded; $conditionCode set.
// Expected against sample data ($conditionCode = 59621000): 7 co-occurring conditions, led by
//   Diabetes mellitus type 2 (44054006, ~537 occurrences on the shipped seed), then Cough (finding)
//   and Coronary Heart Disease. Ordered by Occurrences DESC; exact counts are data-dependent.
MATCH (c1:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE c1 <> c2
RETURN c2.code AS Code, c2.description AS Description, count(*) AS Occurrences
ORDER BY Occurrences DESC;
```

### 6. Provider workload

```cypher
// Purpose: pivot to the provider dimension for resource-allocation and care-coordination analysis —
//   which patients a provider has seen and how often.
// Inputs: $providerId — ask the user, or offer a provider from query 0 (sample: Wilton Pollich).
// Prerequisites: graph loaded; $providerId set.
// Expected against sample data ($providerId = Wilton Pollich): many rows — on the shipped seed this
//   provider sees ~1,125 patients across ~1,276 encounters, ordered by encounter count DESC (up to
//   4 per patient). Exact counts are data-dependent.
MATCH (p:Provider {id: $providerId})<-[:ATTENDED_BY]-(:Encounter)<-[:HAS_ENCOUNTER]-(pt:Patient)
RETURN pt.id AS PatientId, pt.name AS `Patient Name`, count(*) AS Encounters
ORDER BY Encounters DESC;
```

### 7. Single-patient chronological pathway via the NEXT chain

```cypher
// Purpose: reconstruct a patient's encounters in order; demonstrates bounded NEXT traversal.
// Inputs: $patientId — ask the user, or offer a patient from query 0 (sample: Gerardo Covarrubias).
//   The *0..200 bound caps chain length in production.
// Prerequisites: graph loaded; $patientId set; NEXT edges built in date order at import time.
//   Encounter.date is ZONED DATETIME, so wrap it in toString() before concatenating.
// Expected against sample data ($patientId = Gerardo): 1 row — a 3-element pathway in date order:
//   2005-05-26T00:00:00Z (wellness), 2020-08-05T00:00:00Z (ambulatory), 2022-09-01T00:00:00Z (wellness).
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(head:Encounter)
WHERE NOT (:Encounter)-[:NEXT]->(head)
MATCH path = (head)-[:NEXT*0..200]->(tail:Encounter)
WHERE NOT (tail)-[:NEXT]->(:Encounter)
RETURN [enc IN nodes(path) | toString(enc.date) + ' (' + enc.type + ')'] AS Pathway;
```

## B. Graph / visualisation queries

These return nodes, relationships, and paths so Neo4j Browser or Bloom draws a graph rather than a table. Keep viz result sets bounded with `$limit`.

### G1. Patient journey subgraph

```cypher
// Purpose: visualise everything connected to a patient: their encounters, the NEXT chain between
//   them, and each encounter's observations, conditions, drugs, and attending provider.
// Inputs: $patientId — ask the user, or offer a patient from query 0 (sample: Gerardo Covarrubias).
// Prerequisites: graph loaded; $patientId set.
// Expected against sample data ($patientId = Gerardo): a connected subgraph of 1 Patient,
//   3 Encounters (with 2 NEXT edges), 9 Observations, the conditions Hypertension / Coronary Heart
//   Disease / Dyspnea / Cough, the drugs Clopidogrel / Nitroglycerin, and provider Sondra Botsford.
MATCH (pat:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter)
OPTIONAL MATCH (e)-[r:HAS_OBSERVATION|DIAGNOSED|PRESCRIBED|ATTENDED_BY|NEXT]->(x)
RETURN pat, e, r, x;
```

### G2. Shared-condition patient cluster

```cypher
// Purpose: visualise the cohort of patients who share a diagnosis, clustered around the Condition
//   node. This is the clinical analogue of an entity-resolution "ring" view.
// Inputs: $conditionCode — ask the user, or offer a condition from query 0 (sample: 59621000 = Hypertension).
// Prerequisites: graph loaded; $conditionCode set; the code must be shared by >1 patient to cluster.
// Expected against sample data ($conditionCode = 59621000): Hypertension is shared by ~1,600
//   patients, so this returns a large cluster of patient pairs linked through the condition node —
//   capped at $limit paths for a readable graph. Raise $limit or pick a rarer code for the full set.
MATCH path = (p1:Patient)-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)<-[:HAS_ENCOUNTER]-(p2:Patient)
WHERE elementId(p1) < elementId(p2)
RETURN path
LIMIT $limit;
```

### G3. Comorbidity network

```cypher
// Purpose: population-level visualisation of which conditions co-occur, connected through the
//   encounters where both were diagnosed. Higher-degree condition nodes are the common comorbidities.
// Inputs: $limit (default 50) — cap on returned paths for a readable graph.
// Prerequisites: graph loaded.
// Expected against sample data: the comorbidity network across the population — Diabetes type 2 --
//   Hypertension is the heaviest pairing, alongside Coronary Heart Disease -- Hypertension, Cough --
//   Dyspnea, Metabolic syndrome X -- Hypertriglyceridemia, and others. Returned via the connecting
//   encounters and capped at $limit paths; raise $limit to see more of the network.
MATCH path = (c1:Condition)<-[:DIAGNOSED]-(:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE elementId(c1) < elementId(c2)
RETURN path
LIMIT $limit;
```

### G4. Care network around a condition

```cypher
// Purpose: visualise the delivery network for a diagnosis: Condition -> Encounters ->
//   attending Providers -> their Organisations.
// Inputs: $conditionCode — ask the user, or offer a condition from query 0 (sample: 59621000 = Hypertension).
// Prerequisites: graph loaded; $conditionCode set.
// Expected against sample data ($conditionCode = 59621000): the Hypertension node connected out
//   through many encounters to all 4 providers (Sondra Botsford, Wilton Pollich, Martha Ledner,
//   Lyle Dibbert) and their organisations (VA Boston, Milford Regional, PCP9022, PCP1477).
//   Capped at $limit paths for a readable graph.
MATCH path = (c:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)-[:ATTENDED_BY]->(:Provider)-[:BELONGS_TO]->(:Organisation)
RETURN path
LIMIT $limit;
```

### G5. Drug co-prescription network

```cypher
// Purpose: population-level visualisation of medications that co-occur on a prescription,
//   connected through the encounters where they were prescribed together.
// Inputs: $limit (default 50) — cap on returned paths for a readable graph.
// Prerequisites: graph loaded.
// Expected against sample data: the co-prescription network — the strongest pairings are
//   Insulin isophane -- Lisinopril, Acetaminophen -- Hydrochlorothiazide, and
//   Clopidogrel -- Nitroglycerin (drugs that share a condition indication). Returned via the
//   connecting encounters and capped at $limit paths.
MATCH path = (d1:Drug)<-[:PRESCRIBED]-(:Encounter)-[:PRESCRIBED]->(d2:Drug)
WHERE elementId(d1) < elementId(d2)
RETURN path
LIMIT $limit;
```

## Constraints

The node-key constraints below are created automatically when the sample data is loaded via the Import app from `GRAPH_MODEL.json`, which is the only route data takes into the graph. They are listed here as a schema reference and to verify what the import produced:

```cypher
// Node-key constraints matching GRAPH_MODEL.json.
CREATE CONSTRAINT id_Patient_key IF NOT EXISTS
  FOR (p:Patient) REQUIRE p.id IS NODE KEY;
CREATE CONSTRAINT id_Encounter_key IF NOT EXISTS
  FOR (e:Encounter) REQUIRE e.id IS NODE KEY;
CREATE CONSTRAINT id_Observation_key IF NOT EXISTS
  FOR (o:Observation) REQUIRE o.id IS NODE KEY;
CREATE CONSTRAINT code_Condition_key IF NOT EXISTS
  FOR (c:Condition) REQUIRE c.code IS NODE KEY;
CREATE CONSTRAINT code_Drug_key IF NOT EXISTS
  FOR (d:Drug) REQUIRE d.code IS NODE KEY;
CREATE CONSTRAINT id_Provider_key IF NOT EXISTS
  FOR (pr:Provider) REQUIRE pr.id IS NODE KEY;
CREATE CONSTRAINT name_Speciality_key IF NOT EXISTS
  FOR (s:Speciality) REQUIRE s.name IS NODE KEY;
CREATE CONSTRAINT id_Organisation_key IF NOT EXISTS
  FOR (org:Organisation) REQUIRE org.id IS NODE KEY;
```
