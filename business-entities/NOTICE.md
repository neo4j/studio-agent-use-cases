# Source and license notice

The reference ontology in this package is adapted from the **Business Entities (BE) domain of the Financial Industry Business Ontology (FIBO)**, developed by the EDM Council (Enterprise Data Management Council) and published at <https://github.com/edmcouncil/fibo> under the MIT License.

## What was taken from FIBO, and how it was changed

- **Taken:** the concepts the reference ontology is organised around (business entity, legal form, legal entity identifier, date of incorporation, jurisdiction of incorporation, registered address, entity owner and ownership percentage, shareholder, limited liability company member, general and limited partner, board member and executive versus non-executive board member, corporate officer, chief executive officer, chief financial officer, company secretary, managing member, trust, trustor, trustee, trust beneficiary, direct and ultimate consolidating parent), their definitions, and FIBO's class labels for legal forms (publicly held company, privately held company, private limited company, limited liability company, joint stock company, general partnership, limited partnership, limited liability partnership, joint venture, not-for-profit corporation, cooperative society) and trust types (revocable, irrevocable, testamentary). Element descriptions paraphrase FIBO's definitions, and `reference` fields link to the FIBO concepts used.
- **Changed:** FIBO's OWL classes and properties were flattened into labelled nodes, relationships and typed properties. Party roles (owner, shareholder, member, partner, board member, officer, trustor, trustee, beneficiary) became relationships; legal-form and trust class hierarchies became coded properties; FIBO's ownership situations became a single `OWNS` relationship carrying the ownership percentage and an interest type; jurisdictions and addresses became plain nodes; LEI relationship records became two reported-parent relationships. Four properties were added that FIBO does not define as such: a politically-exposed-person flag on people, an offshore-financial-centre policy flag on jurisdictions, an active/inactive registration status on entities, and an interest type on ownership that names FIBO's owner roles.
- **Not taken:** much of the BE domain — government entities and the jurisdiction catalogues, functional entities, organisational sub-units, constitutional documents and agreements, powers of attorney, LEI registration details beyond the identifier and the two parent relationships, and FIBO's distinctions between de jure and de facto control, voting and non-voting shares, and accounting consolidation types.

The result is a simplification for demonstration, not FIBO itself, and it is not endorsed by the EDM Council or the Object Management Group. The sample data is synthetic and contains nothing from FIBO.

## Copyright notices

The FIBO files this package drew on carry these notices, as of the source revision used: `edmcouncil/fibo` master at commit `33a92cd34285d532c158da97bb42add089f135d3` (27 October 2026).

| FIBO file | Notice |
| --------- | ------ |
| `BE/LegalEntities/LegalPersons.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/LegalEntities/FormalBusinessOrganizations.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/LegalEntities/CorporateBodies.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/LegalEntities/LEIEntities.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/FunctionalEntities/FunctionalEntities.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/OwnershipAndControl/OwnershipParties.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group |
| `BE/OwnershipAndControl/ControlParties.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/OwnershipAndControl/CorporateOwnership.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group |
| `BE/OwnershipAndControl/CorporateControl.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/OwnershipAndControl/Executives.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/Trusts/Trusts.rdf` | Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/Partnerships/Partnerships.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `BE/PrivateLimitedCompanies/PrivateLimitedCompanies.rdf` | Copyright (c) 2016-2025 EDM Council, Inc.; Copyright (c) 2016-2025 Object Management Group, Inc. |

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
