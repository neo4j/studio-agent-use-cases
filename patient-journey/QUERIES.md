# Patient Journey — Query Guidance

Cypher for the `patient-journey` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database.

## Prerequisites

- Neo4j 5.x, Cypher 5. No APOC or GDS required.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology.
- The node keys in `ONTOLOGY.json` make `Patient.id`, `Encounter.id`, `Observation.id`, `Condition.code`, `Drug.code`, `Provider.id`, `Speciality.name`, and `Organisation.id` unique, so every anchored lookup below is an index seek rather than a label scan.
- Anchors are parameters, never hardcoded IDs. Before running an anchored query, ask the user which entity they want or offer a real one from **Available anchors**. Do not invent IDs.
- Queries are listed point and tabular first, then the graph and visualisation queries, which return nodes, relationships, and paths for Neo4j Browser or Bloom to draw. Keep visualisation results bounded with `$limit`.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Available anchors

```cypher
/*
 * @name           Available anchors
 * @description    Enumerates the valid anchor values for the parameterised
 *                 queries — every patient, condition and provider — so the
 *                 agent never has to guess or hardcode an ID.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per Patient, Condition and Provider: Kind
 *                 ('patient', 'condition' or 'provider'), Id (the node key —
 *                 Patient.id, Condition.code or Provider.id) and Label (the
 *                 display name or condition description).
 * @usage          Run before any anchored query when the user has not named
 *                 an entity, and offer them a few real anchors to choose
 *                 from. On a large population, filter or page the patient
 *                 rows rather than showing them all.
 * @tags           anchors, orientation, patient, condition, provider
 * @sample         Bundled sample data only: returns 3012 rows — 3000
 *                 patients, 8 conditions and 4 providers.
 */
MATCH (p:Patient)
RETURN 'patient' AS Kind, p.id AS Id, p.name AS Label
UNION
MATCH (c:Condition)
RETURN 'condition' AS Kind, c.code AS Id, c.description AS Label
UNION
MATCH (pr:Provider)
RETURN 'provider' AS Kind, pr.id AS Id, pr.name AS Label;
```

## Reference ontology sanity check — node counts by label

```cypher
/*
 * @name           Reference ontology sanity check — node counts by label
 * @description    Counts nodes per label to confirm the import loaded and
 *                 that shared Condition and Drug nodes merged on their
 *                 standardised codes.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per label: Label and Count, ordered by Count
 *                 descending.
 * @usage          Run straight after an import. Condition and Drug counts
 *                 should be close to the number of distinct codes in the
 *                 source; a Condition count far larger than that means
 *                 conditions were imported per row instead of shared, and
 *                 the comorbidity queries will then return misleading
 *                 results.
 * @tags           sanity-check, import, orientation
 * @sample         Bundled sample data only: returns 8 rows — 5000
 *                 Encounter, 5000 Observation, 3000 Patient, 8 Condition,
 *                 6 Drug, 4 Provider, 4 Organisation, 1 Speciality.
 */
MATCH (n)
RETURN labels(n)[0] AS Label, count(*) AS Count
ORDER BY Count DESC;
```

## Patient's prescribed drugs

```cypher
/*
 * @name           Patient's prescribed drugs
 * @description    Every drug prescribed to one patient across all of their
 *                 encounters, following HAS_ENCOUNTER then PRESCRIBED. Also a
 *                 first-pass check that PRESCRIBED relationships exist.
 * @params         patientId - Patient.id of the patient. Ask the user, or
 *                     offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: Name (the patient's display name) and
 *                 `Prescribed Drugs` (distinct Drug.name values). No row
 *                 when the patient has no prescriptions.
 * @usage          Use for a single patient's medication history. Drug.name
 *                 conventionally includes strength and form, so different
 *                 strengths of one medication appear as separate entries.
 * @tags           patient, drug, prescription
 * @sample         Bundled sample data only: $patientId =
 *                 'fd65a941-3fa1-337f-28e2-6c9d3922c1af' (Gerardo
 *                 Covarrubias) returns 1 row with 2 drugs — Clopidogrel 75
 *                 MG Oral Tablet, Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray.
 */
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:PRESCRIBED]->(d:Drug)
RETURN p.name AS Name, collect(DISTINCT d.name) AS `Prescribed Drugs`;
```

