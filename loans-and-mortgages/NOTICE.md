# Source and license notice

The reference ontology in this package is adapted from the **Loans (LOAN) domain of the Financial Industry Business Ontology (FIBO)**, developed by the EDM Council (Enterprise Data Management Council) and published at <https://github.com/edmcouncil/fibo> under the MIT License.

## What was taken from FIBO, and how it was changed

- **Taken:** the concepts the reference ontology is organised around (loan, loan application, loan product, collateral valuation, payment, servicer, guarantor, lien position, loan-to-value and debt-to-income ratios, NMLSR ID), their definitions, and FIBO's code lists — mortgage loan purposes, property usages, HMDA dispositions, denial reasons, lender lien positions, loan market categories, amortization types and HMDA construction types. Element descriptions paraphrase FIBO's definitions, and `reference` fields link to the FIBO concepts used.
- **Changed:** FIBO's OWL classes and properties were flattened into labelled nodes, relationships and typed properties. Party roles (borrower, guarantor, lender, servicer, originator) became relationships; class hierarchies became coded properties; the loan contract and its loan-specific account were merged into one node; ratios became numbers. Two denial reasons (`debt-to-income ratio`, `other`) and one loan purpose (`personal expenditure`) were added that FIBO does not list.
- **Not taken:** much of the LOAN domain — regulatory reporting, demographics, legal proceedings, and commercial, student, card, marine and vehicle lending.

The result is a simplification for demonstration, not FIBO itself, and it is not endorsed by the EDM Council or the Object Management Group. The sample data is synthetic and contains nothing from FIBO.

## Copyright notices

The FIBO files this package drew on carry these notices, as of the source revision used: `edmcouncil/fibo` master at commit `33a92cd34285d532c158da97bb42add089f135d3` (27 October 2026).

| FIBO file | Notice |
| --------- | ------ |
| `LOAN/LoansGeneral/Loans.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |
| `LOAN/LoansGeneral/LoanApplications.rdf` | Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |
| `LOAN/LoansGeneral/LoanEvents.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |
| `LOAN/LoansSpecific/LoanProducts.rdf` | Copyright (c) 2016-2024 EDM Council, Inc. |
| `LOAN/LoansSpecific/ConsumerLoans.rdf` | Copyright (c) 2015-2025 EDM Council, Inc.; Copyright (c) 2015-2025 Object Management Group, Inc. |
| `LOAN/RealEstateLoans/Mortgages.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |
| `LOAN/RealEstateLoans/MortgageOrigination.rdf` | Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |
| `LOAN/RealEstateLoans/HomeMortgageDisclosureActCoveredMortgages.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |

The FIBO repository as a whole carries: Copyright (c) 2020 Enterprise Data Management Council.

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
