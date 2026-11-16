# Life Sciences Competitive Intelligence — Queries

Runnable Cypher for the reference ontology in `ONTOLOGY.json`.

## Prerequisites

- Neo4j 5.x and Cypher 5. The queries use `EXISTS { … }` subqueries and no other version-specific syntax.
- No APOC and no Graph Data Science.
- Every node, relationship and property the queries use is loaded by Import from the reference ontology. No query writes, and no post-import setup is required.
- Dates (`ClinicalTrial.start_date`, `Patent.filing_date`) are ZONED DATETIME at midnight UTC; only the calendar date carries meaning. The queries wrap them in `date()` for display.
- A drug's `status` describes the asset as a whole; a trial's `status` describes one study. A terminated trial does not by itself mean the drug was discontinued, and the queries keep the two apart.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the
user's database differs — their own ontology, a modified one, or a database
that predates this package — the queries are patterns to rebuild, not
Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`)
   rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no
   counterpart means the pattern below it has no analogue — say so
   rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe
   what the rewritten query actually does.

## Graph census — node counts by label

```cypher
/*
 * @name           Graph census — node counts by label
 * @description    Counts the nodes under each label, to confirm an import
 *                 loaded every part of the reference ontology before any
 *                 analysis runs.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per label: label and nodes, largest first.
 * @usage          Run first after an import. A label with no row did not
 *                 load; check its source table before running anything that
 *                 traverses it.
 * @tags           census, import-check
 * @sample         Bundled sample data only: returns 7 rows — ClinicalTrial
 *                 324, Drug 147, Patent 120, Company 40, Protein 16,
 *                 Disease 8, Phase 4.
 */
MATCH (n)
WITH labels(n)[0] AS label, count(*) AS nodes
RETURN label, nodes
ORDER BY nodes DESC, label;
```

## Company therapeutic focus

```cypher
/*
 * @name           Company therapeutic focus
 * @description    Shows which diseases one company's pipeline addresses, with
 *                 how many of its drugs per disease are approved, active or
 *                 discontinued. A drug counts towards every disease it has
 *                 been trialled in.
 * @params         companyId - Company.id of the company. Look it up by name
 *                     first if the user gives a name.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per disease: company, disease, drugs, and the
 *                 approved, active and discontinued counts among them, most
 *                 drugs first.
 * @usage          The baseline view of a competitor. Read discontinued counts
 *                 as exits from an area, not as current focus.
 * @tags           company, portfolio, focus
 * @sample         Bundled sample data only: $companyId = 'CO-001' (Aldermoor
 *                 Therapeutics) returns 2 rows — Alzheimer's Disease with 1
 *                 active drug, Non-Small Cell Lung Cancer with 1
 *                 discontinued drug.
 */
MATCH (c:Company {id: $companyId})-[:IN_PIPELINE]->(d:Drug)-[:TREATS]->(dis:Disease)
RETURN c.name AS company, dis.name AS disease,
       count(DISTINCT d) AS drugs,
       count(DISTINCT CASE WHEN d.status = 'Approved' THEN d END) AS approved,
       count(DISTINCT CASE WHEN d.status = 'Active' THEN d END) AS active,
       count(DISTINCT CASE WHEN d.status = 'Discontinued' THEN d END) AS discontinued
ORDER BY drugs DESC, disease;
```

## Competitive landscape for a target

```cypher
/*
 * @name           Competitive landscape for a target
 * @description    Lists every company with a drug against one protein
 *                 target, how far each drug has got (the highest clinical
 *                 phase any of its trials reached), its development status,
 *                 and its most recent trial. Answers who else is pursuing
 *                 our target, and how far ahead or behind they are.
 * @params         proteinName - Protein.name of the target. Look it up rather
 *                     than guessing: sources name targets differently, and
 *                     the UniProt accession on Protein is the reliable match.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company and drug: company, drug, mechanism,
 *                 status, highestPhase (1–4), latestTrial (NCT number),
 *                 latestTrialStatus and latestTrialStart, furthest-advanced
 *                 first. A co-developed drug appears once per partner.
 * @usage          highestPhase counts a registered trial that has not started
 *                 yet, so read it with latestTrialStatus. A discontinued drug
 *                 that reached Phase 3 is still informative: the target
 *                 attracted late-stage investment and then failed.
 * @tags           pipeline, competition, target
 * @sample         Bundled sample data only: $proteinName = 'BACE1' returns 8
 *                 rows for 7 drugs — 4 discontinued and 3 active; GBL-731 is
 *                 co-developed by Glenhollow Bio and Harrowgate Pharma.
 *                 Aldermoor Therapeutics' ATL-2301 leads, with a Phase 3
 *                 trial not yet recruiting.
 */
