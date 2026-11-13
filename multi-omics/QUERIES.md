# Multi-Omics Data Integration — Queries

Runnable Cypher for the reference ontology in `ONTOLOGY.json`, simplest first.

## Prerequisites

- Neo4j 5.6 or later (including Aura and 2025.x releases), Cypher 5. The queries use `COUNT {}`, `COLLECT {}` and `EXISTS {}` subqueries. No APOC or GDS.
- The reference ontology imported through the Import flow, either from the bundled sample CSVs or from the user's own data mapped onto it. No post-import setup is needed, and no query writes to the database.
- A `FOUND_DIFFERENTIAL` relationship records a result that reached a nominal p-value below 0.05. Every query applies its own stricter cutoff on `adjPValue` (Benjamini-Hochberg false discovery rate) and on `logFC` (log2 fold change, cases over controls). Direction is the sign of `logFC`.
- The omics layer of a result is the label at its far end: `Gene` for transcriptomics, `Protein` for proteomics. A gene and its protein meet through `CODES`.
- A `HAS_VALUE` relationship exists only where an experiment detected a gene or protein, so its absence means "not measured", never "unchanged".
- `INTERACTS_WITH` is symmetric and stored once per pair, so every query traverses it without a direction.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit. A database that stores only differential results, with no record of what each experiment measured, still supports concordance but not the post-transcriptional check, which must tell "unchanged" from "not measured".
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Comparison overview

```cypher
/*
 * @name           Comparison overview
 * @description    Lists every comparison with its design, tissue, studied
 *                 disease, the experiments it analysed, the size of its case
 *                 and control groups, and how many genes and proteins it
 *                 found changed beyond the cutoffs.
 * @params         maxAdjP - Largest Benjamini-Hochberg adjusted p-value
 *                     (false discovery rate) counted as changed. Start at 0.05,
 *                     the conventional false discovery rate.
 *                 minAbsLogFC - Smallest absolute log2 fold change counted as
 *                     changed. Start at 1, a twofold change.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per comparison: comparisonId, comparison, design,
 *                 tissues, diseases, experiments (layer, platform and
 *                 method), cases, controls, changedGenes, changedProteins.
 * @usage          The entry point: run it first to choose a comparisonId for
 *                 the other queries and to see which comparisons have both
 *                 omics layers. A comparison with no transcriptomics
 *                 experiment can never return concordant changes. Changed
 *                 counts are transcript and protein results separately, not
 *                 genes changed in both.
 * @tags           overview, comparison, study design, differential expression
 * @sample         Bundled sample data only: $maxAdjP = 0.05, $minAbsLogFC = 1
 *                 returns 6 rows; CMP-LIV-MASLD has 22 cases, 8 controls,
 *                 22 changed genes and 23 changed proteins, and CMP-LIV-DIA
 *                 has no transcriptomics experiment and 0 changed genes.
 */
MATCH (c:Comparison)
RETURN c.comparisonId AS comparisonId, c.name AS comparison, c.comparisonType AS design,
       COLLECT { MATCH (c)-[:INCLUDES]->(:Sample)-[:TAKEN_FROM]->(t:Tissue) RETURN DISTINCT t.name AS tissue ORDER BY tissue } AS tissues,
       COLLECT { MATCH (c)-[:STUDIES_DISEASE]->(d:Disease) RETURN d.name AS disease ORDER BY disease } AS diseases,
       COLLECT { MATCH (c)-[:COMPARES]->(e:Experiment)
                 RETURN e.omicsLayer + ': ' + e.platform + ' (' + e.method + ')' AS experiment ORDER BY experiment } AS experiments,
       COUNT { (c)-[:INCLUDES {group: 'case'}]->(:Sample) } AS cases,
       COUNT { (c)-[:INCLUDES {group: 'control'}]->(:Sample) } AS controls,
       COUNT { (c)-[r:FOUND_DIFFERENTIAL]->(:Gene) WHERE r.adjPValue <= $maxAdjP AND abs(r.logFC) >= $minAbsLogFC } AS changedGenes,
       COUNT { (c)-[r:FOUND_DIFFERENTIAL]->(:Protein) WHERE r.adjPValue <= $maxAdjP AND abs(r.logFC) >= $minAbsLogFC } AS changedProteins
ORDER BY comparisonId
```

## Comparisons whose cases carry a phenotype

