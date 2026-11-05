# Life Sciences Competitive Intelligence — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Unless a section says otherwise, every figure below was derived from the CSVs in `sample-data/` by recomputing the query's logic in Python, independently of any database.

## How to run

1. Use a disposable Neo4j 5.x database — the import writes the whole sample.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key and existence constraints.
3. No `SETUP.md` statements are needed.
4. Run each query in `QUERIES.md` with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second.
5. No query writes, so the queries can run in any order.

## Sample-data profile

Synthetic data from a seeded, deterministic generator kept outside the package (`competitive-intelligence-gen.py` at the repository root, seed `20261030`). Every company, drug, trial and patent is fictional. Proteins, their UniProt accessions, diseases and ICD-10 codes are real. Trial and patent identifiers use the real formats from ranges not yet issued (`NCT99…`, `US19…`, `EP9…`), so none can collide with a real record. Dates are relative to 30 October 2026: trials that are not yet recruiting start after it, and every other trial started before it.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Company` | 40 | Market caps: 16 below 2 billion USD, 7 from 2 to 10 billion, 8 from 10 to 50 billion, 9 of 50 billion or more |
| `Drug` | 147 | 86 Active, 18 Approved, 43 Discontinued. One co-developed (GBL-731, Glenhollow Bio and Harrowgate Pharma), one bispecific (ZBE-933, PD-1 and PD-L1) |
| `ClinicalTrial` | 324 | Phase 1 147, Phase 2 112, Phase 3 56, Phase 4 9. Completed 200, Recruiting 43, Terminated 33, Not yet recruiting 21, Active not recruiting 21, Suspended 4, Withdrawn 2 |
| `Patent` | 120 | Granted 46, Pending 36, Expired 24, Abandoned 14. One co-owned (US19081926B2, Ashcombe Pharma and Kelvedon Therapeutics) |
| `Protein` | 16 | BACE1, Amyloid-beta, Tau, TREM2, LRRK2, GBA1, PD-1, PD-L1, EGFR, ALK, KRAS, BRAF, JAK1, IL-6R, BTK, GLP-1R |
| `Disease` | 8 | Alzheimer's Disease, Parkinson's Disease, Non-Small Cell Lung Cancer, Melanoma, Rheumatoid Arthritis, Multiple Sclerosis, Type 2 Diabetes Mellitus, Ulcerative Colitis |
| `Phase` | 4 | Phase 1 to Phase 4 |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `IN_PIPELINE` | 148 | One per company and drug; GBL-731 has two |
| `TARGETS` (Drug → Protein) | 148 | ZBE-933 has two |
| `TREATS` (Drug → Disease) | 150 | One per drug and disease it has been trialled in; repeated trial rows for a pair merge into one |
| `INVESTIGATED_IN` | 324 | One per trial |
| `HAS_PHASE` | 324 | One per trial |
| `FOR_DISEASE` | 324 | One per trial |
| `HAS_OWNER` | 121 | US19081926B2 has two owners |
| `TARGETS` (Patent → Protein) | 120 | One per patent |
| `TREATS` (Patent → Disease) | 120 | One per patent |

Drugs trialled per disease: Non-Small Cell Lung Cancer 41, Alzheimer's Disease 36, Parkinson's Disease 20, Melanoma 17, Rheumatoid Arthritis 15, Multiple Sclerosis 9, Type 2 Diabetes Mellitus 8, Ulcerative Colitis 4.

**Seeded signals.**

- **BACE1 in Alzheimer's disease, a crowded and failure-heavy target.** Seven drugs from eight companies, and no BACE1 drug outside them:
  - ATL-2301 (Aldermoor Therapeutics), Active. Phase 1 completed 2017; a 2019 Phase 2 terminated for slow enrolment; Phase 2 completed 2021; Phase 3 registered for 2027 and not yet recruiting. This is the source scenario's BD team deciding whether to advance into Phase 3, and the one live drug with a terminated trial.
  - BBR-118 (Brightwater Biosciences), Discontinued. Phase 3 terminated in 2017 for cognitive worsening versus placebo.
  - DBU-44 (Dunmore Biologics), Discontinued. Phase 3 terminated in 2016 for liver enzyme elevations.
  - CPA-6672 (Calderra Pharma), Discontinued. Phase 2 terminated in 2016 for lack of efficacy.
  - EPL-907 (Elsworth Pharmaceuticals), Discontinued after a completed Phase 2, with no termination reason.
  - FLE-210 (Fenwick Life Sciences, small cap), Active, Phase 2 recruiting.
  - GBL-731 (Glenhollow Bio, small cap, with Harrowgate Pharma), Active, Phase 1 active and not recruiting.
- **Other Alzheimer's mechanisms:**
  - an approved anti-Amyloid-beta antibody (veltonemab, Ravensmere Pharma, with a Phase 4 recruiting);
  - a Phase 3 Amyloid-beta antibody (Vantmoor Pharma);
  - a Tau antisense oligonucleotide in Phase 2 (Larkfield Pharma, small cap);
  - a discontinued Tau antibody (Thornbury Therapeutics, Phase 2 terminated for futility);
  - a TREM2 agonist antibody in Phase 1 (Marlowe Biotherapeutics, small cap).
- **Acquisition screen:**
  - **Small caps with early active assets:** Fenwick Life Sciences, Glenhollow Bio, Larkfield Pharma, Marlowe Biotherapeutics, Northbrook Oncology (KRAS, Phase 2) and Ortolan Bio (LRRK2, Phase 1).
  - **Seeded near-misses, each with a single asset:**
    - Ivelmont Therapeutics: small cap, its only asset in Phase 3;
    - Juniper Ridge Bio: 2.41 billion USD, just over the ceiling, with a Phase 2 asset;
    - Kestrel Molecular: small cap, its only asset discontinued.
- **Patent estates:**
  - BACE1 in Alzheimer's: Brightwater 3, Calderra 2, Dunmore 2, Aldermoor 2, Fenwick 1 and Harrowgate 1 seeded filings, plus background.
  - PD-1 in lung cancer: Hollinwood Pharma and Ashcombe Pharma, Zennor Biologics.
  - The co-owned filing US19081926B2.
- **Patents ahead of the pipeline:** Penhallow Therapeutics holds 3 TREM2 filings for Alzheimer's and has no TREM2 drug. The near-miss Quillon Biosciences holds a single GBA1 filing and no GBA1 drug.

**Background noise.**
- **Programmes:** every company has further programmes on randomly chosen targets (BACE1 excluded, so the landscape above is complete), with histories dated backwards from their final trial.
- **Approvals:** only on targets that have an approved drug class in reality: Amyloid-beta, PD-1, PD-L1, EGFR, ALK, KRAS, BRAF, JAK1, IL-6R and GLP-1R. Small caps never hold an approved drug.
- **Patents:** 98 background filings, 80% on the owner's own targets.

The background is what makes TREM2 the most-pursued Alzheimer's target in the sample, and what puts LRRK2 and GBA1 overlaps alongside the seeded BACE1 and PD-1 ones.

**Design notes.**
- **Market cap:** 2 billion USD is the conventional small-cap ceiling, chosen before the data. The near-misses were then placed either side of the seeded screen.
- **Overlap threshold:** the patent overlap query has a `$minPatentsEach` gate because, at 1, the background yields 213 overlapping pairs, which nobody could review.

## Graph census — node counts by label

- **Parameters:** none.
- **Invariant:** one row per label in the reference ontology, seven in all, with no other label; counts equal the data rows of each node table.
- **Expected:** 7 rows — ClinicalTrial 324, Drug 147, Patent 120, Company 40, Protein 16, Disease 8, Phase 4.

## Company therapeutic focus

- **Parameters:** `$companyId = 'CO-001'` (Aldermoor Therapeutics).
- **Invariant:** one row per disease that at least one of the company's drugs has been trialled in; in each row, `drugs` equals `approved + active + discontinued`.
- **Expected:** 2 rows — Alzheimer's Disease: 1 drug, 1 active (ATL-2301); Non-Small Cell Lung Cancer: 1 drug, 1 discontinued.

## Competitive landscape for a target

- **Parameters:** `$proteinName = 'BACE1'`.
- **Invariant:**
  - one row per company and drug for every drug targeting BACE1, with a co-developed drug appearing once per partner;
  - `highestPhase` is the highest phase among the drug's trials;
  - `latestTrial` is the drug's trial with the latest start date;
  - rows are ordered by `highestPhase` descending, then company.
- **Expected:** 8 rows for the 7 seeded drugs, in this order:

  | company | drug | status | highestPhase | latestTrial | latestTrialStatus | latestTrialStart |
  | ------- | ---- | ------ | ------------ | ----------- | ----------------- | ---------------- |
  | Aldermoor Therapeutics | ATL-2301 | Active | 3 | NCT99004916 | Not yet recruiting | 2027-11-09 |
  | Brightwater Biosciences | BBR-118 | Discontinued | 3 | NCT99008819 | Terminated | 2017-02-01 |
  | Dunmore Biologics | DBU-44 | Discontinued | 3 | NCT99015324 | Terminated | 2016-03-20 |
  | Calderra Pharma | CPA-6672 | Discontinued | 2 | NCT99011421 | Terminated | 2016-08-18 |
  | Elsworth Pharmaceuticals | EPL-907 | Discontinued | 2 | NCT99017926 | Completed | 2018-10-21 |
  | Fenwick Life Sciences | FLE-210 | Active | 2 | NCT99020528 | Recruiting | 2025-03-24 |
  | Glenhollow Bio | GBL-731 | Active | 1 | NCT99021829 | Active, not recruiting | 2025-10-27 |
  | Harrowgate Pharma | GBL-731 | Active | 1 | NCT99021829 | Active, not recruiting | 2025-10-27 |

- **Sensitivity:** ATL-2301's `highestPhase` of 3 comes from a trial not yet recruiting. Excluding trials with that status would give 2, and it would sort below the two discontinued Phase 3 drugs.

## Disease pipeline intensity

- **Parameters:** `$diseaseName = "Alzheimer's Disease"`.
- **Invariant:**
  - one row per company with at least one trial in the disease;
  - `liveAssets` never exceeds `assets`;
  - `highestLivePhase` is null exactly when `liveAssets` is 0, and never exceeds `highestPhaseReached`;
  - rows are ordered by `highestLivePhase` descending (null last), then `liveAssets` descending, then company.
- **Expected:** 25 rows.
  - **First:** Ravensmere Pharma (1 asset, 1 live, Phase 4).
  - **Live Phase 3, in order:** Netherfield Bio and Vantmoor Pharma (2 live each), then Aldermoor Therapeutics, Eskmere Therapeutics, Merrowby Pharma, Northbrook Oncology, Penhallow Therapeutics, Saltire Biologics and Thornbury Therapeutics (1 live each).
  - **Live Phase 2:** Glenhollow Bio (2), then Fenwick Life Sciences, Kelvedon Therapeutics, Larkfield Pharma and Pendleford Pharma.
  - **Live Phase 1:** Harrowgate Pharma (2), then Corvane Biologics, Lowther Biosciences and Marlowe Biotherapeutics. Marlowe's `highestPhaseReached` is 2, from a discontinued drug.
  - **Last, with no live asset:** Brightwater Biosciences, Calderra Pharma, Dunmore Biologics, Elsworth Pharmaceuticals, Inglebrook Bio and Yarrowdale Therapeutics. Their `highestPhaseReached` values are 3, 2, 3, 2, 2 and 1.

## Target diversification within a disease

- **Parameters:** `$diseaseName = "Alzheimer's Disease"`.
- **Invariant:** one row per protein targeted by a drug trialled in the disease; `discontinued` never exceeds `drugs`; ordered by `companies` descending, then `drugs` descending.
- **Expected:** 4 rows — TREM2 (Receptor): 12 companies, 13 drugs, 6 discontinued; Amyloid-beta (Peptide): 8, 9, 3; BACE1 (Enzyme): 8, 7, 4; Tau (Structural protein): 6, 7, 1. BACE1 has more companies than drugs because GBL-731 is co-developed.

## Failed programmes in a disease

- **Parameters:** `$diseaseName = "Alzheimer's Disease"`.
- **Invariant:**
  - one row per company, drug and target for every Discontinued drug trialled in the disease, and no live drug;
  - in particular, ATL-2301 must not appear despite its terminated 2019 trial;
  - `lastPhase`, `lastTrialStatus` and `reason` describe the drug's latest-starting trial, and `reason` is null exactly when that trial was not stopped early;
  - ordered by `lastTrialStart` descending.
- **Expected:** 14 rows, newest first:
  - Inglebrook Bio IBN-2576 (TREM2, Phase 2, Completed, 2023-10-17)
  - Yarrowdale Therapeutics YTA-2032 (TREM2, Phase 1, Terminated, portfolio reprioritisation, 2023-03-09)
  - Marlowe Biotherapeutics MBA-1624 (TREM2, Phase 2, Terminated, futility, 2021-03-27)
  - Calderra Pharma CPA-5834 (TREM2, Phase 2, Completed, 2020-04-02)
  - Northbrook Oncology NOO-8322 (Amyloid-beta, Phase 2, Terminated, portfolio reprioritisation, 2019-11-25)
  - Thornbury Therapeutics TTH-215 (Tau, Phase 2, Terminated, futility, 2019-09-09)
  - Dunmore Biologics DBU-2453 (Amyloid-beta, Phase 1, Withdrawn, portfolio reprioritisation, 2019-06-19)
  - Elsworth Pharmaceuticals EPL-907 (BACE1, Phase 2, Completed, 2018-10-21)
  - Eskmere Therapeutics ETS-5364 (TREM2, Phase 3, Terminated, portfolio reprioritisation, 2017-12-24)
  - Brightwater Biosciences BBR-118 (BACE1, Phase 3, Terminated, cognitive worsening versus placebo, 2017-02-01)
  - Calderra Pharma CPA-6672 (BACE1, Phase 2, Terminated, lack of efficacy, 2016-08-18)
  - Pendleford Pharma PPE-5902 (Amyloid-beta, Phase 2, Terminated, lack of efficacy, 2016-08-14)
  - Dunmore Biologics DBU-44 (BACE1, Phase 3, Terminated, liver enzyme elevations, 2016-03-20)
  - Thornbury Therapeutics TTH-7278 (TREM2, Phase 2, Terminated, futility, 2014-07-17)

## Acquisition target screening

- **Parameters:** `$maxMarketCapUsd = 2000000000`, `$maxPhase = 2`.
- **Invariant:**
  - every company below the ceiling with at least one Active drug whose highest phase is at most 2 appears, and no other company;
  - in particular, none of the three seeded near-misses appears (Ivelmont Therapeutics, Juniper Ridge Bio, Kestrel Molecular);
  - ordered by `highestPhase` descending, `earlyAssets` descending, then `marketCapMillionsUsd`.
- **Expected:** 14 rows (companyId, marketCapMillionsUsd, earlyAssets, highestPhase, targets):

  | Company | ID | Cap (M USD) | Early assets | Highest phase | Targets |
  | ------- | -- | ----------- | ------------ | ------------- | ------- |
  | Foxhollow Bio | CO-031 | 1520 | 4 | 2 | 3 |
  | Netherfield Bio | CO-038 | 381 | 3 | 2 | 3 |
  | Inglebrook Bio | CO-034 | 468 | 3 | 2 | 3 |
  | Larkfield Pharma | CO-012 | 905 | 3 | 2 | 3 |
  | Eskmere Therapeutics | CO-030 | 538 | 2 | 2 | 2 |
  | Yarrowdale Therapeutics | CO-024 | 745 | 2 | 2 | 2 |
  | Glenhollow Bio | CO-007 | 820 | 2 | 2 | 2 |
  | Bramblecote Bio | CO-027 | 1060 | 2 | 2 | 2 |
  | Fenwick Life Sciences | CO-006 | 1210 | 2 | 2 | 2 |
  | Northbrook Oncology | CO-014 | 1380 | 2 | 2 | 2 |
  | Ulverston Bio | CO-021 | 1840 | 2 | 2 | 2 |
  | Ortolan Bio | CO-015 | 287 | 2 | 1 | 2 |
  | Marlowe Biotherapeutics | CO-013 | 612 | 2 | 1 | 2 |
  | Lowther Biosciences | CO-036 | 1150 | 2 | 1 | 2 |

- **Sensitivity:**
  - `$maxMarketCapUsd = 2500000000` adds exactly Juniper Ridge Bio (15 rows).
  - `$maxPhase = 1` returns 11 companies: Fenwick Life Sciences, Northbrook Oncology, Netherfield Bio and others with only Phase 2 early assets drop out. Glenhollow Bio stays through GBL-731.

## Patent overlap between companies

- **Parameters:** `$minPatentsEach = 2`.
- **Invariant:**
  - one row per pair of companies holding at least 2 filings each on the same target and disease, counting only filings the other company does not co-own;
  - `company1` sorts before `company2` by company id;
  - `overlap` equals `patents1 + patents2`;
  - ordered by `overlap` descending.
- **Expected:** 24 rows. Their overlaps are 7 three times, 6 six times, 5 ten times and 4 five times.
  - **Fifteen are BACE1 in Alzheimer's**, one for every pair of Brightwater Biosciences (4), Calderra Pharma (3), Harrowgate Pharma (3), Aldermoor Therapeutics (2), Dunmore Biologics (2) and Fenwick Life Sciences (2). Brightwater–Calderra and Brightwater–Harrowgate lead at 7.
  - **Three are PD-1 in lung cancer:** Ashcombe Pharma with Hollinwood Pharma (6), and Zennor Biologics with each of them (5).
  - **The rest:** three GBA1 in Parkinson's (Ulverston Bio with Corvane Biologics at 7, with Oakhanger Therapeutics at 6; Corvane with Oakhanger at 5); LRRK2 in Parkinson's (Kestrel Molecular with Ulverston Bio, 5); GLP-1R in Type 2 Diabetes (Eskmere Therapeutics with Merrowby Pharma, 4); and PD-L1 in Melanoma (Yarrowdale Therapeutics with Zennor Biologics, 4).
- **Sensitivity:**
  - `$minPatentsEach = 3` returns 5 rows: Brightwater–Calderra, Brightwater–Harrowgate and Calderra–Harrowgate on BACE1, Ulverston–Corvane on GBA1, and Ashcombe–Hollinwood on PD-1.
  - `$minPatentsEach = 1` returns 213.
  - The co-owned US19081926B2 (Ashcombe and Kelvedon) never counts towards an Ashcombe–Kelvedon overlap.

## Patents without a pipeline programme

- **Parameters:** `$minPatents = 2`.
- **Invariant:** one row per company and target where the company holds at least 2 filings on the target and no drug in its pipeline targets it; ordered by `patents` descending, then `latestFiling` descending.
- **Expected:** 2 rows — Penhallow Therapeutics on TREM2 (3 filings, latest 2023-05-28) and Corvane Biologics on KRAS (2, latest 2023-01-25). Quillon Biosciences (one GBA1 filing) is absent.
- **Sensitivity:** `$minPatents = 1` returns 28 rows. Most are single background filings on targets outside the owner's pipeline.

## Pipeline and patent convergence on a target

- **Parameters:** `$minPhase = 2`.
- **Invariant:**
  - one row per company and target where the company has a non-discontinued drug on the target whose highest phase is at least 2, and holds at least one filing on the same target;
  - no discontinued drug contributes. For example, Brightwater's BACE1 estate never appears through BBR-118;
  - ordered by `highestPhase` descending, then `patents` descending.
- **Expected:** 31 rows.
  - **Phase 4:** Hollinwood Pharma on PD-1 (4 filings), Merrowby Pharma on GLP-1R (2), Ravensmere Pharma on Amyloid-beta (1), Wexcombe Biosciences on KRAS (1).
  - **Phase 3**, 12 rows, among them Ashcombe Pharma on PD-1 (4), Ulverston Bio on GBA1 (4) and Aldermoor Therapeutics on BACE1 (2).
  - **Phase 2**, 15 rows, among them Fenwick Life Sciences on BACE1 (2) and Zennor Biologics on PD-L1 (3).
- **Sensitivity:**
  - `$minPhase = 3` returns 16 rows.
  - `$minPhase = 1` returns 43. Among the additions is Harrowgate Pharma on BACE1, through the Phase 1 GBL-731 and its own BACE1 filing. Its partner Glenhollow Bio does not join it on BACE1, because Glenhollow holds no BACE1 filing.
