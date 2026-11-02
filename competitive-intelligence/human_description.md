# Life Sciences Competitive Intelligence

Connect competitors' drug pipelines, clinical trials and patent filings through the targets and diseases they share, so business development and strategy teams can see who is pursuing what, how far they have got, and where they have failed.

## Overview

### The industry

Pharmaceutical and biotechnology companies make multi-year, multi-billion-dollar bets on which biological targets and diseases to pursue. Business development, portfolio strategy and competitive intelligence teams have to judge those bets against everyone else's: who else is working on the same target, how advanced their programmes are, which approaches have already failed, and which smaller companies hold promising early assets.

The evidence is scattered. Clinical trial registries show committed development, but only once a programme reaches patients. Patent filings reveal strategic intent years earlier, but are written in legal language and filed under company names that change through mergers. Neither source lines up with the other on its own, and both go out of date within weeks as trials start, stop and read out.

### What it helps with

The questions below all depend on joining pipeline and patent evidence through the targets and diseases they share.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Who else is developing a drug against our target, and how far ahead are they? | Every drug links to the protein it targets and to its trials and their phases, so one target gives the whole competitive landscape and each competitor's most advanced trial. |
| How crowded is this disease, and is anyone converging on the same mechanism? | Trials link to diseases and drugs to targets, so a disease can be broken down by company and by target, with live and stopped programmes counted separately. |
| What has already failed here, and why? | A drug's development status is kept apart from each trial's status and the sponsor's stated reason for stopping, so discontinued programmes can be studied without confusing them with a single stopped trial. |
| Which smaller companies have promising early-stage assets? | Companies carry a market value and their drugs carry status and phase, so early, live assets at smaller companies can be screened for acquisition or partnership. |
| Where do competitors' patent estates collide, and who is patenting ahead of the clinic? | Patents link to the same target and disease nodes as drugs, so overlapping claims between companies, and patents on targets a company has no programme for yet, become visible. |

## Ontology

The reference ontology centres on two shared anchors, the protein target and the disease. Drugs and patents both point at targets and diseases, which is what lets pipeline and patent evidence be compared. Companies sit on the other side: they develop drugs and own patents. Each drug's progress is recorded through the clinical trials that study it, each trial with one phase and one disease.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Company` | A pharmaceutical or biotechnology company: the sponsor of development programmes and the owner of patents. |
| `Drug` | A development asset or approved product: one molecule or biologic, possibly developed for several diseases through several trials. |
| `Protein` | A human protein pursued as a drug target, shared by every drug and patent that targets it. |
| `Disease` | A disease or indication that drugs are developed for and patents claim. |
| `ClinicalTrial` | A registered clinical trial of one drug in one disease at one phase. |
| `Phase` | A clinical development phase, 1 to 4, where phase 4 is a study after approval. |
| `Patent` | A patent or published patent application claiming a target and an indication. |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Company` | `id` | String | Identifier of the company, stable across its programmes and patents. |
| `Company` | `name` | String | Registered company name. |
| `Company` | `country` | String | Country of the headquarters, as a two-letter ISO country code. |
| `Company` | `market_cap` | Integer | Market capitalisation in US dollars at a single point in time. |
| `Company` | `focus` | String | The therapeutic areas the company works in, such as Neuroscience or Oncology. |
| `Drug` | `id` | String | The sponsor's compound code for the asset. |
| `Drug` | `name` | String | The asset's non-proprietary name once assigned, otherwise its compound code. |
| `Drug` | `mechanism` | String | How the asset acts on its target, in words — for example an inhibitor or a monoclonal antibody. |
| `Drug` | `administration` | String | Route of administration: Oral, Intravenous, Subcutaneous, Intrathecal or Inhaled. |
| `Drug` | `status` | String | Status of the asset as a whole: Active, Approved or Discontinued. |
| `Protein` | `name` | String | Common name or gene symbol of the target. |
| `Protein` | `uniprot` | String | The protein's UniProt accession, its unambiguous identifier. |
| `Protein` | `function` | String | Short description of the protein's biological role. |
| `Protein` | `type` | String | Target class: Enzyme, Receptor, Kinase, Immune checkpoint, Peptide, Structural protein or Transcription factor. |
| `Disease` | `name` | String | Name of the disease. |
| `Disease` | `icd10` | String | The disease's ICD-10 code. |
| `Disease` | `us_prevalence` | Integer | Approximate number of people in the United States living with the disease, at a point in time. |
| `Disease` | `annual_market_usd` | Integer | Approximate annual US market for treatments, in US dollars, at a point in time. |
| `ClinicalTrial` | `nct_id` | String | The trial's ClinicalTrials.gov registry number (its NCT number). |
| `ClinicalTrial` | `title` | String | Brief title of the study as registered. |
| `ClinicalTrial` | `status` | String | Recruitment status as the registry reports it: Not yet recruiting, Recruiting, Active not recruiting, Completed, Terminated, Withdrawn or Suspended. |
| `ClinicalTrial` | `start_date` | Date and time | Actual start date, or the anticipated one while the trial is not yet recruiting; only the date matters. |
| `ClinicalTrial` | `enrollment` | Integer | Number of participants: actual once the trial has ended, anticipated otherwise. |
| `ClinicalTrial` | `termination_reason` | String | The sponsor's stated reason a trial was stopped early or paused; empty for trials that were not. |
| `Phase` | `name` | String | Phase 1, Phase 2, Phase 3 or Phase 4. |
| `Phase` | `number` | Integer | The phase as a number, 1 to 4, for ordering. |
| `Patent` | `id` | String | Publication number, with its country prefix and kind code. |
| `Patent` | `title` | String | Title of the patent as published. |
| `Patent` | `filing_date` | Date and time | Date the application was filed; only the date matters. |
| `Patent` | `status` | String | Legal status: Pending, Granted, Expired or Abandoned. |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `IN_PIPELINE` | `Company` → `Drug` | A drug in the company's development pipeline, as originator or co-developer. Every drug belongs to at least one company; a company may have many drugs or none. |
| `TARGETS` | `Drug` → `Protein` | A protein the drug is designed to act on. Every drug has at least one target; a protein may be targeted by many drugs or none. |
| `TARGETS` | `Patent` → `Protein` | A protein the patent's claims cover as a drug target. Every patent claims at least one target. |
| `TREATS` | `Drug` → `Disease` | A disease the drug is being developed for or is approved in — every disease it has been trialled in. Every drug treats at least one disease. |
| `TREATS` | `Patent` → `Disease` | A disease the patent's claims name as an indication. Every patent names at least one. |
| `INVESTIGATED_IN` | `Drug` → `ClinicalTrial` | A trial that studies the drug. Each trial studies exactly one drug; every drug has at least one trial. |
| `HAS_PHASE` | `ClinicalTrial` → `Phase` | The trial's development phase. Each trial is in exactly one phase. |
| `FOR_DISEASE` | `ClinicalTrial` → `Disease` | The disease the trial studies. Each trial studies exactly one disease. |
| `HAS_OWNER` | `Patent` → `Company` | A company that owns the patent. Every patent has at least one owner; jointly owned patents have several. |