```cypher
/*
 * @name           Comparisons whose cases carry a phenotype
 * @description    For a phenotype, finds every comparison whose case group
 *                 includes samples from donors with that phenotype, and the
 *                 share of cases and of controls that carry it.
 * @params         phenotypeId - CURIE of the phenotype term (EFO, HP or
 *                     MONDO), e.g. 'HP:0000855' for insulin resistance.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per comparison with at least one case carrying the
 *                 phenotype: phenotype, comparisonId, comparison, casesWith,
 *                 cases, caseFraction, controlsWith, controls,
 *                 controlFraction. Ordered by caseFraction, highest first.
 * @usage          Use to find which contrasts speak to a clinical trait
 *                 before reading their results. A high case fraction with a
 *                 low control fraction means the comparison separates the
 *                 trait; similar fractions in both groups mean the trait is
 *                 not what distinguishes cases from controls, and the
 *                 comparison's results say little about it.
 * @tags           phenotype, trait, cohort, comparison, EFO, HPO
 * @sample         Bundled sample data only: $phenotypeId = 'HP:0000855'
 *                 returns 6 rows, led by CMP-ADI-IR (12 of 12 cases, 0 of 14
 *                 controls); CMP-LIV-MASH carries it in 7 of 10 cases and
 *                 9 of 12 controls.
 */
MATCH (ph:Phenotype {phenotypeId: $phenotypeId})
MATCH (c:Comparison)-[i:INCLUDES]->(s:Sample)
WITH ph, c, i.group AS grp, EXISTS { (s)-[:HAS_PHENOTYPE]->(ph) } AS has
WITH ph, c,
     sum(CASE WHEN grp = 'case' THEN 1 ELSE 0 END) AS cases,
     sum(CASE WHEN grp = 'case' AND has THEN 1 ELSE 0 END) AS casesWith,
     sum(CASE WHEN grp = 'control' THEN 1 ELSE 0 END) AS controls,
     sum(CASE WHEN grp = 'control' AND has THEN 1 ELSE 0 END) AS controlsWith
WHERE casesWith > 0
RETURN ph.name AS phenotype, c.comparisonId AS comparisonId, c.name AS comparison,
       casesWith, cases, round(toFloat(casesWith) / cases, 3) AS caseFraction,
       controlsWith, controls, round(toFloat(controlsWith) / controls, 3) AS controlFraction
ORDER BY caseFraction DESC, comparisonId
```

## Disease associations of a gene

```cypher
/*
 * @name           Disease associations of a gene
 * @description    Lists every disease a gene is associated with, with the
 *                 association score and evidence type, and the comparisons
 *                 studying that disease in which the gene's transcript or
 *                 protein changed beyond the cutoffs.
 * @params         symbol - HGNC gene symbol, e.g. 'PPARG'.
 *                 maxAdjP - Largest adjusted p-value counted as changed.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change counted as
 *                     changed. Start at 1.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per associated disease: gene, mondoId, disease,
 *                 score (0-1), evidenceType, and changes, a list of
 *                 "comparisonId layer logFC" entries for comparisons that
 *                 study the disease. Ordered by score, highest first.
 * @usage          A safety and indication check before choosing a target:
 *                 associations outside the disease of interest are possible
 *                 off-target liabilities or repurposing leads. Scores from
 *                 different resources are not on one scale; compare them
 *                 within a source only. An empty changes list means no
 *                 comparison of that disease showed the gene changed, or none
 *                 studies it.
 * @tags           gene, disease association, safety, off-target, indication
 * @sample         Bundled sample data only: $symbol = 'PPARG' returns 6 rows,
 *                 from type 2 diabetes mellitus (0.89) to breast cancer
 *                 (0.3); only the MASLD row has changes, transcript 1.6 and
 *                 protein 1.3 in CMP-LIV-MASLD.
 */
MATCH (g:Gene {symbol: $symbol})-[r:RELATED_TO]->(d:Disease)
RETURN g.symbol AS gene, d.mondoId AS mondoId, d.name AS disease, r.score AS score, r.evidenceType AS evidenceType,
       COLLECT {
         MATCH (d)<-[:STUDIES_DISEASE]-(c:Comparison)-[fd:FOUND_DIFFERENTIAL]->(f)
         WHERE (f = g OR (g)-[:CODES]->(f)) AND fd.adjPValue <= $maxAdjP AND abs(fd.logFC) >= $minAbsLogFC
         RETURN c.comparisonId + CASE WHEN f:Gene THEN ' transcript ' ELSE ' protein ' END + toString(fd.logFC) AS change
         ORDER BY change
       } AS changes
ORDER BY score DESC, disease
```

## Concordant transcript and protein changes

