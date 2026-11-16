# Retail Banking Fraud — Query Guidance

Cypher for the `retail-banking` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database; the optional Graph Data Science section creates and drops an in-memory projection, and nothing else.

## Prerequisites

- Neo4j 5.9+ and Cypher 5. The ring queries and **Payment to a high-risk jurisdiction** use quantified path patterns (`{3,6}`, `{2,5}`, `{0,3}`); the decay and high-risk queries use chained comparisons (`0.80 <= x <= 1.00`); several queries use `COUNT {}`, `COLLECT {}` and `EXISTS {}` subqueries.
- **Directed ring with distinct accounts** and **Chronological and amount-decay ring** require APOC (`apoc.coll.toSet`) for their distinct-account filter, and say so in their headings. The queries under **Graph Data Science (optional)** require the GDS plugin. Every other query is plain Cypher.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own banking data mapped onto the reference ontology.
- The node keys in `ONTOLOGY.json` make `Customer.customerId`, `Account.accountNumber`, `Transaction.transactionId`, `Session.sessionId`, `Device.deviceId` and the other keys unique, so any anchored lookup is an index seek rather than a label scan.
- The ring queries take no parameter: every account is tried as the starting point of a ring. The other queries take parameters; each `@params` entry gives a starting value and how to tune it.
- Calendar dates (`dateOfBirth`, document dates) are ZONED DATETIME values at midnight UTC: compare them with `datetime(...)` and show them through `date()`.
- The queries are listed in the order to run them. Start with the census; run the ring queries broad to strict, so each one shows which condition removes a candidate ring; then the identity, device, takeover, mule and high-risk payment patterns, simplest first; and the cross-layer ring last, since it joins the ring to the identity and device layers.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Graph census

```cypher
/*
 * @name           Graph census
 * @description    Counts the nodes of every label in the reference ontology
 *                 to confirm the import landed before running anything else.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row with a count per label: customers, accounts,
 *                 transactions, countries, emails, phones, addresses,
 *                 passports, drivingLicenses, sessions, devices and ips.
 * @usage          Run straight after an import. A zero means that label's
 *                 table did not load. The census counts nodes only; a payment
 *                 whose account columns did not resolve still counts as a
 *                 Transaction but sits on no path, and a session whose device
 *                 did not resolve still counts but links to no device.
 * @tags           sanity-check, import, orientation
 * @sample         Bundled sample data only: returns 1 row — customers 1266,
 *                 accounts 1892, transactions 7906, countries 21, emails
 *                 1376, phones 1285, addresses 986, passports 542,
 *                 drivingLicenses 699, sessions 7432, devices 1748, ips 956.
 */
RETURN COUNT { (:Customer) } AS customers,
       COUNT { (:Account) } AS accounts,
       COUNT { (:Transaction) } AS transactions,
       COUNT { (:Country) } AS countries,
       COUNT { (:Email) } AS emails,
       COUNT { (:Phone) } AS phones,
       COUNT { (:Address) } AS addresses,
       COUNT { (:Passport) } AS passports,
       COUNT { (:DrivingLicense) } AS drivingLicenses,
       COUNT { (:Session) } AS sessions,
       COUNT { (:Device) } AS devices,
       COUNT { (:IP) } AS ips;
```

## Directed ring (basic)

```cypher
/*
 * @name           Directed ring (basic)
 * @description    First pass: proves directed rings exist at all. Follows
 *                 money out of an account through PERFORMS to a Transaction
 *                 and on through BENEFITS_TO to the beneficiary account,
 *                 three to six times, ending back at the starting account.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology and Neo4j 5.9+.
 * @returns        One row per ring and starting account: path, alternating
 *                 Account and Transaction nodes from the starting account
 *                 back to it. A ring of n accounts is returned n times, once
 *                 rotated to start at each of its accounts.
 * @usage          The hop bound {3,6} is a literal — Cypher rejects a
 *                 parameter inside a quantifier, so changing it means editing
 *                 the query text. Three is the shortest ring that is not a
 *                 two-account round trip; widen the upper bound one step at a
 *                 time, because cost grows quickly with ring length on a dense
 *                 graph, and never remove it. A bare cycle is a weak signal:
 *                 use this to show rings exist, then tighten with the queries
 *                 below.
 * @tags           ring, cycle, layering, fraud
 * @sample         Bundled sample data only: returns 132 paths covering 33
 *                 distinct rings, among them 12-34-57 43064339 → 12-34-58
 *                 25868819 → 12-34-56 28166225 → 12-34-58 39026094 → back to
 *                 the start, once rotated to start at each of its accounts.
 */
MATCH path =
  (start:Account)
  (()-[:PERFORMS]->()-[:BENEFITS_TO]->()){3,6}
  (start)
RETURN path;
```

