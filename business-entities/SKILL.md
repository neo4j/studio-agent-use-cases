---
name: business-entities
description: Analyse who owns and who controls companies — legal entities, the people and trusts behind them, their directors and officers, where they are incorporated and registered, and the parents they report — as a connected graph built from the Business Entities (BE) domain of the EDM Council's Financial Industry Business Ontology (FIBO), the open-source, governed ontology of financial concepts used by institutions worldwide. For KYC, AML, beneficial-ownership, sanctions and counterparty-risk teams. Provides a reference ontology, bundled sample data, and Cypher for entity lookups, ownership structures and corporate groups, ultimate beneficial owners through layered and multi-path chains, trust look-through, collective ownership by a household, control without ownership through boards and general partners, circular ownership, offshore layering, formation-agent addresses, reported versus ownership-derived parents, and the shortest connection between two companies.
metadata:
  neo4j-card-title: "Business Entities: Ownership and Control"
  neo4j-card-category: Financial Services
  neo4j-card-description: Built on the EDM Council's FIBO Business Entities ontology, trace ownership and control through layers of companies, trusts and boards to find the real owners, hidden links and circular structures a register of direct shareholders misses.
---

# Business Entities: Ownership and Control

Use this skill for KYC, AML, beneficial-ownership, sanctions-screening and counterparty-risk teams, and developers building on their data, who need to answer who really owns and who really controls a company when the answer sits several layers away from the register of direct shareholders.

Source references:

- <https://github.com/edmcouncil/fibo/tree/master/BE> — FIBO Business Entities (BE) domain, EDM Council
- <https://spec.edmcouncil.org/fibo/ontology/BE/LegalEntities/LegalPersons/BusinessEntity> — the FIBO business entity concept
- <https://edmcouncil.org/frameworks/industry-models/fibo/> — about FIBO

Disclaimer: this is an illustrative reference ontology with synthetic data, for demonstration. It is not a legal determination of beneficial ownership or control under any regulation. Treat query results as leads for a compliance analyst to review, never as findings of concealment, sanctions exposure or wrongdoing, and do not present design choices or thresholds as proven guidance.

## Source ontology and license

The reference ontology is adapted from the Business Entities (BE) domain of the **Financial Industry Business Ontology (FIBO)**, the open-source, rigorously governed ontology of financial concepts developed by the **EDM Council** (Enterprise Data Management Council) with industry subject-matter experts, used by financial institutions worldwide, and published under the MIT License. Its concepts and definitions — business entity, legal form, LEI, ownership percentage, board member and corporate officer, trust, trustor, trustee and beneficiary, general and limited partner, registered address, jurisdiction of incorporation, direct and ultimate consolidating parent — come from FIBO, and `reference` fields in `ONTOLOGY.json` link to the FIBO concepts they draw on. Users who already work with FIBO or with LEI data will recognise the vocabulary.