```cypher
/*
 * @name           Concordant transcript and protein changes
 * @description    Finds genes whose transcript and protein both changed
 *                 beyond the cutoffs in the same direction in one
 *                 comparison: the highest-confidence multi-omics signal.
 * @params         comparisonId - The comparison to read, from the
 *                     Comparison overview query.
 *                 maxAdjP - Largest adjusted p-value accepted in each layer.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change accepted
 *                     in each layer. Start at 1.
 * @prerequisites  The comparison must compare a transcriptomics and a
 *                 proteomics experiment.
 * @returns        One row per gene: gene, protein (UniProt accession),
 *                 direction ('up' or 'down', cases over controls),
 *                 transcriptLogFC, proteinLogFC, transcriptAdjP,
 *                 proteinAdjP. Ordered by the mean of the two fold changes,
 *                 largest absolute first.
 * @usage          The headline multi-omics question. Both layers share one
 *                 relationship type, so one pattern from the comparison reaches
 *                 the gene, follows CODES to its protein and returns to the
 *                 comparison. Agreement between layers raises confidence
 *                 that a change is real and functional, but it is not
 *                 evidence of causation. Loosen minAbsLogFC towards 0.58
 *                 (1.5-fold) for a longer list.
 * @tags           concordance, multi-omics, transcriptomics, proteomics, signature
 * @sample         Bundled sample data only: $comparisonId = 'CMP-LIV-MASLD'
 *                 returns 15 rows: 11 up, led by PLIN2 (2.6 transcript, 2.9
 *                 protein) and CD36, and 4 down (ADH4, ACADL, PPARA, CPT1A).
 */
MATCH (c:Comparison {comparisonId: $comparisonId})-[rna:FOUND_DIFFERENTIAL]->(g:Gene)-[:CODES]->(p:Protein)<-[prot:FOUND_DIFFERENTIAL]-(c)
WHERE rna.adjPValue <= $maxAdjP AND prot.adjPValue <= $maxAdjP
  AND abs(rna.logFC) >= $minAbsLogFC AND abs(prot.logFC) >= $minAbsLogFC
  AND sign(rna.logFC) = sign(prot.logFC)
RETURN g.symbol AS gene, p.uniprotId AS protein, CASE WHEN rna.logFC > 0 THEN 'up' ELSE 'down' END AS direction,
       rna.logFC AS transcriptLogFC, prot.logFC AS proteinLogFC,
       rna.adjPValue AS transcriptAdjP, prot.adjPValue AS proteinAdjP
ORDER BY abs(transcriptLogFC + proteinLogFC) DESC, gene
```

## Post-transcriptional candidates

```cypher
/*
 * @name           Post-transcriptional candidates
 * @description    Finds proteins that changed beyond the cutoffs in a
 *                 comparison while their gene's transcript, measured in the
 *                 same comparison, did not change or changed the opposite
 *                 way: candidates for regulation after transcription, such as
 *                 altered translation or protein turnover.
 * @params         comparisonId - The comparison to read.
 *                 maxAdjP - Largest adjusted p-value for a significant
 *                     change, in either layer. Start at 0.05.
 *                 minAbsLogFC - Smallest absolute protein log2 fold change.
 *                     Start at 1.
 * @prerequisites  The comparison must compare a transcriptomics and a
 *                 proteomics experiment.
 * @returns        One row per protein: gene, protein, pattern ('transcript
 *                 unchanged' or 'opposite direction'), proteinLogFC,
 *                 proteinAdjP, transcriptLogFC and transcriptAdjP (null where
 *                 the transcript did not reach the nominal cutoff), and
 *                 transcriptBaseMean, proof the transcript was measured.
 * @usage          The HAS_VALUE match is the point of the query: without it a
 *                 protein whose transcript was never measured, such as a
 *                 circulating protein carried into the tissue by blood, would
 *                 look post-transcriptional. A transcript that moved in the
 *                 same direction at any significant size is excluded, however
 *                 small. Treat each row as a lead for follow-up, since
 *                 measurement noise and timing differences between layers
 *                 also produce discordance.
 * @tags           post-transcriptional, discordance, proteomics, translation, turnover
 * @sample         Bundled sample data only: $comparisonId = 'CMP-LIV-MASLD'
 *                 returns 6 rows: SQSTM1 (protein 1.8), FABP1, APOB, PTEN and
 *                 SOD2 with the transcript unchanged, and LPL in the opposite
 *                 direction (transcript 1.2, protein -1.1).
 */
MATCH (c:Comparison {comparisonId: $comparisonId})-[prot:FOUND_DIFFERENTIAL]->(p:Protein)<-[:CODES]-(g:Gene)
WHERE prot.adjPValue <= $maxAdjP AND abs(prot.logFC) >= $minAbsLogFC
MATCH (c)-[:COMPARES]->(:Experiment {omicsLayer: 'transcriptomics'})-[hv:HAS_VALUE]->(g)
OPTIONAL MATCH (c)-[rna:FOUND_DIFFERENTIAL]->(g)
WITH g, p, prot, hv, rna,
     CASE WHEN rna IS NULL OR rna.adjPValue > $maxAdjP THEN 'transcript unchanged'
          WHEN sign(rna.logFC) <> sign(prot.logFC) THEN 'opposite direction' END AS pattern
WHERE pattern IS NOT NULL
RETURN g.symbol AS gene, p.uniprotId AS protein, pattern,
       prot.logFC AS proteinLogFC, prot.adjPValue AS proteinAdjP,
       rna.logFC AS transcriptLogFC, rna.adjPValue AS transcriptAdjP, hv.baseMean AS transcriptBaseMean
ORDER BY abs(proteinLogFC) DESC, gene
```

