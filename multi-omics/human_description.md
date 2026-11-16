# Multi-Omics: Transcript and Protein Integration

Read transcriptomics and proteomics results together, so you can find the changes confirmed at both molecular layers, spot proteins regulated after transcription, and judge new targets against disease knowledge, interaction networks and pathways.

## Overview

### The industry

Drug discovery and translational research teams profile tissue from patients and healthy donors to learn what goes wrong in disease. Two of the most common profiles are **transcriptomics**, which measures messenger RNA (mRNA) by RNA sequencing (RNA-seq), and **proteomics**, which measures proteins by mass spectrometry. Each study compares a group of cases against controls and reports, for every gene or protein it measured, a fold change and a statistical confidence.

The two layers often disagree. A transcript can rise while its protein stays flat, because the cell controls how much protein is made and how fast it is broken down. A protein can change with no change in its transcript. Studies also differ in tissue, instrument and method, and a protein may simply go undetected — which is not the same as unchanged.

The hard part is reading it all together: lining up results for the same gene across layers, studies and platforms, keeping track of what each experiment actually measured, and placing each hit in what is already known about its diseases, interaction partners and pathways.

### What it helps with

A reference ontology that holds studies, measurements, results and prior knowledge in one connected structure turns cross-layer questions into direct lookups.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Which changes are real and functional, not just transcriptional noise? | A gene's transcript result and its protein's result hang off the same comparison, so genes changed in the same direction at both layers can be found in one step. |
| Which proteins are controlled after transcription? | Each experiment records what it detected, so a protein change with a measured, unchanged transcript is distinguishable from one whose transcript was never measured. |
| Is this candidate new for the disease, or already known? | Concordant changes are checked against scored gene-disease associations, with their evidence type, to separate known biology from novel leads. |
| Does the signal hold up across tissues and platforms? | Comparisons carry their tissue and their instruments, so a change can be counted across tissues, or across proteomics platforms, before it is trusted. |
| What does the evidence behind one result rest on? | Every result traces back to its experiments, platforms, methods, detection strength and the case and control samples assayed. |
| What else moves around a target, and in which pathways? | A scored protein interaction network, Gene Ontology annotations and pathway memberships place each hit among its partners and processes. |

## Ontology