## Directed ring with distinct accounts (requires APOC)

```cypher
/*
 * @name           Directed ring with distinct accounts (requires APOC)
 * @description    The basic directed ring, keeping only rings whose paying
 *                 accounts are all different. Drops rings that revisit an
 *                 intermediate account, which are usually legitimate
 *                 back-and-forth activity rather than layering.
 * @params         None
 * @prerequisites  APOC (apoc.coll.toSet) and Neo4j 5.9+.
 * @returns        One row per ring and starting account: path, as for the
 *                 basic directed ring, restricted to rings with no repeated
 *                 account.
 * @usage          On real payments data this is the filter that does the most
 *                 work. It uses the same literal {3,6} hop bound as the basic
 *                 query. Without APOC, replace
 *                 size(apoc.coll.toSet(source)) = size(source) with a
 *                 reduce-based distinctness check, or accept the repeats and
 *                 filter downstream.
 * @tags           ring, cycle, layering, fraud, apoc
 * @sample         Bundled sample data only: returns 55 paths covering 15
 *                 rings, among them the ring through 12-34-57 43064339 once
 *                 per account; the other 18 rings from Directed ring (basic)
 *                 revisit an account.
 */
MATCH path =
  (start:Account)
  ((source)-[:PERFORMS]->(tx)-[:BENEFITS_TO]->(target)){3,6}
  (start)
WHERE size(apoc.coll.toSet(source)) = size(source)
RETURN path;
```

## Chronological and amount-decay ring (requires APOC)

```cypher
/*
 * @name           Chronological and amount-decay ring (requires APOC)
 * @description    The strictest check: a ring of distinct accounts in which
 *                 each payment executes after the one before it
 *                 (Transaction.date, the execution timestamp) and carries
 *                 80–100% of the previous payment's amount (Transaction.amount,
 *                 in major currency units) — the signature of a cut being
 *                 taken at every hop.
 * @params         None
 * @prerequisites  APOC (apoc.coll.toSet) and Neo4j 5.9+. Every payment on a
 *                 ring in one currency: the reference ontology performs no
 *                 conversion.
 * @returns        One row per qualifying ring: path, from the starting account
 *                 through each payment and intermediate account back to it.
 *                 Only the rotation that starts with the ring's earliest
 *                 payment can qualify, since every other rotation steps back
 *                 in time.
 * @usage          The ratio band 0.80–1.00 is a literal, computed as next
 *                 amount divided by previous amount: it accepts a loss of up
 *                 to 20% per hop — the fee commonly taken as money passes
 *                 through a ring — and rejects any growth. Narrow it towards
 *                 1.00 to target small skims; widen it only with a reason,
 *                 since ordinary commerce passes a wide band. Validate the
 *                 direction on a known example: inverting the ratio silently
 *                 returns amount-growth rings. The repetition bound {2,5} is
 *                 also a literal: two to five intermediate accounts, so rings
 *                 of three to six accounts, matching the other ring queries.
 *                 Its lower bound keeps two-account round trips such as
 *                 refunds and loan repayments out. Partial payments and
 *                 currency conversion break the ratio assumption.
 * @tags           ring, chronology, amount-decay, layering, fraud, apoc
 * @sample         Bundled sample data only: returns 6 paths, one per ring,
 *                 among them the ring anchored at account 12-34-57 43064339,
 *                 amounts 1000.00 → 900.00 → 810.00 → 729.00 on consecutive
 *                 days.
 */
MATCH path =
  (start:Account)-[:PERFORMS]->(firstTx)
  (
    (previousTx)-[:BENEFITS_TO]->(middleAccount)-[:PERFORMS]->(nextTx)
    WHERE previousTx.date < nextTx.date
      AND 0.80 <= nextTx.amount / previousTx.amount <= 1.00
  ){2,5}
  (lastTx)-[:BENEFITS_TO]->(start)
WHERE size(apoc.coll.toSet([start] + middleAccount)) = size([start] + middleAccount)
RETURN path;
```

## Synthetic identity clusters