## Novel targets among concordant changes

```cypher
/*
 * @name           Novel targets among concordant changes
 * @description    Finds genes concordantly changed in a comparison, in both
 *                 transcript and protein, that have no association with the
 *                 comparison's studied disease at or above a score: changes
 *                 the existing disease knowledge does not explain.
 * @params         comparisonId - The comparison to read. It must study a
 *                     disease.
 *                 maxAdjP - Largest adjusted p-value accepted in each layer.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change accepted
 *                     in each layer. Start at 1.
 *                 minScore - Association score at or above which a gene
 *                     counts as already known for the disease. Start at 0.3,
 *                     a starting point with no strong prior; raise it to
 *                     treat weakly supported associations as novel too.
 * @prerequisites  The comparison must compare a transcriptomics and a
 *                 proteomics experiment, and study at least one disease.
 * @returns        One row per gene and studied disease: gene, disease,
 *                 transcriptLogFC, proteinLogFC, existingScore (null when
 *                 there is no association at all), and otherDiseases the
 *                 gene is associated with at or above minScore.
 * @usage          A target-discovery shortlist. otherDiseases is context:
 *                 a gene already linked to a related disease is a less
 *                 surprising lead than one with no associations. No row
 *                 means every concordant gene is already known for the
 *                 disease, or the comparison studies no disease.
 * @tags           target discovery, novelty, disease association, concordance
 * @sample         Bundled sample data only: $comparisonId = 'CMP-LIV-MASLD',
 *                 $minScore = 0.3 returns 6 rows: CXCL10, ACADL, ADH4,
 *                 PIK3CG, TIMP1 with no MASLD association, and CPT1A with a
 *                 weak one (0.22).
 */
MATCH (c:Comparison {comparisonId: $comparisonId})-[:STUDIES_DISEASE]->(d:Disease)
MATCH (c)-[rna:FOUND_DIFFERENTIAL]->(g:Gene)-[:CODES]->(p:Protein)<-[prot:FOUND_DIFFERENTIAL]-(c)
WHERE rna.adjPValue <= $maxAdjP AND prot.adjPValue <= $maxAdjP
  AND abs(rna.logFC) >= $minAbsLogFC AND abs(prot.logFC) >= $minAbsLogFC
  AND sign(rna.logFC) = sign(prot.logFC)
OPTIONAL MATCH (g)-[r:RELATED_TO]->(d)
WITH g, d, rna, prot, r
WHERE r IS NULL OR r.score < $minScore
RETURN g.symbol AS gene, d.name AS disease, rna.logFC AS transcriptLogFC, prot.logFC AS proteinLogFC,
       r.score AS existingScore,
       COLLECT { MATCH (g)-[o:RELATED_TO]->(od:Disease) WHERE o.score >= $minScore RETURN od.name AS name ORDER BY name } AS otherDiseases
ORDER BY abs(transcriptLogFC + proteinLogFC) DESC, gene
```

## Concordant changes shared across tissues

```cypher
/*
 * @name           Concordant changes shared across tissues
 * @description    Finds genes concordantly changed, in both transcript and
 *                 protein, in comparisons drawn from at least a given number
 *                 of different tissues: a candidate systemic signature.
 * @params         maxAdjP - Largest adjusted p-value accepted in each layer.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change accepted
 *                     in each layer. Start at 1.
 *                 minTissues - Fewest distinct tissues. Start at 2, the least
 *                     that makes a change cross-tissue.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per gene: gene, tissueCount, tissues, and
 *                 comparisons, each as "comparisonId (up|down)". Ordered by
 *                 tissueCount, then number of comparisons.
 * @usage          A comparison's tissue is read from the samples it includes.
 *                 Several comparisons from one tissue count once, so a gene
 *                 changed in two liver comparisons does not qualify. Check
 *                 the directions: the same gene changed in opposite
 *                 directions in different tissues is a tissue-specific
 *                 response, not a shared signature. The two lists are
 *                 collected without an order.
 * @tags           cross-tissue, systemic, signature, concordance, replication
 * @sample         Bundled sample data only: $minTissues = 2 returns 4 rows:
 *                 PIK3CG in 3 tissues (liver, islet, visceral adipose), then
 *                 CCL2, SPP1 and CD36 in liver and visceral adipose.
 */
MATCH (c:Comparison)-[rna:FOUND_DIFFERENTIAL]->(g:Gene)-[:CODES]->(p:Protein)<-[prot:FOUND_DIFFERENTIAL]-(c)
WHERE rna.adjPValue <= $maxAdjP AND prot.adjPValue <= $maxAdjP
  AND abs(rna.logFC) >= $minAbsLogFC AND abs(prot.logFC) >= $minAbsLogFC
  AND sign(rna.logFC) = sign(prot.logFC)
MATCH (c)-[:INCLUDES]->(:Sample)-[:TAKEN_FROM]->(t:Tissue)
WITH g, collect(DISTINCT t.name) AS tissues,
     collect(DISTINCT c.comparisonId + CASE WHEN rna.logFC > 0 THEN ' (up)' ELSE ' (down)' END) AS comparisons
WHERE size(tissues) >= $minTissues
RETURN g.symbol AS gene, size(tissues) AS tissueCount, tissues, comparisons
ORDER BY tissueCount DESC, size(comparisons) DESC, gene
```

