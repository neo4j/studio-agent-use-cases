# Identity Validation — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j 5.x database with APOC installed — the import writes the whole sample, and two queries need APOC.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. Run `SETUP.md` statement 1 (the `ssnFuzzyIndex` fulltext index). Statements 2 and 3 are the same Cypher as the first two queries below, so either run them from `SETUP.md` and skip those two queries, or skip them and run the queries — not both. The optional spatial statements are not needed.
4. Run each query in `QUERIES.md`, in file order, with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second. Order matters: the placeholder flags must be applied before the matching queries.

## Sample-data profile

500 synthetic, masked identity profiles from four source systems, of which 35 are hand-seeded and 465 are non-matching background with realistic capture gaps (10–30% missing per attribute).

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Identity` | 500 | Source systems: Ecommerce 129, CallCenter 126, MobileApp 123, CRM 122. Seeded profiles are `ID-1001`–`ID-8107`; background profiles are `ID-9xxx` |
| `PersonName` | 484 | From 500 name rows. 13 names are shared: the 6 seeded clusters, and 7 coincidental background pairs (no query matches on names alone) |
| `Phone` | 428 | From 439 rows. 8 shared: 7 seeded and the placeholder `999-999-9999` |
| `Email` | 386 | From 390 rows. 4 shared: 2 seeded and the placeholders `none@none.com`, `test@test.com` |
| `SSN` | 366 | From 367 rows. 1 shared (`XXX-XX-1190`, the Robert A\*\*\*n cluster) |
| `Address` | 410 | From 416 rows across 12 cities. 4 shared, all seeded |
| `DOB` | 408 | From 416 rows. 6 shared: 4 seeded and 2 coincidental. Only 56 distinct masked `dob` years |
| `IPAddress` | 482 | From 487 rows. 3 shared, all seeded |
| `Location` | 405 | From 407 geocoded addresses. 2 shared, both seeded location-only pairs |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `HAS_NAME` | 500 | Every identity has a name |
| `HAS_PHONE` | 439 | |
| `HAS_EMAIL` | 390 | |
| `HAS_SSN` | 367 | |
| `HAS_ADDRESS` | 416 | |
| `HAS_DOB` | 416 | |
| `HAS_IP` | 487 | |
| `GEOCODED_TO` | 407 | Every address except the 3 seeded implausible ones |

Every identity has at most one of each attribute, and every address at most one location, matching the counts in `ONTOLOGY.json`. Every endpoint resolves; no merged node has conflicting property values across rows.

**Seeded signals**

- **Multi-channel clusters (6, all genuine).**
  - Robert A\*\*\*n: `ID-1001` (CRM), `ID-1002` (MobileApp), `ID-1003` (CallCenter). All three share phone `555-201-8823` and IP `203.0.113.45`; `ID-1001`/`ID-1002` share an email; `ID-1001`/`ID-1003` share SSN `XXX-XX-1190`, address `1210 Foxglove Dr, Austin, TX 78701` and DOB. `ID-1002` has no SSN, address or DOB; `ID-1003` no email.
  - Angela T\*\*\*s: `ID-6001`–`ID-6003`, sharing phone, address (`410 Angel Harbor, Boise`), DOB and IP.
  - Priya N\*\*: `ID-6006`–`ID-6008`, sharing address (`1675 Pacheco Avenue, Denver`) and DOB.
  - Maria C\*\*\*n: `ID-2001`/`ID-2002`, sharing address (`482 Ridgeway Ln, Denver`) and DOB.
  - Marcus O\*\*: `ID-6004`/`ID-6005`, sharing phone and email.
  - Wei Z\*\*\*g: `ID-6009`/`ID-6010`, sharing phone and IP.
- **Synthetic-identity pairs (3).** Each shares only a phone, holds SSNs one digit apart, and carries a near-miss name:
  - David K\*\* `ID-4001` / Daniel K\*\* `ID-4002` — phone `555-334-6689`, SSNs `XXX-XX-4821` / `XXX-XX-4831`, addresses 241.8 m apart in Austin.
  - Carlos M\*\*\*z `ID-7001` / Carla M\*\*\*z `ID-7002` — phone `555-904-9125`, SSNs `XXX-XX-4598` / `XXX-XX-4508`.
  - Tyler B\*\*\*n `ID-7003` / Taylor B\*\*\*n `ID-7004` — phone `555-711-6482`, SSNs `XXX-XX-8517` / `XXX-XX-8017`.
- **Placeholder collisions.** `none@none.com` on `ID-4002` and `ID-5001`; `test@test.com` on `ID-8004` and `ID-8005`; phone `999-999-9999` on `ID-8001`, `ID-8002` and `ID-8003`. Without the flags these create 5 false pairs.
- **Location-only pairs (2).** `ID-8101` / `ID-8102` (`215 Congress Ave` / `215 Congress Avenue`, Austin) and `ID-8103` / `ID-8104` (`900 16th St` / `900 16th Street`, Denver). Each pair's addresses converge on one `Location`, and the pair shares nothing else.
- **Implausible addresses (3).** `ID-8105` (`1 Test Address`, zip `00000`), `ID-8106` (`999 Fake Rd`, zip `99999`) and `ID-8107` (`50 Placeholder Pkwy`, Austin, with Seattle zip `98101`). None is in `locations.csv`.
- **Curated singletons.** `ID-3001` and `ID-5001` match nothing once placeholders are flagged.

**Background noise.** Two coincidental same-birthdate pairs survive into the match results at confidence 1: `ID-7003` / `ID-9120` and `ID-8003` / `ID-9241`. Seven coincidental shared names (for example `ID-8102` / `ID-9178`, both Ethan C\*\*) never reach a result, because names are excluded from candidate generation. 476 of the 500 identities appear in no candidate pair.

Entropy facts the queries are designed around:

- `DOB` keyed on the masked year would give 56 nodes and 1,566 coincidental same-node pairs; keyed on `dateHash` it gives 408 nodes and 10 same-node pairs (8 seeded, 2 coincidental).
- Masked SSNs: 272 pairs of distinct SSN values sit one edit apart (244 single-digit substitutions plus 28 adjacent transpositions), all but 3 of them coincidental; 4,137 pairs sit within two edits.
- Masked names: an unblocked Jaro–Winkler scan at 0.80 matches 2,219 identity pairs with different names (2,075 distinct name pairs). Masked surnames collapse to 148 patterns, so 1,229 identity pairs share an exact masked surname and 645 share a first name.

**Data conventions** (for anyone editing the CSVs).

- Identifiers are masked, not randomised: SSNs as `XXX-XX-####`, phones in the reserved 555 area code, IPs in the documentation ranges `192.0.2.x`, `198.51.100.x`, `203.0.113.x`. Keep that convention; never add real or fully unmasked identifiers.
- `Location.latitude`/`longitude` are real ZIP-centre coordinates for the 12 cities, jittered a few hundred metres per address — not the output of a geocoder run.
- `DOB.dateHash` is a truncated HMAC-SHA256 of the full birthdate under an obviously fake demo key. Regenerate it with an HMAC, never a plain hash.
- `addressId` and `locationId` are derived from exactly the columns they stand for and are CSV-quoted because they contain commas.
- Five masked-name collisions in the original data (for example Bowen and Burton both masking to `B***n`) were resolved by revealing one more surname character on the background record, so every `fullName` maps to exactly one real name.

