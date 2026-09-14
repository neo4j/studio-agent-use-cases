# Patient Journey

Map a patient's care from end to end, and find the conditions and treatments that recur together across a population.

## Overview

### Longitudinal care in healthcare

A person's medical history is not written down in one place. It accumulates as a series of episodes — a consultation here, an admission there, a lab test, a repeat prescription — each recorded by whichever system happened to be in use at the time. Any single record is complete about its own moment and silent about everything around it.

Two quite different groups need that history joined back together:

- **Clinicians and care teams**, who need to see how a patient arrived at their present state: what was measured, what was diagnosed, what was prescribed, and in what order.
- **Population health and research teams**, who need to look across many patients at once to find which conditions travel together, which treatments are prescribed alongside which others, and how care is distributed across providers.

Both questions are awkward in record systems organised around the episode. Reconstructing one patient's pathway means gathering rows from several tables and putting them back in order. The population question is harder still, because it is not really about records at all — it is about whether two patients share something, which means comparing every patient with every other. Written conventionally, that is a join whose cost grows with the square of the population, and the answer depends entirely on whether the two records used the same code for the same thing.

### What it helps with

Representing the record as connected clinical data makes the sequence explicit and lets patients meet each other at the things they have in common.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| A patient's history is scattered across episodes recorded at different times | Walk from the patient along their encounters in order, reaching the measurements, diagnoses and prescriptions attached to each, instead of reassembling rows |
| Working out what happened in what order means sorting records every time | Follow the explicit chain linking each encounter to the one that followed it, so the pathway is stored rather than recomputed |
| Finding which conditions occur together needs every patient compared with every other | Let patients converge on the shared condition, then step back out to everyone else who reached it — a traversal rather than a comparison of all pairs |
| Treatment patterns across a population are hard to see | Follow prescriptions to the shared medication and back out, so drugs that are repeatedly prescribed together become countable |
| Care delivery is hard to attribute beyond the individual visit | Traverse from encounters to the attending clinician and on to their speciality and organisation, so workload and delivery aggregate at any level |
| The clinical picture around a condition is spread across many records | Return the network around a condition — the patients, the co-occurring diagnoses, the drugs prescribed with it — as a picture rather than a list |

Two cautions matter more here than the general ones. First, this is an analytical aid and not clinical guidance: what it surfaces is a pattern worth investigating, never a diagnosis or a treatment decision. Second, the population-level answers depend entirely on conditions and medications being recorded in standardised codes. If source systems use local codes instead, patients will not converge on shared nodes, and comparisons across patients will quietly return far less than the truth — an under-count that looks exactly like a real result.

## Ontology

The reference ontology has eight kinds of thing and eight kinds of connection, arranged around one organising idea: **nothing clinical attaches to a patient directly.**

Every measurement, diagnosis and prescription hangs off an **encounter** — one visit, admission or consultation. That indirection is deliberate. Because the encounter carries the date and the attending clinician, every clinical fact inherits a time and a context automatically, and it becomes impossible to record that a patient has a condition without also recording when that was established and by whom.

The second idea is the division between facts that belong to one patient and facts that are shared by everyone. An observation is a reading taken at one encounter and belongs to that patient alone. A condition and a drug are the opposite: there is one node per standardised code, and every patient who was ever diagnosed with it connects to that same node. Patients meet each other there, and that meeting *is* the comorbidity signal — no extra modelling required. It is also why local codes are so damaging: they prevent the meeting from happening at all.