## Patient's diagnosed conditions

```cypher
/*
 * @name           Patient's diagnosed conditions
 * @description    Every condition diagnosed across one patient's
 *                 encounters, following HAS_ENCOUNTER then DIAGNOSED. Also
 *                 checks that coded Condition nodes are populated.
 * @params         patientId - Patient.id of the patient. Ask the user, or
 *                     offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: Name (the patient's display name) and Conditions
 *                 (distinct Condition.description values). No row when the
 *                 patient has no diagnoses.
 * @usage          Use for a single patient's problem list across their
 *                 journey. Return Condition.code as well when the result
 *                 will be compared across systems.
 * @tags           patient, condition, diagnosis
 * @sample         Bundled sample data only: $patientId =
 *                 'fd65a941-3fa1-337f-28e2-6c9d3922c1af' (Gerardo
 *                 Covarrubias) returns 1 row with 4 conditions —
 *                 Hypertension, Coronary Heart Disease, Dyspnea (finding),
 *                 Cough (finding).
 */
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition)
RETURN p.name AS Name, collect(DISTINCT c.description) AS Conditions;
```

## Comorbidities of other patients who share a condition with a given patient

```cypher
/*
 * @name           Comorbidities of other patients who share a condition with a given patient
 * @description    The core cross-patient pattern: from one patient's
 *                 diagnosed conditions, step out through the shared
 *                 Condition node to every other patient diagnosed with it,
 *                 then count the other conditions those patients have.
 * @params         patientId - Patient.id of the anchor patient. Ask the
 *                     user, or offer one from Available anchors.
 * @prerequisites  Condition nodes shared across patients by standardised
 *                 code; the same code must appear for more than one patient.
 * @returns        One row per co-occurring condition: Code, Description and
 *                 PatientCount (distinct other patients — the anchor patient
 *                 excluded — who share one of the anchor's conditions and
 *                 also have this one), ordered by PatientCount descending.
 * @usage          Population-scale: the result grows with the number of
 *                 patients who share a common condition, so add a LIMIT when
 *                 presenting it. A condition shared with the anchor can
 *                 itself appear in the result, reached through another
 *                 shared condition. An empty result usually means Condition
 *                 nodes did not merge on code — run the sanity check.
 * @tags           comorbidity, cohort, condition, population
 * @sample         Bundled sample data only: $patientId =
 *                 'fd65a941-3fa1-337f-28e2-6c9d3922c1af' (Gerardo
 *                 Covarrubias) returns 8 rows, led by Diabetes mellitus
 *                 type 2 (disorder) (44054006) with 692 patients, then
 *                 Hypertension with 541.
 */
MATCH
    (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition),
    (c)<-[:DIAGNOSED]-(:Encounter)<-[:HAS_ENCOUNTER]-(other:Patient)-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE c <> c2 AND other <> p
RETURN c2.code AS Code, c2.description AS Description, count(DISTINCT other) AS PatientCount
ORDER BY PatientCount DESC;
```

## Comorbidities associated with a condition

```cypher
/*
 * @name           Comorbidities associated with a condition
 * @description    Condition-centric aggregate: the conditions diagnosed at
 *                 the same encounter as a given condition, and how often.
 * @params         conditionCode - Condition.code of the condition, in the
 *                     standardised clinical terminology the data uses. Ask
 *                     the user, or offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per co-diagnosed condition: Code, Description and
 *                 Occurrences (encounters at which both were diagnosed),
 *                 ordered by Occurrences descending.
 * @usage          Same-encounter co-occurrence, not same-patient: two
 *                 conditions diagnosed for one patient at different
 *                 encounters are not counted. For lifetime comorbidity, use
 *                 the patient-anchored comorbidity query instead.
 * @tags           comorbidity, condition, decision-support
 * @sample         Bundled sample data only: $conditionCode = '59621000'
 *                 (Hypertension) returns 7 rows, led by Diabetes mellitus
 *                 type 2 (disorder) with 537 occurrences, then Cough
 *                 (finding) with 225 and Coronary Heart Disease with 190.
 */
MATCH (c1:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE c1 <> c2
RETURN c2.code AS Code, c2.description AS Description, count(*) AS Occurrences
ORDER BY Occurrences DESC;
```