```cypher
/*
 * @name           Synthetic identity clusters
 * @description    Pairs of customers who share at least a given number of
 *                 distinct identifier types — Email, Phone, Address, Passport,
 *                 DrivingLicense — together with the money behind them: the
 *                 accounts the pair holds, when the newest was opened, and
 *                 what those accounts have sent. Identities assembled from
 *                 shared contact details and reused documents converge on the
 *                 same identifier nodes; their accounts show what the cluster
 *                 does with money.
 * @params         minSharedTypes - Minimum number of distinct identifier
 *                     types the two customers share. Integer. Start at 2:
 *                     one shared identifier, an address above all, is
 *                     ordinary among family and flatmates. Raise to 3 to
 *                     separate households, which commonly share an address
 *                     and a landline, from identities assembled from shared
 *                     details.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per customer pair: customer1 and customer2
 *                 (customerId), sharedTypes (the identifier labels shared),
 *                 sharedTypeCount, accounts (accountNumber of every account
 *                 either holds), newestAccountOpened (a date), paymentsSent
 *                 and amountSent (count and total of payments those accounts
 *                 performed, in their recorded currencies). Ordered by
 *                 sharedTypeCount, then newest account first.
 * @usage          A shared passport or driving licence is the strongest
 *                 signal; a shared address alone is the weakest. HAS_ADDRESS
 *                 includes previous addresses (isCurrent false), so two
 *                 people who lived at one address years apart still pair —
 *                 add WHERE r.isCurrent where that matters. A recently opened
 *                 account in a strongly linked pair is the bust-out pattern
 *                 to look at first. The literal LIMIT 50 keeps the list
 *                 reviewable; raise minSharedTypes rather than the limit.
 *                 For clusters larger than a pair, use the GDS section.
 * @tags           synthetic-identity, shared-identifier, first-party-fraud
 * @sample         Bundled sample data only: $minSharedTypes = 2 returns 44
 *                 rows, 6 of them sharing three or more types; the first
 *                 pairs CUS10469 and CUS11143, sharing Address, Email,
 *                 Passport and Phone. $minSharedTypes = 3 returns those 6.
 */
MATCH (c1:Customer)-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]->(identifier)
      <-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]-(c2:Customer)
WHERE elementId(c1) < elementId(c2)
WITH c1, c2, collect(DISTINCT head(labels(identifier))) AS sharedTypes
WHERE size(sharedTypes) >= $minSharedTypes
UNWIND [c1, c2] AS holder
OPTIONAL MATCH (holder)-[:HAS_ACCOUNT]->(a:Account)
WITH DISTINCT c1, c2, sharedTypes, a
OPTIONAL MATCH (a)-[:PERFORMS]->(t:Transaction)
WITH c1, c2, sharedTypes,
     collect(DISTINCT a.accountNumber) AS accounts,
     max(a.openedDate) AS newestOpened,
     count(t) AS paymentsSent,
     sum(t.amount) AS totalSent
RETURN c1.customerId AS customer1,
       c2.customerId AS customer2,
       sharedTypes,
       size(sharedTypes) AS sharedTypeCount,
       accounts,
       date(newestOpened) AS newestAccountOpened,
       paymentsSent,
       round(totalSent, 2) AS amountSent
ORDER BY sharedTypeCount DESC, newestAccountOpened DESC, customer1, customer2
LIMIT 50;
```

## Device sharing

```cypher
/*
 * @name           Device sharing
 * @description    Devices that sessions of several different customers ran
 *                 on, expanded to each of those customers and the accounts
 *                 they hold. One device logging in as many customers is the
 *                 footprint of credential stuffing, of a mule herder
 *                 operating recruited accounts, or of one person behind
 *                 several identities.
 * @params         minCustomers - Minimum number of distinct customers with a
 *                     session on the device. Integer. Start at 3: a device
 *                     shared by a couple is ordinary. Raise until the result
 *                     is reviewable.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per device and customer: device (deviceId),
 *                 deviceType, customersOnDevice, customer (customerId),
 *                 successfulSessions and otherSessions (that customer's
 *                 sessions on the device by Session.status), and accounts
 *                 (each held account as "accountNumber (role)").
 * @usage          Device use is read from sessions, any status: a
 *                 credential-stuffing device shows many failed sessions
 *                 across customers and success on a few, a mule herder's
 *                 device shows successful sessions on every account it
 *                 runs. A family tablet shared by three people looks like
 *                 the second at a low threshold; check deviceType and
 *                 whether the customers share an address. The literal
 *                 LIMIT 100 keeps the list reviewable.
 * @tags           device, digital-footprint, credential-stuffing, mule
 * @sample         Bundled sample data only: $minCustomers = 3 returns 28
 *                 rows over 6 devices; the first, DEV-626ae42f56 (desktop),
 *                 has sessions from 10 customers.
 */
MATCH (d:Device)<-[:SESSION_USES_DEVICE]-(:Session)<-[:HAS_SESSION]-(c:Customer)
WITH d, collect(DISTINCT c) AS customers
WHERE size(customers) >= $minCustomers
UNWIND customers AS c
RETURN d.deviceId AS device,
       d.deviceType AS deviceType,
       size(customers) AS customersOnDevice,
       c.customerId AS customer,
       COUNT { (c)-[:HAS_SESSION]->(s:Session)-[:SESSION_USES_DEVICE]->(d) WHERE s.status = 'success' } AS successfulSessions,
       COUNT { (c)-[:HAS_SESSION]->(s:Session)-[:SESSION_USES_DEVICE]->(d) WHERE s.status <> 'success' } AS otherSessions,
       COLLECT { MATCH (c)-[h:HAS_ACCOUNT]->(a:Account) RETURN a.accountNumber + ' (' + h.role + ')' } AS accounts
ORDER BY customersOnDevice DESC, device, customer
LIMIT 100;
```

