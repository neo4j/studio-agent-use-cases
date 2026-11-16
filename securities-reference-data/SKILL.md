---
name: securities-reference-data
description: Connect securities, their issuers and issuer groups, market identifiers (ISIN, CUSIP, SEDOL, Valoren, Common Code, FIGI), exchange listings and tickers, depositary receipts, convertibles, offerings and underwriters, and the funds that hold them, as a graph built from the Securities (SEC) domain of the EDM Council's Financial Industry Business Ontology (FIBO). For security-master, reference-data, investment-compliance and risk teams. Provides a reference ontology, bundled sample data, and Cypher for identifier resolution, shared and inconsistent identifiers, point-in-time ticker lookup, stale listings of matured bonds, issuer-group capital structure, every route to an issuer's risk through receipts and exchangeables, fund look-through holdings and issuer-group exposure, look-through concentration breaches, and affiliated underwriting.
metadata:
  neo4j-card-title: "Securities: Reference Data and Look-through Exposure"
  neo4j-card-category: Financial Services
  neo4j-card-description: Built on the EDM Council's FIBO Securities ontology, reconcile identifiers and listings, map every route to an issuer group, and see fund exposure and concentration through layers of funds, receipts and subsidiaries.
---

# Securities: Reference Data and Look-through Exposure

Use this skill for security-master and reference-data teams, investment-compliance and risk analysts, and developers building on their data, who need to know which instrument an identifier or ticker means, how an issuer's securities hang together, and how much of a fund really sits with one issuer group once other funds' units, depositary receipts and financing subsidiaries are followed.

Source references:

- <https://github.com/edmcouncil/fibo/tree/master/SEC> — FIBO Securities (SEC) domain, EDM Council
- <https://spec.edmcouncil.org/fibo/ontology/SEC/MetadataSEC/SECDomain> — the FIBO SEC domain in the FIBO viewer
- <https://edmcouncil.org/frameworks/industry-models/fibo/> — about FIBO

Disclaimer: this is an illustrative reference ontology with synthetic data, for demonstration. It is not investment advice, a regulatory compliance determination, or an authoritative security master. Treat query results as leads for a data steward or compliance analyst to review, and do not present design choices or thresholds as regulatory guidance.

## Source ontology and license

The reference ontology is adapted from the Securities (SEC) domain of the **Financial Industry Business Ontology (FIBO)**, the open-source, governed ontology of financial concepts developed by the **EDM Council** (Enterprise Data Management Council) with industry subject-matter experts and published under the MIT License. Its concepts and definitions — security, share, preferred share, depositary receipt and its multiplier, bond and coupon, subordination, convertible security, security identifier, ISIN, national securities identifying number, ticker symbol, listing and home exchange, security form, securities restrictions (Rule 144A, Regulation S, Regulation D), securities offering and underwriter, fund, fund unit and fund manager — come from FIBO, and `reference` fields in `ONTOLOGY.json` link to the FIBO concepts they draw on. Users who already work with FIBO or ISO 6166 identifiers will recognise the vocabulary.