**Reference anchors.** `$identityId = 'ID-1001'` and `$phoneNumber = '555-201-8823'`, both the Robert A\*\*\*n cluster.

**Editing notes.**

- Every expected result below was recomputed from the CSVs during the migration to the current package format, replacing the legacy `// Expected:` query comments and expected-results tables. All agreed except the statistics below, which are corrected here.
  - `Nearby Address`: 241.8 m, so `round()` gives 242. The legacy figure, 241, matches a 6,371 km earth radius; Neo4j's `point.distance()` uses 6,378,140 m.
  - Unblocked SSN fuzzy scan: 272 value pairs, not 244. The legacy count took single-digit substitutions only, but Lucene's fuzzy operator also counts an adjacent transposition as one edit.
  - Unblocked name scan: 2,219, not 2,264. Masked-surname statistics: 148 patterns and 1,229 pairs, not 143 and 1,267. The legacy figures appear to predate the disambiguation of the five masked-name collisions. The first-name figure, 645, is unchanged.
- Two query headings were split during the migration: the placeholder heading became `Placeholder Email Detection` and `Placeholder Phone Detection`, and the graph variants of the SSN and profile-assembly queries became `Near-Duplicate SSN as a Graph` and `Cross-Channel Profile as a Graph`. The two APOC queries gained "(requires APOC)" in their headings. The Cypher is unchanged.
- Where the shipped thresholds come from. Jaro–Winkler 0.80 is a common starting point for name matching. The legacy notes say 500 m was chosen as "deliberately narrow for this sample data's density"; on this data any threshold from 242 m to about 233 km returns the same single row, so the value is not load-bearing here. The 0.7 / 0.3 weights are illustrative, per the source talk. `~1` matches the one-digit alterations the synthetic pairs were built with.
- The `e.g.` samples in `ONTOLOGY.json` come from background profile `ID-9033`, not from a seeded cluster.