## Account takeover

```cypher
/*
 * @name           Account takeover
 * @description    A successful session from a device, or from an IP address
 *                 in a country, that none of the customer's earlier
 *                 successful sessions used, followed within a bounded window
 *                 by a push payment from one of the customer's accounts to an
 *                 account none of them has paid before. The reference
 *                 ontology has no link between a session and a payment, so
 *                 the two are correlated by time on the same customer.
 * @params         windowHours - Hours after the session within which the
 *                     payment must execute. Integer. Start at 24: a takeover
 *                     is cashed out before the customer notices, usually the
 *                     same day; narrow towards 1 to keep only the fastest.
 *                 minPriorSessions - Minimum successful sessions the
 *                     customer had before this one. Integer. Start at 3:
 *                     with fewer there is no history against which a device
 *                     or country is new. A starting point with no strong
 *                     prior.
 *                 paymentTypes - Transaction.type values that count as push
 *                     payments the session could have instructed. List of
 *                     strings. Start with the push-payment methods in the
 *                     user's data — for UK data ['FASTER_PAYMENT', 'SWIFT'] —
 *                     after listing the distinct type values present.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per qualifying session and payment: customer,
 *                 session, sessionAt, device, newDevice, sessionCountry,
 *                 newCountry, payment, paidAt, amount, currency, fromAccount,
 *                 toAccount and minutesAfterLogin.
 * @usage          "Earlier" means earlier successful sessions only, so an
 *                 attacker's failed attempts from the same device do not make
 *                 it look familiar. Without minPriorSessions every
 *                 customer's first logins qualify. A new device alone is
 *                 common (a new phone) and so is a first payment to a friend;
 *                 the pattern is both, close together, followed by a
 *                 beneficiary that then moves the money on — check the
 *                 beneficiary with Mule account. On a large estate,
 *                 restrict s.createdAt to a recent period first. The literal
 *                 LIMIT 50 keeps the list reviewable.
 * @tags           account-takeover, session, device, new-payee
 * @sample         Bundled sample data only: $windowHours = 24,
 *                 $minPriorSessions = 3, $paymentTypes = ['FASTER_PAYMENT',
 *                 'SWIFT'] returns 4 rows; the first is CUS10596's session
 *                 SESS004513 from a new device in RO, followed 25 minutes
 *                 later by TXN4719, 4800.00 to 12-34-56 24563467.
 */
MATCH (c:Customer)-[:HAS_SESSION]->(s:Session {status: 'success'})-[:SESSION_USES_DEVICE]->(d:Device),
      (s)-[:USES_IP]->(:IP)-[:LOCATED_IN]->(country:Country)
WHERE COUNT { (c)-[:HAS_SESSION]->(p:Session {status: 'success'}) WHERE p.createdAt < s.createdAt } >= $minPriorSessions
WITH c, s, d, country,
     NOT EXISTS { (c)-[:HAS_SESSION]->(p:Session {status: 'success'})-[:SESSION_USES_DEVICE]->(d) WHERE p.createdAt < s.createdAt } AS newDevice,
     NOT EXISTS { (c)-[:HAS_SESSION]->(p:Session {status: 'success'})-[:USES_IP]->(:IP)-[:LOCATED_IN]->(country) WHERE p.createdAt < s.createdAt } AS newCountry
WHERE newDevice OR newCountry
MATCH (c)-[:HAS_ACCOUNT]->(a:Account)-[:PERFORMS]->(t:Transaction)-[:BENEFITS_TO]->(b:Account)
WHERE s.createdAt <= t.date <= s.createdAt + duration({hours: $windowHours})
  AND t.type IN $paymentTypes
  AND NOT EXISTS { (c)-[:HAS_ACCOUNT]->(b) }
  AND NOT EXISTS {
    MATCH (c)-[:HAS_ACCOUNT]->(:Account)-[:PERFORMS]->(earlier:Transaction)-[:BENEFITS_TO]->(b)
    WHERE earlier.date < t.date
  }
RETURN c.customerId AS customer,
       s.sessionId AS session,
       s.createdAt AS sessionAt,
       d.deviceId AS device,
       newDevice,
       country.code AS sessionCountry,
       newCountry,
       t.transactionId AS payment,
       t.date AS paidAt,
       t.amount AS amount,
       t.currency AS currency,
       a.accountNumber AS fromAccount,
       b.accountNumber AS toAccount,
       duration.inSeconds(s.createdAt, t.date).minutes AS minutesAfterLogin
ORDER BY paidAt, customer
LIMIT 50;
```

