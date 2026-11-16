---
name: multi-omics
description: Integrate transcriptomics (RNA-seq) and mass-spectrometry proteomics in a Neo4j graph for life-sciences research and drug discovery. Connects samples, tissues, phenotypes, omics experiments and case-control comparisons to the genes and proteins they find changed, with gene-disease associations, Gene Ontology annotations, Reactome pathways and protein-protein interactions. Provides a reference ontology, bundled sample data from a metabolic-disease programme (MASLD and MASH liver, type 2 diabetes islets, metabolic-syndrome adipose), and Cypher for concordant transcript-protein changes, post-transcriptional candidates, novel targets, cross-tissue signatures, cross-platform replication, evidence trails, interaction neighbourhoods, Gene Ontology guilt by association, and pathway overlap.
metadata:
  neo4j-card-title: "Multi-Omics: Transcript and Protein Integration"
  neo4j-card-category: Healthcare & Life Sciences
  neo4j-card-description: Read RNA-seq and proteomics results side by side to find changes confirmed at both layers, proteins regulated after transcription, and new targets in their disease, network and pathway context.
---

# Multi-Omics: Transcript and Protein Integration

Use this skill for translational and discovery scientists, bioinformaticians and data engineers in life sciences who hold transcriptomics and proteomics results for the same studies and want to read them together: to find genes whose change is confirmed at both the transcript and protein layer, proteins that change without their transcript, and candidate targets placed in their disease, interaction-network and pathway context.

Source references:

- <https://github.com/neo4j-documentation/field-industry-use-cases/blob/main/modules/ROOT/pages/life-sciences/research-development/multi-omics.adoc> — Neo4j multi-omics use case
- <https://github.com/neo4j-documentation/field-industry-use-cases/blob/main/modules/ROOT/pages/life-sciences/research-development/single-omics.adoc> — Neo4j single-omics use case