## Provider workload

```cypher
/*
 * @name           Provider workload
 * @description    Pivots to the provider dimension: which patients a
 *                 provider has seen, and at how many encounters, following
 *                 ATTENDED_BY (Encounter → Provider) and HAS_ENCOUNTER back
 *                 to the patient.
 * @params         providerId - Provider.id of the provider. Ask the user, or
 *                     offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per patient seen: PatientId, `Patient Name` and
 *                 Encounters (encounters this provider attended for that
 *                 patient), ordered by Encounters descending.
 * @usage          For resource-allocation and care-coordination analysis.
 *                 Returns one row per patient, so a busy provider produces
 *                 a long result — summarise it or add a LIMIT when
 *                 presenting.
 * @tags           provider, workload, care-delivery
 * @sample         Bundled sample data only: $providerId =
 *                 'e2edaa6b-9fea-3a37-8581-df6a8b8f64f5' (Wilton Pollich)
 *                 returns 1125 rows covering 1276 encounters, at most 4
 *                 encounters per patient.
 */
MATCH (p:Provider {id: $providerId})<-[:ATTENDED_BY]-(:Encounter)<-[:HAS_ENCOUNTER]-(pt:Patient)
RETURN pt.id AS PatientId, pt.name AS `Patient Name`, count(*) AS Encounters
ORDER BY Encounters DESC;
```

## Single-patient chronological pathway via the NEXT chain

```cypher
/*
 * @name           Single-patient chronological pathway via the NEXT chain
 * @description    Reconstructs one patient's encounters in date order by
 *                 walking the NEXT chain from its first encounter (no
 *                 incoming NEXT) to its last (no outgoing NEXT).
 * @params         patientId - Patient.id of the patient. Ask the user, or
 *                     offer one from Available anchors.
 * @prerequisites  NEXT relationships loaded in date order. Encounter.date is
 *                 a ZONED DATETIME, so the query wraps it in toString()
 *                 before concatenating.
 * @returns        One row per chain: Pathway, a list of
 *                 '<Encounter.date> (<Encounter.type>)' strings in date
 *                 order. A patient whose encounters are fully chained
 *                 returns exactly one row.
 * @usage          The traversal bound *0..200 is a literal that caps chain
 *                 length; raise it only for populations with very long
 *                 histories. Not every encounter is guaranteed to be
 *                 chained, so more than one row means the patient's chain
 *                 has gaps — each row is one unbroken segment.
 * @tags           pathway, patient, encounter, sequence
 * @sample         Bundled sample data only: $patientId =
 *                 'fd65a941-3fa1-337f-28e2-6c9d3922c1af' (Gerardo
 *                 Covarrubias) returns 1 row with 3 entries —
 *                 2005-05-26T00:00:00Z (wellness), 2020-08-05T00:00:00Z
 *                 (ambulatory), 2022-09-01T00:00:00Z (wellness).
 */
MATCH (p:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(head:Encounter)
WHERE NOT (:Encounter)-[:NEXT]->(head)
MATCH path = (head)-[:NEXT*0..200]->(tail:Encounter)
WHERE NOT (tail)-[:NEXT]->(:Encounter)
RETURN [enc IN nodes(path) | toString(enc.date) + ' (' + enc.type + ')'] AS Pathway;
```

## Patient journey subgraph

