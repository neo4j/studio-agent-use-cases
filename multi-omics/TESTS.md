# Multi-Omics Data Integration — Tests

Expected results of every query in `QUERIES.md` on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it.

## How to run

1. Use a disposable Neo4j 5.6+ database (Aura or local). No APOC or GDS is needed.
2. Import the sample data through the Import flow from `ONTOLOGY.json`: all twenty-five CSVs in `sample-data/`. Every node and relationship is mapped; nothing needs adding by hand.
3. No `SETUP.md` statements exist; run the queries straight after the import.
4. Run each query in `QUERIES.md` with the parameters below and compare against the section of the same name. Check the invariant first: it is the contract. The expected values are a convenience that holds for the CSVs as committed.
5. `SHOW CONSTRAINTS` should list the eleven node keys at the end of `QUERIES.md`. The reference ontology also flags as required `Gene.symbol`, `Experiment.omicsLayer`, `GOTerm.aspect`, `INCLUDES.group`, `FOUND_DIFFERENTIAL.logFC`, `FOUND_DIFFERENTIAL.pValue`, `FOUND_DIFFERENTIAL.adjPValue`, `RELATED_TO.score` and `INTERACTS_WITH.score`; note whether Import creates existence constraints for them.

## Sample-data profile

### Counts

| Label | Nodes |
| ----- | ----- |
| `Project` | 3 |
| `Sample` | 80 (30 liver, 24 islet, 26 visceral adipose) |
| `Tissue` | 3 |
| `Phenotype` | 6 |
| `Experiment` | 7 (3 transcriptomics, 4 proteomics) |
| `Comparison` | 6 |
| `Gene` | 279 |
| `Protein` | 279 |
| `Disease` | 12 |
| `GOTerm` | 35 (29 biological process, 3 molecular function, 3 cellular component) |
| `Pathway` | 26 |

| Relationship | Count | Source |
| ------------ | ----- | ------ |
| `HAS_SAMPLE` | 80 | `samples.csv` |
| `TAKEN_FROM` | 80 | `samples.csv` |
| `HAS_PHENOTYPE` | 157 | `sample_phenotypes.csv` |
| `HAS_EXPERIMENT` | 172 | `experiment_samples.csv` |
| `COMPARES` | 11 | `comparison_experiments.csv` |
| `INCLUDES` | 144 | `comparison_samples.csv` |
| `STUDIES_DISEASE` | 5 | `comparison_diseases.csv` |
| `HAS_VALUE` (to `Gene`) | 731 | `gene_values.csv` |
| `HAS_VALUE` (to `Protein`) | 580 | `protein_values.csv` |
| `FOUND_DIFFERENTIAL` (to `Gene`) | 296 | `gene_differentials.csv` |
| `FOUND_DIFFERENTIAL` (to `Protein`) | 168 | `protein_differentials.csv` |
| `CODES` | 279 | `proteins.csv` |
| `RELATED_TO` | 137 | `gene_diseases.csv` |
| `ASSOCIATED_WITH` | 497 | `protein_go.csv` |
| `INTERACTS_WITH` | 638 | `protein_interactions.csv` |
| `PARTICIPATES_IN` | 233 | `protein_pathways.csv` |
| `INVOLVES_PATHWAY` | 18 | `disease_pathways.csv` |

No relationship CSV repeats an endpoint pair, so every row becomes one relationship.

Measurements by experiment: liver RNA-seq 258 genes, islet RNA-seq 240, adipose RNA-seq 233; liver TMT 153 proteins, liver DIA-PASEF 165, islet label-free 124, adipose TMT 138. Differential results (nominal p < 0.05) by comparison, genes / proteins: CMP-LIV-MASLD 63 / 41, CMP-LIV-MASH 64 / 28, CMP-LIV-DIA 0 / 30, CMP-ISL-T2D 62 / 25, CMP-ADI-METS 57 / 23, CMP-ADI-IR 50 / 21. Interactions: 229 at score 0.7 or above, 561 at 0.4 or above. Gene-disease evidence types: 41 genetic association, 29 literature, 23 known drug, 17 RNA expression, 15 animal model, 10 somatic mutation, 2 affected pathway.