## Placeholder Email Detection

- **Parameters:** none.
- **Invariant:** flags exactly the emails in the literal list or matching the word-boundary pattern — on this data, the two seeded placeholder collisions and no ordinary masked address.
- **Expected:** 2 rows, `none@none.com` then `test@test.com`. Both nodes gain `:Placeholder`.

## Placeholder Phone Detection

- **Parameters:** none.
- **Invariant:** flags exactly the phones in the literal list — the seeded `999-999-9999` and nothing else.
- **Expected:** 1 row, `999-999-9999`.

## Shared Identifier Fan-out (Basic)

- **Parameters:** none.
- **Invariant:** one row for each pair of identities and each non-placeholder phone, email, SSN, address, DOB or IP node both carry; every pair in the six seeded clusters and the three synthetic pairs appears, plus the two coincidental DOB pairs; no placeholder value and no location-only pair appears.
- **Expected:** 39 rows across 17 pairs, ordered by `sharedSignal`: `HAS_ADDRESS` 8, `HAS_DOB` 10, `HAS_EMAIL` 2, `HAS_IP` 7, `HAS_PHONE` 11, `HAS_SSN` 1.
- **Sensitivity:** before the placeholder flags are applied, 44 rows across 22 pairs — the 5 extra pairs are the placeholder false positives listed under Confidence-Scored Identity Matches.

## Confidence-Scored Identity Matches

- **Parameters:** none.
- **Invariant:** one row per pair from the fan-out, with confidence the number of distinct identifier types they share. The seeded multi-channel pairs rank at confidence 2–5; the synthetic pairs and the coincidental DOB pairs sit at confidence 1.
- **Expected:** 17 rows, in order:

  | identity1 | identity2 | sharedSignals | confidence |
  | --------- | --------- | ------------- | ---------- |
  | ID-1001 | ID-1003 | address, DOB, IP, phone, SSN | 5 |
  | ID-6001 | ID-6002 | address, DOB, IP, phone | 4 |
  | ID-6001 | ID-6003 | address, DOB, IP, phone | 4 |
  | ID-6002 | ID-6003 | address, DOB, IP, phone | 4 |
  | ID-1001 | ID-1002 | email, IP, phone | 3 |
  | ID-1002 | ID-1003 | IP, phone | 2 |
  | ID-2001 | ID-2002 | address, DOB | 2 |
  | ID-6004 | ID-6005 | email, phone | 2 |
  | ID-6006 | ID-6007 | address, DOB | 2 |
  | ID-6006 | ID-6008 | address, DOB | 2 |
  | ID-6007 | ID-6008 | address, DOB | 2 |
  | ID-6009 | ID-6010 | IP, phone | 2 |
  | ID-4001 | ID-4002 | phone | 1 |
  | ID-7001 | ID-7002 | phone | 1 |
  | ID-7003 | ID-7004 | phone | 1 |
  | ID-7003 | ID-9120 | DOB | 1 |
  | ID-8003 | ID-9241 | DOB | 1 |

  The order of types within `sharedSignals` is not fixed. 24 identities appear; 476 do not. 17 pairs out of 124,750 possible pairings.
