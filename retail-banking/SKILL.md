---
name: retail-banking
description: Detect retail banking fraud on one connected graph of money, identity and digital access — customers, accounts, payments, shared identifiers and identity documents, sessions, devices, IP addresses and countries — built on Neo4j's Transaction and Account Data Model with definitions drawn from the EDM Council's FIBO. Provides a reference ontology, bundled synthetic sample data, and Cypher for transaction rings (cycles, chronology and amount decay), synthetic identity clusters, device sharing, account takeover followed by a payment to a new beneficiary, money mule accounts by account age and dwell time, layered payments to high-risk jurisdictions, and rings whose members share a device or identifier, plus optional Graph Data Science clustering.
metadata:
  neo4j-card-title: Retail Banking Fraud
  neo4j-card-category: Financial Services
  neo4j-card-description: Follow money, people and devices together to expose transaction rings, money mules, account takeovers and synthetic identities.
---

# Retail Banking Fraud

Use this skill for retail-banking fraud and financial-crime teams, and developers building on their data, who need to see fraud that only appears across payments, identities and digital sessions together: money laundered round rings of accounts, identities assembled from shared details, accounts taken over and emptied, and mule accounts that pass stolen money on.

Source references:

- <https://neo4j.com/developer/industry-use-cases/data-models/transaction-graph/transaction/transaction-base-model/> — Transaction and Account Data Model, the structure this reference ontology follows
- <https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/transaction-ring/>
- <https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/synthetic-identity-fraud/>
- <https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/account-takeover-fraud/>
- <https://neo4j.com/developer/industry-use-cases/finserv/retail-banking/transaction-monitoring/rules/transaction-monitoring-high-risk-jurisdictions/>
- <https://neo4j.com/developer/industry-use-cases/whitepapers/finserv/fraud/mule-account-mitigation/>
- <https://github.com/edmcouncil/fibo> — FIBO, the source of the definitions, aliases and references

Do not treat this as legal or regulatory advice; use it for graph-modelling and query-pattern guidance. Treat every result as an investigative lead requiring analyst review, not proof of fraud, and never as a basis for action against a customer on its own. The bundled sample data is synthetic.

## Sources and license