## Protein changes replicated across platforms

```cypher
/*
 * @name           Protein changes replicated across platforms
 * @description    For a disease, finds proteins that changed beyond the
 *                 cutoffs in the same direction in comparisons whose
 *                 proteomics ran on different instrument platforms.
 * @params         mondoId - MONDO CURIE of the disease, e.g. 'MONDO:0013209'.
 *                 maxAdjP - Largest adjusted p-value accepted. Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change accepted.
 *                     Start at 1.
 *                 minPlatforms - Fewest distinct platforms. Start at 2, the
 *                     least that makes a change replicated.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per protein and direction: gene, protein,
 *                 direction, platforms, and results, each as
 *                 "comparisonId: logFC". Ordered by gene.
 * @usage          Proteomics platforms and methods (TMT labelling,
 *                 label-free, data-independent acquisition) differ in depth
 *                 and bias; a change seen on two of them is less likely to be
 *                 a platform artefact. Compare fold changes, never the raw
 *                 HAS_VALUE intensities, across platforms. The platform is
 *                 read from the comparison's proteomics experiment, so a
 *                 comparison that combines several proteomics experiments
 *                 counts each of their platforms.
 * @tags           replication, proteomics, platform, batch effect, robustness
 * @sample         Bundled sample data only: $mondoId = 'MONDO:0013209'
 *                 returns 7 rows, each seen on Orbitrap Fusion Lumos and
 *                 timsTOF Pro: ACADL, CD36, CPT1A, FASN, PLIN2, SCD, SQSTM1.
 */
MATCH (d:Disease {mondoId: $mondoId})<-[:STUDIES_DISEASE]-(c:Comparison)-[fd:FOUND_DIFFERENTIAL]->(p:Protein)
WHERE fd.adjPValue <= $maxAdjP AND abs(fd.logFC) >= $minAbsLogFC
MATCH (c)-[:COMPARES]->(e:Experiment {omicsLayer: 'proteomics'})
MATCH (g:Gene)-[:CODES]->(p)
WITH g, p, CASE WHEN fd.logFC > 0 THEN 'up' ELSE 'down' END AS direction,
     collect(DISTINCT e.platform) AS platforms, collect(DISTINCT c.comparisonId + ': ' + toString(fd.logFC)) AS results
WHERE size(platforms) >= $minPlatforms
RETURN g.symbol AS gene, p.uniprotId AS protein, direction, platforms, results
ORDER BY gene, direction
```

## Evidence trail for a gene in a comparison