- **Sensitivity:** without the placeholder flags, 22 rows — adding `ID-4002`/`ID-5001` (`none@none.com`), `ID-8004`/`ID-8005` (`test@test.com`) and the three pairs among `ID-8001`–`ID-8003` (`999-999-9999`), each at confidence 1.

## Match Cluster as a Graph

- **Parameters:** `$identityId = 'ID-1001'`.
- **Invariant:** every path runs from the seed through a non-placeholder attribute it carries to another identity carrying the same attribute; the seed never matches itself.
- **Expected:** 8 paths — to `ID-1003` through phone, SSN, address, DOB and IP (5), and to `ID-1002` through phone, email and IP (3). The drawing shows the three Robert A\*\*\*n records.

## Implausible Address Detection

- **Parameters:** none.
- **Invariant:** exactly the identities whose address has no `GEOCODED_TO` — the three seeded implausible addresses.
- **Expected:** 3 rows ordered by zipcode: `ID-8105` (`1 Test Address`, Austin, TX, `00000`), `ID-8107` (`50 Placeholder Pkwy`, Austin, TX, `98101`), `ID-8106` (`999 Fake Rd`, Denver, CO, `99999`).

## Location Match: Same Coordinates, Different Address Text

- **Parameters:** none.
- **Invariant:** exactly the two seeded location-only pairs; no pair that shares an `Address` node appears.
- **Expected:** 2 rows ordered by latitude: `ID-8101` / `ID-8102` (`215 Congress Ave` / `215 Congress Avenue`, 30.2686, -97.7411), then `ID-8103` / `ID-8104` (`900 16th St` / `900 16th Street`, 39.7488, -104.9903).

## Descriptor Similarity: Near-Miss Name Spelling (requires APOC)

- **Parameters:** none.
- **Invariant:** exactly the three seeded synthetic pairs. Of the 15 pairs that pass blocking, 12 carry identical names and are excluded by `n1.fullName <> n2.fullName`; the remaining 3 all clear the threshold.
- **Expected:** 3 rows — `ID-7001` Carlos M\*\*\*z / `ID-7002` Carla M\*\*\*z 0.948, `ID-7003` Tyler B\*\*\*n / `ID-7004` Taylor B\*\*\*n 0.923, `ID-4001` David K\*\* / `ID-4002` Daniel K\*\* 0.861. Similarities computed with the commons-text Jaro–Winkler that `apoc.text.jaroWinklerDistance` wraps.
- **Sensitivity:** a threshold above 0.861 drops David/Daniel, and above 0.923 leaves only Carlos/Carla. Lowering it adds nothing, since only 3 pairs are scored. An unblocked scan at 0.80 matches 2,219 identity pairs.

## Nearby Address (Geographic Distance as Descriptor)

- **Parameters:** none.
- **Invariant:** only the synthetic pair whose addresses were seeded close together; every other blocked pair is either at the same `Location` (excluded by `l1 <> l2`) or hundreds of kilometres apart.
- **Expected:** 1 row — `ID-4001` (`19 Birchwood Ct`) / `ID-4002` (`340 Sunset Blvd`), metersApart 242 (241.8 m). 11 pairs pass blocking; 5 of them resolve to two different Locations (`ID-4001`/`ID-4002` at 241.8 m, then `ID-6009`/`ID-6010` at about 233 km and three pairs over 440 km).
- **Sensitivity:** any threshold from 242 m to about 233 km returns this one row.

## Weighted Composite Match Score (requires APOC)