## Mule account

```cypher
/*
 * @name           Mule account
 * @description    Internal accounts that, soon after opening, receive money
 *                 from several unrelated senders and pass it on quickly: the
 *                 fan-in and short dwell time of a money mule. A sender is
 *                 unrelated when no customer holds both accounts, so a
 *                 customer moving money between their own accounts never
 *                 counts.
 * @params         maxAccountAgeDays - Only inflows that arrive within this
 *                     many days of Account.openedDate count. Integer. Start
 *                     at 90; a starting point with no strong prior. Widen it
 *                     to see established accounts that behave the same way.
 *                 minSenders - Minimum distinct unrelated sender accounts.
 *                     Integer. Start at 5, more unrelated payers than a new
 *                     personal account normally has; no strong prior.
 *                 maxDwellHours - An outgoing payment counts as quick when
 *                     it executes within this many hours after a counted
 *                     inflow. Integer. Start at 48; widen to 168 to include
 *                     weekly payers.
 *                 minPassThrough - Minimum share of the counted inflows that
 *                     left again in quick outgoing payments. Float. Start at
 *                     0.5 and raise towards 0.9 for near-total pass-through.
 * @prerequisites  None beyond the imported reference ontology. Accounts
 *                 without openedDate are skipped.
 * @returns        One row per account: account (accountNumber), opened (a
 *                 date), senders, inflowTotal, quickOutflowTotal,
 *                 passThrough (quickOutflowTotal / inflowTotal) and
 *                 quickOutflowCount, highest pass-through first.
 * @usage          Amounts are summed as recorded, so mixed currencies on one
 *                 account distort passThrough. A pass-through above 1 means
 *                 the account pays out more than these inflows brought in —
 *                 typically a business funded from elsewhere, not a mule.
 *                 Fan-in alone is ordinary for a trader or a club treasurer;
 *                 the combination with a new account and fast pass-through
 *                 is what separates a mule. Follow a hit's outgoing payments
 *                 with Payment to a high-risk jurisdiction, and its senders
 *                 with Account takeover. The literal LIMIT 50 keeps the list
 *                 reviewable.
 * @tags           mule, fan-in, fan-out, dwell-time, account-age
 * @sample         Bundled sample data only: $maxAccountAgeDays = 90,
 *                 $minSenders = 5, $maxDwellHours = 48, $minPassThrough = 0.5
 *                 returns 2 rows; the first is 12-34-56 24563467, opened
 *                 2023-11-02, with 7 senders and passThrough 0.95.
 */
MATCH (m:Account {accountScope: 'INTERNAL'})<-[:BENEFITS_TO]-(inTx:Transaction)<-[:PERFORMS]-(sender:Account)
WHERE inTx.date < m.openedDate + duration({days: $maxAccountAgeDays})
  AND NOT EXISTS { (m)<-[:HAS_ACCOUNT]-(:Customer)-[:HAS_ACCOUNT]->(sender) }
WITH m, collect(inTx) AS inflows, count(DISTINCT sender) AS senders
WHERE senders >= $minSenders
UNWIND inflows AS inTx
OPTIONAL MATCH (m)-[:PERFORMS]->(outTx:Transaction)
WHERE inTx.date <= outTx.date <= inTx.date + duration({hours: $maxDwellHours})
WITH m, senders, inflows, collect(DISTINCT outTx) AS quickOutflows
WITH m, senders,
     reduce(total = 0.0, t IN inflows | total + t.amount) AS inflowTotal,
     reduce(total = 0.0, t IN quickOutflows | total + t.amount) AS quickOutflowTotal,
     size(quickOutflows) AS quickOutflowCount
WHERE quickOutflowTotal >= $minPassThrough * inflowTotal
RETURN m.accountNumber AS account,
       date(m.openedDate) AS opened,
       senders,
       round(inflowTotal, 2) AS inflowTotal,
       round(quickOutflowTotal, 2) AS quickOutflowTotal,
       round(quickOutflowTotal / inflowTotal, 2) AS passThrough,
       quickOutflowCount
ORDER BY passThrough DESC, senders DESC, account
LIMIT 50;
```

## Payment to a high-risk jurisdiction