```cypher
/*
 * @name           Evidence trail for a gene in a comparison
 * @description    Shows, layer by layer, the evidence behind a gene's result
 *                 in one comparison: each experiment the comparison
 *                 analysed, its platform and method, how many of the
 *                 comparison's cases and controls it assayed, whether it
 *                 detected the gene or protein and at what abundance, and
 *                 the differential result.
 * @params         symbol - HGNC gene symbol, e.g. 'PIK3CG'.
 *                 comparisonId - The comparison to read.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per experiment the comparison analysed (and per
 *                 protein, for a gene with several): comparisonId,
 *                 experimentId, omicsLayer, platform, method, casesAssayed,
 *                 controlsAssayed, measured (true or false), baseMean
 *                 (transcriptomics), intensity, peptides and coverage
 *                 (proteomics), logFC, pValue, adjPValue. A null logFC
 *                 with measured true means tested but below the nominal
 *                 cutoff.
 * @usage          Use before reporting any finding, to show what it rests on.
 *                 Low peptide counts or low coverage make a protein result
 *                 fragile; an experiment that assayed only part of the
 *                 comparison's samples has less power than the group sizes
 *                 suggest.
 * @tags           provenance, evidence, experiment, platform, quality
 * @sample         Bundled sample data only: $symbol = 'PIK3CG',
 *                 $comparisonId = 'CMP-LIV-MASLD' returns 2 rows: EXP-LIV-RNA
 *                 (22 cases, 8 controls, logFC 1.4) and EXP-LIV-TMT
 *                 (5 peptides, coverage 13.1, logFC 1.2).
 */
MATCH (c:Comparison {comparisonId: $comparisonId})-[:COMPARES]->(e:Experiment)
MATCH (g:Gene {symbol: $symbol})-[:CODES]->(p:Protein)
WITH c, e, CASE WHEN e.omicsLayer = 'transcriptomics' THEN g ELSE p END AS f
OPTIONAL MATCH (e)-[hv:HAS_VALUE]->(f)
OPTIONAL MATCH (c)-[fd:FOUND_DIFFERENTIAL]->(f)
RETURN DISTINCT c.comparisonId AS comparisonId, e.experimentId AS experimentId, e.omicsLayer AS omicsLayer,
       e.platform AS platform, e.method AS method,
       COUNT { (c)-[:INCLUDES {group: 'case'}]->(:Sample)-[:HAS_EXPERIMENT]->(e) } AS casesAssayed,
       COUNT { (c)-[:INCLUDES {group: 'control'}]->(:Sample)-[:HAS_EXPERIMENT]->(e) } AS controlsAssayed,
       hv IS NOT NULL AS measured, hv.baseMean AS baseMean, hv.intensity AS intensity, hv.peptides AS peptides,
       hv.coverage AS coverage, fd.logFC AS logFC, fd.pValue AS pValue, fd.adjPValue AS adjPValue
ORDER BY omicsLayer DESC, experimentId
```

## Interaction partners of a gene

```cypher
/*
 * @name           Interaction partners of a gene
 * @description    Lists the interaction partners of the protein a gene
 *                 encodes, above a confidence score, with each partner's
 *                 protein result in a comparison.
 * @params         symbol - HGNC gene symbol, e.g. 'PIK3CG'.
 *                 minScore - Smallest interaction score, 0-1. Start at 0.7,
 *                     STRING's high-confidence band; 0.4 is its medium band.
 *                 comparisonId - The comparison whose protein results to
 *                     show alongside each partner.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per partner: gene, partner, partnerProtein,
 *                 score, partnerProteinLogFC and partnerProteinAdjP (null
 *                 when the partner protein had no result in the comparison).
 *                 Ordered by score, highest first.
 * @usage          The first step from a single hit to its network: a target
 *                 whose partners also change is more likely to sit in an
 *                 affected pathway. The partner result is shown at the
 *                 nominal cutoff, with no adjusted p-value filter, so read
 *                 partnerProteinAdjP before calling a partner changed.
 * @tags           protein interaction, PPI, STRING, network, neighbourhood
 * @sample         Bundled sample data only: $symbol = 'PIK3CG',
 *                 $minScore = 0.7, $comparisonId = 'CMP-LIV-MASLD' returns
 *                 6 rows, PIK3R1 (0.95) to RAC1 (0.73); PTEN carries a
 *                 protein logFC of -1.2.
 */
MATCH (g:Gene {symbol: $symbol})-[:CODES]->(p:Protein)-[i:INTERACTS_WITH]-(n:Protein)<-[:CODES]-(ng:Gene)
WHERE i.score >= $minScore
OPTIONAL MATCH (:Comparison {comparisonId: $comparisonId})-[fd:FOUND_DIFFERENTIAL]->(n)
RETURN g.symbol AS gene, ng.symbol AS partner, n.uniprotId AS partnerProtein, i.score AS score,
       fd.logFC AS partnerProteinLogFC, fd.adjPValue AS partnerProteinAdjP
ORDER BY score DESC, partner
```

## Changed proteins within two interaction hops