- **Parameters:** none.
- **Invariant:** one row per pair that passes phone/email/SSN/address blocking and has a name on both sides. Every exact-name seeded pair outscores every near-miss-name synthetic pair, and the coincidental DOB pairs do not appear (DOB is not a blocking signal).
- **Expected:** 15 rows:

  | identity1 | identity2 | identifierConfidence | nameSimilarity | weightedScore |
  | --------- | --------- | -------------------- | -------------- | ------------- |
  | ID-1001 | ID-1003 | 5 | 1.0 | 0.883 |
  | ID-6001 | ID-6002 | 4 | 1.0 | 0.767 |
  | ID-6001 | ID-6003 | 4 | 1.0 | 0.767 |
  | ID-6002 | ID-6003 | 4 | 1.0 | 0.767 |
  | ID-1001 | ID-1002 | 3 | 1.0 | 0.65 |
  | ID-1002 | ID-1003 | 2 | 1.0 | 0.533 |
  | ID-2001 | ID-2002 | 2 | 1.0 | 0.533 |
  | ID-6004 | ID-6005 | 2 | 1.0 | 0.533 |
  | ID-6006 | ID-6007 | 2 | 1.0 | 0.533 |
  | ID-6006 | ID-6008 | 2 | 1.0 | 0.533 |
  | ID-6007 | ID-6008 | 2 | 1.0 | 0.533 |
  | ID-6009 | ID-6010 | 2 | 1.0 | 0.533 |
  | ID-7001 | ID-7002 | 1 | 0.95 | 0.401 |
  | ID-7003 | ID-7004 | 1 | 0.92 | 0.393 |
  | ID-4001 | ID-4002 | 1 | 0.86 | 0.375 |

## Near-Duplicate SSN (Synthetic Identity Signal)

- **Parameters:** none. Requires `ssnFuzzyIndex`.
- **Invariant:** exactly the three seeded synthetic pairs, each once, corroborated by its shared phone. No coincidental near-duplicate survives corroboration.
- **Expected:** 3 rows — `ID-7002` `XXX-XX-4508` / `ID-7001` `XXX-XX-4598`, `ID-4001` `XXX-XX-4821` / `ID-4002` `XXX-XX-4831`, `ID-7004` `XXX-XX-8017` / `ID-7003` `XXX-XX-8517`, all `corroboratingSignal` `HAS_PHONE`. Row order follows the Lucene score, which is not fixed here.
- **Sensitivity:** without the corroboration match, 273 rows — one per identity pair holding SSNs one edit apart (272 value pairs; `XXX-XX-1190` is held by two identities). At `~2` the corroborated result is the same 3 rows, while the unblocked candidate count rises to about 4,137 value pairs.

## Near-Duplicate SSN as a Graph

- **Parameters:** none. Requires `ssnFuzzyIndex`.
- **Invariant:** one row per pair found by the tabular query and per corroborating attribute.
- **Expected:** 3 rows, each joining a synthetic pair through its shared `Phone`, plus each identity's own `SSN`.

## Cross-Channel Profile Assembly

- **Parameters:** `$phoneNumber = '555-201-8823'`.
- **Invariant:** one row per identity carrying the phone, with null in every column whose attribute that record lacks.
- **Expected:** 3 rows ordered by `sourceSystem` (`CRM` sorts before `CallCenter`): `ID-1001` CRM with every column filled; `ID-1003` CallCenter with no email; `ID-1002` MobileApp with no SSN, address or DOB. All three names are `Robert A***n`.

## Cross-Channel Profile as a Graph

- **Parameters:** `$phoneNumber = '555-201-8823'`.
- **Invariant:** one path per attribute relationship of each identity carrying the phone.
- **Expected:** 17 paths — 7 from `ID-1001`, 4 from `ID-1002`, 6 from `ID-1003`. The drawing shows 3 identities sharing one `Phone`, `Email`, `IPAddress`, `Address`, `SSN`, `DOB` and `PersonName`.