```cypher
/*
 * @name           Patient journey subgraph
 * @description    Visualises everything connected to one patient: their
 *                 encounters, the NEXT chain between them, and each
 *                 encounter's observations, diagnosed conditions,
 *                 prescribed drugs and attending provider.
 * @params         patientId - Patient.id of the patient. Ask the user, or
 *                     offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Rows of pat (Patient), e (Encounter), r (an outgoing
 *                 HAS_OBSERVATION, DIAGNOSED, PRESCRIBED, ATTENDED_BY or
 *                 NEXT relationship) and x (its target node), for Browser
 *                 or Bloom to draw as one connected subgraph.
 * @usage          Visual, not tabular — for a text answer use the pathway,
 *                 drug and condition queries instead. Size grows with the
 *                 patient's number of encounters and observations.
 * @tags           visualisation, patient, journey, subgraph
 * @sample         Bundled sample data only: $patientId =
 *                 'fd65a941-3fa1-337f-28e2-6c9d3922c1af' (Gerardo
 *                 Covarrubias) draws 1 patient, 3 encounters with 2 NEXT
 *                 links, 9 observations, 4 conditions, 2 drugs and 1
 *                 provider (Sondra Botsford).
 */
MATCH (pat:Patient {id: $patientId})-[:HAS_ENCOUNTER]->(e:Encounter)
OPTIONAL MATCH (e)-[r:HAS_OBSERVATION|DIAGNOSED|PRESCRIBED|ATTENDED_BY|NEXT]->(x)
RETURN pat, e, r, x;
```

## Shared-condition patient cluster

```cypher
/*
 * @name           Shared-condition patient cluster
 * @description    Visualises the cohort of patients who share a diagnosis,
 *                 clustered around the Condition node — the clinical
 *                 analogue of an entity-resolution "ring" view.
 * @params         conditionCode - Condition.code of the condition. Ask the
 *                     user, or offer one from Available anchors.
 *                 limit - Maximum number of patient-pair paths returned.
 *                     Start at 50 for a readable graph; raise it only as far
 *                     as the picture stays legible.
 * @prerequisites  The code must be shared by more than one patient to form
 *                 a cluster.
 * @returns        Paths Patient → Encounter → Condition ← Encounter ←
 *                 Patient, one per patient pair (each pair once), at most
 *                 $limit of them.
 * @usage          A common condition yields far more pairs than any limit
 *                 shows, and LIMIT without ordering picks an arbitrary
 *                 subset — treat the picture as an illustration of the
 *                 cluster, not its membership. Pick a rarer code to see a
 *                 whole cohort.
 * @tags           visualisation, cohort, condition, cluster
 * @sample         Bundled sample data only: $conditionCode = '59621000'
 *                 (Hypertension), $limit = 50 returns 50 paths drawn from
 *                 the 1615 patients diagnosed with it.
 */
MATCH path = (p1:Patient)-[:HAS_ENCOUNTER]->(:Encounter)-[:DIAGNOSED]->(c:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)<-[:HAS_ENCOUNTER]-(p2:Patient)
WHERE elementId(p1) < elementId(p2)
RETURN path
LIMIT $limit;
```

## Comorbidity network

```cypher
/*
 * @name           Comorbidity network
 * @description    Population-level visualisation of which conditions are
 *                 diagnosed together at the same encounter. Ranks condition
 *                 pairs by how many encounters diagnosed both, keeps the
 *                 strongest, and draws one connecting encounter per pair
 *                 with the pair's weight.
 * @params         limit - Maximum number of condition pairs returned,
 *                     strongest first. Start at 50 for a readable graph;
 *                     lower it to see only the dominant comorbidities.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per condition pair: path (Condition ← Encounter →
 *                 Condition, through one representative encounter) and
 *                 coOccurrences (encounters at which both were diagnosed),
 *                 ordered by coOccurrences descending.
 * @usage          Same-encounter co-occurrence. The drawn encounter is an
 *                 example only; the weight is in coOccurrences. Each pair is
 *                 counted once. Aggregates every co-diagnosis in the
 *                 database, so on a large population expect it to take
 *                 longer than the anchored queries.
 * @tags           visualisation, comorbidity, condition, population
 * @sample         Bundled sample data only: $limit = 50 returns all 28
 *                 condition pairs, led by Diabetes mellitus type 2
 *                 (disorder) – Hypertension with 537, then Cough (finding)
 *                 – Hypertension with 225.
 */
MATCH (c1:Condition)<-[:DIAGNOSED]-(e:Encounter)-[:DIAGNOSED]->(c2:Condition)
WHERE elementId(c1) < elementId(c2)
WITH c1, c2, count(e) AS coOccurrences, head(collect(e)) AS example
ORDER BY coOccurrences DESC
LIMIT $limit
MATCH path = (c1)<-[:DIAGNOSED]-(example)-[:DIAGNOSED]->(c2)
RETURN path, coOccurrences
ORDER BY coOccurrences DESC;
```