Be precise about the relationship: this is a simplification of FIBO for a graph demo, not FIBO itself, and it is not endorsed by the EDM Council. Credit FIBO as the source when explaining the reference ontology. The attribution, the copyright notices of the FIBO files used, the MIT License text, and exactly what was taken and changed are in `NOTICE.md`.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: ownership and control are chains, not rows. The person who really owns a company may sit four companies away across three jurisdictions, hold it through two paths that each look small, split it across a household, or control it through a board seat or a general partner while owning almost nothing — and only following the connections reveals it.
- The reference ontology is built from a real-world, governed source: the Business Entities domain of the EDM Council's Financial Industry Business Ontology (FIBO), used by financial institutions worldwide. It keeps FIBO's concepts and definitions but is simplified for a demo — roles such as owner, director, trustee and beneficiary become relationships.
- The bundled sample data is a synthetic register of companies, people and trusts that deliberately seeds each pattern the queries look for, alongside ordinary corporate groups, small companies and near misses.
- What you can help with: explaining the reference ontology, walking through the query patterns, importing the sample data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Parties: `Person {personId, name, nationality, isPoliticallyExposed}`, `LegalEntity {entityId, name, legalForm, lei, registrationNumber, status, incorporationDate}` and `Trust {trustId, name, trustType, establishedDate}`.
- Ownership: `(Person|LegalEntity|Trust)-[:OWNS {percentage, interestType}]->(LegalEntity)`. `percentage` is the direct share of the owned entity's equity in percent (0–100); `interestType` is `shares`, `membership interest`, `general partner interest` or `limited partner interest`. Effective ownership along a chain is the product of the percentages; a person's effective ownership of an entity is the sum over every distinct chain.
- Control and roles: `(Person)-[:DIRECTOR_OF {role, appointedDate}]->(LegalEntity)`, `(Person)-[:OFFICER_OF {title}]->(LegalEntity)`; `(Person)-[:TRUSTOR_OF]->(Trust)`, `(Person)-[:BENEFICIARY_OF]->(Trust)`, `(Person|LegalEntity)-[:TRUSTEE_OF]->(Trust)`.
- Places: `(LegalEntity)-[:INCORPORATED_IN]->(Jurisdiction {jurisdictionId, name, isOffshoreCentre})`, `(Trust)-[:ESTABLISHED_IN]->(Jurisdiction)`, `(LegalEntity)-[:REGISTERED_AT]->(Address {addressId, street, city, postalCode, countryCode})`, `(Person)-[:RESIDES_AT]->(Address)`. One `Address` node per distinct address, so entities and people at the same address meet at one node.
- Reported parents: `(LegalEntity)-[:DIRECTLY_CONSOLIDATED_BY]->(LegalEntity)` and `-[:ULTIMATELY_CONSOLIDATED_BY]->`, as in LEI Level 2 relationship records — reported facts that can go stale, compared against ownership by one of the queries.
- Conventions: `percentage` is economic ownership, not voting rights. "Control" in the queries is a chain of `OWNS` links each above `$controlPct` (50 by default) or a `general partner interest`, plus board seats and offices. `jurisdictionId` is ISO 3166-1 alpha-2, or ISO 3166-2 where company law sits below the national level (`US-DE`). `isOffshoreCentre` and `isPoliticallyExposed` are flags the user's own policy and screening set, not FIBO concepts. `lei` is empty when an entity has none. Every date is a `ZONED DATETIME` at midnight UTC (Import does not accept `DATE` for local CSV files), so only the calendar date carries meaning — compare with `datetime(...)`, not `date(...)`, and wrap values in `date()` for display.
- How it departs from FIBO: roles (shareholder, LLC member, partner, board member, officer, trustor, trustee, beneficiary) are relationships, not classes; FIBO's legal-form and trust class hierarchies are coded properties using FIBO's labels; ownership situations are a single `OWNS` relationship carrying FIBO's ownership percentage; jurisdictions and addresses are plain nodes. Left out for the demo: government entities, functional entities, organisational sub-units, constitutional documents, and voting versus economic share classes.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases`, allowed values (`one_of`, `pattern`) and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Settlor` or `Registered office` often names the user's equivalent), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Natural person | `Person` | One resolved identity per real individual, linked to every holding, seat and trust role they have, so ownership and control can be summed across them |
| Owned or controlled party | `LegalEntity` | A node that can be both owned and an owner, so chains of any depth can be walked |
| Ownership link | `OWNS` | A directed edge from holder to held carrying a numeric percentage, so effective ownership can be multiplied along chains |
| Arrangement without owners | `Trust` | A node that holds shares but whose people are reached through role links rather than ownership |
| Control seat | `DIRECTOR_OF`, `OFFICER_OF` | Person-to-entity links for board and executive positions, separate from ownership |
| Shared location | `Address`, `Jurisdiction` | A value-keyed node many entities or people converge on, so a shared address or offshore jurisdiction is one hop away |

`DIRECTLY_CONSOLIDATED_BY` and `ULTIMATELY_CONSOLIDATED_BY` matter only to the reported-parent comparison; any reported parent field in the user's data will do.

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Supporting files

| File | Load when |
| ---- | --------- |
| `NOTICE.md` | The user asks about the FIBO source, licensing, copyright or attribution, or exactly which parts of FIBO were used and how they were changed |

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.x and Cypher 5, at a release that supports `COUNT {}` and `COLLECT {}` subqueries (5.6 or later). No APOC or GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of an `@sample` anchor (for example the `$entityId` given for Entity overview) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Keep variable-length `OWNS` traversals bounded and keep the filter that visits each node once: without it, circular ownership makes paths loop and double counts effective ownership. On a large graph, anchor the portfolio-wide queries (household ownership, offshore layering) to an entity or a list of entities before running them.
- A complete beneficial-ownership answer for one entity reads three queries together: Ultimate beneficial owners (ownership), Trust look-through (trusts, no threshold), and Control without ownership (seats and general partners). Say which prongs you ran.
- Effective ownership assumes the recorded percentages are complete and current. Missing holders, nominee arrangements and share classes with different voting rights are not visible to it.
- Every pattern here has innocent explanations — a family that divides shares for inheritance, a lawful offshore fund structure, a busy professional director, a listed cross-shareholding, a parent record not yet updated after a deal. Present results as leads for review, never as findings.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