MATCH (d:Drug)-[:TARGETS]->(:Protein {name: $proteinName})
MATCH (c:Company)-[:IN_PIPELINE]->(d)
MATCH (d)-[:INVESTIGATED_IN]->(t:ClinicalTrial)-[:HAS_PHASE]->(ph:Phase)
WITH c, d, max(ph.number) AS highestPhase, max(t.start_date) AS latestStart
MATCH (d)-[:INVESTIGATED_IN]->(latest:ClinicalTrial {start_date: latestStart})
RETURN c.name AS company, d.name AS drug, d.mechanism AS mechanism, d.status AS status,
       highestPhase, latest.nct_id AS latestTrial, latest.status AS latestTrialStatus,
       date(latest.start_date) AS latestTrialStart
ORDER BY highestPhase DESC, company, drug;
```

## Disease pipeline intensity

```cypher
/*
 * @name           Disease pipeline intensity
 * @description    Measures how crowded one disease is: for every company with
 *                 a trial in the disease, how many of its drugs have been
 *                 trialled there, how many of those are still live (not
 *                 discontinued), and the highest phase reached by a live
 *                 drug and by any drug.
 * @params         diseaseName - Disease.name exactly as stored.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company: company, assets, liveAssets,
 *                 highestLivePhase (null when every drug was discontinued)
 *                 and highestPhaseReached, most advanced live programme
 *                 first.
 * @usage          A company with assets but no live ones has left the
 *                 disease; one whose highestPhaseReached exceeds its
 *                 highestLivePhase has lost its lead programme. Counts are of
 *                 drugs trialled in this disease only.
 * @tags           pipeline, disease, market-entry
 * @sample         Bundled sample data only: $diseaseName = "Alzheimer's
 *                 Disease" returns 25 rows; Ravensmere Pharma leads with a
 *                 live Phase 4 programme, and Brightwater Biosciences is last
 *                 with no live asset.
 */
MATCH (:Disease {name: $diseaseName})<-[:FOR_DISEASE]-(t:ClinicalTrial)<-[:INVESTIGATED_IN]-(d:Drug)
MATCH (c:Company)-[:IN_PIPELINE]->(d)
MATCH (t)-[:HAS_PHASE]->(ph:Phase)
WITH c,
     count(DISTINCT d) AS assets,
     count(DISTINCT CASE WHEN d.status <> 'Discontinued' THEN d END) AS liveAssets,
     max(CASE WHEN d.status <> 'Discontinued' THEN ph.number END) AS highestLivePhase,
     max(ph.number) AS highestPhaseReached
RETURN c.name AS company, assets, liveAssets, highestLivePhase, highestPhaseReached
ORDER BY coalesce(highestLivePhase, 0) DESC, liveAssets DESC, company;
```

## Target diversification within a disease

```cypher
/*
 * @name           Target diversification within a disease
 * @description    Shows which protein targets companies are pursuing for one
 *                 disease, how many companies and drugs each target has, and
 *                 how many of those drugs were discontinued. Answers whether
 *                 competitors are converging on one mechanism or spreading
 *                 their bets.
 * @params         diseaseName - Disease.name exactly as stored.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per target: target, targetClass, companies, drugs
 *                 and discontinued, most-pursued first.
 * @usage          A target with many discontinued drugs is a crowded failure;
 *                 one with few companies and no discontinuations may be
 *                 white space. A bispecific drug counts under each of its
 *                 targets.
 * @tags           pipeline, disease, target, white-space
 * @sample         Bundled sample data only: $diseaseName = "Alzheimer's
 *                 Disease" returns 4 rows — TREM2 (12 companies), Amyloid-beta
 *                 (8), BACE1 (8, of whose 7 drugs 4 were discontinued) and
 *                 Tau (6).
 */