```cypher
/*
 * @name           Payment to a high-risk jurisdiction
 * @description    Payments in a review window to accounts hosted in a
 *                 country with isHighRiskJurisdiction true, each traced back
 *                 through up to three earlier payments to an internal
 *                 origin account. Every payment on the chain executes after
 *                 the one before it, inside the window, and carries an
 *                 amount within a band of the final payment — the same money
 *                 layered through intermediaries before it leaves.
 * @params         windowEnd - End of the review window, an ISO 8601
 *                     datetime string. On a live system, now; on a static
 *                     extract, the latest payment date
 *                     (MATCH (t:Transaction) RETURN max(t.date)).
 *                 windowDays - Length of the window in days. Integer. Start
 *                     at 30, the rolling period of the source monitoring
 *                     rule.
 *                 minRatio - Lower bound of each earlier payment's amount as
 *                     a fraction of the final payment's. Float. Start at
 *                     0.9, the source rule's band.
 *                 maxRatio - Upper bound, as above. Float. Start at 1.1.
 *                 minIntermediaries - Minimum accounts between the origin
 *                     and the beneficiary. Integer. Start at 1: layering
 *                     needs at least one intermediary; 0 also lists every
 *                     direct payment to a flagged country.
 * @prerequisites  Country.isHighRiskJurisdiction set from the institution's
 *                 own policy list. Neo4j 5.9+ for the quantified path.
 * @returns        One row per payment to a high-risk jurisdiction whose
 *                 longest qualifying chain has enough intermediaries:
 *                 country, beneficiary, payment, paidAt, amount, origin,
 *                 intermediaries, accounts and amounts along the chain, and
 *                 path.
 * @usage          The chain bound {0,3} is a literal: up to three earlier
 *                 payments, four in all. Where several chains qualify, the
 *                 longest is kept, then the one whose first payment is
 *                 latest. The band compares single payments; the source rule
 *                 compares totals per account pair, which also catches money
 *                 split into several payments. A chain whose first payment is
 *                 from an external account starts at the first internal
 *                 account instead. Direct remittances to family in a flagged
 *                 country are ordinary; a chain through new or unrelated
 *                 accounts is not. The literal LIMIT 50 keeps the list
 *                 reviewable.
 * @tags           high-risk-jurisdiction, layering, aml, transaction-monitoring
 * @sample         Bundled sample data only: $windowEnd =
 *                 '2024-01-01T00:00:00Z', $windowDays = 30, $minRatio = 0.9,
 *                 $maxRatio = 1.1, $minIntermediaries = 1 returns 3 rows;
 *                 the first is TXN6716, 9400.00 to an MC account, from origin
 *                 12-34-57 69122237 through 2 intermediaries.
 */
WITH datetime($windowEnd) AS windowEnd,
     datetime($windowEnd) - duration({days: $windowDays}) AS windowStart
MATCH (lastTx:Transaction)-[:BENEFITS_TO]->(dest:Account)-[:IS_HOSTED]->(hrj:Country {isHighRiskJurisdiction: true})
WHERE windowStart <= lastTx.date < windowEnd
MATCH path = (origin:Account {accountScope: 'INTERNAL'})-[:PERFORMS]->(firstTx:Transaction)
  (
    (prevTx:Transaction)-[:BENEFITS_TO]->(mid:Account)-[:PERFORMS]->(nextTx:Transaction)
    WHERE prevTx.date < nextTx.date
  ){0,3}
  (lastTx)
WHERE all(t IN prevTx WHERE t.date >= windowStart
                        AND $minRatio * lastTx.amount <= t.amount <= $maxRatio * lastTx.amount)
WITH lastTx, dest, hrj, path, origin, firstTx, size(mid) AS hops
ORDER BY hops DESC, firstTx.date DESC, origin.accountNumber
WITH lastTx, dest, hrj, collect({path: path, origin: origin, hops: hops})[0] AS longest
WHERE longest.hops >= $minIntermediaries
RETURN hrj.code AS country,
       dest.accountNumber AS beneficiary,
       lastTx.transactionId AS payment,
       lastTx.date AS paidAt,
       lastTx.amount AS amount,
       longest.origin.accountNumber AS origin,
       longest.hops AS intermediaries,
       [n IN nodes(longest.path) WHERE n:Account | n.accountNumber] AS accounts,
       [n IN nodes(longest.path) WHERE n:Transaction | n.amount] AS amounts,
       longest.path AS path
ORDER BY intermediaries DESC, paidAt
LIMIT 50;
```

## Cross-layer ring

