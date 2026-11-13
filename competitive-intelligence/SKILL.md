---
name: competitive-intelligence
description: Life sciences competitive intelligence with Neo4j for pharma and biotech business development — competitor drug pipelines by target and disease, clinical-trial phase and status, failed-programme analysis, disease pipeline crowding, small-cap acquisition screening, and patent overlap between companies, all connected through shared protein targets and diseases. Use for questions about who is developing drugs against a target, how advanced competitors are, which programmes were discontinued and why, how crowded a disease is, where companies' patent estates overlap, and which companies patent a target ahead of any clinical programme.
metadata:
  neo4j-card-title: Life Sciences Competitive Intelligence
  neo4j-card-category: Healthcare & Life Sciences
  neo4j-card-description: Map competitors' drug pipelines and patent estates against shared targets and diseases to spot crowding, failures and acquisition candidates.
---

# Life Sciences Competitive Intelligence

Use this skill for pharmaceutical and biotech competitive intelligence: mapping competitors' development pipelines against protein targets and diseases, tracking how far each programme has got in clinical trials, learning from discontinued programmes, screening smaller companies as acquisition or partnership candidates, and comparing pipelines with patent filings on the same targets.

Source references:

- <https://github.com/jarasch/field-industry-use-cases/blob/main/modules/ROOT/pages/life-sciences/competitive-intelligence/pipeline-intelligence.adoc>
- <https://github.com/jarasch/field-industry-use-cases/blob/main/modules/ROOT/pages/life-sciences/competitive-intelligence/patent-intelligence.adoc>

This is a graph-modelling and query-pattern aid, not investment, legal or clinical advice. Treat results as competitive signals that need an analyst's judgement. The bundled sample data is synthetic: its companies, drugs, trials and patents are fictional, attached to real protein targets and diseases.

## Introducing this package

When the user first opens this package, greet them with a short
introduction in your own words — don't recite this file. Convey:

- Competitive intelligence joins three things that live in separate sources —
  who is developing which drug, how far each trial has got, and who has
  patented which target — and a graph lets one question cross all three,
  such as which companies both trial and patent the same target.
- The sample data is synthetic: fictional companies, drugs, trials and patents
  on real targets and diseases, deliberately seeded with a crowded target full
  of failed programmes, small-cap acquisition candidates and overlapping
  patent estates.
- What you can help with: explaining the reference ontology, walking through the query
  patterns, importing the sample data or their own, and running Cypher
  once a database is connected.

End with a clear next step, such as asking whether they'd like to explore
the reference ontology or start importing data.

## Reference ontology

- `Company` (pharma or biotech; `id`, `name`, ISO `country`, `market_cap` in US dollars, `focus`) has `IN_PIPELINE` drugs and owns patents (`Patent`-`HAS_OWNER`->`Company`).
- `Drug` (`id`, `name`, `mechanism`, `administration`, `status` Active, Approved or Discontinued) `TARGETS` one or more `Protein`s, `TREATS` the `Disease`s it has been trialled in, and is `INVESTIGATED_IN` `ClinicalTrial`s.
- `ClinicalTrial` (`nct_id`, `title`, ClinicalTrials.gov `status`, `start_date`, `enrollment`, `termination_reason`) `HAS_PHASE` exactly one `Phase` (1–4, with a numeric `number`) and is `FOR_DISEASE` exactly one `Disease` (`name`, ICD-10 `icd10`, `us_prevalence`, `annual_market_usd`).
- `Patent` (`id`, `title`, `filing_date`, legal `status`) `TARGETS` a `Protein` (`name`, UniProt `uniprot`, `function`, target-class `type`) and `TREATS` a `Disease`. Drugs and patents share the same `Protein` and `Disease` nodes, which is where pipeline and patent evidence meet.
- Design choices that depart from the source pages: `Phase` is the clinical phase only, so a programme's outcome lives in `Drug.status` and each trial's in `ClinicalTrial.status` and `termination_reason`, never in a "Discontinued" phase. `TREATS` from a drug is derived from its trials. The publication layer the source pages describe (publications, authors, institutions, genes) is not part of this reference ontology.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in
  `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model",
  "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term —
  `description` above all, plus `aliases`, allowed values (`one_of`,
  `pattern`) and relationship counts. Quote them when explaining the
  reference ontology, rely on them when adapting queries to the user's
  own data (an alias often names the user's equivalent label), and never
  contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Sponsor | `Company` | Links to the assets it develops and the patents it owns; a market value for screening |
| Development asset | `Drug` | A status that separates live from stopped programmes, and links to its target and its trials |
| Target | `Protein` | One shared node per target, reached from both assets and patents — names normalised, ideally to a UniProt accession |
| Indication | `Disease` | One shared node per disease, reached from both trials and patents |
| Clinical milestone | `ClinicalTrial` and `Phase` | A phase that orders progress, and a trial status with a stop reason |
| IP claim | `Patent` | An owner, a claimed target and indication, and a filing date |

When the user's database differs from the reference ontology, map their
labels onto these roles before rewriting anything from `QUERIES.md`. A role with no
counterpart in their data means the patterns resting on it have no
analogue — say so plainly rather than forcing a fit.

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only
  through it. Never ship or offer a write-based data seed, a `LOAD CSV`
  statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing,
  and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Queries open with a `/* @... */` annotation block. Keep the block with
  the query when showing or running it — it exists to help the user
  understand the query — and treat it as context, not ground truth: on
  any conflict, the Cypher logic wins. When adapting a query, update its
  annotations to match.
- Starting parameter values in `@params` are starting points, not
  defaults that fit any dataset. Read the result and retune before
  presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the
  connected database holds that sample — you imported it in this
  conversation, or a lookup of the `@sample` anchor (for example its
  `$companyId`) finds it. Then use its values as starting parameters, and
  treat a result that differs from it as a sign the import went wrong.
  Otherwise ignore it: never present it, or anything derived from it, as
  an expectation of the user's own data.
- Keep a drug's status and a trial's status apart: a terminated trial does not mean the drug was discontinued, and a discontinued drug's last trial may have completed normally.
- Pipeline data dates quickly: trial statuses change within weeks, and public registries miss preclinical and undisclosed programmes. `market_cap` is a point-in-time snapshot. Say so whenever a result drives a recommendation.
- Match targets by name only after normalising: sources name the same protein differently, and the UniProt accession is the reliable key. Disease and protein names are exact-match in the queries.
- Patent counts include pending, expired and abandoned filings unless the query filters `Patent.status`.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
