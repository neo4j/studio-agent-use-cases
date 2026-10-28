# Patient Journey — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j 5.x database — the import writes the whole sample.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. No `SETUP.md` statements are needed.
4. Run each query in `QUERIES.md` with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second.

## Sample-data profile

Synthetic data generated with Synthea (Massachusetts, seed 100) and reduced to a fixed vocabulary, so cross-patient patterns are dense.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Patient` | 3000 | 1527 with one encounter, 1037 with 2, 355 with 3, 71 with 4, 10 with 5 |
| `Encounter` | 5000 | Dated 2005-01-01 to 2024-12-31. Types: ambulatory 1033, inpatient 1029, wellness 998, outpatient 990, emergency 950 |
| `Observation` | 5000 | Three LOINC codes only: Body Weight (29463-7, kg) 1671, Systolic Blood Pressure (8480-6, mm[Hg]) 1667, Diastolic Blood Pressure (8462-4, mm[Hg]) 1662. Values are numeric strings |
| `Condition` | 8 | SNOMED CT codes, listed below |
| `Drug` | 6 | RxNorm codes, listed below |
| `Provider` | 4 | Sondra Botsford, Wilton Pollich, Martha Ledner, Lyle Dibbert — all General Practice |
| `Speciality` | 1 | General Practice |
| `Organisation` | 4 | VA Boston Healthcare System, Milford Regional Medical Center, PCP9022, PCP1477 — one per provider |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `HAS_ENCOUNTER` | 5000 | One per encounter |
| `NEXT` | 2000 | Every patient with more than one encounter is fully chained, in date order; no chain has gaps |
| `HAS_OBSERVATION` | 5000 | On 3147 encounters, 1–5 each |
| `DIAGNOSED` | 7256 | Every encounter diagnoses 1–4 conditions; no duplicate encounter–condition pairs |
| `PRESCRIBED` | 7130 | On 4356 encounters, 1–5 each; no duplicate encounter–drug pairs |
| `ATTENDED_BY` | 5000 | Wilton Pollich 1276, Lyle Dibbert 1272, Martha Ledner 1228, Sondra Botsford 1224 |
| `HAS_SPECIALITY` | 4 | |
| `BELONGS_TO` | 4 | |

**Conditions** — `DIAGNOSED` rows / distinct patients: Hypertension (59621000) 2395 / 1615; Diabetes mellitus type 2 (disorder) (44054006) 1705 / 1149; Coronary Heart Disease (53741008) 665 / 454; Cough (finding) (49727002) 593 / 457; Dyspnea (finding) (267036007) 556 / 434; Hypertriglyceridemia (disorder) (302870006) 544 / 366; Metabolic syndrome X (disorder) (237602007) 488 / 329; Familial Alzheimer's disease of early onset (disorder) (230265002) 310 / 215. Patients carry 1–5 distinct conditions.

**Drugs** — `PRESCRIBED` rows: Lisinopril 10 MG Oral Tablet (314076) 1672; Hydrochlorothiazide 25 MG Oral Tablet (310798) 1662; Acetaminophen 325 MG Oral Tablet (209387) 1624; Insulin isophane 70 UNT/ML (106892) 1223; Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray (705129) 489; Clopidogrel 75 MG Oral Tablet (309362) 460.

**Signals.** The data is not seeded with a single planted pattern; the signal is the shared vocabulary. Every condition and drug is shared by hundreds of patients, so every cross-patient query has a dense, non-empty result. Hypertension is the hub condition and co-occurs with every other condition at encounter level; Hydrochlorothiazide–Lisinopril is the dominant co-prescription.

**Reference anchors.** Used throughout:

- Patient Gerardo Covarrubias, `fd65a941-3fa1-337f-28e2-6c9d3922c1af`: 3 encounters, all attended by Sondra Botsford — 2005-05-26 wellness, 2020-08-05 ambulatory, 2022-09-01 wellness — chained by 2 `NEXT` links, with 9 observations (3 each of systolic, diastolic and body weight). Conditions: Hypertension, Coronary Heart Disease, Dyspnea (finding), Cough (finding). Drugs: Clopidogrel, Nitroglycerin.
- Condition Hypertension, `59621000`.
- Provider Wilton Pollich, `e2edaa6b-9fea-3a37-8581-df6a8b8f64f5`.

**Editing notes.**

- The legacy expected-results comments for the comorbidity network and the drug co-prescription network were inaccurate. They named Cough–Dyspnea and Metabolic syndrome X–Hypertriglyceridemia as heavy pairings (actual 38 and 17, near the bottom), and Insulin isophane–Lisinopril as the strongest co-prescription (actual 264, fifth). The values below are recomputed from the CSVs.
- Three queries changed in the migration to the current package format. The patient-anchored comorbidity query now excludes the anchor patient from "other", which takes 1 off each of the anchor's own conditions. The comorbidity network and the drug co-prescription network now rank pairs by weight before applying `$limit`. Before, they returned an arbitrary `$limit` paths.
- `$limit = 50` on the visualisation queries is a readability cap, not a value tuned to this data.

## Available anchors

- **Parameters:** none.
- **Invariant:** one row per `Patient`, `Condition` and `Provider` node, and nothing else; `Kind` takes only the values `patient`, `condition`, `provider`.
- **Expected:** 3012 rows — 3000 `patient`, 8 `condition`, 4 `provider`.

## Reference ontology sanity check — node counts by label

- **Parameters:** none.
- **Invariant:** one row per label in the reference ontology. `Condition` and `Drug` counts equal the number of distinct codes in `conditions.csv` and `drugs.csv`, which proves the shared nodes merged on code.
- **Expected:** 8 rows — Encounter 5000, Observation 5000, Patient 3000, Condition 8, Drug 6, Provider 4, Organisation 4, Speciality 1. Encounter and Observation tie, so their order is not fixed.

## Patient's prescribed drugs

- **Parameters:** `$patientId = 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'` (Gerardo Covarrubias).
- **Invariant:** one row whose list holds exactly the distinct drugs on `drugs.csv` rows for the patient's encounters.
- **Expected:** 1 row, Name `Gerardo Covarrubias`, 2 drugs — Clopidogrel 75 MG Oral Tablet, Nitroglycerin 0.4 MG/ACTUAT Mucosal Spray.

