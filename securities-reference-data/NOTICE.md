# Source and license notice

The reference ontology in this package is adapted from the **Securities (SEC) domain of the Financial Industry Business Ontology (FIBO)**, developed by the EDM Council (Enterprise Data Management Council) and published at <https://github.com/edmcouncil/fibo> under the MIT License.

## What was taken from FIBO, and how it was changed

- **Taken:** the concepts the reference ontology is organised around (security, issuer, share, common share, preferred share, depositary receipt and its traded share and multiplier, bond, bond coupon, subordination, convertible security and conversion into another security, fund unit, collective investment vehicle, fund manager, security identifier, International Securities Identification Number, National Securities Identifying Number, CUSIP, CINS, SEDOL, Valoren, Euroclear Clearstream common code, Financial Instrument Global Identifier, ticker symbol, listing, home exchange, listing and delisting dates, exchange, financial instrument classification code, security form, securities restriction, securities offering, underwriter), their definitions, and FIBO's labels for security forms (registered, bearer, book entry, bearer and registered, miscellaneous), US securities restrictions (Rule 144A, Regulation S, Regulation D), offering types (public, private, exempt; firm commitment, best efforts) and fund types (mutual fund, exchange-traded fund, closed-end investment, hedge fund, fund of funds, pension fund). Element descriptions paraphrase FIBO's definitions, and `reference` fields link to the FIBO concepts used. The direct consolidating parent relationship comes from FIBO's Business Entities (BE) domain, as in this repository's business-entities package.
- **Changed:** FIBO's OWL classes and properties were flattened into labelled nodes, relationships and typed properties. Security, fund, offering and security-form class hierarchies became coded properties using FIBO's labels; FIBO's pairwise `isSubordinatedTo` became a four-level `seniority` property; issuer, underwriter, depositary and fund-manager roles became relationships to a single legal-entity node; each identifier became a node keyed by scheme and value; fund positions became one `HOLDS` relationship carrying a portfolio weight and market value. Five properties were added that FIBO does not define as such: a sector name on legal entities, a face amount outstanding on securities, an underwriter's syndicate role, a fund's total net assets and its holdings reporting date.
- **Not taken:** much of the SEC domain — asset-backed, mortgage-backed and collateralised debt obligation structures and their pools; baskets and parametric schedules; call, put, sinking-fund and redemption provisions and their schedules; interest and principal payment terms and day-count conventions; dividends and share payment status; voting rights and share classes; identifier schemes and registries as entities; the CFI code's individual attribute classes; European securities restrictions; pension plans; and derivatives, which FIBO covers in a separate domain.

The result is a simplification for demonstration, not FIBO itself, and it is not endorsed by the EDM Council or the Object Management Group. The sample data is synthetic and contains nothing from FIBO.

## Copyright notices

The FIBO files this package drew on carry these notices, as of the source revision used: `edmcouncil/fibo` master at commit `33a92cd34285d532c158da97bb42add089f135d3` (27 October 2026).

| FIBO file | Notice |
| --------- | ------ |
| `SEC/Securities/SecuritiesIssuance.rdf` | Copyright (c) 2016-2025 Object Management Group, Inc.; Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc. |
| `SEC/Securities/SecuritiesIdentification.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2018-2025 Object Management Group, Inc. |
| `SEC/Securities/SecuritiesIdentificationIndividuals.rdf` | Copyright (c) 2016-2025 Object Management Group, Inc.; Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc. |
| `SEC/Securities/SecuritiesListings.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2018-2025 Object Management Group, Inc. |
| `SEC/Securities/SecuritiesClassification.rdf` | Copyright (c) 2016-2025 Object Management Group, Inc.; Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc. |
| `SEC/Securities/SecuritiesRestrictions.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2018-2025 Object Management Group, Inc. |
| `SEC/Securities/NorthAmericanSecurities/USSecuritiesRestrictions.rdf` | Copyright (c) 2024-2025 EDM Council, Inc.; Copyright (c) 2024-2025 Object Management Group, Inc. |
| `SEC/Securities/Pools.rdf` | Copyright (c) 2016-2025 Object Management Group, Inc.; Copyright (c) 2016-2026 EDM Association dba EDM Council, Inc. |
| `SEC/Equities/EquityInstruments.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2018-2026 EDM Association dba EDM Council, Inc. |
| `SEC/Equities/DepositaryReceipts.rdf` | Copyright (c) 2013-2024 EDM Council, Inc.; Copyright (c) 2013-2024 Object Management Group, Inc. |
| `SEC/Debt/DebtInstruments.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2018-2025 Object Management Group, Inc. |
| `SEC/Debt/Bonds.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2018-2025 Object Management Group, Inc. |
| `SEC/Funds/Funds.rdf` | Copyright (c) 2018-2025 Object Management Group; Copyright (c) 2018-2026 EDM Association dba EDM Council, Inc. |

The direct consolidating parent relationship cites `BE/LegalEntities/LEIEntities.rdf` (Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc.), and the `reference` links for security, issuer and exchange point to FIBO's Financial Business and Commerce (FBC) domain, whose definitions SEC builds on; no text was taken from those files beyond the concept names.

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
