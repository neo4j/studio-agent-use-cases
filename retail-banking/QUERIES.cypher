// # Retail Banking — Query Guidance

// Cypher for the `retail-banking` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database.

// ## Prerequisites

// - Neo4j 5.9+ and Cypher 5. The ring queries use quantified path patterns (`{3,6}`, `{2,5}`), and the decay query uses a chained comparison (`0.80 <= x <= 1.00`).
// - **Directed ring with distinct accounts** and **Chronological and amount-decay ring** require APOC (`apoc.coll.toSet`) for their distinct-account filter, and say so in their headings. The other queries need no plugin.
// - The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own payments data mapped onto the reference ontology.
// - The node keys in `ONTOLOGY.json` make `Account.accountNumber` and `Transaction.transactionId` unique, so any anchored lookup is an index seek rather than a label scan.
// - No query takes a parameter: every account is tried as the starting point of a ring.
// - The queries are listed in the order to run them. Start with the census, then run the ring queries broad to strict — each one adds a condition to the one before, which shows which condition removes a candidate ring.

// ## Adapting these queries

// These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

// 1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
// 2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
// 3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

// ## Graph census

/*
 * @name           Graph census
 * @description    Counts Account and Transaction nodes to confirm the import
 *                 landed before running anything else.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: accounts (Account count) and transactions
 *                 (Transaction count).
 * @usage          Run straight after an import. No row at all means no
 *                 Transaction nodes were imported. The census counts nodes
 *                 only; a payment whose account columns did not resolve still
 *                 counts as a Transaction but sits on no ring.
 * @tags           sanity-check, import, orientation
 * @sample         Bundled sample data only: returns 1 row — accounts 1449,
 *                 transactions 5050.
 */
MATCH (a:Account)
WITH count(a) AS accounts
MATCH (t:Transaction)
RETURN accounts, count(t) AS transactions;

// ## Directed ring (basic)

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
 * @sample         Bundled sample data only: returns 143 paths covering 37
 *                 distinct rings, among them 1 → 2 → 3 → 4 → 1 once rotated to
 *                 start at each of its accounts.
 */
MATCH path =
  (start:Account)
  (()-[:PERFORMS]->()-[:BENEFITS_TO]->()){3,6}
  (start)
RETURN path;

// ## Directed ring with distinct accounts (requires APOC)

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
 *                 rings, among them 1 → 2 → 3 → 4 → 1 once per account; the
 *                 other 22 rings from Directed ring (basic) revisit an
 *                 account.
 */
MATCH path =
  (start:Account)
  ((source)-[:PERFORMS]->(tx)-[:BENEFITS_TO]->(target)){3,6}
  (start)
WHERE size(apoc.coll.toSet(source)) = size(source)
RETURN path;

// ## Chronological and amount-decay ring (requires APOC)

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
 *                 among them the ring anchored at account 1, amounts
 *                 1000.00 → 900.00 → 810.00 → 729.00 on consecutive days.
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

// ## Node-key constraints

// Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

CREATE CONSTRAINT accountNumber_Account_key IF NOT EXISTS
  FOR (a:Account) REQUIRE a.accountNumber IS NODE KEY;
CREATE CONSTRAINT transactionId_Transaction_key IF NOT EXISTS
  FOR (t:Transaction) REQUIRE t.transactionId IS NODE KEY;