## Patient's diagnosed conditions

- **Parameters:** `$patientId = 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'` (Gerardo Covarrubias).
- **Invariant:** one row whose list holds exactly the distinct conditions on `conditions.csv` rows for the patient's encounters.
- **Expected:** 1 row, Name `Gerardo Covarrubias`, 4 conditions — Hypertension, Coronary Heart Disease, Dyspnea (finding), Cough (finding).

## Comorbidities of other patients who share a condition with a given patient

- **Parameters:** `$patientId = 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'` (Gerardo Covarrubias).
- **Invariant:** non-empty. Each PatientCount counts distinct patients other than the anchor who share at least one of the anchor's conditions and also have the row's condition through a different shared condition. The anchor patient never contributes. The result is ordered by PatientCount descending.
- **Expected:** 8 rows (2265 other patients share at least one of Gerardo's conditions):

  | Code | Description | PatientCount |
  | ---- | ----------- | ------------ |
  | 44054006 | Diabetes mellitus type 2 (disorder) | 692 |
  | 59621000 | Hypertension | 541 |
  | 49727002 | Cough (finding) | 288 |
  | 53741008 | Coronary Heart Disease | 247 |
  | 267036007 | Dyspnea (finding) | 247 |
  | 302870006 | Hypertriglyceridemia (disorder) | 202 |
  | 237602007 | Metabolic syndrome X (disorder) | 184 |
  | 230265002 | Familial Alzheimer's disease of early onset (disorder) | 103 |

- **Sensitivity:** before the `other <> p` fix, the four conditions Gerardo has were each 1 higher (Hypertension 542, Cough 289, Coronary Heart Disease 248, Dyspnea 248). Zero rows means `Condition` did not merge on code.

## Comorbidities associated with a condition

- **Parameters:** `$conditionCode = '59621000'` (Hypertension).
- **Invariant:** one row per other condition that shares at least one encounter with Hypertension. Occurrences equals the number of encounters whose `conditions.csv` rows include both codes. Hypertension itself never appears.
- **Expected:** 7 rows — Diabetes mellitus type 2 (disorder) 537, Cough (finding) 225, Coronary Heart Disease 190, Dyspnea (finding) 187, Metabolic syndrome X (disorder) 148, Hypertriglyceridemia (disorder) 146, Familial Alzheimer's disease of early onset (disorder) 77.

## Provider workload

- **Parameters:** `$providerId = 'e2edaa6b-9fea-3a37-8581-df6a8b8f64f5'` (Wilton Pollich).
- **Invariant:** one row per patient with at least one encounter whose `providerId` is this provider. The sum of Encounters equals the provider's `ATTENDED_BY` count. The result is ordered by Encounters descending.
- **Expected:** 1125 rows, Encounters summing to 1276. Distribution: 991 patients with 1 encounter, 120 with 2, 11 with 3, 3 with 4.

## Single-patient chronological pathway via the NEXT chain

- **Parameters:** `$patientId = 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'` (Gerardo Covarrubias).
- **Invariant:** exactly one row for any patient in this data, because every chain is complete. The list holds every one of the patient's encounters in ascending date order.
- **Expected:** 1 row — `["2005-05-26T00:00:00Z (wellness)", "2020-08-05T00:00:00Z (ambulatory)", "2022-09-01T00:00:00Z (wellness)"]`. `toString()` of a ZONED DATETIME may render as `2005-05-26T00:00Z`. Either form is correct.

## Patient journey subgraph

- **Parameters:** `$patientId = 'fd65a941-3fa1-337f-28e2-6c9d3922c1af'` (Gerardo Covarrubias).
- **Invariant:** the drawn graph contains the patient, all of their encounters, the `NEXT` links between them, and every observation, condition, drug and provider attached to those encounters — nothing belonging to another patient's encounters.
- **Expected:** 1 Patient, 3 Encounters, 2 `NEXT` links, 9 Observations, 4 Conditions (Hypertension, Coronary Heart Disease, Dyspnea (finding), Cough (finding)), 2 Drugs (Clopidogrel, Nitroglycerin), 1 Provider (Sondra Botsford).

## Shared-condition patient cluster

- **Parameters:** `$conditionCode = '59621000'` (Hypertension), `$limit = 50`.
- **Invariant:** every path joins two different patients through the Hypertension node, each unordered pair at most once per encounter combination. No more than `$limit` paths are returned.
- **Expected:** 50 paths, drawn from the 1615 patients diagnosed with Hypertension. Which pairs are returned is not fixed.

## Comorbidity network

- **Parameters:** `$limit = 50`.
- **Invariant:** one row per unordered condition pair that is co-diagnosed at least once, strongest first. coOccurrences equals the number of encounters diagnosing both, and each path runs through one such encounter.
- **Expected:** 28 rows — every pair of the 8 conditions occurs. Top five: Diabetes mellitus type 2 (disorder)–Hypertension 537, Cough (finding)–Hypertension 225, Coronary Heart Disease–Hypertension 190, Dyspnea (finding)–Hypertension 187. Fifth place is a tie at 148, between Metabolic syndrome X (disorder)–Hypertension and Diabetes mellitus type 2 (disorder)–Dyspnea (finding). Weakest: Familial Alzheimer's disease of early onset (disorder)–Metabolic syndrome X (disorder) 7.
- **Sensitivity:** `$limit = 5` returns the top five above (the tie at 148 makes the fifth row either pair).

## Care network around a condition

- **Parameters:** `$conditionCode = '59621000'` (Hypertension), `$limit = 50`.
- **Invariant:** every path runs Hypertension ← Encounter → Provider → Organisation, and each provider appears with its own organisation only. No more than `$limit` paths.
- **Expected:** 50 of the 2395 possible paths. Without the limit, all 4 providers appear: Wilton Pollich 633, Sondra Botsford 594, Lyle Dibbert 589, Martha Ledner 579, each with their organisation. With `$limit = 50`, which providers appear is not fixed.

## Drug co-prescription network

- **Parameters:** `$limit = 50`.
- **Invariant:** one row per unordered drug pair co-prescribed at least once, strongest first. coPrescriptions equals the number of encounters prescribing both.
- **Expected:** 15 rows — every pair of the 6 drugs occurs. In order: Hydrochlorothiazide–Lisinopril 1155, Acetaminophen–Hydrochlorothiazide 356, Acetaminophen–Lisinopril 343, Clopidogrel–Nitroglycerin 331, Insulin isophane–Lisinopril 264, Acetaminophen–Insulin isophane 262, Hydrochlorothiazide–Insulin isophane 249, Lisinopril–Nitroglycerin 99, Clopidogrel–Hydrochlorothiazide 96, then Hydrochlorothiazide–Nitroglycerin 93 and Clopidogrel–Lisinopril 93 (tied), Acetaminophen–Nitroglycerin 82, Acetaminophen–Clopidogrel 68, Insulin isophane–Nitroglycerin 59, Clopidogrel–Insulin isophane 50.