Around the clinical core sits a small delivery hierarchy — encounters are attended by providers, who have a speciality and belong to an organisation — which lets care be aggregated above the individual visit.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Patient` | A person receiving care, and the anchor of a longitudinal record. Every clinical fact reaches them through an encounter rather than attaching directly, so when something was recorded is never lost |
| `Encounter` | A single episode of care — one visit, admission or consultation. The pivot of the ontology: observations, diagnoses, prescriptions and the attending clinician all hang off it |
| `Observation` | One measurement or test result recorded at an encounter. Belongs to exactly one encounter and is never shared between patients |
| `Condition` | A clinical condition, shared across the whole population. One per standardised code, so every patient diagnosed with it reaches the same node — which is what makes comorbidity analysis a traversal |
| `Drug` | A medication, shared across the whole population. One per standardised code, so co-prescription and treatment patterns become traversable in the same way |
| `Provider` | A clinician who delivers care at encounters. An entity in its own right so workload and referral patterns can be measured |
| `Speciality` | A field of clinical practice, shared by every provider who works in it. Keyed on its name, so providers converge only when the source spells it identically |
| `Organisation` | A healthcare facility or provider organisation clinicians belong to — the institutional level above the individual provider |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Patient` | `id` | String | Stable identifier for the patient in the source system, opaque rather than derived from any identifying detail |
| `Patient` | `name` | String | Display name. Not an identifier — distinct patients may share a name, so it is never used for matching |
| `Patient` | `birthDate` | Zoned datetime | Date of birth. Only the calendar date carries meaning; the time and zone are an artefact of storing a date in a temporal type |
| `Encounter` | `id` | String | Stable identifier for the encounter in the source system |
| `Encounter` | `date` | Zoned datetime | Date the encounter took place, with only the calendar date meaningful. Ordering on this is what reconstructs a pathway |
| `Encounter` | `type` | String | Class of encounter, as a lower-case keyword from the source system's own small vocabulary rather than a coded terminology value |
| `Observation` | `id` | String | Stable identifier for this individual result |
| `Observation` | `code` | String | Code for what was measured, from a standard observation terminology, in that system's own notation |
| `Observation` | `description` | String | Human-readable name of what was measured, carried alongside the code so results are legible without a terminology lookup |
| `Observation` | `value` | String | The measured result, held as text so numeric, coded and free-text results can share one property. Numeric comparisons need an explicit conversion; the unit is held separately |
| `Observation` | `units` | String | Unit of the measured value, in UCUM notation. Absent or meaningless for non-numeric results |
| `Condition` | `code` | String | The condition's identifier in a standardised clinical terminology, and the key on which patients' diagnoses converge |
| `Condition` | `description` | String | Human-readable name of the condition, corresponding to its code |
| `Drug` | `code` | String | The medication's identifier in a standardised medication terminology, and the key on which prescriptions converge |
| `Drug` | `name` | String | Human-readable name of the medication, conventionally including strength and form |
| `Provider` | `id` | String | Stable identifier for the provider in the source system |
| `Provider` | `name` | String | Display name of the provider. Not an identifier |
| `Speciality` | `name` | String | Name of the speciality as the source system records it, and the key on which providers converge |
| `Organisation` | `id` | String | Stable identifier for the organisation in the source system |
| `Organisation` | `name` | String | Name of the organisation as published |
| `Organisation` | `address` | String | Postal address as a single unparsed line, with no separate town, region or postcode fields and no geocoding |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `HAS_ENCOUNTER` | `Patient` → `Encounter` | Attaches an episode of care to the patient who received it. Exactly one patient per encounter; a patient may have many, or none |
| `NEXT` | `Encounter` → `Encounter` | Chains an encounter to the one that followed it for the same patient, in date order. At most one either way, so the chain is a simple line per patient and never branches. Not every encounter is chained, so its absence does not mean an encounter was the last |
| `HAS_OBSERVATION` | `Encounter` → `Observation` | Records that this measurement was taken at this encounter. Exactly one encounter per observation; an encounter may carry several, or none |
| `DIAGNOSED` | `Encounter` → `Condition` | Records that this condition was diagnosed at this encounter. An encounter may diagnose several; a condition, being shared, is diagnosed at many. Two patients meet here, which is what comorbidity analysis traverses |
| `PRESCRIBED` | `Encounter` → `Drug` | Records that this medication was prescribed at this encounter. An encounter may prescribe several; a drug, being shared, is prescribed at many. Repeated pairs reached this way are what co-prescription analysis counts |
| `ATTENDED_BY` | `Encounter` → `Provider` | Records the clinician who delivered this encounter. Exactly one attending provider per encounter; a provider attends many, or none |
| `HAS_SPECIALITY` | `Provider` → `Speciality` | Places a provider in their field of practice. Exactly one speciality per provider, recording the current one rather than a history; a speciality is shared by many providers |
| `BELONGS_TO` | `Provider` → `Organisation` | Places a provider within the organisation they practise at. Exactly one per provider, so a clinician working across several sites cannot be represented without extending the ontology; an organisation may have many providers |