```cypher
/*
 * @name           Cross-layer ring
 * @description    Transaction rings of distinct accounts whose holders are
 *                 also linked outside the money: two holders who banked from
 *                 the same device, or who share an email, phone, address,
 *                 passport or driving licence. A ring whose members are
 *                 connected people is one operation, not a coincidence of
 *                 payments.
 * @params         minLinkTypes - Minimum distinct link kinds (Device, Email,
 *                     Phone, Address, Passport, DrivingLicense) found among
 *                     the ring's holders. Integer. Start at 1 to see every
 *                     ring with any link; raise to 2 to drop rings joined only
 *                     by a shared household address.
 * @prerequisites  None beyond the imported reference ontology and Neo4j 5.9+.
 *                 Plain Cypher: distinctness is checked without APOC.
 * @returns        One row per ring: ringAccounts (accountNumber, in payment
 *                 order), holders (customerId), linkTypes, linkTypeCount and
 *                 linkedPairs (each linked pair of holders with its links).
 * @usage          The ring uses the same literal {3,6} bound and distinct-
 *                 account rule as Directed ring with distinct accounts, and
 *                 each ring is returned once, not once per rotation. Device
 *                 links come from sessions of any status. A shared address
 *                 alone is the weakest link — a family moving money round is
 *                 not fraud — while a shared device or document is the
 *                 strongest. Check the ring itself with Chronological and
 *                 amount-decay ring. The literal LIMIT 25 keeps the list
 *                 reviewable.
 * @tags           ring, cross-layer, shared-identifier, device, fraud
 * @sample         Bundled sample data only: $minLinkTypes = 1 returns 3
 *                 rows; $minLinkTypes = 2 returns 2, the five-account ring
 *                 through 12-34-56 42536850 (Device, Phone) and the
 *                 four-account ring through 12-34-56 47357986 (Address,
 *                 Email).
 */
MATCH (start:Account)
  ((source:Account)-[:PERFORMS]->(:Transaction)-[:BENEFITS_TO]->(:Account)){3,6}
  (start)
WHERE all(i IN range(0, size(source) - 2) WHERE NOT source[i] IN source[i + 1..])
  AND all(a IN source WHERE elementId(start) <= elementId(a))
WITH DISTINCT source AS ring
UNWIND ring AS account
MATCH (holder:Customer)-[:HAS_ACCOUNT]->(account)
WITH ring, collect(DISTINCT holder) AS holders
UNWIND holders AS c1
UNWIND holders AS c2
WITH ring, holders, c1, c2
WHERE elementId(c1) < elementId(c2)
WITH ring, holders, c1, c2,
     CASE WHEN EXISTS {
       (c1)-[:HAS_SESSION]->(:Session)-[:SESSION_USES_DEVICE]->(:Device)<-[:SESSION_USES_DEVICE]-(:Session)<-[:HAS_SESSION]-(c2)
     } THEN ['Device'] ELSE [] END
     + COLLECT {
       MATCH (c1)-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]->(shared)
             <-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]-(c2)
       RETURN DISTINCT head(labels(shared))
     } AS links
WHERE size(links) > 0
WITH ring, holders,
     collect({customers: [c1.customerId, c2.customerId], links: links}) AS linkedPairs,
     collect(links) AS linkLists
WITH ring, holders, linkedPairs,
     reduce(acc = [], l IN linkLists | acc + [x IN l WHERE NOT x IN acc]) AS linkTypes
WHERE size(linkTypes) >= $minLinkTypes
RETURN [a IN ring | a.accountNumber] AS ringAccounts,
       [h IN holders | h.customerId] AS holders,
       linkTypes,
       size(linkTypes) AS linkTypeCount,
       linkedPairs
ORDER BY linkTypeCount DESC, size(linkedPairs) DESC, ringAccounts
LIMIT 25;
```

## Graph Data Science (optional)

The statements below require the Graph Data Science (GDS) plugin; check that `gds.version()` returns before offering them. They group the customers that **Synthetic identity clusters** pairs into connected clusters with Weakly Connected Components (WCC). Run them in order: project the identity links into an in-memory graph, stream the clusters, then drop the projection. The projection is built from a Cypher aggregation, so nothing is written to the database; it lives until it is dropped or the database restarts, and a second projection under the same name fails until the first is dropped.

## Project identity links (requires GDS)

```cypher
/*
 * @name           Project identity links (requires GDS)
 * @description    Projects an in-memory, undirected graph named
 *                 identity-links: one node per customer who shares at least
 *                 a given number of identifier types with another customer,
 *                 one relationship per such pair.
 * @params         minSharedTypes - As in Synthetic identity clusters.
 *                     Integer. Start at 2; use the same value as there so the
 *                     clusters and the pairs agree.
 * @prerequisites  GDS plugin. No projection named identity-links exists.
 * @returns        One row: graph (name), customers (nodeCount) and links
 *                 (relationshipCount, which counts each undirected link in
 *                 both directions).
 * @usage          Run before Identity clusters with WCC, and drop the
 *                 projection afterwards. Customers with no qualifying link
 *                 are not projected, so every cluster has at least two
 *                 members.
 * @tags           gds, projection, synthetic-identity
 * @sample         Bundled sample data only: $minSharedTypes = 2 projects 49
 *                 customers.
 */
MATCH (c1:Customer)-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]->(identifier)
      <-[:HAS_EMAIL|HAS_PHONE|HAS_ADDRESS|HAS_PASSPORT|HAS_DRIVING_LICENSE]-(c2:Customer)
WHERE elementId(c1) < elementId(c2)
WITH c1, c2, count(DISTINCT head(labels(identifier))) AS sharedTypes
WHERE sharedTypes >= $minSharedTypes
WITH gds.graph.project('identity-links', c1, c2, {}, {undirectedRelationshipTypes: ['*']}) AS g
RETURN g.graphName AS graph, g.nodeCount AS customers, g.relationshipCount AS links;
```

