# Retail Banking — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j 5.9+ database with APOC installed — two of the ring queries call `apoc.coll.toSet`.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. No `SETUP.md` statements are needed.
4. Run the queries in `QUERIES.md` in file order. None takes parameters. Compare each result with the Invariant first and the Expected values second.

## Sample-data profile

Four months (2023-09-01 to 2023-12-31) of synthetic retail-banking payments, generated deterministically by a seeded script that is not shipped with the package. Eleven rings — six genuine and five near-misses, one per filter step — are seeded into ordinary activity that closes innocent loops of its own. The four legacy rows (ring A) are kept byte-identical as the first rows of each CSV.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Account` | 1449 | 1300 individuals (149 of them dormant, with no transactions), 70 merchants (8 of them utilities), 20 suppliers, 12 employers, 47 ring accounts. Account numbers 5–1449 are assigned at random across roles; ring A keeps 1–4 |
| `Transaction` | 5050 | 5006 `gbp`, 27 `eur`, 17 `usd` — non-`gbp` only on purchases and on two refunds of them. IDs `TXN001`–`TXN004` are the legacy rows; `TXN005` onwards are numbered in date order |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `PERFORMS` | 5050 | One per transaction, from `sourceAccountNumber` |
| `BENEFITS_TO` | 5050 | One per transaction, to `targetAccountNumber` |

No transaction pays an account to itself.

**Transactions by kind**

| Kind | Count | Min amount | Median | Max | What it is |
| ---- | ----- | ---------- | ------ | --- | ---------- |
| payroll | 1980 | 1350.17 | 2788.29 | 4297.58 | Monthly salary, employer → employee (06:00 on the 25th–28th; 20 December) |
| spend | 1763 | 6.10 | 69.72 | 1195.72 | Card and bank purchases, individual → merchant |
| utility | 448 | 35.73 | 99.40 | 157.36 | Monthly direct debit, individual → utility merchant (05:30) |
| supplier | 384 | 422.25 | 7128.24 | 17912.75 | Monthly settlement, merchant → supplier |
| p2p | 337 | 6.07 | 50.00 | 179.91 | Transfers within friend groups |
| seeded | 48 | 729.00 | 6840.94 | 20000.00 | The 11 seeded rings below |
| loan | 30 | 28.00 | 350.00 | 592.00 | Individual lends to individual |
| refund | 30 | 3.10 | 55.98 | 188.65 | Merchant → customer, 2–20 days after the purchase, full or partial |
| repayment | 30 | 28.00 | 350.00 | 592.00 | Loan repaid 3–30 days later |

Busiest accounts: a merchant receiving 149 payments, an employer making 332.

**How the background is shaped.** Payroll runs employer → employee, retail spend individual → merchant, settlement merchant → supplier. Employers receive nothing and suppliers pay nothing, so none of those flows can close a cycle. Only three kinds of payment can: P2P transfers inside small friend groups (110 groups of 3–5 people, 2–4 payments each), loans with a later repayment (30 pairs, 24 repaid exactly and 6 with a little extra), and merchant refunds (30 from 22 merchants, full or partial, to at most two customers per merchant). Every background cycle is therefore small and local: no group of mutually reachable background accounts has more than 3 members.

**Ring accounts carry ordinary activity too** — 100 payroll credits, 117 purchases and 16 utility direct debits — but never receive a refund or a P2P payment, so no background cycle passes through them. Account 1 also makes 2 purchases; account 4 is paid monthly by an employer and pays a utility monthly.

**The seeded rings**

| Ring | Kind | Accounts, in payment order | Basic | Distinct | Decay |
| ---- | ---- | -------------------------- | ----- | -------- | ----- |
| A | True ring (legacy rows), 4 accounts, ×0.90 per hop | 1 → 2 → 3 → 4 → 1 | 4 | 4 | 1 |
| B | True ring, 3 accounts | 913 → 1134 → 826 → 913 | 3 | 3 | 1 |
| C | True ring, 5 accounts | 1449 → 71 → 985 → 1210 → 1404 → 1449 | 5 | 5 | 1 |
| D | True ring, 6 accounts | 1320 → 1331 → 1213 → 1240 → 244 → 723 → 1320 | 6 | 6 | 1 |
| E | True ring, 4 accounts | 936 → 386 → 988 → 1431 → 936 | 4 | 4 | 1 |
| F | True ring, 3 accounts | 363 → 1110 → 1252 → 363 | 3 | 3 | 1 |
| R | Revisits account 153: back and forth 230 ↔ 153 and 153 ↔ 751, chronological, ×0.90 per hop | 230 → 153 → 751 → 153 → 230 | 4 | 0 | 0 |
| O | Distinct, ×0.90 per hop, but the dates run out of order | 1004 → 63 → 372 → 351 → 1004 | 4 | 4 | 0 |
| G | Distinct and chronological, but each hop grows ×1.08 | 1154 → 326 → 1169 → 978 → 1154 | 4 | 4 | 0 |
| H | Distinct and chronological, but one hop loses 25% | 951 → 1416 → 1076 → 1150 → 951 | 4 | 4 | 0 |
| L | Chronological, ×0.95 per hop, but 7 accounts | 271 → 756 → 1303 → 1145 → 120 → 645 → 40 → 271 | 0 | 0 | 0 |

The columns on the right are paths returned by **Directed ring (basic)**, **Directed ring with distinct accounts** and **Chronological and amount-decay ring**. Each seeded ring completes within 15 hours to 6 days. Rings B to L move 2,000–20,000 per payment, more than any background payment except payroll and supplier settlements. Ring A's legacy amounts (729.00–1000.00) overlap ordinary spending. Every true-ring hop keeps between 85% and 96% of the previous amount.

Every seeded payment:

| Ring | Transaction | From → To | Amount | Date | Ratio to previous |
| ---- | ----------- | --------- | ------ | ---- | ----------------- |
| A | `TXN001` | 1 → 2 | 1000.00 | 2023-10-24T10:00:00Z | — |
| A | `TXN002` | 2 → 3 | 900.00 | 2023-10-25T11:30:00Z | 0.9000 |
| A | `TXN003` | 3 → 4 | 810.00 | 2023-10-26T09:15:00Z | 0.9000 |
| A | `TXN004` | 4 → 1 | 729.00 | 2023-10-27T14:45:00Z | 0.9000 |
| B | `TXN347` | 913 → 1134 | 4800.00 | 2023-09-12T09:20:00Z | — |
| B | `TXN372` | 1134 → 826 | 4560.00 | 2023-09-13T11:20:00Z | 0.9500 |
| B | `TXN398` | 826 → 913 | 4195.20 | 2023-09-14T18:20:00Z | 0.9200 |
| C | `TXN1328` | 1449 → 71 | 9500.00 | 2023-10-03T08:45:00Z | — |
| C | `TXN1347` | 71 → 985 | 8740.00 | 2023-10-04T04:45:00Z | 0.9200 |
| C | `TXN1375` | 985 → 1210 | 7866.00 | 2023-10-05T02:45:00Z | 0.9000 |
| C | `TXN1409` | 1210 → 1404 | 7236.72 | 2023-10-06T05:45:00Z | 0.9200 |
| C | `TXN1438` | 1404 → 1449 | 6874.88 | 2023-10-07T00:45:00Z | 0.9500 |
| D | `TXN2731` | 1320 → 1331 | 12000.00 | 2023-11-06T11:10:00Z | — |
| D | `TXN2767` | 1331 → 1213 | 10800.00 | 2023-11-07T17:10:00Z | 0.9000 |
| D | `TXN2796` | 1213 → 1240 | 9936.00 | 2023-11-08T11:10:00Z | 0.9200 |
| D | `TXN2833` | 1240 → 244 | 8942.40 | 2023-11-09T12:10:00Z | 0.9000 |
| D | `TXN2873` | 244 → 723 | 7601.04 | 2023-11-11T05:10:00Z | 0.8500 |
| D | `TXN2895` | 723 → 1320 | 6840.94 | 2023-11-12T03:10:00Z | 0.9000 |
| E | `TXN3104` | 936 → 386 | 2500.00 | 2023-11-20T14:05:00Z | — |
| E | `TXN3167` | 386 → 988 | 2400.00 | 2023-11-22T15:05:00Z | 0.9600 |
| E | `TXN3190` | 988 → 1431 | 2232.00 | 2023-11-23T14:05:00Z | 0.9300 |
| E | `TXN3277` | 1431 → 936 | 2120.40 | 2023-11-25T18:05:00Z | 0.9500 |
| F | `TXN3921` | 363 → 1110 | 15000.00 | 2023-12-04T10:30:00Z | — |
| F | `TXN3928` | 1110 → 1252 | 12750.00 | 2023-12-04T16:30:00Z | 0.8500 |
| F | `TXN3932` | 1252 → 363 | 11475.00 | 2023-12-05T01:30:00Z | 0.9000 |
| R | `TXN700` | 230 → 153 | 6000.00 | 2023-09-25T10:15:00Z | — |
| R | `TXN812` | 153 → 751 | 5400.00 | 2023-09-26T07:15:00Z | 0.9000 |
| R | `TXN1051` | 751 → 153 | 4860.00 | 2023-09-27T07:15:00Z | 0.9000 |
| R | `TXN1218` | 153 → 230 | 4374.00 | 2023-09-28T06:15:00Z | 0.9000 |
| O | `TXN1776` | 1004 → 63 | 7200.00 | 2023-10-18T09:00:00Z | — |
| O | `TXN1726` | 63 → 372 | 6480.00 | 2023-10-16T13:00:00Z | 0.9000 |
| O | `TXN1801` | 372 → 351 | 5832.00 | 2023-10-19T15:00:00Z | 0.9000 |
| O | `TXN1751` | 351 → 1004 | 5248.80 | 2023-10-17T11:00:00Z | 0.9000 |
| G | `TXN2927` | 1154 → 326 | 3000.00 | 2023-11-13T09:40:00Z | — |
| G | `TXN2944` | 326 → 1169 | 3240.00 | 2023-11-14T07:40:00Z | 1.0800 |
| G | `TXN2976` | 1169 → 978 | 3499.20 | 2023-11-15T08:40:00Z | 1.0800 |
| G | `TXN2995` | 978 → 1154 | 3779.14 | 2023-11-16T07:40:00Z | 1.0800 |
| H | `TXN4134` | 951 → 1416 | 8000.00 | 2023-12-11T10:00:00Z | — |
| H | `TXN4155` | 1416 → 1076 | 7360.00 | 2023-12-12T10:00:00Z | 0.9200 |
| H | `TXN4175` | 1076 → 1150 | 5520.00 | 2023-12-13T06:00:00Z | 0.7500 |
| H | `TXN4203` | 1150 → 951 | 5188.80 | 2023-12-14T08:00:00Z | 0.9400 |
| L | `TXN2536` | 271 → 756 | 20000.00 | 2023-10-30T09:00:00Z | — |
| L | `TXN2558` | 756 → 1303 | 19000.00 | 2023-10-31T03:00:00Z | 0.9500 |
| L | `TXN2573` | 1303 → 1145 | 18050.00 | 2023-10-31T23:00:00Z | 0.9500 |
| L | `TXN2606` | 1145 → 120 | 17147.50 | 2023-11-01T21:00:00Z | 0.9500 |
| L | `TXN2635` | 120 → 645 | 16290.12 | 2023-11-02T16:00:00Z | 0.9500 |
| L | `TXN2659` | 645 → 40 | 15475.61 | 2023-11-03T13:00:00Z | 0.9500 |
| L | `TXN2683` | 40 → 271 | 14701.83 | 2023-11-04T13:00:00Z | 0.9500 |

**Background closed trails.** The basic ring query also returns 27 closed trails made entirely of background payments — 102 paths. Each is listed once below, in its rotation that starts with its smallest transaction ID. Twenty-one revisit an account (a round trip is part of them), so the distinct-account filter removes them. The six P2P triangles survive it; one pair of them shares two payments and differs only in which of two transfers from 1079 to 94 it uses. None of the 27 reaches the decay query: the 21 revisit an account, and no rotation of the six triangles keeps every hop within the amount band.

| # | Accounts, in payment order | Transactions | Made of | Paths | Revisits an account |
| - | -------------------------- | ------------ | ------- | ----- | ------------------- |
| 1 | 9 → 270 → 274 → 270 → 9 | `TXN3014`, `TXN4885`, `TXN3962`, `TXN3923` | 1 loan, 1 repayment, 2 P2P | 4 | yes |
| 2 | 692 → 1417 → 692 → 68 → 692 | `TXN2324`, `TXN2949`, `TXN364`, `TXN4118` | 1 loan, 1 repayment, 2 P2P | 4 | yes |
| 3 | 699 → 842 → 699 → 179 → 699 | `TXN1323`, `TXN4034`, `TXN1805`, `TXN2797` | 1 loan, 1 repayment, 2 P2P | 4 | yes |
| 4 | 1270 → 1400 → 428 → 1400 → 1270 | `TXN198`, `TXN2962`, `TXN3086`, `TXN274` | 1 loan, 1 repayment, 2 P2P | 4 | yes |
| 5 | 516 → 440 → 516 → 1195 → 516 | `TXN1456`, `TXN719`, `TXN2632`, `TXN2770` | 1 purchase, 1 refund, 1 loan, 1 repayment | 4 | yes |
| 6 | 47 → 1044 → 47 → 781 → 47 | `TXN167`, `TXN424`, `TXN1698`, `TXN2765` | 2 loans, 2 repayments | 4 | yes |
| 7 | 940 → 1189 → 803 → 1189 → 940 | `TXN1283`, `TXN2610`, `TXN3155`, `TXN1762` | 2 loans, 2 repayments | 4 | yes |
| 8 | 183 → 490 → 198 → 490 → 183 | `TXN277`, `TXN634`, `TXN304`, `TXN337` | 2 purchases, 2 refunds | 4 | yes |
| 9 | 306 → 706 → 971 → 706 → 306 | `TXN2596`, `TXN3218`, `TXN2744`, `TXN2868` | 2 purchases, 2 refunds | 4 | yes |
| 10 | 471 → 1429 → 245 → 1429 → 471 | `TXN316`, `TXN613`, `TXN357`, `TXN607` | 2 purchases, 2 refunds | 4 | yes |
| 11 | 642 → 114 → 444 → 114 → 642 | `TXN1878`, `TXN560`, `TXN415`, `TXN2665` | 2 purchases, 2 refunds | 4 | yes |
| 12 | 672 → 353 → 672 → 1192 → 672 | `TXN2517`, `TXN2799`, `TXN4219`, `TXN5018` | 2 purchases, 2 refunds | 4 | yes |
| 13 | 968 → 982 → 890 → 982 → 968 | `TXN240`, `TXN610`, `TXN520`, `TXN536` | 2 purchases, 2 refunds | 4 | yes |
| 14 | 1042 → 264 → 1042 → 817 → 1042 | `TXN1254`, `TXN353`, `TXN2872`, `TXN2764` | 2 purchases, 2 refunds | 4 | yes |
| 15 | 1248 → 1191 → 1315 → 1191 → 1248 | `TXN4145`, `TXN830`, `TXN594`, `TXN5036` | 2 purchases, 2 refunds | 4 | yes |
| 16 | 1280 → 415 → 1280 → 1414 → 1280 | `TXN1433`, `TXN518`, `TXN3199`, `TXN3112` | 2 purchases, 2 refunds | 4 | yes |
| 17 | 1315 → 1191 → 1248 → 1191 → 1315 | `TXN095`, `TXN5036`, `TXN4145`, `TXN830` | 2 purchases, 2 refunds | 4 | yes |
| 18 | 116 → 384 → 116 → 384 → 116 | `TXN2567`, `TXN2835`, `TXN523`, `TXN563` | 4 P2P | 4 | yes |
| 19 | 116 → 384 → 116 → 384 → 116 | `TXN2567`, `TXN563`, `TXN523`, `TXN2835` | 4 P2P | 4 | yes |
| 20 | 689 → 511 → 753 → 511 → 689 | `TXN1461`, `TXN2544`, `TXN4275`, `TXN4057` | 4 P2P | 4 | yes |
| 21 | 1376 → 1193 → 1265 → 1193 → 1376 | `TXN1411`, `TXN2952`, `TXN519`, `TXN3114` | 4 P2P | 4 | yes |
| 22 | 693 → 92 → 361 → 693 | `TXN1422`, `TXN2543`, `TXN2762` | 3 P2P | 3 | no |
| 23 | 1079 → 94 → 1271 → 1079 | `TXN1927`, `TXN566`, `TXN3370` | 3 P2P | 3 | no |
| 24 | 1079 → 94 → 1271 → 1079 | `TXN1932`, `TXN566`, `TXN3370` | 3 P2P | 3 | no |
| 25 | 1147 → 603 → 487 → 1147 | `TXN1478`, `TXN1822`, `TXN2534` | 3 P2P | 3 | no |
| 26 | 1236 → 1095 → 1341 → 1236 | `TXN1412`, `TXN2987`, `TXN3186` | 3 P2P | 3 | no |
| 27 | 1314 → 266 → 1028 → 1314 | `TXN124`, `TXN4927`, `TXN5008` | 3 P2P | 3 | no |

**Reference anchors.** Ring A (accounts 1–4, `TXN001`–`TXN004`) is the anchor every `@sample` names. The decay query returns each true ring starting from its first payment: accounts 1, 913, 1449, 1320, 936 and 363.

**Editing notes.**

- The migration replaced the four-row legacy sample with this one at the user's request. The legacy sample had one ring and no non-matching activity, so no filter ever removed anything. The legacy rows are kept unchanged as ring A. The reference ontology's `e.g.` values were moved off ring A onto an unremarkable background payment (`TXN3001`: account `1247`, `131.46`, `gbp`, `2023-11-16T11:15:00Z`), so no sample value points at a seeded ring.
- The decay query's repetition changed from `*` to `{2,5}` in the same migration, so it covers rings of 3 to 6 accounts like the other ring queries. Under `*` it would return 56 paths here instead of 6 (see its Sensitivity).
- The shipped thresholds come from the source page, not from this data. The `{3,6}` hop bound is the source's own, and the 0.80–1.00 band encodes its "fee of up to 20%" per hop. The source's decay query divides the previous amount by the next one, which accepts growth; this package divides next by previous, which accepts decay as described.
- Expected results were computed by simulating each query's matching rules over the CSVs. That includes Cypher's rule that a path never uses the same relationship twice, which is why a closed trail may pass through an account twice in the basic query.

## Graph census

- **Parameters:** none.
- **Invariant:** one row whose counts equal the number of data rows in `accounts.csv` and `transactions.csv`.
- **Expected:** 1 row — `accounts` 1449, `transactions` 5050.

## Directed ring (basic)

- **Parameters:** none.
- **Invariant:** every row is a closed directed trail of 3 to 6 payments that starts and ends at the same account, never using a transaction twice. Each seeded ring of 3 to 6 hops — A to F, R, O, G and H — is returned once per starting position. Ring L (7 accounts) never appears. Every other row is made only of P2P, loan, repayment, purchase and refund payments that close a loop; payroll, utility and supplier payments never appear.
- **Expected:** 143 paths over 37 closed trails:
  - Seeded, 41 paths: A 4, B 3, C 5, D 6, E 4, F 3, R 4, O 4, G 4, H 4.
  - Background, 102 paths over the 27 trails tabled above:
    - 10 purchase–refund trails, 40 paths.
    - 7 loan-and-repayment trails, 28 paths: 4 with 2 P2P payments, 1 with a purchase and refund, and 2 made of two loans and their repayments.
    - 4 trails of repeated P2P between the same people, 16 paths.
    - 6 P2P triangles, 18 paths.
- **Sensitivity:**
  - An upper bound of 7 (`{3,7}`) adds ring L: 7 paths, 150 in total.
  - An upper bound of 5 returns 137 paths, losing ring D.
  - An upper bound of 4 returns 132, also losing ring C.
  - No background trail is longer than 4 hops.

## Directed ring with distinct accounts (requires APOC)

- **Parameters:** none.
- **Invariant:** exactly the rows of **Directed ring (basic)** whose paying accounts are all different. Ring R and every background trail that contains a round trip are removed. Rings A–F, O, G and H survive, and so do P2P triangles, which are genuinely distinct cycles.
- **Expected:** 55 paths over 15 rings:
  - Seeded, 37 paths: A 4, B 3, C 5, D 6, E 4, F 3, O 4, G 4, H 4.
  - Background, 18 paths: the 6 P2P triangles, 3 paths each.
- **Sensitivity:** the filter removes 88 of the 143 basic paths — ring R's 4 and 84 background ones.

## Chronological and amount-decay ring (requires APOC)

- **Parameters:** none.
- **Invariant:** exactly one row per true ring, A to F, starting at the ring's earliest payment, and nothing else. No negative ring and no background trail qualifies:
  - R repeats an account.
  - O's dates run backwards.
  - G grows.
  - H has a hop at 0.75.
  - L needs 6 repetitions.
- **Expected:** 6 paths:

  | Ring | Path (accounts) | Repetitions |
  | ---- | --------------- | ----------- |
  | A | 1 → 2 → 3 → 4 → 1 | 3 |
  | B | 913 → 1134 → 826 → 913 | 2 |
  | C | 1449 → 71 → 985 → 1210 → 1404 → 1449 | 4 |
  | D | 1320 → 1331 → 1213 → 1240 → 244 → 723 → 1320 | 5 |
  | E | 936 → 386 → 988 → 1431 → 936 | 3 |
  | F | 363 → 1110 → 1252 → 363 | 2 |

- **Sensitivity:**
  - Repetition `*`, the query before this migration: 56 paths. It adds 49 two-account round trips — 24 loan repayments, 19 purchase refunds, 5 P2P pairs, and ring R's 153 → 751 → 153 — plus ring L.
  - Repetition `{2,6}` adds ring L (7 paths). `{2,4}` drops D (5 paths); `{2,3}` also drops C (4 paths).
  - A floor of 0.75 adds ring H (7 paths). A floor of 0.86 drops D and F, whose steepest hop keeps 85% (4 paths). A ceiling of 0.95 drops E, which has a hop at 0.96 (5 paths).
  - Without the date condition, ring O qualifies too (7 paths). Rotating it to start at its largest payment decays ×0.90 all the way round.
  - Without the amount band, rings G and H qualify, and so do 4 background P2P triangles whose dates happen to run in order (12 paths).
  - With the ratio inverted (previous divided by next), only ring G qualifies (1 path) — the amount-growth trap the query's annotation warns about.