## Care network around a condition

```cypher
/*
 * @name           Care network around a condition
 * @description    Visualises the delivery network for a diagnosis:
 *                 Condition ← Encounter (DIAGNOSED) → Provider (ATTENDED_BY)
 *                 → Organisation (BELONGS_TO).
 * @params         conditionCode - Condition.code of the condition. Ask the
 *                     user, or offer one from Available anchors.
 *                 limit - Maximum number of paths returned. Start at 50 for
 *                     a readable graph; raise it until every provider of
 *                     interest appears.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths Condition ← Encounter → Provider → Organisation, at
 *                 most $limit of them.
 * @usage          One path per encounter, so a common condition needs a
 *                 high limit before every provider appears; LIMIT without
 *                 ordering picks an arbitrary subset of encounters. For
 *                 counts per provider, aggregate rather than draw.
 * @tags           visualisation, care-delivery, provider, organisation, condition
 * @sample         Bundled sample data only: $conditionCode = '59621000'
 *                 (Hypertension), $limit = 50 returns 50 of 2395 possible
 *                 paths; all 4 providers and their 4 organisations treat
 *                 it.
 */
MATCH path = (c:Condition {code: $conditionCode})<-[:DIAGNOSED]-(:Encounter)-[:ATTENDED_BY]->(:Provider)-[:BELONGS_TO]->(:Organisation)
RETURN path
LIMIT $limit;
```

## Drug co-prescription network

```cypher
/*
 * @name           Drug co-prescription network
 * @description    Population-level visualisation of medications prescribed
 *                 together at the same encounter. Ranks drug pairs by how
 *                 many encounters prescribed both, keeps the strongest, and
 *                 draws one connecting encounter per pair with the pair's
 *                 weight.
 * @params         limit - Maximum number of drug pairs returned, strongest
 *                     first. Start at 50 for a readable graph; lower it to
 *                     see only the dominant pairings.
 * @prerequisites  Drug nodes shared across patients by standardised code.
 * @returns        One row per drug pair: path (Drug ← Encounter → Drug,
 *                 through one representative encounter) and
 *                 coPrescriptions (encounters at which both were
 *                 prescribed), ordered by coPrescriptions descending.
 * @usage          Same-encounter co-prescription. Drug nodes are one per
 *                 code, and codes conventionally distinguish strength and
 *                 form, so two strengths of one medication count as
 *                 different drugs. The drawn encounter is an example only.
 *                 Pairs that recur usually share an indication — a lead for
 *                 review, not a safety finding.
 * @tags           visualisation, drug, co-prescription, population
 * @sample         Bundled sample data only: $limit = 50 returns all 15 drug
 *                 pairs, led by Hydrochlorothiazide 25 MG Oral Tablet –
 *                 Lisinopril 10 MG Oral Tablet with 1155.
 */
MATCH (d1:Drug)<-[:PRESCRIBED]-(e:Encounter)-[:PRESCRIBED]->(d2:Drug)
WHERE elementId(d1) < elementId(d2)
WITH d1, d2, count(e) AS coPrescriptions, head(collect(e)) AS example
ORDER BY coPrescriptions DESC
LIMIT $limit
MATCH path = (d1)<-[:PRESCRIBED]-(example)-[:PRESCRIBED]->(d2)
RETURN path, coPrescriptions
ORDER BY coPrescriptions DESC;
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
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