## Identity clusters with WCC (requires GDS)

```cypher
/*
 * @name           Identity clusters with WCC (requires GDS)
 * @description    Streams Weakly Connected Components over identity-links:
 *                 each component is a group of customers joined, directly or
 *                 through one another, by shared identifiers.
 * @params         minClusterSize - Minimum customers in a cluster. Integer.
 *                     Start at 3: pairs are already listed by Synthetic
 *                     identity clusters.
 * @prerequisites  GDS plugin; Project identity links run first.
 * @returns        One row per cluster: componentId (arbitrary, valid only for
 *                 this run), clusterSize and customers (customerId), largest
 *                 first.
 * @usage          A household that shares an address and a landline forms a
 *                 small cluster of its own; a cluster of unrelated names
 *                 around one phone or document is the synthetic-identity
 *                 pattern. Read each cluster's accounts with Synthetic
 *                 identity clusters. The literal LIMIT 50 caps the list.
 * @tags           gds, wcc, synthetic-identity, cluster
 * @sample         Bundled sample data only: $minClusterSize = 3 returns 8
 *                 clusters, three of four customers and five of three.
 */
CALL gds.wcc.stream('identity-links')
YIELD nodeId, componentId
WITH componentId, collect(gds.util.asNode(nodeId).customerId) AS customers
WHERE size(customers) >= $minClusterSize
RETURN componentId, size(customers) AS clusterSize, customers
ORDER BY clusterSize DESC, componentId
LIMIT 50;
```

## Drop identity links projection (requires GDS)

```cypher
/*
 * @name           Drop identity links projection (requires GDS)
 * @description    Removes the identity-links projection from memory.
 * @params         None
 * @prerequisites  GDS plugin.
 * @returns        One row: graphName, or no row when no projection of that
 *                 name exists.
 * @usage          Run after Identity clusters with WCC, and before
 *                 projecting again under the same name.
 * @tags           gds, projection, cleanup
 */
CALL gds.graph.drop('identity-links', false)
YIELD graphName
RETURN graphName;
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
CREATE CONSTRAINT customerId_Customer_key IF NOT EXISTS
  FOR (c:Customer) REQUIRE c.customerId IS NODE KEY;
CREATE CONSTRAINT accountNumber_Account_key IF NOT EXISTS
  FOR (a:Account) REQUIRE a.accountNumber IS NODE KEY;
CREATE CONSTRAINT transactionId_Transaction_key IF NOT EXISTS
  FOR (t:Transaction) REQUIRE t.transactionId IS NODE KEY;
CREATE CONSTRAINT code_Country_key IF NOT EXISTS
  FOR (c:Country) REQUIRE c.code IS NODE KEY;
CREATE CONSTRAINT address_Email_key IF NOT EXISTS
  FOR (e:Email) REQUIRE e.address IS NODE KEY;
CREATE CONSTRAINT phoneNumber_Phone_key IF NOT EXISTS
  FOR (p:Phone) REQUIRE p.phoneNumber IS NODE KEY;
CREATE CONSTRAINT addressId_Address_key IF NOT EXISTS
  FOR (a:Address) REQUIRE a.addressId IS NODE KEY;
CREATE CONSTRAINT passportId_Passport_key IF NOT EXISTS
  FOR (p:Passport) REQUIRE p.passportId IS NODE KEY;
CREATE CONSTRAINT licenseId_DrivingLicense_key IF NOT EXISTS
  FOR (d:DrivingLicense) REQUIRE d.licenseId IS NODE KEY;
CREATE CONSTRAINT sessionId_Session_key IF NOT EXISTS
  FOR (s:Session) REQUIRE s.sessionId IS NODE KEY;
CREATE CONSTRAINT deviceId_Device_key IF NOT EXISTS
  FOR (d:Device) REQUIRE d.deviceId IS NODE KEY;
CREATE CONSTRAINT ipAddress_IP_key IF NOT EXISTS
  FOR (i:IP) REQUIRE i.ipAddress IS NODE KEY;
```