MATCH (:Disease {name: $diseaseName})<-[:FOR_DISEASE]-(:ClinicalTrial)<-[:INVESTIGATED_IN]-(d:Drug)-[:TARGETS]->(p:Protein)
MATCH (c:Company)-[:IN_PIPELINE]->(d)
WITH p, count(DISTINCT c) AS companies, count(DISTINCT d) AS drugs,
     count(DISTINCT CASE WHEN d.status = 'Discontinued' THEN d END) AS discontinued
RETURN p.name AS target, p.type AS targetClass, companies, drugs, discontinued
ORDER BY companies DESC, drugs DESC, target;
```

## Failed programmes in a disease

```cypher
/*
 * @name           Failed programmes in a disease
 * @description    Lists every discontinued drug developed for one disease,
 *                 with its target, mechanism, and its last trial: the phase,
 *                 how that trial ended and the reason given. Learning from
 *                 competitors' failures avoids repeating them, and a sound
 *                 mechanism stopped for business reasons can be an
 *                 opportunity.
 * @params         diseaseName - Disease.name exactly as stored.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company, drug and target: company, drug,
 *                 target, mechanism, lastPhase, lastTrialStatus, reason (the
 *                 termination reason, null when the last trial ran to
 *                 completion) and lastTrialStart, most recent first.
 * @usage          Only drugs whose status is Discontinued appear; a live drug
 *                 with a terminated trial does not. The last trial may be in
 *                 another disease the drug was also tried in. A null reason
 *                 means the sponsor stopped after a completed trial, which
 *                 often signals a disappointing readout or a portfolio
 *                 decision rather than a safety stop.
 * @tags           pipeline, failure, disease
 * @sample         Bundled sample data only: $diseaseName = "Alzheimer's
 *                 Disease" returns 14 rows, among them the BACE1 inhibitors
 *                 BBR-118 (Phase 3, cognitive worsening versus placebo) and
 *                 DBU-44 (Phase 3, liver enzyme elevations).
 */
MATCH (:Disease {name: $diseaseName})<-[:TREATS]-(d:Drug {status: 'Discontinued'})
MATCH (d)-[:INVESTIGATED_IN]->(t:ClinicalTrial)
WITH d, max(t.start_date) AS lastStart
MATCH (d)-[:INVESTIGATED_IN]->(last:ClinicalTrial {start_date: lastStart})-[:HAS_PHASE]->(ph:Phase)
MATCH (c:Company)-[:IN_PIPELINE]->(d)
MATCH (d)-[:TARGETS]->(p:Protein)
RETURN c.name AS company, d.name AS drug, p.name AS target, d.mechanism AS mechanism,
       ph.name AS lastPhase, last.status AS lastTrialStatus, last.termination_reason AS reason,
       date(last.start_date) AS lastTrialStart
ORDER BY lastTrialStart DESC, company, drug, target;
```

## Acquisition target screening

```cypher
/*
 * @name           Acquisition target screening
 * @description    Finds companies below a market-capitalisation ceiling that
 *                 hold active drugs still in early clinical development, as
 *                 candidates for acquisition or partnership before late-stage
 *                 data reprices them.
 * @params         maxMarketCapUsd - Market capitalisation ceiling in whole US
 *                     dollars. Start at 2000000000, the conventional upper
 *                     bound of a small-cap company, and raise towards
 *                     10000000000 to include mid-caps.
 *                 maxPhase - Highest phase a drug may have reached to count
 *                     as early. Start at 2: through Phase 2 an asset is
 *                     unproven at scale and cheapest to buy.
 * @prerequisites  Company.market_cap is a point-in-time snapshot; confirm its
 *                 date before acting on the screen.
 * @returns        One row per company: companyId, company,
 *                 marketCapMillionsUsd, earlyAssets (active drugs whose
 *                 highest phase is at most maxPhase), highestPhase among
 *                 them and targets (distinct proteins they address), most
 *                 advanced and broadest first.
 * @usage          Only Active drugs count: approved and discontinued ones do
 *                 not. A company also holding later-stage assets still
 *                 qualifies through its early ones, so check the company's
 *                 focus before treating it as an early-stage play.
 * @tags           business-development, acquisition, screening
 * @sample         Bundled sample data only: $maxMarketCapUsd = 2000000000,
 *                 $maxPhase = 2 returns 14 rows, Foxhollow Bio first with 4
 *                 early assets; it includes Fenwick Life Sciences and
 *                 Glenhollow Bio (both with BACE1 assets) and excludes
 *                 Ivelmont Therapeutics, Juniper Ridge Bio and Kestrel
 *                 Molecular.
 */