The structure — labels, relationships, keys — follows Neo4j's Transaction and Account Data Model. FIBO (the EDM Council's Financial Industry Business Ontology, MIT License) supplies only meaning: descriptions paraphrase FIBO definitions, `aliases` use its synonyms, and `reference` fields link to the FIBO concepts used. FIBO has no fraud or anti-money-laundering concepts, so none of the patterns come from it. This is not FIBO and is not endorsed by the EDM Council; credit FIBO when explaining what a term means. The attribution, the copyright notices of the FIBO files used, the MIT License text, and what was taken and changed are in `NOTICE.md`.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: retail fraud hides in the connections between payments, people and devices. A ring of payments, a cluster of customers sharing one phone, a login from a new device followed by a payment to a stranger, a new account that passes money straight on — each is invisible one record at a time, and a graph makes each one a traversal.
- The bundled sample data is synthetic: a few months of everyday retail banking — salaries, card spend, bills, transfers between friends, remittances, logins — with rings, synthetic identities, account takeovers, mule accounts and layered payments abroad seeded among it, each beside a look-alike the stricter query should reject.
- What you can help with: explaining the reference ontology, walking through the query patterns from simple to strict, importing the sample data or mapping their own data onto the reference ontology, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- **Money.** `Customer {customerId}` holds `Account {accountNumber}` through `HAS_ACCOUNT {role, since}`, where `role` is `PRIMARY` or `SECONDARY` (FIBO's primary and secondary account holder). `Account` carries `accountScope` (`INTERNAL` or `EXTERNAL`), `accountType` and `openedDate`, and is hosted in a `Country {code}` (`IS_HOSTED`). A payment is a `Transaction {transactionId, amount, currency, date, type}` node: `(Account)-[:PERFORMS]->(Transaction)-[:BENEFITS_TO]->(Account)`.
- **Identity.** `Customer` links to `Email {address}`, `Phone {phoneNumber}` and `Address {addressId}` (`HAS_EMAIL`, `HAS_PHONE` with `since`; `HAS_ADDRESS` with `addedAt`, `lastChangedAt`, `isCurrent`), and to `Passport {passportId}` and `DrivingLicense {licenseId}` (`HAS_PASSPORT`, `HAS_DRIVING_LICENSE` with `verificationDate`, `verificationMethod`, `verificationStatus`). An address is `LOCATED_IN` a `Country`.
- **Digital footprint.** `(Customer)-[:HAS_SESSION]->(Session {sessionId, status, createdAt})`, and each session `SESSION_USES_DEVICE` one `Device {deviceId}` and `USES_IP` one `IP {ipAddress}`, which is `LOCATED_IN` a `Country`.
- **Shared values are shared nodes.** Two customers with one email, phone, address or document converge on one node, which is what every identity pattern traverses. Normalise values upstream: the reference ontology performs none.
- **Divergences from the base model:**
  - `Internal`, `External` and `HighRiskJurisdiction` labels became properties: `Account.accountScope`, and `Country.isHighRiskJurisdiction` reached through `IS_HOSTED`. `Account` keeps a single label.
  - `(Device)-[:USED_BY]->(Customer)` is dropped: it is derivable from sessions, and sessions are the source of truth for device use.
  - `HAS_SESSION` is added: the account-takeover page uses it, but the base model does not declare it.
  - There is no link between a `Session` and a `Transaction`, as in the source; **Account takeover** correlates the two by time on the same customer.
  - `IP` geolocates straight to `Country` through `LOCATED_IN`, not through `Location`. `LOCATED_IN` is reused on two node pairs and carries no constraint flags.
  - The composite keys became single surrogate keys built from the same parts, so MERGE deduplicates exactly as before, and the parts stay as properties: `addressId` (line 1, post town and postcode, normalised and joined), `passportId` and `licenseId` (`<issuingCountry>:<number>`).
  - `Phone`'s key is `phoneNumber`, as in the base model's property list; its constraint and demo code say `number`.
  - Every temporal property is ZONED DATETIME. Calendar dates (`dateOfBirth`, document issue and expiry) are midnight UTC, because Import cannot load `DATE` from local files.
  - `accountNumber` is a STRING (sort code and account number, or IBAN), not an integer.
  - Left out because no query uses them: `Customer` middle name, place and country of birth; `Account` closed and suspended dates; `Transaction.message`; `Address` region and coordinates; `Passport.nationality`; and the `createdAt` record timestamps on identifier, document, device and IP nodes.
- **Excluded from the base model:**
  - Investigation workflow — `Alert`, `Case`, `SUBJECT_OF`, `TRIGGERED` and the `Flagged`, `UnderInvestigation` and `Confirmed` labels: the package shows the fraud in the data, not the operations around it, and the source marks them as proposed.
  - `Face`: it needs embeddings and a vector index.
  - `Movement`: instalment payments are not a fraud story here.
  - `Counterparty`: deferred, since external accounts have no `Customer` behind them.
  - `ISP` and `Location`: an IP address geolocates straight to `Country`.
  - `HAS_NATIONALITY`: no query needs it.
  - The account-takeover page's event nodes (`Authentication`, `ChangePhone`, `ChangeEmail`, `ChangeAddress`, `AddExternalAccount`, `Transfer`, `NEXT`): they belong to the separate fraud event-sequence model.
- **Where queries differ from the source pages:**
  - The decay query divides each payment's amount by the previous one's and accepts 0.80–1.00, a loss of up to 20% per hop. The source page's version divides the other way round, which accepts growth instead of decay; this package follows the page's stated intent, not its Cypher.
  - The high-risk payment query compares single payments with the final payment's amount and bounds the chain at three earlier payments; the source rule compares 30-day totals per account pair and is unbounded.
  - Device sharing reads device use from sessions, not from `USED_BY`.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything. The optional GDS statements build an in-memory projection, which is not written to the database.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases`, allowed values (`one_of`, `pattern`) and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias often names the user's equivalent label), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Party | `Customer` | One node per real person, linked to the accounts they hold. Without resolved identity, shared identifiers link records of one person to themselves |
| Account money passes through | `Account` | A stable key that payments both leave and arrive at, whether it is held here or elsewhere, plus an opening date and an internal-or-external flag for the mule and high-risk patterns |
| Directed transfer | `Transaction` | A node per payment with one payer and one beneficiary, a positive amount, a true execution timestamp and a payment method. Transfers stored as account-to-account relationships need the patterns rewritten around relationship properties |
| Shared identifier | `Email`, `Phone`, `Address`, `Passport`, `DrivingLicense` | Each value as its own node, so customers who share it converge on it. Identifiers stored as plain properties need a join on equal values instead |
| Digital access | `Session` → `Device`, `IP` | Timestamped login events per customer with the device and network used. Without them the device and takeover patterns have no analogue |
| Jurisdiction | `Country` | Where an account is held and where an IP address geolocates, with the institution's own high-risk classification |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Supporting files

| File | Load when |
| ---- | --------- |
| `NOTICE.md` | The user asks about the FIBO source, licensing, copyright or attribution, or exactly which parts of FIBO were used and how they were changed |

## Operational Constraints

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes or constraints after Import.
- Neo4j 5.9+ and Cypher 5. The two ring queries headed "(requires APOC)" need `apoc.coll.toSet`, and the statements headed "(requires GDS)" need the Graph Data Science plugin; check the procedure exists before offering them. Every other query is plain Cypher. Run the GDS statements in order — project, cluster, drop — and always drop the projection.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params`, and the literal hop bounds and amount band in the ring queries, are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding. Quantifier bounds cannot be parameters, so a different depth means editing the query text; never remove an upper bound.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or the **Graph census** and an `@sample` anchor match it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Run the ring checks in order, broad to strict: directed rings, then distinct accounts, then chronology and amount decay. The progression shows which condition removes a ring. Validate the ratio direction against a known example before trusting results; inverting it silently returns amount-growth rings. Amount ratios assume one currency per ring; partial payments and conversion break them.
- Before applying any time-based check to the user's data, confirm `Transaction.date` and `Session.createdAt` are true event timestamps rather than posting or batch dates, and that `amount` is numeric.
- `Country.isHighRiskJurisdiction` is the institution's policy setting. Ask whose list the user's data reflects before calling a payment high-risk, and never present the sample's flags as an official list.
- Shared identifiers have innocent explanations — households share addresses and landlines, families share tablets, mobile networks share IP addresses — and closed payment loops do too: refunds, loan repayments, transfers between a customer's own accounts. Weigh a result by how many independent layers agree (a ring whose members also share a device, a takeover whose beneficiary is a new pass-through account) rather than presenting any single pattern as a finding.
- The bundled sample's patterns are seeded deliberately, so a hit rate on it is not a measure of precision on real data.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