```cypher
/*
 * @name           Changed proteins within two interaction hops
 * @description    From the protein a gene encodes, walks the interaction
 *                 network up to two hops through interactions at or above a
 *                 score, and returns the proteins reached that changed
 *                 beyond the cutoffs in a comparison: a candidate module of
 *                 co-changed proteins around a target.
 * @params         symbol - HGNC gene symbol of the starting gene, e.g. 'CD36'.
 *                 comparisonId - The comparison whose protein results to use.
 *                 minScore - Smallest score accepted on every hop. Start at
 *                     0.7, STRING's high-confidence band.
 *                 maxAdjP - Largest adjusted p-value accepted. Start at 0.05.
 *                 minAbsLogFC - Smallest absolute protein log2 fold change.
 *                     Start at 1.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per changed protein reached: gene, changedPartner,
 *                 partnerProtein, hops (1 or 2, the shortest qualifying
 *                 walk), proteinLogFC, proteinAdjP. Never the starting
 *                 protein. Ordered by hops, then size of change.
 * @usage          Every hop must meet minScore, so a protein reachable only
 *                 through a weak interaction is left out. Two hops is the
 *                 bound: interaction networks are small-world, and a third
 *                 hop reaches much of the network and stops meaning
 *                 anything. Lowering minScore widens the result fast;
 *                 change it in small steps.
 * @tags           protein interaction, network expansion, module, co-target
 * @sample         Bundled sample data only: $symbol = 'CD36', $comparisonId =
 *                 'CMP-LIV-MASLD' returns 6 rows: PLIN2 and LPL at 1 hop,
 *                 then SCD, FABP1, APOB and PPARG at 2.
 */
MATCH (g:Gene {symbol: $symbol})-[:CODES]->(p:Protein)
MATCH path = (p)-[:INTERACTS_WITH*1..2]-(n:Protein)
WHERE n <> p AND all(r IN relationships(path) WHERE r.score >= $minScore)
MATCH (:Comparison {comparisonId: $comparisonId})-[fd:FOUND_DIFFERENTIAL]->(n)
WHERE fd.adjPValue <= $maxAdjP AND abs(fd.logFC) >= $minAbsLogFC
WITH g, n, fd, min(length(path)) AS hops
MATCH (ng:Gene)-[:CODES]->(n)
RETURN g.symbol AS gene, ng.symbol AS changedPartner, n.uniprotId AS partnerProtein, hops,
       fd.logFC AS proteinLogFC, fd.adjPValue AS proteinAdjP
ORDER BY hops, abs(proteinLogFC) DESC, changedPartner
```

## Candidate genes sharing processes with disease genes

```cypher
/*
 * @name           Candidate genes sharing processes with disease genes
 * @description    Finds genes not associated with a disease whose proteins
 *                 share Gene Ontology biological processes with the
 *                 disease's known genes, and that changed beyond the cutoffs
 *                 in a comparison studying the disease: guilt by
 *                 association, backed by the data.
 * @params         mondoId - MONDO CURIE of the disease, e.g. 'MONDO:0005148'.
 *                 minScore - Association score at or above which a gene
 *                     counts as known for the disease. Start at 0.5, so
 *                     "known" means moderately supported; no strong prior.
 *                 minSharedTerms - Fewest shared biological processes.
 *                     Start at 2: broad processes link many unrelated
 *                     genes, and one shared term is weak evidence.
 *                 maxAdjP - Largest adjusted p-value for the change.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change. Start
 *                     at 1.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per candidate: candidate, sharedProcessCount,
 *                 sharedProcesses, knownGenes it shares them with, and
 *                 changes ("comparisonId layer logFC"). Ordered by
 *                 sharedProcessCount, highest first.
 * @usage          Only biological_process terms count; molecular functions
 *                 and cellular components say little about disease
 *                 mechanism. A candidate excluded because it has any
 *                 association with the disease, however weak, is already
 *                 known. Hypothesis-generating: follow up with literature
 *                 and orthogonal data before calling any candidate a target.
 * @tags           target discovery, Gene Ontology, guilt by association, candidate
 * @sample         Bundled sample data only: $mondoId = 'MONDO:0005148'
 *                 returns 1 row: GCG, sharing glucose homeostasis and insulin
 *                 secretion with known genes, changed in CMP-ISL-T2D
 *                 (transcript 1.3, protein 1.2).
 */
MATCH (d:Disease {mondoId: $mondoId})<-[r:RELATED_TO]-(known:Gene)-[:CODES]->(:Protein)-[:ASSOCIATED_WITH]->(t:GOTerm {aspect: 'biological_process'})<-[:ASSOCIATED_WITH]-(:Protein)<-[:CODES]-(cand:Gene)
WHERE r.score >= $minScore AND cand <> known AND NOT (cand)-[:RELATED_TO]->(d)
WITH d, cand, collect(DISTINCT t.name) AS sharedProcesses, collect(DISTINCT known.symbol) AS knownGenes
WHERE size(sharedProcesses) >= $minSharedTerms
MATCH (d)<-[:STUDIES_DISEASE]-(c:Comparison)-[fd:FOUND_DIFFERENTIAL]->(f)
WHERE (f = cand OR (cand)-[:CODES]->(f)) AND fd.adjPValue <= $maxAdjP AND abs(fd.logFC) >= $minAbsLogFC
WITH cand, sharedProcesses, knownGenes,
     collect(c.comparisonId + CASE WHEN f:Gene THEN ' transcript ' ELSE ' protein ' END + toString(fd.logFC)) AS changes
RETURN cand.symbol AS candidate, size(sharedProcesses) AS sharedProcessCount, sharedProcesses, knownGenes, changes
ORDER BY sharedProcessCount DESC, candidate
```

## Pathways with concordant changes