MATCH (c:Company)
WHERE c.market_cap < $maxMarketCapUsd
MATCH (c)-[:IN_PIPELINE]->(d:Drug {status: 'Active'})-[:INVESTIGATED_IN]->(:ClinicalTrial)-[:HAS_PHASE]->(ph:Phase)
WITH c, d, max(ph.number) AS drugPhase
WHERE drugPhase <= $maxPhase
MATCH (d)-[:TARGETS]->(p:Protein)
WITH c, count(DISTINCT d) AS earlyAssets, max(drugPhase) AS highestPhase, count(DISTINCT p) AS targets
RETURN c.id AS companyId, c.name AS company, c.market_cap / 1000000 AS marketCapMillionsUsd,
       earlyAssets, highestPhase, targets
ORDER BY highestPhase DESC, earlyAssets DESC, marketCapMillionsUsd, company;
```

## Patent overlap between companies

```cypher
/*
 * @name           Patent overlap between companies
 * @description    Finds pairs of companies that each hold patents claiming
 *                 the same protein target for the same disease: direct IP
 *                 competition, a possible dispute, or a sign that
 *                 differentiation is needed. A patent the two companies own
 *                 jointly is collaboration, not competition, and is not
 *                 counted.
 * @params         minPatentsEach - Minimum filings each company must hold on
 *                     the shared target and disease. Start at 2: a single
 *                     filing can be defensive or licensed in, while two or
 *                     more show a deliberate patent estate.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company pair, target and disease: company1,
 *                 company2, target, disease, patents1 and patents2 (each
 *                 company's filings there) and overlap (their sum), largest
 *                 overlap first.
 * @usage          Counts include pending, expired and abandoned filings; add
 *                 a filter on Patent.status to restrict to patents in force.
 *                 Lower minPatentsEach to 1 to see every touch point.
 * @tags           patent, competition, ip
 * @sample         Bundled sample data only: $minPatentsEach = 2 returns 24
 *                 rows; the largest overlaps (7) are Brightwater Biosciences
 *                 with Calderra Pharma and with Harrowgate Pharma on BACE1 in
 *                 Alzheimer's Disease, and Ulverston Bio with Corvane
 *                 Biologics on GBA1 in Parkinson's Disease.
 */
MATCH (c1:Company)<-[:HAS_OWNER]-(p1:Patent)-[:TARGETS]->(prot:Protein)
MATCH (p1)-[:TREATS]->(dis:Disease)
MATCH (c2:Company)<-[:HAS_OWNER]-(p2:Patent)-[:TARGETS]->(prot)
MATCH (p2)-[:TREATS]->(dis)
WHERE c1.id < c2.id AND p1 <> p2
  AND NOT (p1)-[:HAS_OWNER]->(c2) AND NOT (p2)-[:HAS_OWNER]->(c1)
WITH c1, c2, prot, dis, count(DISTINCT p1) AS patents1, count(DISTINCT p2) AS patents2
WHERE patents1 >= $minPatentsEach AND patents2 >= $minPatentsEach
RETURN c1.name AS company1, c2.name AS company2, prot.name AS target, dis.name AS disease,
       patents1, patents2, patents1 + patents2 AS overlap
ORDER BY overlap DESC, company1, company2, target;
```

## Patents without a pipeline programme

```cypher
/*
 * @name           Patents without a pipeline programme
 * @description    Finds companies patenting a protein target that none of
 *                 their pipeline drugs address. Patents ahead of any trial
 *                 signal strategic intent not yet visible in the clinic — an
 *                 early programme, a planned licence, or a filing made to
 *                 block competitors.
 * @params         minPatents - Minimum filings on the target for a company
 *                     to count. Start at 2: a single filing can be
 *                     incidental, while two or more on one target show
 *                     sustained interest.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company and target: company, target, patents
 *                 and latestFiling (date of the most recent filing), most
 *                 filings first.
 * @usage          Recent filings matter most: an estate whose latest filing
 *                 is old may have been abandoned as a strategy even if
 *                 granted patents remain.
 * @tags           patent, strategy, early-signal
 * @sample         Bundled sample data only: $minPatents = 2 returns 2 rows —
 *                 Penhallow Therapeutics on TREM2 (3 filings) and Corvane
 *                 Biologics on KRAS (2); Quillon Biosciences' single GBA1
 *                 filing is excluded.
 */
