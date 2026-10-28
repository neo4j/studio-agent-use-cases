---
name: loans-and-mortgages
description: Analyse consumer lending — mortgages, home equity lines and loans, and personal loans — as a connected graph of applicants, applications, products, loans, lenders, servicers, loan officers, payments, properties and appraisals, built from the Loans (LOAN) domain of the EDM Council's Financial Industry Business Ontology (FIBO), the open-source, governed ontology of financial concepts used by institutions worldwide. Provides a reference ontology, bundled sample data, and Cypher for loan and borrower lookups, portfolio and application-pipeline views, delinquency by servicer, combined loan-to-value across stacked liens, rapid re-appraisal of collateral, connected-party exposure and default contagion through co-borrowers and guarantors, and early payment default by loan officer.
metadata:
  neo4j-card-title: Loans and Mortgages
  neo4j-card-category: Financial Services
  neo4j-card-description: Built on the EDM Council's FIBO Loans ontology, connect borrowers, loans, collateral and originators to see combined exposure, stacked liens and early-default patterns that loan-by-loan reporting misses.
---

# Loans and Mortgages

Use this skill for lending risk, credit portfolio and mortgage operations teams, and developers building on their data, who want to look across a consumer loan book rather than one loan at a time: who is exposed to which loans, which properties are over-leveraged, and which originators produce loans that fail early.

Source references:

- <https://github.com/edmcouncil/fibo/tree/master/LOAN> — FIBO Loans (LOAN) domain, EDM Council
- <https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/Loan> — the FIBO Loan concept
- <https://edmcouncil.org/frameworks/industry-models/fibo/> — about FIBO

Disclaimer: this is an illustrative reference ontology with synthetic data, for demonstration. It is not a credit model, an underwriting policy, or a regulatory (HMDA) report. Treat query results as leads for a credit or fraud analyst to review, never as credit decisions or findings of misconduct, and do not present design choices or thresholds as proven guidance.

## Source ontology and license

The reference ontology is adapted from the Loans (LOAN) domain of the **Financial Industry Business Ontology (FIBO)**, the open-source, rigorously governed ontology of financial concepts developed by the **EDM Council** (Enterprise Data Management Council) with industry subject-matter experts, used by financial institutions worldwide, and published under the MIT License. Its concepts, definitions and code lists — loan purposes, HMDA dispositions, denial reasons, lien positions, market categories, amortization types — come from FIBO, and `reference` fields in `ONTOLOGY.json` link to the FIBO concepts they draw on. Users who already work with FIBO will recognise the vocabulary.

