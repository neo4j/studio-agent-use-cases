# Insurance Claims Fraud

Uncover fraud rings and suspicious claims through the connections between claimants, doctors, vehicles and the claims they share.

## Overview

### Claims fraud in general insurance

Motor and personal-injury insurers settle claims at volume and under time pressure. A claim arrives, it is assessed against the policy, and it is paid — usually quickly, because slow settlement is itself a cost and a source of complaints. Special investigation units work alongside that flow, expected to pull the fraudulent minority out of it without holding up everyone else.

What they are looking for runs from the opportunistic to the organised:

- **Exaggerated injuries** — a real accident, an inflated account of the harm it caused.
- **Inflated costs** — genuine repairs or treatment billed well above what was delivered.
- **Staged accidents** — a collision arranged deliberately so a claim can be made against it.
- **Crash-for-cash rings** — groups of claimants, vehicles and cooperating professionals working the same method repeatedly, each claim sized to stay under the threshold that would attract attention.

The difficulty is that a single claim is the wrong unit of analysis. Organised fraud is spread across records by design: no one claim is remarkable, and the parties are chosen so that nothing on the claim form connects them. What gives a ring away is repetition *across* claims — a vehicle that keeps reappearing in unrelated accidents, a clinician attached to an implausible share of high-value injury claims, a claimant whose name has come up before.

Rules that score claims one at a time cannot see any of that, because the evidence is not in the claim. It is in how claims relate to one another.

### What it helps with

Modelling the parties and their claims as connected data turns each of those questions into a traversal rather than a manual cross-check.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Organised fraud is spread across records that each look legitimate | Examine claims as a connected population rather than one at a time, so the repetition that defines a ring is visible even when no single claim is unusual |
| The same vehicle is recycled through staged accidents | Follow a vehicle to every claim it appeared in, and on to the people who own it, so a car that has crashed implausibly often surfaces directly |
| One clinician sits behind a disproportionate share of injury claims | Count and total the claims attached to each medical professional, so an outlier by volume or by value stands out against their peers |
| Repeat claimants are hard to see across a large portfolio | Group claims by the person who filed them and rank by frequency and total value, instead of relying on an adjuster's recall |
| Parties who look unconnected on paper are working together | Traverse from claimant to vehicle to claim to clinician and back, so shared parties reveal a group that no individual record names |
| A clinician's caseload and their claim involvement are not the same thing | Compare who a professional treats against which claims they are attached to, since the gap between the two is more telling than either alone |
| Investigators need to see the shape of a case, not a spreadsheet | Return the network around a claim or a person as a picture, so a reviewer can judge whether a pattern is a ring or a coincidence |

Everything surfaced this way is a lead for a human investigator, never a finding. The patterns are suggestive rather than conclusive — a busy clinic and a fraudulent one look alike from the outside — and the thresholds deciding what counts as "unusual" have to be tuned to the portfolio before any of it means much. None of it is a determination of fraud.

## Ontology

The reference ontology is deliberately small: four kinds of thing and five kinds of connection, covering the parties to a motor injury claim and the ways they meet.

A claimant files claims and owns vehicles. A vehicle is involved in claims. A claim is handled by a medical professional, who also treats claimants.

That last pair repays careful reading. The ontology records a professional's link to a **claim** separately from their link to a **person**, because these are different facts and the gap between them is informative: a clinician who treats someone whose claim they were never attached to is in a different position from one who simply has a large caseload. Collapsing the two would erase the distinction.

Direction carries meaning throughout. Ownership and involvement run from the party to the thing claimed on; treatment runs outward from the professional. Read undirected, the ontology loses the difference between filing a claim and merely being named in one.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Claimant` | A person who has filed one or more claims against a policy. Identified by name alone, so a spelling variant reads as a different person — identity is expected to be resolved before the data arrives |
| `Claim` | A single claim submitted for settlement after an incident. The unit at which money is sought and fraud is ultimately assessed, though rarely the unit at which it is detectable |
| `Vehicle` | A motor vehicle that can be owned by a claimant and named in claims. Held separately from the claim so one vehicle appearing across several unconnected incidents becomes visible |
| `MedicalProfessional` | A clinician who assesses or treats claimants and whose assessment supports an injury claim. An entity in its own right because concentration of claims on one professional is itself a signal |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Claimant` | `name` | String | Full name of the claimant, and the identifier by which the same person is recognised across separate claims. Expected to be already normalised, as no fuzzy matching is performed |
| `Claim` | `claimID` | String | The insurer's reference for the claim, unique across the portfolio |
| `Claim` | `date` | String | Calendar date of the incident the claim relates to, in ISO year-month-day form. Held as text rather than as a date, so comparisons are character-by-character — which orders correctly for this format but needs an explicit conversion before any date arithmetic |
| `Claim` | `amountClaimed` | Integer | Amount sought on the claim, as a whole currency unit with no minor units. No currency is recorded, so totals across claims assume a single-currency portfolio |
| `Vehicle` | `VIN` | String | Vehicle identification number — the manufacturer's 17-character serial. The identifier that survives a change of registration plate or owner, which is what makes it usable for linking claims |
| `MedicalProfessional` | `name` | String | Full name of the professional, including any title as recorded by the insurer, and the identifier by which they are recognised across separate claims |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `HAS_CLAIM` | `Claimant` → `Claim` | Records that this person filed this claim. Exactly one claimant per claim; a claimant may file many. Counting along this is the simplest repeat-claimant check available |
| `OWNS` | `Claimant` → `Vehicle` | Records that this person owns this vehicle. Exactly one owner per vehicle, so this represents current ownership rather than a history of it; a claimant may own several vehicles, or none |
| `INVOLVED_IN` | `Vehicle` → `Claim` | Records that this vehicle featured in the incident behind the claim. Exactly one vehicle per claim; a vehicle may appear in several. A vehicle involved implausibly often is the entry point to a staged-accident ring |
| `TREATED_BY` | `Claim` → `MedicalProfessional` | Records that this professional was attached to the claim and gave the clinical assessment it rests on. Exactly one professional per claim; a professional may be attached to many. Concentration here is what marks an outlier |
| `TREATS` | `MedicalProfessional` → `Claimant` | Records a care relationship between a professional and a person, independent of any claim. Many-to-many in both directions, and held apart from the claim link precisely so the two can be compared |
