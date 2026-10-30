# Retail Banking Fraud — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/` by simulating each query's matching rules over them, not from a database run.

## How to run

1. Use a disposable Neo4j 5.9+ database. Install APOC for the two ring queries headed "(requires APOC)" and Graph Data Science for the three statements headed "(requires GDS)"; every other query is plain Cypher.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. No `SETUP.md` statements are needed.
4. Run the queries in `QUERIES.md` in file order, with the parameters given in each section below. Run the three GDS statements in order: project, cluster, drop. Compare each result with the Invariant first and the Expected values second.

## Sample-data profile

Four months (2023-09-01 to 2023-12-31) of synthetic retail-banking activity, generated deterministically by a seeded script that is not shipped with the package (`retail-banking-v2-gen.py`, seed 3, kept outside the repository). The data replaces the earlier two-table sample. It carries over all eleven earlier transaction rings unchanged in membership, amounts and dates, and adds customers, identifiers, documents, sessions, devices, IP addresses and countries.

### Nodes

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Customer` | 1266 | 1157 background customers (40 of them onboarded during the period) and 109 with a seeded role, listed below. Customer IDs are assigned at random, so a seeded customer's ID says nothing about it |
| `Account` | 1892 | 1709 `INTERNAL` (1391 `CURRENT`, 302 `SAVINGS`, 16 `BUSINESS`) and 183 `EXTERNAL`. UK accounts are written `NN-NN-NN NNNNNNNN`; internal ones use sort codes `12-34-56` to `12-34-58`. 45 external accounts abroad carry IBANs: BG 8, LB 7, PL 6, PT 6, RO 6, ES 2, FR 2, GR 2, IT 2, LT 2, AE 1, MC 1 |
| `Transaction` | 7906 | 7825 `gbp`, 59 `eur`, 22 `usd`. `TXN001`–`TXN004` are ring A; the rest are numbered in date order |
| `Country` | 21 | `isHighRiskJurisdiction` true for BG, LB, MC and IR, flags reviewed and confirmed for the sample by the package owner. They are the sample institution's policy setting; a user's own data carries its own |
| `Email` | 1376 | All on reserved example domains |
| `Phone` | 1285 | Ofcom's reserved drama ranges only: mobiles `+447700900xxx` and landlines in ten cities' fiction ranges |
| `Address` | 986 | All in GB |
| `Passport` | 542 | Issuing countries GB 489, IN 13, PL 12, RO 11, IT 10, IE 8 (counted per link: 543 links, one passport shared) |
| `DrivingLicense` | 699 | All GB, in the DVLA number format |
| `Session` | 7432 | 7052 `success`, 275 `failed`, 105 `timeout`; no `suspicious` |
| `Device` | 1748 | 1175 `mobile`, 516 `desktop`, 57 `tablet` |
| `IP` | 956 | IPv4 from the documentation ranges (501) and IPv6 from `2001:db8::/32` (455). GB 925, GR 8, PT 6, ES 5, IT 5, FR 4, RO 2, NG 1 |

### Relationships

| Type | Count | Notes |
| ---- | ----- | ----- |
| `HAS_ACCOUNT` | 1833 | 1709 `PRIMARY` (one per internal account) and 124 `SECONDARY` (joint accounts) |
| `PERFORMS` | 7906 | One per transaction |
| `BENEFITS_TO` | 7906 | One per transaction |
| `IS_HOSTED` | 1892 | One per account |
| `HAS_EMAIL` | 1383 | |
| `HAS_PHONE` | 1316 | |
| `HAS_ADDRESS` | 1445 | 1266 current, 179 previous (`isCurrent` false) |
| `HAS_PASSPORT` | 543 | Verification status: 497 `VERIFIED`, 27 `EXPIRED`, 14 `PENDING`, 5 `REJECTED` |
| `HAS_DRIVING_LICENSE` | 701 | 637 `VERIFIED`, 37 `EXPIRED`, 22 `PENDING`, 5 `REJECTED` |
| `LOCATED_IN` | 1942 | 986 from Address, 956 from IP |
| `HAS_SESSION` | 7432 | One per session |
| `SESSION_USES_DEVICE` | 7432 | One per session |
| `USES_IP` | 7432 | One per session |

No transaction pays an account to itself, and every transaction touches at least one internal account: a payment between two external accounts would not be visible to the bank.

### Transactions by kind

| Kind | Type | Count | Min | Median | Max | What it is |
| ---- | ---- | ----- | --- | ------ | --- | ---------- |
| payroll | BACS | 2058 | 1360.83 | 2746.77 | 4297.12 | External employer → employee's current account, monthly |
| spend | CARD | 2024 | 6.55 | 70.58 | 1192.95 | Card purchases at merchants, 2% in eur or usd |
| savings | STANDING_ORDER | 1116 | 27.00 | 280.00 | 500.00 | Current → own savings, monthly |
| joint-contribution | STANDING_ORDER | 992 | 203.00 | 563.00 | 899.00 | Each partner's current → their joint account, monthly |
| utility | DIRECT_DEBIT | 919 | 35.41 | 109.14 | 159.52 | Monthly direct debits from current and joint accounts |
| p2p | FASTER_PAYMENT | 322 | 5.24 | 50.00 | 179.20 | Transfers inside 110 friend groups, some members banking elsewhere |
| remittance | SWIFT | 112 | 139.68 | 378.37 | 621.02 | 28 customers paying family abroad monthly: 12 to BG or LB, 16 to PL, RO or PT |
| supplier | BACS | 88 | 523.15 | 2568.84 | 6357.49 | Sole-trader business accounts → external suppliers |
| seeded rings | FASTER_PAYMENT | 48 | 729.00 | 6840.94 | 20000.00 | The eleven rings below |
| travel-spend | CARD | 44 | 8.42 | 53.93 | 119.75 | Card spend abroad in eur during a customer's trip |
| loan / repayment | FASTER_PAYMENT | 30 + 30 | 25.00 | 213.00 | 596.00 | Informal loans between customers, repaid 3–30 days later |
| refund | CARD | 20 | 6.75 | 61.94 | 193.21 | Merchant → customer, full or partial, at most two customers per merchant |
| savings-withdrawal | FASTER_PAYMENT | 16 | 176.00 | 887.00 | 1472.00 | Savings → own current, at most once per customer |
| other seeded | mixed | 115 | | | | Takeover, mule, high-risk and near-miss payments, listed below |

**How the background is shaped.** Payroll comes from external employers, card spend goes to merchants, settlements go to external suppliers, and employers and suppliers never pay back, so none of those flows can close a cycle. Only P2P inside friend groups, loans with their repayments, refunds, and single savings withdrawals can. Friend groups never include two members of one household, and remitters are kept out of friend groups, loans, refunds and withdrawals, so no ordinary payment chain reaches a high-risk country through an intermediary. Households share an address; 16 of them also share a landline, and 42 share a tablet between two or three members. Each customer's devices all appear in their first sessions, so "new device" later means a genuinely new device: 26 background customers replace their phone mid-period and 23 spend a few days abroad.

### Seeded rings

The eleven earlier rings, with the same members, amounts and dates as before. Every ring account is an internal current account with its own primary holder.

| Ring | Kind | Accounts, in payment order | Holders |
| ---- | ---- | -------------------------- | ------- |
| A | True ring, 4 accounts, ×0.90 per hop | 12-34-57 43064339 → 12-34-58 25868819 → 12-34-56 28166225 → 12-34-58 39026094 | CUS10586, CUS10961, CUS10568, CUS10269 |
| B | True ring, 3 accounts | 12-34-57 81395942 → 12-34-57 41271392 → 12-34-57 56576969 | CUS10708, CUS10835, CUS10298 |
| C | True ring, 5 accounts; holders share a device and a phone | 12-34-56 42536850 → 12-34-56 96197502 → 12-34-56 51507083 → 12-34-56 90626530 → 12-34-57 26675516 | CUS11059, CUS10876, CUS10981, CUS10435, CUS10816 |
| D | True ring, 6 accounts | 12-34-57 18921121 → 12-34-58 89506596 → 12-34-57 74740402 → 12-34-58 82010171 → 12-34-56 26430181 → 12-34-56 20693364 | CUS10421, CUS11128, CUS11260, CUS10843, CUS10232, CUS10220 |
| E | True ring, 4 accounts; holders share an email and an address | 12-34-58 37132309 → 12-34-56 47357986 → 12-34-57 95182331 → 12-34-57 32336182 | CUS11234, CUS10926, CUS10340, CUS10267 |
| F | True ring, 3 accounts | 12-34-56 62677430 → 12-34-58 85701835 → 12-34-56 58443261 | CUS10314, CUS10039, CUS10626 |
| R | Revisits the middle account: X → Y → Z → Y → X, chronological, ×0.90 | 12-34-58 59263787 → 12-34-58 23888652 → 12-34-56 19591830 → 12-34-58 23888652 → back | CUS10272, CUS11264, CUS10960 |
| O | Distinct, ×0.90 per hop, dates out of order | 12-34-56 27986138 → 12-34-56 48261327 → 12-34-56 77846707 → 12-34-57 71713350 | CUS10932, CUS11016, CUS10662, CUS10699 |
| G | Distinct and chronological, each hop grows ×1.08 | 12-34-56 81712862 → 12-34-56 32216522 → 12-34-56 29943945 → 12-34-58 61083419 | CUS10639, CUS11065, CUS10201, CUS10197 |
| H | Distinct and chronological, one hop loses 25% | 12-34-58 76932442 → 12-34-58 49221003 → 12-34-58 18408457 → 12-34-57 61193804 | CUS11013, CUS10606, CUS10776, CUS10579 |
| L | Chronological, ×0.95 per hop, but 7 accounts | 12-34-57 10014985 → 12-34-58 35952017 → 12-34-57 51282550 → 12-34-57 97553294 → 12-34-56 78260585 → 12-34-56 54053982 → 12-34-57 83366605 | CUS10286, CUS10914, CUS10623, CUS10969, CUS10459, CUS10845, CUS10228 |

Every seeded ring payment:

| Ring | Transaction | From → To | Amount | Date |
| ---- | ----------- | --------- | ------ | ---- |
| A | `TXN001` | 12-34-57 43064339 → 12-34-58 25868819 | 1000.00 | 2023-10-24T10:00:00Z |
| A | `TXN002` | 12-34-58 25868819 → 12-34-56 28166225 | 900.00 | 2023-10-25T11:30:00Z |
| A | `TXN003` | 12-34-56 28166225 → 12-34-58 39026094 | 810.00 | 2023-10-26T09:15:00Z |
| A | `TXN004` | 12-34-58 39026094 → 12-34-57 43064339 | 729.00 | 2023-10-27T14:45:00Z |
| B | `TXN661` | 12-34-57 81395942 → 12-34-57 41271392 | 4800.00 | 2023-09-12T09:20:00Z |
| B | `TXN719` | 12-34-57 41271392 → 12-34-57 56576969 | 4560.00 | 2023-09-13T11:20:00Z |
| B | `TXN773` | 12-34-57 56576969 → 12-34-57 81395942 | 4195.20 | 2023-09-14T18:20:00Z |
| C | `TXN2234` | 12-34-56 42536850 → 12-34-56 96197502 | 9500.00 | 2023-10-03T08:45:00Z |
| C | `TXN2274` | 12-34-56 96197502 → 12-34-56 51507083 | 8740.00 | 2023-10-04T04:45:00Z |
| C | `TXN2308` | 12-34-56 51507083 → 12-34-56 90626530 | 7866.00 | 2023-10-05T02:45:00Z |
| C | `TXN2358` | 12-34-56 90626530 → 12-34-57 26675516 | 7236.72 | 2023-10-06T05:45:00Z |
| C | `TXN2378` | 12-34-57 26675516 → 12-34-56 42536850 | 6874.88 | 2023-10-07T00:45:00Z |
| D | `TXN4332` | 12-34-57 18921121 → 12-34-58 89506596 | 12000.00 | 2023-11-06T11:10:00Z |
| D | `TXN4389` | 12-34-58 89506596 → 12-34-57 74740402 | 10800.00 | 2023-11-07T17:10:00Z |
| D | `TXN4420` | 12-34-57 74740402 → 12-34-58 82010171 | 9936.00 | 2023-11-08T11:10:00Z |
| D | `TXN4482` | 12-34-58 82010171 → 12-34-56 26430181 | 8942.40 | 2023-11-09T12:10:00Z |
| D | `TXN4559` | 12-34-56 26430181 → 12-34-56 20693364 | 7601.04 | 2023-11-11T05:10:00Z |
| D | `TXN4591` | 12-34-56 20693364 → 12-34-57 18921121 | 6840.94 | 2023-11-12T03:10:00Z |
| E | `TXN4969` | 12-34-58 37132309 → 12-34-56 47357986 | 2500.00 | 2023-11-20T14:05:00Z |
| E | `TXN5065` | 12-34-56 47357986 → 12-34-57 95182331 | 2400.00 | 2023-11-22T15:05:00Z |
| E | `TXN5108` | 12-34-57 95182331 → 12-34-57 32336182 | 2232.00 | 2023-11-23T14:05:00Z |
| E | `TXN5563` | 12-34-57 32336182 → 12-34-58 37132309 | 2120.40 | 2023-11-25T18:05:00Z |
| F | `TXN6280` | 12-34-56 62677430 → 12-34-58 85701835 | 15000.00 | 2023-12-04T10:30:00Z |
| F | `TXN6287` | 12-34-58 85701835 → 12-34-56 58443261 | 12750.00 | 2023-12-04T16:30:00Z |
| F | `TXN6300` | 12-34-56 58443261 → 12-34-56 62677430 | 11475.00 | 2023-12-05T01:30:00Z |
| R | `TXN1576` | 12-34-58 59263787 → 12-34-58 23888652 | 6000.00 | 2023-09-25T10:15:00Z |
| R | `TXN1642` | 12-34-58 23888652 → 12-34-56 19591830 | 5400.00 | 2023-09-26T07:15:00Z |
| R | `TXN1806` | 12-34-56 19591830 → 12-34-58 23888652 | 4860.00 | 2023-09-27T07:15:00Z |
| R | `TXN1847` | 12-34-58 23888652 → 12-34-58 59263787 | 4374.00 | 2023-09-28T06:15:00Z |
| O | `TXN2870` | 12-34-56 27986138 → 12-34-56 48261327 | 7200.00 | 2023-10-18T09:00:00Z |
| O | `TXN2804` | 12-34-56 48261327 → 12-34-56 77846707 | 6480.00 | 2023-10-16T13:00:00Z |
| O | `TXN2915` | 12-34-56 77846707 → 12-34-57 71713350 | 5832.00 | 2023-10-19T15:00:00Z |
| O | `TXN2843` | 12-34-57 71713350 → 12-34-56 27986138 | 5248.80 | 2023-10-17T11:00:00Z |
| G | `TXN4658` | 12-34-56 81712862 → 12-34-56 32216522 | 3000.00 | 2023-11-13T09:40:00Z |
| G | `TXN4691` | 12-34-56 32216522 → 12-34-56 29943945 | 3240.00 | 2023-11-14T07:40:00Z |
| G | `TXN4749` | 12-34-56 29943945 → 12-34-58 61083419 | 3499.20 | 2023-11-15T08:40:00Z |
| G | `TXN4803` | 12-34-58 61083419 → 12-34-56 81712862 | 3779.14 | 2023-11-16T07:40:00Z |
| H | `TXN6589` | 12-34-58 76932442 → 12-34-58 49221003 | 8000.00 | 2023-12-11T10:00:00Z |
| H | `TXN6623` | 12-34-58 49221003 → 12-34-58 18408457 | 7360.00 | 2023-12-12T10:00:00Z |
| H | `TXN6666` | 12-34-58 18408457 → 12-34-57 61193804 | 5520.00 | 2023-12-13T06:00:00Z |
| H | `TXN6708` | 12-34-57 61193804 → 12-34-58 76932442 | 5188.80 | 2023-12-14T08:00:00Z |
| L | `TXN3849` | 12-34-57 10014985 → 12-34-58 35952017 | 20000.00 | 2023-10-30T09:00:00Z |
| L | `TXN3868` | 12-34-58 35952017 → 12-34-57 51282550 | 19000.00 | 2023-10-31T03:00:00Z |
| L | `TXN3886` | 12-34-57 51282550 → 12-34-57 97553294 | 18050.00 | 2023-10-31T23:00:00Z |
| L | `TXN4000` | 12-34-57 97553294 → 12-34-56 78260585 | 17147.50 | 2023-11-01T21:00:00Z |
| L | `TXN4099` | 12-34-56 78260585 → 12-34-56 54053982 | 16290.12 | 2023-11-02T16:00:00Z |
| L | `TXN4211` | 12-34-56 54053982 → 12-34-57 83366605 | 15475.61 | 2023-11-03T13:00:00Z |
| L | `TXN4246` | 12-34-57 83366605 → 12-34-57 10014985 | 14701.83 | 2023-11-04T13:00:00Z |

Ring accounts carry ordinary activity too (payroll for some, card spend, direct debits) but never receive a refund or a P2P payment, so no background cycle passes through them. Each ring completes within 15 hours to 6 days; every true-ring hop keeps between 85% and 96% of the previous amount.

**Household triangle.** Three customers at one address (CUS10142, CUS10939, CUS11242; `74 HAZEL GROVE, LONDON, SW11 1UQ`) pay each other round a triangle: 12-34-56 37953089 → 12-34-57 91529245 (`TXN2630`, 120.00) → 12-34-56 33029244 (`TXN2703`, 45.50) → 12-34-56 37953089 (`TXN2979`, 80.00). It is a genuine distinct-account ring linked only by an address — the cross-layer near-miss.

### Seeded identity signals

| Group | Customers | Shared identifiers |
| ----- | --------- | ------------------ |
| SI-1 | CUS10386, CUS10469, CUS11143, CUS10618 | All four: phone `+447700900606`, address `146 QUEENS ROAD, MANCHESTER, M8 5HS`. The first three: email `j.reynolds.lettings@inbox.example`. CUS10469 and CUS11143: passport `GB:983208276`. Accounts opened 2023-09-18 to 2023-10-20. CUS10618 also holds MULE-2 |
| SI-2 | CUS10491, CUS10624, CUS11025 | Driving licence `GB:HARVE909074E99ZJ`, email `quickloans.contact@example.net`, phone `+447700900557` |
| Ring E holders | CUS11234, CUS10926, CUS10340, CUS10267 | Address `81 MARKET STREET, BRISTOL, BS1 8AS`, email `accounts.admin77@mail.example` |
| Ring C holders | CUS11059, CUS10876, CUS10981, CUS10435, CUS10816 | Phone `+447700900243`, and device `DEV-946954bd68` (below) |
| Household triangle | CUS10142, CUS10939, CUS11242 | Address only |

Background near-miss: 16 households share an address and a landline (29 customer pairs). No background pair shares a third identifier type.

### Seeded devices

| Device | Type | Customers with sessions on it |
| ------ | ---- | ----------------------------- |
| `DEV-626ae42f56` | desktop, headless browser user agent | Credential stuffing: failed sessions on six background customers (CUS10104, CUS10322, CUS10838, CUS10886, CUS11120, CUS11133) and on the four takeover victims, then one successful session on each victim |
| `DEV-946954bd68` | desktop | Ring C's five holders, three successful sessions each |
| `DEV-45b24a72d3` | mobile | Mule herder: MULE-1's holder CUS10869, MULE-2's holder CUS10618, and two recruits CUS10644 and CUS10779 |
| `DEV-3e7d6cb209` | desktop | SI-1's laptop: CUS10386, CUS10469, CUS11143 (their only device) |

Background near-miss: 42 household tablets, 40 used by two members and 2 by three (`DEV-a4e366ea47`, `DEV-34f86ef78f`).

### Seeded account takeovers

Each victim has an established account and four to twelve successful sessions on their own devices from GB IP addresses before the attack. The stuffing device fails against the victim (and, for the first three, against two other customers), then logs in from abroad; a push payment to an account the victim has never paid follows.

| Victim | Session | Country | Payment | Minutes later | Beneficiary |
| ------ | ------- | ------- | ------- | ------------- | ----------- |
| CUS10596 | `SESS004513`, 2023-11-14 21:05 | RO | `TXN4719`, 4800.00 FASTER_PAYMENT | 25 | MULE-1 |
| CUS10941 | `SESS005011`, 2023-11-22 13:10 | RO | `TXN5062`, 3950.00 FASTER_PAYMENT | 40 | MULE-1 |
| CUS11139 | `SESS005675`, 2023-12-03 14:02 | NG | `TXN6245`, 4000.00 FASTER_PAYMENT | 15 | MULE-1 |
| CUS10775 | `SESS005875`, 2023-12-06 22:30 | RO | `TXN6393`, 6200.00 SWIFT | 70 | `LT051363754385334748` (external, LT) |

Near-misses:

| Customer | What happens | Session → payment |
| -------- | ------------ | ----------------- |
| CUS10451 | New phone, then a first payment to a builder 50 hours 15 minutes later | `SESS004862` → `TXN5055`, 1250.00 FASTER_PAYMENT |
| CUS10408 | Customer onboarded 2023-11-25 with two phone sessions, then a new laptop and a first payment 40 minutes later | `SESS005614` → `TXN6133`, 450.00 FASTER_PAYMENT |
| CUS11171 | Holiday: first login from ES on their own phone, card spend at a Spanish merchant 150 minutes later | `SESS002626` → `TXN2711`, 86.40 eur CARD |
| CUS10770 | New phone, then 20 minutes later a payment to a friend first paid on 2023-09-15 (`TXN824`) | `SESS004121` → `TXN4440`, 300.00 FASTER_PAYMENT |

### Seeded mules

| Account | Holder | Opened | Inflows | Outflows |
| ------- | ------ | ------ | ------- | -------- |
| MULE-1 `12-34-56 24563467` | CUS10869 | 2023-11-02T10:12:00Z | 7 senders, 20900.00 in all: takeover victims CUS10596 (`TXN4719`), CUS10941 (`TXN5062`), CUS11139 (`TXN6245`); APP-fraud victims CUS10669 (`TXN4881`, 1650.00) and CUS10085 (`TXN6475`, 2500.00); external accounts `53-36-33 90304800` (`TXN5803`, 2200.00) and `26-61-87 35345910` (`TXN6549`, 1800.00) | Each inflow forwarded at 95% by SWIFT within 95–260 minutes: November's four to `LT169404837175302881`, December's three to `BG69TVNK94831093024404` (`TXN6247`, `TXN6480`, `TXN6551`) |
| MULE-2 `12-34-57 31478046` | CUS10618 (SI-1) | 2023-10-20T11:00:00Z | 5 senders, 7450.00: APP-fraud victims CUS10789, CUS10244, CUS11017 and external accounts `34-38-05 11068112`, `83-69-99 69455840` | Each forwarded at 93% by SWIFT within 2–20 hours to `AE820016973547453642788` |

Two recruits (CUS10644 `12-34-57 10466685`, CUS10779 `12-34-56 42205594`) each pass two small payments through to the LT account — mules in waiting, below any sender threshold.

Near-misses:

| Account | Holder | Shape | Why the default rejects it |
| ------- | ------ | ----- | -------------------------- |
| `12-34-56 87211505` | Club treasurer CUS10010 | Opened 2016-03-14. Nine club members pay 150.00 each over 2023-11-06 to 11-09; the treasurer pays the venue 1350.00 on 11-09 (`TXN4477`) | Account age |
| `12-34-56 81930635` | Sole trader CUS11130 (new BUSINESS account) | Opened 2023-09-15. Eight customers pay 15 times, Tuesday to Friday; 70% of each week's takings goes to one supplier the next Monday at 09:00, at least 64 hours after the last inflow | Dwell time |
| `12-34-56 54587831` | Student CUS11259 | Opened 2023-09-04. Two parents (CUS10867, CUS11033) and a student-loan company pay in; rent of 1800.00 leaves within 30 hours of the loan | Sender count |

### Seeded high-risk-jurisdiction payments

| Chain | Payments | Note |
| ----- | -------- | ---- |
| December layering chain | 12-34-57 69122237 → 12-34-56 35227092 (`TXN6624`, 9800.00, 12-12) → 12-34-56 77240020 (`TXN6679`, 9650.00, 12-13) → `MC6833037549948170432045945` (`TXN6716`, 9400.00, 12-14) | Two intermediaries |
| Takeover money through MULE-1 | CUS11139's `TXN6245` 4000.00 → MULE-1 → `TXN6247` 3800.00 to BG | One intermediary |
| APP money through MULE-1 | CUS10085's `TXN6475` 2500.00 → MULE-1 → `TXN6480` 2375.00 to BG | One intermediary |
| External money through MULE-1 | `26-61-87 35345910` `TXN6549` 1800.00 → MULE-1 → `TXN6551` 1710.00 to BG | The origin is external, so the chain starts at MULE-1: no intermediary |
| October chain | 12-34-57 78140836 → 12-34-58 82926275 (`TXN2492`, 8900.00, 10-09) → 12-34-56 22875346 (`TXN2540`, 8700.00, 10-10) → `LB03156409028191915712608558` (`TXN2576`, 8500.00, 10-11) | Outside a 30-day window ending 2024-01-01 |
| Out-of-band chain | 12-34-56 53241224 → 12-34-56 37339759 (`TXN6759`, 15000.00, 12-15) → `BG03CFJF69666911099098` (`TXN6799`, 9200.00, 12-16) | The first payment is 163% of the last |
| Family remittances | 12 customers pay family accounts in BG or LB monthly by SWIFT; 12 such payments fall in December | Direct, no intermediary |

### Background closed trails

**Directed ring (basic)** also returns 22 closed trails made only of background payments, plus the household triangle. Each is listed once.

| # | Accounts, in payment order | Transactions | Made of | Paths | Revisits an account |
| - | -------------------------- | ------------ | ------- | ----- | ------------------- |
| 1 | 12-34-57 30214617 → 12-34-56 88494707 → 12-34-56 38985011 | `TXN663`, `TXN7691`, `TXN6766` | 3 P2P | 3 | no |
| 2 | 12-34-57 10012395 → 12-34-58 14491804 → 12-34-56 60035914 | `TXN2767`, `TXN5816`, `TXN6888` | 3 P2P | 3 | no |
| 3 | 12-34-58 51471988 → 12-34-56 67553834 → 12-34-56 72413051 | `TXN226`, `TXN2668`, `TXN4251` | 3 P2P | 3 | no |
| 4 | 12-34-56 85676002 → 12-34-58 64931257 → 12-34-58 48089203 | `TXN1204`, `TXN4672`, `TXN7709` | 3 P2P | 3 | no |
| 5 | 12-34-58 13664571 → 12-34-57 22128821 → 12-34-57 82774961 | `TXN2250`, `TXN7512`, `TXN3018` | 3 P2P | 3 | no |
| 6 | 12-34-57 10012395 → 12-34-58 14491804 → 12-34-56 60035914 → 88-56-94 94412912 → 12-34-56 60035914 | `TXN2767`, `TXN5816`, `TXN7679`, `TXN7847`, `TXN6888` | 3 P2P, a purchase and its refund | 5 | yes |
| 7 | 12-34-58 99809908 → 12-34-56 32997279 → 12-34-56 21501824 → 12-34-56 32997279 | `TXN2122`, `TXN4921`, `TXN6009`, `TXN2616` | 2 loans, 2 repayments | 4 | yes |
| 8 | 12-34-56 45981026 → 12-34-58 22394117 → 12-34-57 11067175 → 12-34-58 22394117 | `TXN2341`, `TXN3135`, `TXN4261`, `TXN802` | 2 loans, 2 repayments | 4 | yes |
| 9 | 12-34-56 80047205 → 12-34-57 38157088 → 12-34-56 80047205 → 12-34-58 55001940 | `TXN2674`, `TXN4421`, `TXN4385`, `TXN5559` | 2 loans, 2 repayments | 4 | yes |
| 10 | 12-34-58 69059346 → 12-34-57 55739462 → 12-34-58 24015066 → 12-34-57 55739462 | `TXN1029`, `TXN910`, `TXN387`, `TXN904` | 2 loans, 2 repayments | 4 | yes |
| 11 | 12-34-58 45644577 → 12-34-57 61857340 → 12-34-58 45644577 → 12-34-58 14539464 | `TXN1652`, `TXN897`, `TXN3610`, `TXN2588` | 2 loans, 2 repayments | 4 | yes |
| 12 | 12-34-57 34952604 → 12-34-58 14127917 → 50-28-71 23984481 → 12-34-58 14127917 | `TXN2243`, `TXN6379`, `TXN6525`, `TXN2705` | a loan, its repayment, a purchase and its refund | 4 | yes |
| 13 | 12-34-57 34952604 → 12-34-58 14127917 → 50-28-71 23984481 → 12-34-56 52178377 → 50-28-71 23984481 → 12-34-58 14127917 | `TXN2243`, `TXN6379`, `TXN4295`, `TXN3128`, `TXN6525`, `TXN2705` | a loan, its repayment, 2 purchases and refunds | 6 | yes |
| 14 | 12-34-58 50758533 → 25-00-56 55264518 → 12-34-56 29020499 → 25-00-56 55264518 | `TXN5017`, `TXN854`, `TXN623`, `TXN6248` | 2 purchases, 2 refunds | 4 | yes |
| 15 | 12-34-56 95038876 → 12-34-57 99147914 → 12-34-56 95038876 → 12-34-56 33827138 | `TXN3612`, `TXN764`, `TXN6526`, `TXN4977` | 2 purchases, 2 refunds | 4 | yes |
| 16 | 12-34-57 99147914 → 12-34-56 95038876 → 12-34-56 33827138 → 12-34-56 95038876 | `TXN1049`, `TXN6526`, `TXN4977`, `TXN3612` | 2 purchases, 2 refunds | 4 | yes |
| 17 | 12-34-57 99147914 → 12-34-56 95038876 → 12-34-56 33827138 → 12-34-56 95038876 | `TXN2884`, `TXN6526`, `TXN4977`, `TXN3612` | 2 purchases, 2 refunds | 4 | yes |
| 18 | 12-34-56 52178377 → 50-28-71 23984481 → 12-34-58 14127917 → 50-28-71 23984481 | `TXN3128`, `TXN6525`, `TXN6379`, `TXN4295` | 2 purchases, 2 refunds | 4 | yes |
| 19 | 12-34-56 93526490 → 12-34-58 40717302 → 12-34-56 83486636 → 12-34-58 40717302 | `TXN2538`, `TXN5854`, `TXN4539`, `TXN2881` | 2 purchases, 2 refunds | 4 | yes |
| 20 | 12-34-57 93697982 → 22-52-89 81682949 → 12-34-56 96482815 → 22-52-89 81682949 | `TXN2305`, `TXN3055`, `TXN2621`, `TXN2555` | 2 purchases, 2 refunds | 4 | yes |
| 21 | 65-46-16 31804375 → 12-34-57 93697982 → 22-52-89 81682949 → 12-34-57 93697982 | `TXN1076`, `TXN2305`, `TXN2555`, `TXN863` | 2 purchases, 2 refunds | 4 | yes |
| 22 | 65-46-16 31804375 → 12-34-57 93697982 → 22-52-89 81682949 → 12-34-56 96482815 → 22-52-89 81682949 → 12-34-57 93697982 | `TXN1076`, `TXN2305`, `TXN3055`, `TXN2621`, `TXN2555`, `TXN863` | 3 purchases, 3 refunds | 6 | yes |

The five P2P triangles survive the distinct-account filter; none reaches the decay query, because no rotation keeps every hop inside the amount band.

### Reference anchors and editing notes

- **Anchors.** Ring A (12-34-57 43064339 and its three partners, `TXN001`–`TXN004`) anchors the ring queries' `@sample`. MULE-1 `12-34-56 24563467` connects the takeover, mule and high-risk patterns.
- **What carried over from the earlier sample.** The eleven rings keep their members, amounts, dates and ratios, so every ring invariant below is the earlier one restated. What changed is the identifiers: `accountNumber` is now a STRING sort-code-and-account number, so ring A is no longer accounts 1–4, and transaction IDs other than `TXN001`–`TXN004` are renumbered in date order. The background is new, so its trail counts differ.
- **Where the shipped thresholds come from.** The ring bounds, the 0.80–1.00 band and the high-risk 30-day window and 90–110% band come from the source pages, not from this data. The other starting values are domain judgements stated in `@params`; the Sensitivity sections below say where the data, rather than the domain, decides a result.
- **`e.g.` values** in `ONTOLOGY.json` come from unremarkable background rows, never a seeded entity.

## Graph census

- **Parameters:** none.
- **Invariant:** one row whose counts equal the distinct key values in the CSVs: data rows of `customers.csv`, `accounts.csv`, `transactions.csv`, `countries.csv`, `addresses.csv`, `sessions.csv`, `devices.csv`, `ip_addresses.csv`, and distinct emails, phones, passports and licences in the link tables.
- **Expected:** 1 row — customers 1266, accounts 1892, transactions 7906, countries 21, emails 1376, phones 1285, addresses 986, passports 542, drivingLicenses 699, sessions 7432, devices 1748, ips 956.

## Directed ring (basic)

- **Parameters:** none.
- **Invariant:** every row is a closed directed trail of 3 to 6 payments that starts and ends at the same account, never using a transaction twice. Each seeded ring of 3 to 6 hops — A to F, R, O, G and H — is returned once per starting position. Ring L (7 accounts) never appears. Every other row is made only of P2P, loan, repayment, purchase, refund and savings payments that close a loop; payroll, supplier, utility, remittance and seeded takeover, mule or high-risk payments never appear.
- **Expected:** 132 paths over 33 closed trails:
  - Seeded rings, 41 paths: A 4, B 3, C 5, D 6, E 4, F 3, R 4, O 4, G 4, H 4.
  - Household triangle, 3 paths.
  - Background, 88 paths over the 22 trails tabled above: 5 P2P triangles (15 paths), 5 loan-and-repayment pairs (20), 2 loan-and-refund trails (10), 1 P2P-and-refund trail (5), 8 purchase-refund trails of four payments (32) and 1 of six (6).
- **Sensitivity:**
  - An upper bound of 7 (`{3,7}`) adds ring L: 139 paths.
  - An upper bound of 5 returns 114 paths, losing ring D and the two six-payment background trails; 4 returns 104, also losing ring C and the five-payment trail.

## Directed ring with distinct accounts (requires APOC)

- **Parameters:** none.
- **Invariant:** exactly the rows of **Directed ring (basic)** whose paying accounts are all different. Ring R and every background trail that contains a round trip are removed. Rings A–F, O, G and H survive, and so do the household triangle and the P2P triangles, which are genuinely distinct cycles.
- **Expected:** 55 paths over 15 rings: seeded 37 (A 4, B 3, C 5, D 6, E 4, F 3, O 4, G 4, H 4), household triangle 3, and the 5 P2P triangles 15.
- **Sensitivity:** the filter removes 77 of the 132 basic paths — ring R's 4 and 73 background ones.

## Chronological and amount-decay ring (requires APOC)

- **Parameters:** none.
- **Invariant:** exactly one row per true ring, A to F, starting at the ring's earliest payment, and nothing else. No negative ring and no background trail qualifies: R repeats an account, O's dates run backwards, G grows, H has a hop at 0.75, and L needs six repetitions.
- **Expected:** 6 paths:

  | Ring | Path (accounts) | Repetitions |
  | ---- | --------------- | ----------- |
  | A | 12-34-57 43064339 → 12-34-58 25868819 → 12-34-56 28166225 → 12-34-58 39026094 → back | 3 |
  | B | 12-34-57 81395942 → 12-34-57 41271392 → 12-34-57 56576969 → back | 2 |
  | C | 12-34-56 42536850 → 12-34-56 96197502 → 12-34-56 51507083 → 12-34-56 90626530 → 12-34-57 26675516 → back | 4 |
  | D | 12-34-57 18921121 → 12-34-58 89506596 → 12-34-57 74740402 → 12-34-58 82010171 → 12-34-56 26430181 → 12-34-56 20693364 → back | 5 |
  | E | 12-34-58 37132309 → 12-34-56 47357986 → 12-34-57 95182331 → 12-34-57 32336182 → back | 3 |
  | F | 12-34-56 62677430 → 12-34-58 85701835 → 12-34-56 58443261 → back | 2 |

- **Sensitivity:**
  - Repetition `*`: 55 paths — it adds 48 two-account round trips (24 loan repayments, 13 purchase refunds, 7 savings withdrawals, 3 P2P pairs and ring R's middle round trip) and ring L.
  - Repetition `{2,6}` adds ring L (7 paths). `{2,4}` drops D (5 paths); `{2,3}` also drops C (4 paths).
  - A floor of 0.75 adds ring H (7 paths). A floor of 0.86 drops D and F, whose steepest hop keeps 85% (4 paths). A ceiling of 0.95 drops E, which has a hop at 0.96 (5 paths).
  - Without the date condition, ring O qualifies too (7 paths): rotated to start at its largest payment it decays ×0.90 all the way round.
  - Without the amount band, rings G and H qualify, and so do the household triangle and 3 of the P2P triangles, whose dates happen to run in order (12 paths).
  - With the ratio inverted (previous divided by next), only ring G qualifies (1 path) — the amount-growth trap the query's annotation warns about.

## Synthetic identity clusters

- **Parameters:** `$minSharedTypes = 2`, then `3`.
- **Invariant:** at 3, exactly the pairs inside SI-1 and SI-2 that share three or more types, and no other pair. At 2, those plus SI-1's remaining pairs, ring E's six holder pairs (Address and Email), and household pairs sharing an address and a landline; no pair sharing a single type.
- **Expected:**
  - At 2: 44 rows. SI-1 6 (CUS10469 and CUS11143 at 4 types; CUS10386 with each of them at 3; CUS10618 with each of the other three at 2, Address and Phone), SI-2 3 (all at 3: DrivingLicense, Email, Phone), ring E 6 (at 2), background households 29 (at 2, Address and Phone). The first row is CUS10469 / CUS11143.
  - At 3: 6 rows — SI-1's three pairs and SI-2's three pairs.
  - SI-1's rows that include CUS10618 list three accounts, MULE-2 among them, with a newest account opened 2023-10-20.
- **Sensitivity:** no background pair shares three types, so 3 isolates the seeds exactly. That is a fact about the generator — households share at most an address and a landline here — not a guarantee about real data, where a couple can also share an email.

## Device sharing

- **Parameters:** `$minCustomers = 3`.
- **Invariant:** every seeded device appears with exactly its seeded customers — the stuffing device with the four victims and six failed targets, ring C's device with its five holders, the herder device with its four mule holders, SI-1's laptop with three SI-1 customers — and every other device is a household tablet used by members of one household.
- **Expected:** 28 rows over 6 devices: `DEV-626ae42f56` (10 customers), `DEV-946954bd68` (5), `DEV-45b24a72d3` (4), `DEV-3e7d6cb209` (3), and household tablets `DEV-a4e366ea47` and `DEV-34f86ef78f` (3 each). On the stuffing device the six targets have only failed sessions; each victim has failed sessions and one success.
- **Sensitivity:**
  - At 2: 108 rows over 46 devices, adding 40 two-person household tablets.
  - At 4: 19 rows over the three seeded devices with four or more customers. The jump from 3 to 4 removes the household tablets because the generator caps tablet sharing at three people, which is not a domain rule.

## Account takeover

- **Parameters:** `$windowHours = 24`, `$minPriorSessions = 3`, `$paymentTypes = ['FASTER_PAYMENT', 'SWIFT']`.
- **Invariant:** exactly the four seeded takeover sessions, each with its own victim's payment, and no near-miss: the 50-hour gap, the two-session newcomer, the holiday card spend and the payment to a known friend are all rejected.
- **Expected:** 4 rows, ordered by payment date: CUS10596 (`SESS004513` → `TXN4719`, 25 minutes), CUS10941 (`SESS005011` → `TXN5062`, 40), CUS11139 (`SESS005675` → `TXN6245`, 15), CUS10775 (`SESS005875` → `TXN6393`, 70). Every row has `newDevice` and `newCountry` true.
- **Sensitivity:**
  - `$windowHours = 1`: 3 rows; CUS10775's payment at 70 minutes drops.
  - `$windowHours = 72`: 6 rows, adding CUS10451's builder payment (`TXN5055`) and one background coincidence: CUS10133 replaced their phone and made a first P2P payment 50 hours later (`TXN6855`). `$windowHours = 168`: 7 rows, adding another background new phone (CUS10131, `TXN1150`).
  - `$minPriorSessions = 2` adds CUS10408 (`TXN6133`): 5 rows. `$minPriorSessions = 0`: 9 rows, adding CUS10408 and four background customers whose first session on a device, early in their history, precedes a first P2P or loan payment.
  - Adding `'CARD'` to `$paymentTypes`: 17 rows, adding CUS11171's holiday spend (`TXN2711`), 11 background travel spends and one background card purchase after a new phone.
  - Dropping the never-paid-before condition adds CUS10770's payment to a known friend (`TXN4440`): 5 rows.

## Mule account

- **Parameters:** `$maxAccountAgeDays = 90`, `$minSenders = 5`, `$maxDwellHours = 48`, `$minPassThrough = 0.5`.
- **Invariant:** exactly MULE-1 and MULE-2, and none of the near-misses: the treasurer fails on age, the sole trader on dwell time, the student on sender count.
- **Expected:** 2 rows — `12-34-56 24563467` (opened 2023-11-02, 7 senders, inflowTotal 20900.00, quickOutflowTotal 19855.00, passThrough 0.95, 7 quick outflows) and `12-34-57 31478046` (opened 2023-10-20, 5 senders, 7450.00, 6928.50, 0.93, 5).
- **Sensitivity:**
  - `$minSenders = 6` drops MULE-2, which was seeded with exactly five senders so that it sits on the starting value; `$minSenders = 3` adds the student (3 senders, passThrough 0.63).
  - `$maxDwellHours = 168` adds the sole trader (8 senders, passThrough 0.68). With `$minPassThrough = 0`, the sole trader appears at 48 hours too, with passThrough 0.00.
  - `$maxAccountAgeDays = 365` adds three sole-trader business accounts opened between 2022-12 and 2023-02, with passThrough between 1.85 and 10.77 — supplier settlements funded by takings this bank does not see. `3650` returns 14 rows: those, eight more business accounts, and the club treasurer (passThrough 1.00).
  - `$minPassThrough = 0.9` keeps both mules.

## Payment to a high-risk jurisdiction

- **Parameters:** `$windowEnd = '2024-01-01T00:00:00Z'`, `$windowDays = 30`, `$minRatio = 0.9`, `$maxRatio = 1.1`, `$minIntermediaries = 1`.
- **Invariant:** exactly the December layering chain and the two December MULE-1 forwards whose money came from an internal victim, each traced to its seeded origin. Direct remittances, the externally funded forward, the out-of-band chain and the October chain are absent.
- **Expected:** 3 rows:

  | Payment | Amount | Country | Origin | Intermediaries |
  | ------- | ------ | ------- | ------ | -------------- |
  | `TXN6716` | 9400.00 | MC | 12-34-57 69122237 | 2 |
  | `TXN6247` | 3800.00 | BG | 12-34-56 38357453 (CUS11139) | 1 |
  | `TXN6480` | 2375.00 | BG | 12-34-58 42326828 (CUS10085) | 1 |

- **Sensitivity:**
  - `$minIntermediaries = 0`: 17 rows, adding the 12 December remittances, MULE-1's forward of external money (`TXN6551`, starting at MULE-1) and the out-of-band chain's final payment (`TXN6799`, starting at 12-34-56 37339759). `$minIntermediaries = 2`: only `TXN6716`.
  - `$windowDays = 120`: 5 rows, adding the October chain (`TXN2576`, 2 intermediaries) and `TXN6551` traced to CUS10669's November payment into MULE-1 (`TXN4881`, 1650.00, within 10% of 1710.00). Money in a mule account is fungible, so a wider window can attach an outflow to a different inflow.
  - `$maxRatio = 1.7`: 5 rows, adding the out-of-band chain (`TXN6759` → `TXN6799`) and `TXN6551` traced to CUS10085's `TXN6475`.
  - A band of 0.95–1.05: only `TXN6716`; the mule forwards keep 95% of what came in, a ratio of 1.053.

## Cross-layer ring

- **Parameters:** `$minLinkTypes = 1`, then `2`.
- **Invariant:** at 2, exactly rings C and E. At 1, those plus the household triangle. No other ring of distinct accounts — B, D, F, O, G, H, A, or any P2P triangle — has linked holders.
- **Expected:**
  - At 1: 3 rows — ring C (linkTypes Device and Phone; all 10 holder pairs linked), ring E (Address and Email; all 6 pairs), the household triangle (Address; all 3 pairs).
  - At 2: 2 rows — rings C and E.
- **Sensitivity:** 15 distinct-account rings exist; 12 of them have no link between holders at all.

## Project identity links (requires GDS)

- **Parameters:** `$minSharedTypes = 2`.
- **Invariant:** the projected customers are exactly those in at least one row of **Synthetic identity clusters** at the same threshold.
- **Expected:** 1 row — graph `identity-links`, customers 49, links 88 (the 44 pairs, each counted in both directions).
- **Sensitivity:** at `$minSharedTypes = 3`, 6 customers and 6 pairs.

## Identity clusters with WCC (requires GDS)

- **Parameters:** `$minClusterSize = 3`, after projecting with `$minSharedTypes = 2`.
- **Invariant:** SI-1 (four customers), SI-2 (three) and ring E's holders (four) each form one cluster on their own; every other cluster is a single household.
- **Expected:** 8 clusters — SI-1, ring E and one background household of four; SI-2 and four background households of three.
- **Sensitivity:** projected with `$minSharedTypes = 3`, 2 clusters remain, SI-1's three email-sharing customers (CUS10386, CUS10469, CUS11143) and SI-2.

## Drop identity links projection (requires GDS)

- **Parameters:** none.
- **Invariant:** the projection made by **Project identity links** is removed, and projecting again under the same name succeeds afterwards.
- **Expected:** 1 row — graphName `identity-links`. Run a second time, no row.