Disclaimer: the bundled data is synthetic. Gene, protein, disease, tissue, phenotype, Gene Ontology and pathway identifiers and names are real, but every measurement, statistic, gene-disease association and score, annotation, pathway membership and interaction score was generated for the demo. Treat query results as research leads for a scientist to review, never as biological findings, clinical advice or evidence for a target.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: a change in a gene's transcript is not always a change in its protein, and the protein is what acts. Holding both layers, and what each experiment actually measured, in one graph turns "which changes are real, which are regulated after transcription, and which are new for this disease" into single traversals — and links each hit to its interaction partners and pathways.
- The bundled sample data is a synthetic metabolic-disease programme (liver biopsies for MASLD and MASH, pancreatic islets for type 2 diabetes, visceral fat for metabolic syndrome and insulin resistance) built on real gene and protein identifiers. It deliberately seeds the patterns the queries look for, alongside ordinary background and near misses.
- What you can help with: explaining the reference ontology, walking through the query patterns, importing the sample data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Study design: `(Project {projectId, name})-[:HAS_SAMPLE]->(Sample {sampleId, donorId})-[:TAKEN_FROM]->(Tissue {uberonId, name})`; `(Sample)-[:HAS_PHENOTYPE]->(Phenotype {phenotypeId, name})`. One donor may give samples from several tissues, which share `donorId`.
- Measurement: `(Sample)-[:HAS_EXPERIMENT]->(Experiment {experimentId, name, omicsLayer, platform, method})`, where `omicsLayer` is `transcriptomics` or `proteomics`. `(Experiment)-[:HAS_VALUE {baseMean}]->(Gene)` for transcriptomics and `(Experiment)-[:HAS_VALUE {intensity, peptides, coverage}]->(Protein)` for proteomics. `HAS_VALUE` exists only for what the experiment detected: its absence means not measured, never unchanged.
- Analysis: `(Comparison {comparisonId, name, comparisonType})-[:INCLUDES {group}]->(Sample)` with `group` `case` or `control`; `(Comparison)-[:COMPARES]->(Experiment)`, normally one experiment per layer; `(Comparison)-[:STUDIES_DISEASE]->(Disease {mondoId, name})`. Results: `(Comparison)-[:FOUND_DIFFERENTIAL {logFC, pValue, adjPValue}]->(Gene|Protein)` — one relationship type for both layers, told apart by the end label, recorded only for results with nominal p below 0.05.
- Conventions: `logFC` is log2 fold change, cases over controls (positive means higher in cases, 1 means twofold); `adjPValue` is the Benjamini-Hochberg false discovery rate across every feature the comparison tested in that layer. `baseMean` is mean normalised counts; `intensity` is linear, arbitrary units, comparable within one experiment only; `coverage` is percent.
- Molecular knowledge: `(Gene {ensemblId, symbol, name, hgncId, ncbiGeneId})-[:CODES]->(Protein {uniprotId, name})`, exactly one gene per protein; `(Gene)-[:RELATED_TO {score, evidenceType}]->(Disease)`, score 0–1, evidence types in Open Targets' names; `(Protein)-[:ASSOCIATED_WITH]->(GOTerm {goId, name, aspect})`; `(Protein)-[:PARTICIPATES_IN]->(Pathway {pathwayId, name, source})`; `(Disease)-[:INVOLVES_PATHWAY]->(Pathway)`; `(Protein)-[:INTERACTS_WITH {score}]-(Protein)`, symmetric, stored once per pair, score 0–1 as STRING's combined score (0.7 high confidence, 0.4 medium).
- Identifiers are the standard ones for each concept — Ensembl, HGNC and NCBI Gene for genes, UniProtKB for proteins, MONDO for diseases (which uses current names, so NAFLD is MASLD and NASH is MASH), UBERON for tissues, EFO or HP for phenotypes, GO and Reactome — so a user's own data maps on by identifier, not by name.
- How it departs from the source use case: phenotypes and GO terms have readable labels (`Phenotype`, `GOTerm`) rather than `EFO` and `GO`; NCBI and HGNC cross-references are properties on `Gene` rather than separate nodes; case and control membership is one `INCLUDES` relationship with a `group`; `FOUND_DIFFERENTIAL` drops the `data_type`, `regulated` and `significance` properties, which the end label and the sign and adjusted p-value of `logFC` already carry; `HAS_VALUE` holds what an experiment detected rather than repeating fold changes; pathway membership is direct from protein to pathway, as Reactome publishes it; and every relationship, including the many-to-many ones, loads through Import.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases`, allowed values (`one_of`, `pattern`) and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Contrast`, `Assay` or `DE result` often names the user's equivalent), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Measured feature, per layer | `Gene` (transcript), `Protein` (protein) | One node per gene and per protein, keyed by a standard identifier, so results from different experiments meet on it |
| Gene-to-product link | `CODES` | A link from each gene to the protein it encodes; without it the two layers cannot be compared |
| Differential result | `Comparison`, `FOUND_DIFFERENTIAL` | A contrast node with per-feature fold change and adjusted p-value, for both layers, sign giving direction |
| What was measured | `Experiment`, `HAS_VALUE`, `COMPARES` | A record of which features each experiment detected and which experiments a contrast used; without it "unchanged" and "not measured" look the same |
| Study context | `Sample`, `INCLUDES`, `Tissue`, `Phenotype`, `STUDIES_DISEASE` | Contrast membership by case or control, each sample's tissue and traits, and the disease the contrast studies |
| Prior knowledge | `RELATED_TO`, `INTERACTS_WITH`, `ASSOCIATED_WITH`, `PARTICIPATES_IN` | Scored gene-disease links, a scored protein interaction network, and protein annotations to processes and pathways |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes. No bundled query writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.6 or later (including Aura), Cypher 5: the queries use `COUNT {}`, `COLLECT {}` and `EXISTS {}` subqueries. No APOC or GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of the `@sample` anchor (for example its `$comparisonId`) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Start with the Comparison overview query to choose a comparison; a comparison with only one omics layer cannot return concordant changes or post-transcriptional candidates.
- Never filter on `FOUND_DIFFERENTIAL` alone to say a gene is unchanged: check `HAS_VALUE` from the comparison's experiment for that layer first.
- Compare fold changes, never `HAS_VALUE` intensities, across platforms or methods; raw intensities are not on a common scale.
- Traverse `INTERACTS_WITH` without a direction, and keep every variable-length walk at two hops or fewer with a score floor on every hop.
- Agreement between layers is evidence that a change is real, not that it causes disease. Pathway overlap here is a ranking, not a statistical enrichment test; say so when presenting it.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