Be precise about the relationship: this is a simplification of FIBO for a graph demo, not FIBO itself, and it is not endorsed by the EDM Council. Credit FIBO as the source when explaining the reference ontology. The attribution, the copyright notices of the FIBO files used, the MIT License text, and exactly what was taken and changed are in `NOTICE.md`.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: securities data is a web, not a table. A ticker means different instruments in different years, one identifier can end up on two securities, an issuer's risk reaches a portfolio through its subsidiaries' bonds, depositary receipts issued by a bank and exchangeables issued by someone else, and a fund's real exposure sits inside the other funds it holds — only following the connections shows it.
- The reference ontology is built from a real-world, governed source: the Securities domain of the EDM Council's Financial Industry Business Ontology (FIBO). It keeps FIBO's concepts and definitions, simplified for a demo — FIBO's class hierarchies become coded properties and roles such as issuer, underwriter and fund manager become relationships.
- The bundled sample data is a synthetic market of issuers, securities, listings, offerings and funds that deliberately seeds each pattern the queries look for, alongside ordinary data and near misses.
- What you can help with: explaining the reference ontology, walking through the query patterns, importing the sample data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Securities and issuers: `(Security {securityId, name, securityType, cfiCode, currency, issueDate, maturityDate, couponRate, seniority, faceAmountOutstanding, securityForm, restriction})-[:ISSUED_BY]->(LegalEntity {entityId, name, lei, countryCode, sector})`. A depositary receipt's issuer is the depositary bank; a fund unit's issuer is the fund vehicle.
- Issuer groups: `(LegalEntity)-[:DIRECTLY_CONSOLIDATED_BY]->(LegalEntity)`, as in LEI Level 2 records. The ultimate parent is the entity with no outgoing link; issuer exposure is aggregated to it.
- Identifiers: `(Security)-[:IDENTIFIED_BY]->(Identifier {identifierId, scheme, value})`, one node per distinct scheme and value (`identifierId` is `scheme:value`), so a shared identifier is one node with two securities. An ISIN embeds the national number of its prefix's country in characters 3 to 11, zero-padded to nine: CUSIP for US and CA, SEDOL for GB and IE, Valoren for CH and LI, Common Code for XS.
- Listings: `(Listing {listingId, ticker, listingDate, delistingDate, isPrimary})-[:LISTS]->(Security)` and `-[:LISTED_ON]->(Exchange {mic, name, countryCode})`. A listing is active from `listingDate` up to, but not including, `delistingDate`; tickers are reassignable, so resolve them as of a date.
- Links between securities: `(Security)-[:REPRESENTS {multiplier}]->(Security)` from a depositary receipt to its underlying share; `(Security)-[:CONVERTIBLE_INTO {conversionRatio}]->(Security)` from a convertible or exchangeable to its target.
- Funds: `(Fund {fundId, name, fundType, domicile, baseCurrency, totalNetAssets, reportingDate})-[:HOLDS {weightPct, marketValue}]->(Security)`, `(Fund)-[:MANAGED_BY]->(LegalEntity)`, and `(Security)-[:UNIT_OF]->(Fund)` for fund units. A fund holding another fund's units is a look-through link; look-through weight is the product of `weightPct / 100` along the chain.
- Offerings: `(Offering {offeringId, offeringType, underwritingType, closingDate})-[:OFFERS]->(Security)` and `-[:UNDERWRITTEN_BY {role}]->(LegalEntity)`.
- Conventions: `weightPct` is percent of the fund's total net assets (0–100); `couponRate` is percent a year of face value; `faceAmountOutstanding`, `totalNetAssets` and `marketValue` are in whole currency units. Codes are ISO: 3166-1 alpha-2 countries, 4217 currencies, 10383 MICs, 10962 CFI codes, 17442 LEIs. Every date is a `ZONED DATETIME` at midnight UTC (Import does not accept `DATE` for local CSV files) — compare with `datetime(...)`, not `date(...)`, and wrap values in `date()` for display.
- How it departs from FIBO: FIBO's security, fund, offering and form class hierarchies are coded properties using FIBO's labels; subordination is a `seniority` property rather than pairwise `isSubordinatedTo` links; issuer, underwriter, depositary and fund-manager roles are relationships to one `LegalEntity` label; fund holdings are one `HOLDS` relationship. Left out: derivatives, pools and asset-backed structures, payment and redemption schedules, call and put features, dividends, prices, and identifier registries.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases`, allowed values (`one_of`, `pattern`) and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Instrument`, `Trading venue` or `Portfolio` often names the user's equivalent), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Instrument | `Security` | One node per instrument, linked to its issuer, so identifiers, listings, holdings and links between instruments meet on it |
| Issuer and its group | `LegalEntity`, `DIRECTLY_CONSOLIDATED_BY` | An issuer node with a parent link that can be walked to the top, so subsidiaries' securities aggregate to one group |
| Market identifier | `Identifier` | A value-keyed node per scheme and value, so two instruments sharing an identifier meet at one node; a property on the instrument supports lookup only |
| Venue listing over time | `Listing`, `Exchange` | A dated record per instrument, venue and ticker, with start and end dates, so a ticker can be resolved as of a date |
| Instrument-to-instrument link | `REPRESENTS`, `CONVERTIBLE_INTO` | A directed edge from a receipt or convertible to the instrument whose risk it carries |
| Holding portfolio | `Fund`, `HOLDS`, `UNIT_OF` | A portfolio node with weighted holdings, whose own units are instruments other portfolios can hold, so look-through can multiply along the chain |
| Distribution event | `Offering`, `UNDERWRITTEN_BY` | A record linking a newly issued instrument to the parties that brought it to market |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Supporting files

| File | Load when |
| ---- | --------- |
| `NOTICE.md` | The user asks about the FIBO source, licensing, copyright or attribution, or exactly which parts of FIBO were used and how they were changed |

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes. No bundled query writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.23 or later (including Aura), Cypher 5: the queries use `COLLECT {}` subqueries and the `CALL (x) { … }` scope clause. No APOC or GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of an `@sample` anchor (for example the ISIN given for Resolve a security by identifier) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Keep variable-length walks bounded: `HOLDS|UNIT_OF` look-through at seven relationships (three layers of fund units) and `DIRECTLY_CONSOLIDATED_BY` at eight levels. Fund-of-funds structures can loop in bad data, and an unbounded walk then multiplies weights indefinitely. On a large graph, anchor the portfolio-wide screens (concentration breaches, affiliated underwriting) to a list of funds.
- Look-through is only as current as the oldest `reportingDate` in the chain, and weights assume each fund's holdings are complete. Say so when presenting look-through figures.
- Concentration limits differ by regime, fund type and instrument, and sovereign debt is usually treated separately. Present breaches as a screen against the fund's own limits, never as a regulatory finding. Affiliated underwriting likewise needs trade records to confirm the fund bought in the offering.
- Identifier and listing defects have innocent explanations too — a vendor's late update, a corporate action in progress, a legitimate secondary line. Present them as items for a data steward to check at the source.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