The reference ontology has three parts. The study part records projects, the samples they collect, each sample's tissue and donor traits, and the experiments that profile them. The analysis part records comparisons between case and control samples and the genes and proteins each comparison found changed, together with what each experiment detected. The knowledge part links genes to the proteins they encode, genes to diseases, proteins to Gene Ontology terms, pathways and one another, and diseases to the pathways implicated in them. Identifiers follow the standards of each field, so external data joins on them directly.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Project` | A research study or programme grouping the samples collected under one protocol, such as a biopsy cohort. |
| `Sample` | A biological specimen taken from one donor, at one time, from one tissue. |
| `Tissue` | The anatomical tissue or structure a sample comes from, as an UBERON (Uber-anatomy Ontology) term. |
| `Phenotype` | A clinical trait or abnormality seen in a sample's donor, as a term from the Experimental Factor Ontology (EFO) or the Human Phenotype Ontology (HP). |
| `Experiment` | One omics profiling run: samples assayed together on one platform with one method. |
| `Comparison` | A statistical contrast between case and control samples — a differential expression or abundance analysis. |
| `Gene` | A protein-coding gene, identified by its Ensembl ID; the unit transcriptomics measures. |
| `Protein` | A protein, identified by its UniProtKB accession; the unit proteomics measures. |
| `Disease` | A disease or disorder, identified by its MONDO (Mondo Disease Ontology) term. |
| `GOTerm` | A Gene Ontology term: a biological process, molecular function or cellular component. |
| `Pathway` | A curated biological pathway, such as a Reactome pathway. |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Project` | `projectId` | String | Unique identifier of the project. |
| `Project` | `name` | String | Title of the project. |
| `Sample` | `sampleId` | String | Unique identifier of the sample. |
| `Sample` | `donorId` | String | Pseudonymous identifier of the donor; shared by samples from one donor's different tissues. Never a name or record number. |
| `Tissue` | `uberonId` | String | UBERON term identifier, such as `UBERON:` and seven digits. |
| `Tissue` | `name` | String | UBERON label of the tissue. |
| `Phenotype` | `phenotypeId` | String | Term identifier with an EFO, HP or MONDO prefix and seven digits. |
| `Phenotype` | `name` | String | Label of the phenotype term. |
| `Experiment` | `experimentId` | String | Unique identifier of the experiment. |
| `Experiment` | `name` | String | Title of the experiment. |
| `Experiment` | `omicsLayer` | String | The layer measured: `transcriptomics` (mRNA, recorded on genes) or `proteomics` (protein, recorded on proteins). |
| `Experiment` | `platform` | String | Instrument model the experiment ran on. |
| `Experiment` | `method` | String | Library preparation or acquisition method, such as RNA-seq, isobaric (TMT) labelling, label-free or data-independent acquisition. Quantities from different methods are not directly comparable. |
| `Comparison` | `comparisonId` | String | Unique identifier of the comparison. |
| `Comparison` | `name` | String | Description of the contrast, cases first. |
| `Comparison` | `comparisonType` | String | Design of the contrast, such as disease against control, more against less severe disease, or donors with against without a trait. |
| `Gene` | `ensemblId` | String | Ensembl stable gene ID, without a version suffix. |
| `Gene` | `symbol` | String | Approved HGNC gene symbol. Always present. |
| `Gene` | `name` | String | Approved HGNC gene name. |
| `Gene` | `hgncId` | String | HGNC identifier. |
| `Gene` | `ncbiGeneId` | String | NCBI Gene (Entrez) identifier, digits only. |
| `Protein` | `uniprotId` | String | UniProtKB accession, without an isoform suffix. |
| `Protein` | `name` | String | UniProt recommended protein name. |
| `Disease` | `mondoId` | String | MONDO term identifier. |
| `Disease` | `name` | String | MONDO label, in current nomenclature (for example, metabolic dysfunction-associated steatotic liver disease, formerly non-alcoholic fatty liver disease). |
| `GOTerm` | `goId` | String | Gene Ontology term identifier. |
| `GOTerm` | `name` | String | Gene Ontology label of the term. |
| `GOTerm` | `aspect` | String | The Gene Ontology aspect: `biological_process`, `molecular_function` or `cellular_component`. Always present. |
| `Pathway` | `pathwayId` | String | Stable identifier in the source database, such as a Reactome stable ID. |
| `Pathway` | `name` | String | Name of the pathway in its source database. |
| `Pathway` | `source` | String | Pathway database, such as Reactome, WikiPathways or KEGG. |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `HAS_SAMPLE` | `Project` → `Sample` | The project collected the sample. Every sample belongs to exactly one project; a project has one or more samples. |
| `TAKEN_FROM` | `Sample` → `Tissue` | The sample came from the tissue. Every sample has exactly one tissue. |
| `HAS_PHENOTYPE` | `Sample` → `Phenotype` | The donor showed the trait when the sample was taken. Any number either way. |
| `HAS_EXPERIMENT` | `Sample` → `Experiment` | The sample was assayed in the experiment. Every experiment assays at least one sample; a sample may be assayed in several. |
| `COMPARES` | `Comparison` → `Experiment` | The comparison analysed the experiment's data, normally one experiment per layer. Every comparison uses at least one. |
| `INCLUDES` | `Comparison` → `Sample` | The comparison placed the sample in its case or control group. Every comparison includes at least two samples; a sample may be in several comparisons. |
| `STUDIES_DISEASE` | `Comparison` → `Disease` | The comparison's cases have the disease, or a more severe form of it. Usually one disease; a comparison stratified by a trait may study none. |
| `HAS_VALUE` | `Experiment` → `Gene` | The transcriptomics experiment detected the gene's transcripts. Absence means not measured, not unchanged. |
| `HAS_VALUE` | `Experiment` → `Protein` | The proteomics experiment detected the protein. Absence means not measured, not unchanged. |
| `FOUND_DIFFERENTIAL` | `Comparison` → `Gene` | The comparison found the gene's transcript level different between cases and controls (nominal p-value below 0.05). At most one per comparison and gene. |
| `FOUND_DIFFERENTIAL` | `Comparison` → `Protein` | The comparison found the protein's level different between cases and controls (nominal p-value below 0.05). At most one per comparison and protein. |
| `CODES` | `Gene` → `Protein` | The gene encodes the protein. Every protein has exactly one gene. |
| `RELATED_TO` | `Gene` → `Disease` | Curated knowledge associates the gene with the disease. At most one per gene and disease; absence means no recorded association. |
| `ASSOCIATED_WITH` | `Protein` → `GOTerm` | The protein is annotated with the Gene Ontology term. Any number either way. |
| `INTERACTS_WITH` | `Protein` → `Protein` | The two proteins interact, physically or functionally. Symmetric: each pair is recorded once and read both ways. |
| `PARTICIPATES_IN` | `Protein` → `Pathway` | The protein takes part in the pathway. Any number either way. |
| `INVOLVES_PATHWAY` | `Disease` → `Pathway` | Curated knowledge implicates the pathway in the disease's mechanism. Any number either way. |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `INCLUDES` | `group` | String | `case` (the condition of interest) or `control` (the reference). Always present. |
| `HAS_VALUE` (to `Gene`) | `baseMean` | Float | Mean normalised read count for the gene across the experiment's samples: how strongly it is expressed, not how much it changed. |
| `HAS_VALUE` (to `Protein`) | `intensity` | Float | Mean normalised protein intensity across the experiment's samples, linear scale, arbitrary units; comparable within one experiment only. |
| `HAS_VALUE` (to `Protein`) | `peptides` | Integer | Number of unique peptides identified for the protein. |
| `HAS_VALUE` (to `Protein`) | `coverage` | Float | Percentage of the protein's sequence covered by identified peptides, 0 to 100. |
| `FOUND_DIFFERENTIAL` | `logFC` | Float | Log2 fold change, cases over controls: positive means higher in cases, 1 means twofold. Always present. |
| `FOUND_DIFFERENTIAL` | `pValue` | Float | Nominal p-value of the comparison's test; below 0.05 on every recorded result. Always present. |
| `FOUND_DIFFERENTIAL` | `adjPValue` | Float | Benjamini-Hochberg adjusted p-value (false discovery rate) across every feature the comparison tested in that layer. Always present. |
| `RELATED_TO` | `score` | Float | Overall association score from 0 to 1; higher means stronger evidence. Scores from different resources are not on one scale. Always present. |
| `RELATED_TO` | `evidenceType` | String | Strongest type of evidence behind the association, such as genetic association, known drug, literature or animal model. |
| `INTERACTS_WITH` | `score` | Float | Combined confidence of the interaction from 0 to 1, as in STRING; 0.7 and above is high confidence. Always present. |