```cypher
/*
 * @name           Pathways with concordant changes
 * @description    Counts, for each pathway, the participating proteins whose
 *                 gene changed concordantly in transcript and protein in a
 *                 comparison, as a share of the pathway's participants, and
 *                 flags pathways curated knowledge links to the
 *                 comparison's studied disease.
 * @params         comparisonId - The comparison to read.
 *                 maxAdjP - Largest adjusted p-value accepted in each layer.
 *                     Start at 0.05.
 *                 minAbsLogFC - Smallest absolute log2 fold change accepted
 *                     in each layer. Start at 1.
 *                 minGenes - Fewest concordant genes in a pathway. Start at
 *                     2; a single hit is not a pathway-level signal.
 * @prerequisites  The comparison must compare a transcriptomics and a
 *                 proteomics experiment.
 * @returns        One row per pathway: pathway, pathwayId, hits, members,
 *                 hitFraction, genes, linkedToStudiedDisease (true when the
 *                 comparison's disease INVOLVES_PATHWAY it). Ordered by
 *                 hitFraction, then hits.
 * @usage          An overlap ranking, not a statistical enrichment test: it
 *                 has no p-value and no background correction. For a formal
 *                 test, take hits, members, the number of concordant genes
 *                 and the number of genes measured to a hypergeometric or
 *                 gene-set test outside the graph. Small pathways reach high
 *                 fractions easily; read hits alongside the fraction.
 * @tags           pathway, enrichment, Reactome, concordance, mechanism
 * @sample         Bundled sample data only: $comparisonId = 'CMP-LIV-MASLD'
 *                 returns 6 rows, led by PPARA activates gene expression
 *                 (4 of 10 members) and Regulation of lipid metabolism by
 *                 PPARalpha (5 of 14), both linked to MASLD.
 */
MATCH (c:Comparison {comparisonId: $comparisonId})-[rna:FOUND_DIFFERENTIAL]->(g:Gene)-[:CODES]->(p:Protein)<-[prot:FOUND_DIFFERENTIAL]-(c)
WHERE rna.adjPValue <= $maxAdjP AND prot.adjPValue <= $maxAdjP
  AND abs(rna.logFC) >= $minAbsLogFC AND abs(prot.logFC) >= $minAbsLogFC
  AND sign(rna.logFC) = sign(prot.logFC)
MATCH (p)-[:PARTICIPATES_IN]->(pw:Pathway)
WITH c, pw, collect(DISTINCT g.symbol) AS genes
WHERE size(genes) >= $minGenes
WITH c, pw, genes, COUNT { (pw)<-[:PARTICIPATES_IN]-(:Protein) } AS members
RETURN pw.name AS pathway, pw.pathwayId AS pathwayId, size(genes) AS hits, members,
       round(toFloat(size(genes)) / members, 3) AS hitFraction, genes,
       EXISTS { (c)-[:STUDIES_DISEASE]->(:Disease)-[:INVOLVES_PATHWAY]->(pw) } AS linkedToStudiedDisease
ORDER BY hitFraction DESC, hits DESC, pathway
```

## Node keys

Import creates these constraints from the `key: true` properties in `ONTOLOGY.json`. They are listed so the live database can be checked with `SHOW CONSTRAINTS`, not to be run: creating them again conflicts with the constraints Import made.

```cypher
CREATE CONSTRAINT project_key IF NOT EXISTS FOR (n:Project) REQUIRE n.projectId IS NODE KEY;
CREATE CONSTRAINT sample_key IF NOT EXISTS FOR (n:Sample) REQUIRE n.sampleId IS NODE KEY;
CREATE CONSTRAINT tissue_key IF NOT EXISTS FOR (n:Tissue) REQUIRE n.uberonId IS NODE KEY;
CREATE CONSTRAINT phenotype_key IF NOT EXISTS FOR (n:Phenotype) REQUIRE n.phenotypeId IS NODE KEY;
CREATE CONSTRAINT experiment_key IF NOT EXISTS FOR (n:Experiment) REQUIRE n.experimentId IS NODE KEY;
CREATE CONSTRAINT comparison_key IF NOT EXISTS FOR (n:Comparison) REQUIRE n.comparisonId IS NODE KEY;
CREATE CONSTRAINT gene_key IF NOT EXISTS FOR (n:Gene) REQUIRE n.ensemblId IS NODE KEY;
CREATE CONSTRAINT protein_key IF NOT EXISTS FOR (n:Protein) REQUIRE n.uniprotId IS NODE KEY;
CREATE CONSTRAINT disease_key IF NOT EXISTS FOR (n:Disease) REQUIRE n.mondoId IS NODE KEY;
CREATE CONSTRAINT goterm_key IF NOT EXISTS FOR (n:GOTerm) REQUIRE n.goId IS NODE KEY;
CREATE CONSTRAINT pathway_key IF NOT EXISTS FOR (n:Pathway) REQUIRE n.pathwayId IS NODE KEY;
```