Be precise about the relationship: this is a simplification of FIBO for a graph demo, not FIBO itself, and it is not endorsed by the EDM Council. Credit FIBO as the source when explaining the reference ontology. The attribution, the copyright notices of the FIBO files used, the MIT License text, and exactly what was taken and changed are in `NOTICE.md`.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: lending risk sits in the connections between loans — one person borrowing on some loans and guaranteeing others, two liens from different lenders on the same house, a run of early defaults behind one loan officer — and loan-by-loan reporting does not see them.
- The reference ontology is built from a real-world, governed source: the Loans domain of the EDM Council's Financial Industry Business Ontology (FIBO), used by financial institutions worldwide. It keeps FIBO's concepts and code lists but is simplified for a demo — roles such as borrower, guarantor, lender and servicer become relationships.
- The bundled sample data is a synthetic US consumer loan book that deliberately seeds each pattern the queries look for, alongside ordinary loans and near misses.
- What you can help with: explaining the reference ontology, walking through the query patterns, importing the sample data or their own, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- People and applications: `Person {personId, name}` -[:APPLIED_FOR {applicantRole}]-> `LoanApplication {applicationId, applicationDate, requestedAmount, loanPurpose, occupancy, creditScore, monthlyIncome, dtiRatio, disposition, dispositionDate, denialReason}` -[:FOR_PRODUCT]-> `LoanProduct {productId, name, marketCategory, creditType, amortizationType, termMonths, isSecured}`; the application -[:HANDLED_BY]-> `LoanOfficer {officerId, name, nmlsId}` -[:EMPLOYED_BY]-> `FinancialInstitution {institutionId, name, lei}`.
- Loans: `(LoanApplication)-[:RESULTED_IN]->(Loan {loanId, principalAmount, interestRate, originationDate, maturityDate, lienPosition, ltvAtOrigination, currentBalance, balanceAsOfDate, status})`; `(Person)-[:BORROWER_ON {borrowerRole}]->(Loan)` and `(Person)-[:GUARANTEES]->(Loan)`; the loan -[:LENT_BY]-> and -[:SERVICED_BY]-> a `FinancialInstitution`, and -[:HAS_PAYMENT]-> `Payment {paymentId, dueDate, amountDue, amountPaid, paidDate, daysLate}`.
- Collateral: `(Loan)-[:SECURED_BY]->(Property {propertyId, address, city, state, postalCode, constructionType, dwellingUnits})` for mortgages and home equity lending; `(Appraisal {appraisalId, appraisalDate, appraisedValue})-[:VALUES]->(Property)`. A property can secure several loans and gather several appraisals.
- Conventions: US market, amounts in US dollars; `interestRate`, `ltvAtOrigination` and `dtiRatio` are percentages (80 means 80%); `creditScore` is FICO-style 300–850 at application; every date is a `ZONED DATETIME` at midnight UTC (Import does not accept `DATE` for local CSV files), so only the calendar date carries meaning — compare with `datetime(...)`, not `date(...)`, and wrap values in `date()` for display; `Loan.status` is the servicer's snapshot as of `balanceAsOfDate` (`current`, `delinquent` 30–89 days past due, `in default` 90+, `paid in full`); a missed installment is a `Payment` whose `amountPaid` is below `amountDue`. The product of a loan is reached through its application, and so is its originating officer.
- How it departs from FIBO: roles (borrower, co-maker, guarantor, lender, servicer, originator) are relationships, not classes; FIBO's class hierarchies (closed- vs open-end, secured vs unsecured, mortgage purpose, HMDA disposition, lien position, amortization type) are coded properties using FIBO's own labels; the loan contract and its loan-specific account are one `Loan` node with `Payment` nodes for the payment history; ratios are numbers, not objects. Left out for the demo: regulatory reporting, demographics, legal proceedings, commercial, student, card and vehicle loans.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases`, allowed values (`one_of`, `pattern`) and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Mortgage loan originator` or `Collateral` often names the user's equivalent), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Obligor | `Person` | One resolved identity per real party, linked to every loan they borrow on or guarantee, so liability can be summed across loans |
| Credit exposure | `Loan` | One node per funded loan carrying an outstanding balance and a status, linked to its obligors, lender and servicer |
| Collateral | `Property` | A node several loans can be secured on, so balances can be combined against one value |
| Valuation event | `Appraisal` | Dated values attached to the collateral, so values can be compared over time and the latest one found |
| Repayment event | `Payment` | One record per scheduled installment with amount due, amount paid and timing, linked to its loan |
| Originator | `LoanOfficer` via `LoanApplication` | The person or channel that originated each loan, reachable from the loan, so loan outcomes can be grouped by who wrote them |

`LoanProduct` and `FinancialInstitution` are grouping dimensions (by product, by servicer) rather than roles; any categorical equivalent in the user's data will do.

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
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding. For early payment default, set `$fromDate` from the payment history the database actually holds, as `@params` describes.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of an `@sample` anchor (for example the `$loanId` given for Loan overview) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Exposure sums charge each co-borrower and each guarantor the full balance, so totals across people double count shared loans by design. Combined LTV uses the most recent appraisal, whatever it was ordered for.
- Payment-history queries only see the period the history covers: a loan whose history starts late cannot show early misses, and early payment default needs the first months after origination to be present.
- Do not use the application data for fair-lending conclusions: the reference ontology holds no demographic data and no controls. Denial-reason and early-default views are operational leads only.
- Every pattern here has innocent explanations — a renovation behind a higher appraisal, a busy officer serving thin-file borrowers, a solvent co-borrower behind a defaulted loan. Present results as leads for review, never as findings.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
