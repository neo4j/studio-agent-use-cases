# Source and license notice

The structure of the reference ontology in this package — its labels, relationships and keys — follows **Neo4j's Transaction and Account Data Model** (<https://neo4j.com/developer/industry-use-cases/data-models/transaction-graph/transaction/transaction-base-model/>), not FIBO. Its descriptions, aliases and references draw on the **Financial Industry Business Ontology (FIBO)**, developed by the EDM Council (Enterprise Data Management Council) and published at <https://github.com/edmcouncil/fibo> under the MIT License.

## What was taken from FIBO, and how it was changed

- **Taken:** definitions, synonyms and concept IRIs for the customer (`Customer`), the account (`DepositAccount`, with `DemandDepositAccount` and `TimeDepositAccount` named in the account type), the payment (`IndividualTransaction`), the account holder with its primary and secondary holder properties (`AccountHolder`, `hasPrimaryAccountHolder`, `hasSecondaryAccountHolder`), the payer and payee roles (`Payer`, `Payee`), identity documents (`Passport`, `DriversLicense`), and contact points (`ElectronicMailAddress`, `TelephoneNumber`, `PhysicalAddress`). Element descriptions paraphrase FIBO's definitions, `aliases` use its synonyms where it has them, and `reference` fields link to the FIBO concepts used.
- **Changed:** FIBO's OWL classes and properties were flattened into labelled nodes, relationships and typed properties shaped by the Neo4j base model. The primary and secondary holder properties became the `role` of a customer-to-account relationship; FIBO's payer and payee roles became the direction of a payment between two accounts; the deposit-account subclasses became an open account-type text; and identity documents, which FIBO links to the person they identify, became relationships from the customer to the document, carrying verification details FIBO does not model. `Customer` is defined in FIBO's general products-and-services module rather than in clients and accounts.
- **Not taken:** FIBO's structure; its ownership and account-identifier patterns; the `IdentityDocument` superclass, since the base model keeps passports and driving licences as separate labels; `NetworkLocation`, the nearest FIBO concept to an IP address, which describes a location rather than an address; Country, which FIBO takes from the OMG Commons library rather than defining; and all fraud and anti-money-laundering content, which FIBO does not cover. Device, session and IP address have no FIBO equivalent and are described from the Neo4j pages.

The result is a simplification for demonstration, not FIBO itself, and it is not endorsed by the EDM Council or the Object Management Group. The sample data is synthetic and contains nothing from FIBO.

## Copyright notices

The FIBO files this package drew on carry these notices, as of the source revision used: `edmcouncil/fibo` master at commit `33a92cd34285d532c158da97bb42add089f135d3` (27 October 2026).

| FIBO file | Notice |
| --------- | ------ |
| `FBC/ProductsAndServices/ClientsAndAccounts.rdf` | Copyright (c) 2015-2025 Object Management Group, Inc.; Copyright (c) 2015-2026 EDM Association dba EDM Council, Inc. |
| `FND/ProductsAndServices/ProductsAndServices.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `FND/ProductsAndServices/PaymentsAndSchedules.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `FND/AgentsAndPeople/People.rdf` | Copyright (c) 2013-2025 Object Management Group, Inc.; Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc. |
| `FND/Places/VirtualPlaces.rdf` | Copyright (c) 2013-2025 EDM Council, Inc.; Copyright (c) 2013-2025 Object Management Group, Inc. |
| `FND/Places/Addresses.rdf` | Copyright (c) 2013-2025 Object Management Group, Inc.; Copyright (c) 2013-2026 EDM Association dba EDM Council, Inc. |

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