MATCH (c:Company)<-[:HAS_OWNER]-(pat:Patent)-[:TARGETS]->(prot:Protein)
WHERE NOT EXISTS { (c)-[:IN_PIPELINE]->(:Drug)-[:TARGETS]->(prot) }
WITH c, prot, count(DISTINCT pat) AS patents, max(pat.filing_date) AS latest
WHERE patents >= $minPatents
RETURN c.name AS company, prot.name AS target, patents, date(latest) AS latestFiling
ORDER BY patents DESC, latestFiling DESC, company;
```

## Pipeline and patent convergence on a target

```cypher
/*
 * @name           Pipeline and patent convergence on a target
 * @description    Finds companies whose live clinical programme and own
 *                 patent filings converge on the same protein target: the
 *                 strongest signal of strategic commitment, since the company
 *                 is both spending on trials and protecting the mechanism.
 * @params         minPhase - Lowest phase a live drug must have reached to
 *                     count. Start at 2, where a programme has moved into
 *                     patients and committed real investment; raise to 3 for
 *                     late-stage commitment only.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per company and target: company, target, drugs
 *                 (live drugs at or beyond minPhase), highestPhase among them
 *                 and patents (the company's filings on the target), most
 *                 advanced first.
 * @usage          Discontinued drugs are excluded, so a company that patents
 *                 a target after its programme failed does not appear. A
 *                 company with patents and an early programme below minPhase
 *                 appears once minPhase is lowered.
 * @tags           pipeline, patent, convergence, strategy
 * @sample         Bundled sample data only: $minPhase = 2 returns 31 rows,
 *                 led by Hollinwood Pharma on PD-1 (Phase 4, 4 filings);
 *                 Aldermoor Therapeutics on BACE1 (Phase 3, 2 filings) and
 *                 Fenwick Life Sciences on BACE1 (Phase 2, 2 filings) are
 *                 among them.
 */
MATCH (c:Company)-[:IN_PIPELINE]->(d:Drug)-[:TARGETS]->(prot:Protein)
WHERE d.status <> 'Discontinued'
MATCH (d)-[:INVESTIGATED_IN]->(:ClinicalTrial)-[:HAS_PHASE]->(ph:Phase)
WITH c, d, prot, max(ph.number) AS drugPhase
WHERE drugPhase >= $minPhase
MATCH (c)<-[:HAS_OWNER]-(pat:Patent)-[:TARGETS]->(prot)
WITH c, prot, count(DISTINCT d) AS drugs, max(drugPhase) AS highestPhase, count(DISTINCT pat) AS patents
RETURN c.name AS company, prot.name AS target, drugs, highestPhase, patents
ORDER BY highestPhase DESC, patents DESC, company, target;
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
CREATE CONSTRAINT id_Company_key IF NOT EXISTS FOR (n:Company) REQUIRE (n.id) IS NODE KEY;
CREATE CONSTRAINT id_Drug_key IF NOT EXISTS FOR (n:Drug) REQUIRE (n.id) IS NODE KEY;
CREATE CONSTRAINT name_Protein_key IF NOT EXISTS FOR (n:Protein) REQUIRE (n.name) IS NODE KEY;
CREATE CONSTRAINT name_Disease_key IF NOT EXISTS FOR (n:Disease) REQUIRE (n.name) IS NODE KEY;
CREATE CONSTRAINT nct_id_ClinicalTrial_key IF NOT EXISTS FOR (n:ClinicalTrial) REQUIRE (n.nct_id) IS NODE KEY;
CREATE CONSTRAINT name_Phase_key IF NOT EXISTS FOR (n:Phase) REQUIRE (n.name) IS NODE KEY;
CREATE CONSTRAINT id_Patent_key IF NOT EXISTS FOR (n:Patent) REQUIRE (n.id) IS NODE KEY;
```