### How the data was generated

A seeded, deterministic script (`multi-omics-gen.py`, kept outside the package at the repository root; seed `20261113`, with one random stream per stage so editing one stage's seeds does not reshuffle the others) writes every CSV. Identifiers and names are real and were checked on 13 November 2026 against HGNC (gene symbols, names, HGNC, Ensembl and NCBI IDs), UniProt (accessions and recommended names), OLS (MONDO, UBERON and HP terms), QuickGO (GO terms, none obsolete) and the Reactome content service (pathway IDs and names). Every measurement, statistic, gene-disease association and score, GO annotation, pathway membership and interaction score is synthetic. Two source symbols were dropped as ambiguous (NDUFA4 has no HGNC record under that symbol; UGT1A1 is a complex locus).

**Study design.** Seventy donors: 8 liver controls, 12 with simple steatosis and 10 with MASH (liver biopsies); 14 with metabolic syndrome and 12 controls (visceral adipose; ten of the metabolic-syndrome donors also gave a liver biopsy, so `donorId` repeats across tissues); 12 with type 2 diabetes and 12 non-diabetic organ donors (islets). Phenotypes are assigned per donor and copied to each of the donor's samples. Experiments: RNA-seq on every sample of each tissue; TMT proteomics on all liver and adipose samples; DIA-PASEF on 16 liver samples (the 8 controls and 8 steatosis donors); label-free proteomics on 20 of the 24 islet samples.

| Comparison | Cases | Controls | Experiments | Studies |
| ---------- | ----- | -------- | ----------- | ------- |
| CMP-LIV-MASLD | 22 MASLD (steatosis and MASH) | 8 | EXP-LIV-RNA, EXP-LIV-TMT | MASLD |
| CMP-LIV-MASH | 10 MASH | 12 simple steatosis | EXP-LIV-RNA, EXP-LIV-TMT | MASH |
| CMP-LIV-DIA | 8 steatosis | 8 | EXP-LIV-DIA (proteomics only) | MASLD |
| CMP-ISL-T2D | 12 T2D | 12 | EXP-ISL-RNA, EXP-ISL-LFQ | T2D |
| CMP-ADI-METS | 14 metabolic syndrome | 12 | EXP-ADI-RNA, EXP-ADI-TMT | metabolic syndrome |
| CMP-ADI-IR | 12 insulin resistant | 14 insulin sensitive | EXP-ADI-RNA, EXP-ADI-TMT | none (phenotype-stratified) |

**Background.** Abundance is tissue-aware: islet hormones and transcription factors are transcribed only in islets, hepatocyte genes only in liver, adipokines only in adipose; housekeeping genes are high everywhere. Proteomics detects a protein with a probability that rises with abundance and with platform depth (DIA-PASEF > TMT > label-free), and never detects IL6, IL1B, IL10 or CXCL8. Plasma proteins (ALB, APOA1, HP, TF, FGB, SERPINA1, APOB) are detected in islet and adipose proteomics with no transcript, and circulating adiponectin (ADIPOQ) in liver proteomics. For each comparison a quarter of genes carry a true effect of N(0, 0.45) log2 units, the protein following at 0.55 times the transcript plus noise; observed fold changes add sampling noise and are **clipped to ±0.95**, so no background feature ever reaches the twofold cutoff the queries start at. P-values come from a z-test on the observed change; adjusted p-values are Benjamini-Hochberg across every feature the comparison tested in that layer, including those not stored. Only results with nominal p < 0.05 are written. In each comparison with both layers, four genes whose protein was not detected also get a strong transcript-only change (|log2FC| 1.15–1.9), so strong single-layer changes exist that can never be concordant. Interactions: explicit seeded edges around PIK3CG and CD36 (which get no random edges), then random edges within functional modules (scores 0.40–0.96) and 160 weak cross-module edges (0.15–0.62).

**Seeded signals** (log2 fold changes, transcript / protein):

- **S1 concordant, CMP-LIV-MASLD:** up PLIN2 (2.6 / 2.9), CD36 (2.4 / 2.1), SCD (2.2 / 1.9), CXCL10 (2.0 / 1.6), SPP1 (1.9 / 1.5), SREBF1 (1.8 / 1.4), CCL2 (1.7 / 1.3), PPARG (1.6 / 1.3), FASN (1.5 / 1.7), PIK3CG (1.4 / 1.2), TIMP1 (1.3 / 1.1); down ADH4 (−1.6 / −1.3), ACADL (−1.4 / −1.5), PPARA (−1.3 / −1.2), CPT1A (−1.2 / −1.1).
- **S1 concordant, other comparisons:** CMP-LIV-MASH COL3A1, COL1A1, COL1A2, TIMP1, SPP1, LOXL2, ACTA2, CCL2, TGFB1 (all up); CMP-ISL-T2D TXNIP, DDIT3, GCG, PIK3CG up and SLC2A2, MAFA, INS, PDX1 down; CMP-ADI-METS LEP, CCL2, SPP1, CD68, TNF, CD36, PIK3CG up and ADIPOQ, SLC2A4, PPARGC1A down; CMP-ADI-IR RBP4, SOCS3 up and SLC2A4, ADIPOQ, IRS1 down.
- **S2 concordance near misses, CMP-LIV-MASLD:** TGFB1 (1.3 / 1.2, protein adjusted p 0.126); COL1A1 (1.5 / 0.7, protein below twofold); LPL (1.2 / −1.1, opposite directions). CMP-LIV-MASH: MMP2 (1.1 / 0.8). CMP-ISL-T2D: GLP1R (−1.3 / −0.6), TNF transcript only (protein forced undetected). CMP-ADI-METS: IL6 transcript only.
- **S3 post-transcriptional, CMP-LIV-MASLD:** protein changed with the transcript measured but flat — SQSTM1 (protein 1.8, no transcript result), APOB (1.4, none), SOD2 (−1.2, none), FABP1 (−1.5; transcript −0.3, adjusted p 0.164), PTEN (−1.2; transcript −0.4, adjusted p 0.136); LPL in the opposite direction. Near misses: HMOX1 (transcript 0.8 significant, same direction as protein 1.3) and ADIPOQ (protein −1.6, no liver transcript measured).
- **S4 novelty:** gene-disease associations deliberately leave PIK3CG, CXCL10, TIMP1, ACADL and ADH4 without a MASLD association, and give CPT1A a weak one (0.22); CCL2 (0.36) and SPP1 (0.41) are just above the 0.3 starting cutoff.
- **S5 cross-tissue:** PIK3CG concordant in liver, islet and adipose; CD36, CCL2 and SPP1 in liver and adipose. Near misses: TIMP1 (two liver comparisons), ADIPOQ and SLC2A4 (two adipose comparisons).
- **S6 platform replication, CMP-LIV-DIA:** CD36, PLIN2, SCD, FASN, SQSTM1 up and ACADL, CPT1A down on DIA-PASEF as on TMT. Near misses: SPP1 (DIA 0.35, not significant), PIK3CG (DIA 0.9, below twofold).
- **S7 interaction neighbourhoods:** PIK3CG–PIK3R1 0.95, AKT1 0.91, PIK3CA 0.87, PDPK1 0.84, PTEN 0.79, RAC1 0.73, then below 0.7 CCR2 0.66, MTOR 0.58, CXCL10 0.45, HSP90AA1 0.41. CD36–THBS1 0.92, TLR4 0.86, FABP4 0.81, PLIN2 0.78, LPL 0.75, ITGB1 0.72, PPARG 0.69 (just below 0.7); PLIN2–SCD 0.74, LPL–APOB 0.84, FABP4–PPARG 0.83, TLR4–SQSTM1 0.52, SCD–FASN 0.82.
- **S8 GO sharing:** GCG annotated with glucose homeostasis and insulin secretion, both shared with known type 2 diabetes genes. DDIT3 keeps only its ER-stress annotation (one shared process) as a near miss.

## Comparison overview

**Parameters:** `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** One row per comparison, ordered by comparisonId. Cases plus controls equal the comparison's `INCLUDES` count. CMP-LIV-DIA, which compares no transcriptomics experiment, has 0 changedGenes. CMP-ADI-IR has an empty diseases list.

**Expected:** 6 rows.

| comparisonId | tissues | cases | controls | changedGenes | changedProteins |
| ------------ | ------- | ----- | -------- | ------------ | --------------- |
| CMP-ADI-IR | visceral abdominal adipose tissue | 12 | 14 | 9 | 5 |
| CMP-ADI-METS | visceral abdominal adipose tissue | 14 | 12 | 15 | 10 |
| CMP-ISL-T2D | islet of Langerhans | 12 | 12 | 14 | 8 |
| CMP-LIV-DIA | liver | 8 | 8 | 0 | 7 |
| CMP-LIV-MASH | liver | 10 | 12 | 14 | 9 |
| CMP-LIV-MASLD | liver | 22 | 8 | 22 | 23 |

Every comparison except CMP-LIV-DIA lists two experiments (transcriptomics on Illumina NovaSeq 6000 plus one proteomics experiment); CMP-LIV-DIA lists `proteomics: timsTOF Pro (DIA-PASEF)` only.

**Sensitivity:** Because background fold changes are clipped below 0.95, changedGenes and changedProteins at `$minAbsLogFC = 1` count only seeded features and the transcript-only hits. At `$minAbsLogFC = 0.5` the background comes in: changedGenes / changedProteins become CMP-ADI-IR 34 / 9, CMP-ADI-METS 41 / 14, CMP-ISL-T2D 38 / 9, CMP-LIV-DIA 0 / 14, CMP-LIV-MASH 36 / 14, CMP-LIV-MASLD 44 / 32 (observed on Relate).

## Comparisons whose cases carry a phenotype

**Parameters:** `$phenotypeId = 'HP:0000855'`

**Invariant:** Only comparisons with at least one case carrying insulin resistance; ordered by caseFraction descending. CMP-ADI-IR is first with caseFraction 1.0 and controlFraction 0.0, since its groups are defined by the phenotype.

**Expected:** 6 rows: CMP-ADI-IR 12/12 cases (1.0), 0/14 controls; CMP-LIV-DIA 7/8 (0.875), 0/8; CMP-LIV-MASLD 16/22 (0.727), 0/8; CMP-ADI-METS 10/14 (0.714), 2/12 (0.167); CMP-LIV-MASH 7/10 (0.7), 9/12 (0.75); CMP-ISL-T2D 7/12 (0.583), 1/12 (0.083).

**Sensitivity:** CMP-LIV-MASH is the instructive row: similar fractions in cases and controls, so it says nothing about insulin resistance. `$phenotypeId = 'HP:0001395'` (hepatic fibrosis) returns 2 rows: CMP-LIV-MASH (8 of 10 cases, 0.8; no controls) and CMP-LIV-MASLD (8 of 22, 0.364).

## Disease associations of a gene

**Parameters:** `$symbol = 'PPARG'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** One row per `RELATED_TO` from PPARG, ordered by score descending. A changes entry appears only for a comparison that `STUDIES_DISEASE` that row's disease.

**Expected:** 6 rows: type 2 diabetes mellitus 0.89 known_drug; abdominal obesity-metabolic syndrome 0.7 genetic_association; obesity disorder 0.65 genetic_association; metabolic dysfunction-associated steatotic liver disease 0.62 known_drug, changes `CMP-LIV-MASLD protein 1.3` and `CMP-LIV-MASLD transcript 1.6`; atherosclerosis 0.41 known_drug; breast cancer 0.3 literature. Every row but MASLD has an empty changes list.

**Sensitivity:** `$symbol = 'PIK3CG'` returns 1 row (atherosclerosis 0.38, animal_model) with no changes, since no comparison studies atherosclerosis — the gene's changes in MASLD, T2D and metabolic syndrome comparisons do not show, because it has no association with those diseases.

## Concordant transcript and protein changes

**Parameters:** `$comparisonId = 'CMP-LIV-MASLD'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** Exactly the fifteen S1 genes for CMP-LIV-MASLD and no other gene. Never TGFB1, COL1A1 or LPL (S2), and none of the post-transcriptional genes (S3). Every row has both adjusted p-values at or below 0.05, both absolute fold changes at least 1, and matching signs.

**Expected:** 15 rows: up PLIN2, CD36, SCD, CXCL10, SPP1, FASN, SREBF1, CCL2, PPARG, PIK3CG, TIMP1; down ACADL, ADH4, PPARA, CPT1A. Order by mean fold change: PLIN2 (2.6, 2.9) first, then CD36, SCD, CXCL10, SPP1; FASN and SREBF1 tie at 3.2, and ACADL, ADH4 and PPARG at 2.9, in floating-point order; CPT1A last.

**Sensitivity:** Other comparisons: CMP-LIV-MASH 9 rows, CMP-ISL-T2D 8, CMP-ADI-METS 10, CMP-ADI-IR 5, CMP-LIV-DIA 0 (no transcriptomics). Raising `$maxAdjP` to 0.15 admits TGFB1 alone (protein adjusted p 0.126; 16 rows). Lowering `$minAbsLogFC` to 0.6 gives 20 rows: COL1A1 (protein 0.7) and HMOX1 (transcript 0.8) from the seeded near misses, and three background genes, TXN (−0.95 / −0.95), APP and BRCA1. LPL never qualifies at any cutoff (opposite signs).

## Post-transcriptional candidates

**Parameters:** `$comparisonId = 'CMP-LIV-MASLD'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** Exactly the S3 genes: SQSTM1, FABP1, APOB, PTEN, SOD2 as `transcript unchanged` and LPL as `opposite direction`. Never HMOX1 (transcript moved the same way) or ADIPOQ (no liver transcript measured). Every row has a non-null transcriptBaseMean.

**Expected:** 6 rows ordered by absolute protein change: SQSTM1 1.8 (transcript null), FABP1 −1.5 (transcript −0.3, adjusted p 0.164), APOB 1.4 (null), then PTEN −1.2 (−0.4, 0.136) and SOD2 −1.2 (null) in either order, LPL −1.1 (transcript 1.2, adjusted p 0.0036).

**Sensitivity:** Other comparisons return 0 rows: their seeded protein changes all have a matching transcript change, and background proteins never reach twofold. CMP-LIV-DIA returns 0 rows because it has no transcriptomics experiment. Dropping the `HAS_VALUE` match would add ADIPOQ (protein −1.6), the near miss it exists to stop.

## Novel targets among concordant changes

**Parameters:** `$comparisonId = 'CMP-LIV-MASLD'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`, `$minScore = 0.3`

**Invariant:** A subset of the CMP-LIV-MASLD concordant genes; every row has existingScore null or below 0.3; every concordant gene not returned has a MASLD association of 0.3 or more.

**Expected:** 6 rows: CXCL10 (null, otherDiseases empty), ACADL (null, empty), ADH4 (null, empty), PIK3CG (null, [atherosclerosis]), TIMP1 (null, [cirrhosis of liver, metabolic dysfunction-associated steatohepatitis]), CPT1A (0.22, empty). ACADL and ADH4 tie on mean fold change.

**Sensitivity:** `$minScore = 0.45` adds CCL2 (0.36) and SPP1 (0.41), seeded just above the starting cutoff; `$minScore = 0.2` drops CPT1A. The 0.3 starting value has no strong prior: it was chosen to sit between CPT1A's deliberately weak score and CCL2's. CMP-ISL-T2D returns DDIT3, GCG and PIK3CG; CMP-ADI-IR returns no rows (it studies no disease).

## Concordant changes shared across tissues

**Parameters:** `$maxAdjP = 0.05`, `$minAbsLogFC = 1`, `$minTissues = 2`

**Invariant:** Exactly the S5 genes; never TIMP1, ADIPOQ or SLC2A4, which are concordant in two comparisons of one tissue. Lists are compared as sets.

**Expected:** 4 rows: PIK3CG, 3 tissues (liver, islet of Langerhans, visceral abdominal adipose tissue), comparisons CMP-LIV-MASLD (up), CMP-ISL-T2D (up), CMP-ADI-METS (up); CCL2 and SPP1, 2 tissues (liver, visceral abdominal adipose tissue), 3 comparisons each (CMP-LIV-MASLD, CMP-LIV-MASH, CMP-ADI-METS, all up); CD36, 2 tissues, 2 comparisons (CMP-LIV-MASLD, CMP-ADI-METS).

**Sensitivity:** `$minTissues = 1` returns every gene concordant in any comparison (37 rows), with ADIPOQ, SLC2A4 and TIMP1 the only one-tissue genes changed in two comparisons; `$minTissues = 3` returns only PIK3CG.

## Protein changes replicated across platforms

**Parameters:** `$mondoId = 'MONDO:0013209'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`, `$minPlatforms = 2`

**Invariant:** Exactly the S6 proteins, each with platforms Orbitrap Fusion Lumos and timsTOF Pro and results from CMP-LIV-MASLD and CMP-LIV-DIA in the same direction. Never SPP1 or PIK3CG.

**Expected:** 7 rows, ordered by gene: ACADL down, CD36 up, CPT1A down, FASN up, PLIN2 up, SCD up, SQSTM1 up.

**Sensitivity:** `$minPlatforms = 1` returns every protein changed in either MASLD comparison (23 in CMP-LIV-MASLD and 7 in CMP-LIV-DIA, 23 distinct, since all 7 DIA hits are also TMT hits). Other diseases have one proteomics platform per disease and return 0 rows.

## Evidence trail for a gene in a comparison

**Parameters:** `$symbol = 'PIK3CG'`, `$comparisonId = 'CMP-LIV-MASLD'`

**Invariant:** One row per experiment CMP-LIV-MASLD compares, transcriptomics first. Both rows have measured true. casesAssayed and controlsAssayed never exceed the comparison's group sizes.

**Expected:** 2 rows. EXP-LIV-RNA, transcriptomics, Illumina NovaSeq 6000, poly(A) RNA-seq, 22 cases and 8 controls assayed, baseMean 500.5, logFC 1.4, pValue 0.0003, adjPValue 0.00204. EXP-LIV-TMT, proteomics, Orbitrap Fusion Lumos, TMTpro 16-plex, 22 and 8 assayed, intensity 218320, 5 peptides, coverage 13.1, logFC 1.2, pValue 0.0009, adjPValue 0.00599.

**Sensitivity:** `$symbol = 'INS'`, `$comparisonId = 'CMP-ISL-T2D'` shows the label-free experiment assayed only 10 of 12 cases and 10 of 12 controls. `$symbol = 'ADIPOQ'`, `$comparisonId = 'CMP-LIV-MASLD'` shows measured false on the RNA-seq row and a protein result (logFC −1.6) on the TMT row: the S3 near miss.

## Interaction partners of a gene

**Parameters:** `$symbol = 'PIK3CG'`, `$minScore = 0.7`, `$comparisonId = 'CMP-LIV-MASLD'`

**Invariant:** Every partner has score at least 0.7; ordered by score descending; never PIK3CG itself.

**Expected:** 6 rows: PIK3R1 0.95, AKT1 0.91, PIK3CA 0.87, PDPK1 0.84 (partner protein logFC −0.363, adjusted p 0.175), PTEN 0.79 (logFC −1.2, adjusted p 0.00483), RAC1 0.73. PIK3R1, AKT1, PIK3CA and RAC1 have null partner results.

**Sensitivity:** `$minScore = 0.4` adds CCR2 0.66, MTOR 0.58, CXCL10 0.45 (partner protein logFC 1.6) and HSP90AA1 0.41 (10 rows).

## Changed proteins within two interaction hops

**Parameters:** `$symbol = 'CD36'`, `$comparisonId = 'CMP-LIV-MASLD'`, `$minScore = 0.7`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** Never CD36. Every partner is reachable within two hops through interactions all scoring 0.7 or more, and changed beyond the cutoffs in CMP-LIV-MASLD. Never SQSTM1 or SOD2 (reachable in two hops only through an interaction below 0.7) and never FASN, SREBF1, CCL2 or CXCL10 (three hops away at 0.7).

**Expected:** 6 rows: PLIN2 (1 hop, 2.9), LPL (1, −1.1), SCD (2, 1.9), FABP1 (2, −1.5), APOB (2, 1.4), PPARG (2, 1.3). PPARG's direct interaction with CD36 scores 0.69, so it is reached at 2 hops through FABP4.

**Sensitivity:** `$minScore = 0.5` gives 7 rows: PPARG becomes a 1-hop partner and SQSTM1 is added at 2 hops (through TLR4 at 0.52). Raising the bound to three hops would add FASN, SREBF1, CCL2 and CXCL10 — the reason the query stops at two.

## Candidate genes sharing processes with disease genes

**Parameters:** `$mondoId = 'MONDO:0005148'`, `$minScore = 0.5`, `$minSharedTerms = 2`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`

**Invariant:** Every candidate has no `RELATED_TO` type 2 diabetes mellitus at any score, shares at least two biological-process terms with known genes, and changed in CMP-ISL-T2D. Never DDIT3 (one shared process).

**Expected:** 1 row: GCG, 2 shared processes (glucose homeostasis, insulin secretion), changes `CMP-ISL-T2D transcript 1.3` and `CMP-ISL-T2D protein 1.2`. knownGenes is a set of known T2D genes carrying those terms.

**Sensitivity:** `$minSharedTerms = 1` gives 4 rows, adding DDIT3 (response to endoplasmic reticulum stress), DGAT1 (lipid storage, a transcript-only change of −1.197) and PIK3CG (insulin receptor signaling pathway). The GO annotations below the module defaults are drawn at random by the generator, so this candidate list is the most generator-dependent result in the file.

## Pathways with concordant changes

**Parameters:** `$comparisonId = 'CMP-LIV-MASLD'`, `$maxAdjP = 0.05`, `$minAbsLogFC = 1`, `$minGenes = 2`

**Invariant:** Every pathway has at least two concordant genes from the CMP-LIV-MASLD S1 set; hitFraction equals hits divided by members; ordered by hitFraction descending. linkedToStudiedDisease is true exactly for the pathways MASLD `INVOLVES_PATHWAY`.

**Expected:** 6 rows: PPARA activates gene expression (4 of 10, 0.4, linked: CD36, CPT1A, PLIN2, PPARA); Regulation of lipid metabolism by PPARalpha (5 of 14, 0.357, linked); Fatty acyl-CoA biosynthesis (2 of 6, 0.333, linked: FASN, SCD); Mitochondrial Fatty Acid Beta-Oxidation (2 of 8, 0.25, not linked: ACADL, CPT1A); Cytokine Signaling in Immune system and Extracellular matrix organization (2 of 14 each, 0.143, not linked).

**Sensitivity:** CMP-LIV-MASH returns Extracellular matrix organization (7 of 14) and Activation of Matrix Metalloproteinases (2 of 4), both linked to MASH; CMP-ISL-T2D returns Regulation of insulin secretion (3 of 8) and Integration of energy metabolism (3 of 12), both linked. `$minGenes = 1` gives 11 rows, adding five single-hit pathways.
