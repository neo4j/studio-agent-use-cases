# Query Templates

Runnable Cypher for the Identity Graph model. Every query carries a leading `//` comment block stating its purpose, inputs, prerequisites, and expected result against the bundled sample data, so the comment acts as a lightweight test oracle.

Expected counts are a property of this dataset. If you regenerate or extend `sample-data/`, re-run every template and update the comments.

Prerequisites in one place:

- Neo4j 5.x / Cypher 5 (negated label expressions such as `:!Placeholder`).
- The bundled sample data imported from `sample-data/`.
- `SETUP.md` run post-import: its required statement creates the fulltext index `Near-Duplicate SSN` depends on, and its recommended statements apply the placeholder flags every matching query excludes.
- APOC, for `Descriptor Similarity` and `Weighted Composite Match Score` only.

Run order matters: the two flagging queries first, then matching, then corroboration.

## Placeholder & Invalid Identifier Detection

Run this first, before any matching query. (These two statements are steps 2 and 3 of `SETUP.md` — if setup was run at import time, they are already applied; don't run them twice.) Source systems often stuff a non-null filler value into a required field when the real value isn't known (`"none@none.com"`, `"N/A"`, `"999-999-9999"`). Those are not identifiers, and left alone they silently create false-positive matches between unrelated people. This flags known placeholder values with a `:Placeholder` label so the matching queries can exclude them.

```cypher
// Purpose: flag filler/placeholder email values with a :Placeholder label so they
//   cannot act as a shared identifier in any matching query.
// Inputs: the knownPlaceholderEmails list below; extend per source system.
// Prerequisites: sample data imported. This query WRITES a label (no data change).
// Expected: 2 rows against the sample data — "none@none.com" (shared by ID-4002
//   and ID-5001) and "test@test.com" (shared by ID-8004 and ID-8005). Both pairs
//   are otherwise unrelated, so both disappear from the match results afterwards.
WITH ['none@none.com', 'n/a', 'test@test.com', 'unknown@unknown.com'] AS knownPlaceholderEmails
MATCH (e:Email)
WHERE toLower(e.email) IN knownPlaceholderEmails
   OR e.email =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*'
SET e:Placeholder
RETURN e.email AS flaggedEmail
ORDER BY flaggedEmail;
```

```cypher
// Purpose: flag filler/placeholder phone values with a :Placeholder label.
// Inputs: the knownPlaceholderPhones list below; extend per source system.
// Prerequisites: sample data imported. This query WRITES a label (no data change).
// Expected: 1 row against the sample data — "999-999-9999", shared by ID-8001,
//   ID-8002 and ID-8003, three otherwise-unrelated identities.
WITH ['999-999-9999', '000-000-0000', '555-555-5555'] AS knownPlaceholderPhones
MATCH (p:Phone)
WHERE p.phoneNumber IN knownPlaceholderPhones
SET p:Placeholder
RETURN p.phoneNumber AS flaggedPhone
ORDER BY flaggedPhone;
```

Extend both lists — and add an equivalent check for `SSN` (values starting `000`, `666`, or `900`–`999`, which the SSA never issues) — per the placeholder conventions of your own source systems.

## Shared Identifier Fan-out (Basic)

The simplest pattern in this package, and the right place to start. It returns the full `path`, so it renders directly as a graph in Neo4j Browser rather than a table of disconnected fields.

```cypher
// Purpose: find every pair of identities that share any single strong identifier,
//   returning the connecting path so the result renders as a graph.
// Inputs: none. Add a filter on a specific identity or value to narrow it.
// Prerequisites: sample data imported; placeholder detection already run, or the
//   :!Placeholder filter has nothing to exclude yet.
// Expected: 39 rows spanning 17 distinct identity pairs against the sample data
//   (each row is one pair plus one shared attribute node). Without placeholder
//   detection first, 22 pairs appear — the 5 extra are placeholder false positives.
MATCH path = (i1:Identity)-[r1:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
             (shared:!Placeholder)
             <-[r2:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]-(i2:Identity)
WHERE i1.identityId < i2.identityId
RETURN i1.identityId AS identity1,
       i2.identityId AS identity2,
       type(r1) AS sharedSignal,
       shared,
       path
ORDER BY sharedSignal, identity1, identity2
LIMIT 200;
```

The `LIMIT` is a habit worth keeping rather than a necessity here: this dataset is deliberately sparse in matches, but the same query against a real population returns far more, and browsing the whole result set is rarely what you want. Filter to a specific identity or attribute value you're investigating instead.

## Confidence-Scored Identity Matches

```cypher
// Purpose: rank candidate pairs by how many distinct identifier types they share.
// Inputs: none.
// Prerequisites: sample data imported; placeholder detection already run.
// Expected: 17 rows against the sample data — 1 pair at confidence 5
//   (ID-1001/ID-1003), 3 at confidence 4 (the Angela Torres cluster), 1 at
//   confidence 3, 7 at confidence 2, and 5 at confidence 1. Confidence 3+ picks
//   out the seeded multi-channel clusters with no tuning. 476 of the 500
//   identities have no match at all.
MATCH (i1:Identity)-[r1:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
      (shared:!Placeholder)
      <-[r2:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]-(i2:Identity)
WHERE i1.identityId < i2.identityId
WITH i1, i2, collect(DISTINCT type(r1)) AS sharedSignals
RETURN i1.identityId AS identity1,
       i2.identityId AS identity2,
       sharedSignals,
       size(sharedSignals) AS confidence
ORDER BY confidence DESC, identity1, identity2
LIMIT 50;
```

`confidence` is how many distinct identifier types a pair shares — one shared phone is confidence 1, a shared phone _and_ address is confidence 2. It is a count, not a probability: higher is stronger evidence, but treat it as a triage ranking, not a calibrated likelihood.

Run this with and without the placeholder-detection step to see the difference. Without it, unrelated identities show false-positive matches purely from shared filler values.

## Match Cluster as a Graph

The confidence query above answers "which pairs?" in a table. This answers "what does one cluster actually look like?" as a graph — the view to put on screen in a demo.

```cypher
// Purpose: return the full match cluster around one identity as paths, so Browser
//   renders the identities and the attribute nodes that connect them.
// Inputs: $identityId — an Identity.identityId, e.g. "ID-1001".
// Prerequisites: sample data imported; placeholder detection already run.
// Expected: 8 paths for $identityId = "ID-1001" — 5 shared attributes linking it
//   to ID-1003 (phone, SSN, address, DOB, IP) and 3 linking it to ID-1002 (phone,
//   email, IP). Renders as the 3-record Robert Anderson cluster across CRM,
//   MobileApp and CallCenter.
MATCH path = (seed:Identity {identityId: $identityId})
             -[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
             (shared:!Placeholder)
             <-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]-
             (match:Identity)
WHERE match <> seed
RETURN path;
```

## Implausible Address Detection

The same "flag junk before matching on it" idea as placeholder detection, applied to addresses. Instead of a filler value it's an address a geocoder can't resolve at all. Rather than enumerating every way an address can be wrong, this flags by absence: any `Address` with no `GEOCODED_TO` relationship is one the geocoding step couldn't place.

```cypher
// Purpose: surface addresses the geocoding step could not resolve, by absence of a
//   GEOCODED_TO relationship rather than by inspecting values.
// Inputs: none.
// Prerequisites: sample data imported (addresses.csv and locations.csv both).
// Expected: exactly 3 rows against the sample data — ID-8105 (zip 00000, invalid
//   format), ID-8106 (zip 99999, invalid format) and ID-8107 (zip 98101, a Seattle
//   zip on an Austin address). Run before the two location queries below: an
//   unresolved address has no Location, so it is excluded from both automatically.
MATCH (i:Identity)-[:HAS_ADDRESS]->(a:Address)
WHERE NOT (a)-[:GEOCODED_TO]->(:Location)
RETURN i.identityId AS identity,
       a.address AS address,
       a.city AS city,
       a.state AS state,
       a.zipcode AS zipcode
ORDER BY a.zipcode;
```

## Location Match: Same Coordinates, Different Address Text

Two different address strings — "215 Congress Ave" vs "215 Congress Avenue" — can still geocode to the same `Location`. That convergence is itself a match signal, the same way two identities sharing a `Phone` node converge into a match: here `Location` is the identifier, not `Address`.

```cypher
// Purpose: find identities whose address text differs but whose geocoded location
//   is identical — matches that string-based fan-out cannot see. Returns paths.
// Inputs: none.
// Prerequisites: sample data imported; Implausible Address Detection run first.
// Expected: exactly 2 rows against the sample data — "215 Congress Ave" /
//   "215 Congress Avenue" in Austin (ID-8101/ID-8102), and "900 16th St" /
//   "900 16th Street" in Denver (ID-8103/ID-8104). Neither pair shares any other
//   identifier, so this is the only template in the package that catches them.
MATCH path = (i1:Identity)-[:HAS_ADDRESS]->(a1:Address)-[:GEOCODED_TO]->
             (l:Location)
             <-[:GEOCODED_TO]-(a2:Address)<-[:HAS_ADDRESS]-(i2:Identity)
WHERE i1.identityId < i2.identityId
  AND a1.address <> a2.address
RETURN i1.identityId AS identity1,
       a1.address AS address1,
       i2.identityId AS identity2,
       a2.address AS address2,
       l.latitude AS latitude,
       l.longitude AS longitude,
       path
ORDER BY latitude, longitude;
```

The `a1.address <> a2.address` filter is what makes this distinct from the plain fan-out: identities sharing the _exact same_ address string already appear there via `HAS_ADDRESS`. This surfaces only the cases the string comparison misses.

## Descriptor Similarity: Near-Miss Name Spelling

`PersonName` is a **descriptor**, not an identifier. Plenty of unrelated people share a name, so a name alone should never establish a match — which is why it is excluded from the fan-out. Once two identities are already suspected of being the same person via a real identifier, a near-miss spelling is corroborating evidence.

This deliberately scores only pairs that already share a real identifier, never all name pairs in the graph. Jaro-Winkler rewards a matching prefix heavily, so two unrelated people who happen to share a first name can outscore a genuine near-miss spelling; run over the full population it returns mostly noise. Against this dataset an unblocked scan at the same threshold returns 2,264 pairs, versus 3 when blocked.

`apoc.text.jaroWinklerDistance` returns a **distance** (0 = identical, larger = more different), not a similarity — most Jaro-Winkler implementations elsewhere return a similarity, so the mistake is easy to make. The query converts with `1 - apoc.text.jaroWinklerDistance(...)` so `nameSimilarity` means what it says and the threshold reads naturally. Skipping the conversion doesn't error; it just sorts and thresholds backwards.

```cypher
// Purpose: corroborate an already-suspected match with a near-miss name spelling.
// Inputs: threshold 0.80 below; raise it to tighten.
// Prerequisites: APOC installed; sample data imported; placeholder detection run.
// Expected: exactly 3 rows against the sample data — the seeded synthetic-identity
//   pairs Carlos/Carla Marquez (0.948), Tyler/Taylor Bowen (0.923) and
//   David/Daniel Kim (0.861), each already flagged by a shared phone number.
//   15 candidate pairs enter the scoring step; 3 clear the threshold.
MATCH (i1:Identity)-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS]->(shared)
      <-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS]-(i2:Identity)
WHERE i1.identityId < i2.identityId
  AND NOT shared:Placeholder
WITH DISTINCT i1, i2
MATCH (i1)-[:HAS_NAME]->(n1:PersonName)
MATCH (i2)-[:HAS_NAME]->(n2:PersonName)
WHERE n1.fullName <> n2.fullName
WITH i1, i2, n1, n2,
     1 - apoc.text.jaroWinklerDistance(n1.fullName, n2.fullName) AS nameSimilarity
WHERE nameSimilarity >= 0.80
RETURN i1.identityId AS identity1,
       n1.fullName AS name1,
       i2.identityId AS identity2,
       n2.fullName AS name2,
       round(nameSimilarity, 3) AS nameSimilarity
ORDER BY nameSimilarity DESC;
```

The blocking set is `HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS`, excluding `HAS_DOB` and `HAS_IP` — see `query-patterns.md` for why.

## Nearby Address (Geographic Distance as Descriptor)

Geographic distance is a descriptor for the same reason a name is: plenty of unrelated people live near each other. Like the name query, this scores only pairs already blocked by a real identifier — here phone, email, or SSN, deliberately excluding `HAS_ADDRESS`, since address plausibility is exactly what's being corroborated.

`point.distance()` returns metres directly for geographic points. The query constructs the points inline from `latitude` and `longitude`, so it works against imported data with no extra step. If you materialise a `coordinates` point property (see the optional section of `SETUP.md`), substitute `l1.coordinates` and `l2.coordinates`.

```cypher
// Purpose: corroborate an already-suspected match with geographic proximity.
// Inputs: 500m threshold below; tune down for denser real-world address data.
// Prerequisites: sample data imported; Implausible Address Detection run first.
//   Built-in point.distance() — no APOC or plugin needed.
// Expected: exactly 1 row against the sample data — ID-4001 (David Kim) and
//   ID-4002 (Daniel Kim), 241m apart in Austin. That pair is already flagged by a
//   shared phone and a near-miss name, so this is a third corroborating signal,
//   not a new discovery. 11 candidate pairs enter the distance step.
MATCH (i1:Identity)-[:HAS_PHONE|HAS_EMAIL|HAS_SSN]->(shared)
      <-[:HAS_PHONE|HAS_EMAIL|HAS_SSN]-(i2:Identity)
WHERE i1.identityId < i2.identityId
  AND NOT shared:Placeholder
WITH DISTINCT i1, i2
MATCH (i1)-[:HAS_ADDRESS]->(a1:Address)-[:GEOCODED_TO]->(l1:Location)
MATCH (i2)-[:HAS_ADDRESS]->(a2:Address)-[:GEOCODED_TO]->(l2:Location)
WHERE l1 <> l2
WITH i1, i2, a1, a2,
     point.distance(
       point({latitude: l1.latitude, longitude: l1.longitude}),
       point({latitude: l2.latitude, longitude: l2.longitude})
     ) AS metersApart
WHERE metersApart <= 500
RETURN i1.identityId AS identity1,
       a1.address AS address1,
       i2.identityId AS identity2,
       a2.address AS address2,
       round(metersApart) AS metersApart
ORDER BY metersApart;
```

This is meant to strengthen an already-suspected match, not to discover one on distance alone. An unblocked version at real address density would return plenty of coincidentally-nearby strangers.

## Weighted Composite Match Score

Blends identifier confidence with descriptor similarity into one illustrative score. `size(sharedSignals) / 6.0` rescales the identifier count (1–6, never 0 here, since every returned pair already passed the blocking match) into the same 0–1 range as `nameSimilarity`, so the two terms can be weighted and summed meaningfully. The 0.7/0.3 split is a starting point, not a tuned value.

```cypher
// Purpose: rank candidate pairs by a single score combining identifier confidence
//   with name similarity, for triaging a large candidate list.
// Inputs: the 0.7/0.3 weights below — illustrative, tune with domain expertise.
// Prerequisites: APOC installed; sample data imported; placeholder detection run.
// Expected: 15 rows against the sample data. The seeded multi-channel clusters
//   (Robert Anderson, Angela Torres, Marcus Odom, Wei Zhang, Maria Chen, Priya
//   Nair) occupy the top at 0.533–0.883, and the 3 synthetic-identity pairs sit
//   distinctly below at 0.375–0.401 — the ambiguous band a human should review.
MATCH (i1:Identity)-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS]->(shared)
      <-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS]-(i2:Identity)
WHERE i1.identityId < i2.identityId
  AND NOT shared:Placeholder
WITH DISTINCT i1, i2
MATCH (i1)-[r1:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->(sharedAny)
      <-[r2:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]-(i2)
WHERE NOT sharedAny:Placeholder
WITH i1, i2, collect(DISTINCT type(r1)) AS sharedSignals
MATCH (i1)-[:HAS_NAME]->(n1:PersonName)
MATCH (i2)-[:HAS_NAME]->(n2:PersonName)
WITH i1, i2, sharedSignals,
     1 - apoc.text.jaroWinklerDistance(n1.fullName, n2.fullName) AS nameSimilarity
RETURN i1.identityId AS identity1,
       i2.identityId AS identity2,
       sharedSignals,
       size(sharedSignals) AS identifierConfidence,
       round(nameSimilarity, 2) AS nameSimilarity,
       round(0.7 * (size(sharedSignals) / 6.0) + 0.3 * nameSimilarity, 3) AS weightedScore
ORDER BY weightedScore DESC, identity1, identity2
LIMIT 50;
```

## Near-Duplicate SSN (Synthetic Identity Signal)

Everything above catches records that match exactly. A synthetic-identity fraudster doesn't need an exact match to slip past those checks: reuse a victim's real contact details so the application looks legitimate, but alter one digit of the SSN so it doesn't collide under exact-match dedup. The fan-out and confidence queries would never catch that, because the SSNs genuinely don't match.

The masked SSN carries only 4 digits of entropy (10,000 possible values). Across 500 people that produces 244 coincidental edit-distance-1 pairs with no relationship to each other. The fix is the same as elsewhere: only treat a near-duplicate SSN as meaningful when the same two identities _also_ share a real contact identifier.

```cypher
// Purpose: find SSNs that are almost identical (edit distance 1) and corroborated
//   by a genuinely shared contact identifier — the synthetic-identity signature.
// Inputs: the ~1 fuzzy operator below; ~2 widens it (Lucene caps at 2).
// Prerequisites: ssnFuzzyIndex fulltext index with the 'keyword' analyzer, created
//   by SETUP.md; sample data imported; placeholder detection run.
// Expected: exactly 3 rows against the sample data — the seeded synthetic-identity
//   pairs Carla/Carlos Marquez (XXX-XX-4508 / XXX-XX-4598), David/Daniel Kim
//   (XXX-XX-4821 / XXX-XX-4831) and Taylor/Tyler Bowen (XXX-XX-8017 /
//   XXX-XX-8517), each corroborated by a shared phone number. Without the
//   corroboration match, 244 coincidental pairs are returned instead.
MATCH (s:SSN)
WITH s, replace(s.ssn, '-', '\\-') AS escapedSsn
CALL db.index.fulltext.queryNodes('ssnFuzzyIndex', escapedSsn + '~1') YIELD node, score
WHERE s.ssn < node.ssn
MATCH (i1:Identity)-[:HAS_SSN]->(s)
MATCH (i2:Identity)-[:HAS_SSN]->(node)
MATCH (i1)-[rc1:HAS_PHONE|HAS_EMAIL|HAS_ADDRESS]->(corrob)
      <-[rc2:HAS_PHONE|HAS_EMAIL|HAS_ADDRESS]-(i2)
WHERE NOT corrob:Placeholder
RETURN i1.identityId AS identity1,
       s.ssn AS ssn1,
       i2.identityId AS identity2,
       node.ssn AS ssn2,
       score,
       type(rc1) AS corroboratingSignal
ORDER BY score DESC;
```

The `-` in each SSN must be escaped before it reaches the Lucene query parser, since `-` is a reserved character there. Using the fulltext index rather than a pairwise self-join is what makes this scale: the fuzzy lookup itself is fast, and it was the lack of corroboration that caused the noise, not the lookup mechanism.

Same query, returned as a graph for a demo:

```cypher
// Purpose: same synthetic-identity detection, returned as paths so Browser renders
//   the two identities, their near-duplicate SSNs, and the shared phone that
//   corroborates the link.
// Inputs: none.
// Prerequisites: as above — ssnFuzzyIndex, sample data, placeholder detection.
// Expected: 3 rows for the same 3 seeded fraud pairs, each with 3 path columns
//   that Browser merges into one graph view per row.
MATCH (s:SSN)
WITH s, replace(s.ssn, '-', '\\-') AS escapedSsn
CALL db.index.fulltext.queryNodes('ssnFuzzyIndex', escapedSsn + '~1') YIELD node
WHERE s.ssn < node.ssn
MATCH (i1:Identity)-[:HAS_SSN]->(s)
MATCH (i2:Identity)-[:HAS_SSN]->(node)
MATCH corroborationPath = (i1)-[:HAS_PHONE|HAS_EMAIL|HAS_ADDRESS]->(corrob)
                          <-[:HAS_PHONE|HAS_EMAIL|HAS_ADDRESS]-(i2)
WHERE NOT corrob:Placeholder
MATCH ssnPath1 = (i1)-[:HAS_SSN]->(s)
MATCH ssnPath2 = (i2)-[:HAS_SSN]->(node)
RETURN corroborationPath, ssnPath1, ssnPath2;
```

## Cross-Channel Profile Assembly

Everything above is about _finding_ candidate matches. Once a cluster is worth trusting, this is the operational query that follows: given one known identifier, pull every `Identity` linked to it and assemble the full picture across source systems. Each attribute is an `OPTIONAL MATCH`, so a record missing a field returns `null` for that column instead of dropping out.

```cypher
// Purpose: assemble one resolved profile across every source system that holds a
//   record for a known identifier.
// Inputs: $phoneNumber — e.g. "555-201-8823".
// Prerequisites: sample data imported.
// Expected: 3 rows for $phoneNumber = "555-201-8823" — ID-1001 (CRM), ID-1002
//   (MobileApp) and ID-1003 (CallCenter), all Robert A***n. ID-1002 returns null
//   for address, SSN and DOB; ID-1003 returns null for email. That is the point:
//   no single record is complete, and together they are.
MATCH (p:Phone {phoneNumber: $phoneNumber})<-[:HAS_PHONE]-(i:Identity)
OPTIONAL MATCH (i)-[:HAS_NAME]->(n:PersonName)
OPTIONAL MATCH (i)-[:HAS_EMAIL]->(e:Email)
OPTIONAL MATCH (i)-[:HAS_SSN]->(s:SSN)
OPTIONAL MATCH (i)-[:HAS_ADDRESS]->(a:Address)
OPTIONAL MATCH (i)-[:HAS_DOB]->(d:DOB)
OPTIONAL MATCH (i)-[:HAS_IP]->(ip:IPAddress)
RETURN i.identityId AS identity,
       i.sourceSystem AS sourceSystem,
       n.fullName AS name,
       e.email AS email,
       s.ssn AS ssn,
       a.address AS address,
       d.dob AS dob,
       ip.ip AS ip
ORDER BY sourceSystem;
```

Same assembly, returned as a graph:

```cypher
// Purpose: the assembled profile as paths, so Browser renders every source-system
//   record around the shared identifier as one connected picture.
// Inputs: $phoneNumber — e.g. "555-201-8823".
// Prerequisites: sample data imported.
// Expected: 17 paths for $phoneNumber = "555-201-8823" — 7 attributes on ID-1001,
//   4 on ID-1002 and 6 on ID-1003. Renders as 3 Identity nodes sharing a Phone,
//   an Email, an IPAddress, an Address, an SSN, a DOB and a PersonName.
MATCH (:Phone {phoneNumber: $phoneNumber})<-[:HAS_PHONE]-(i:Identity)
MATCH path = (i)-[:HAS_NAME|HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
             (attribute)
RETURN path;
```

## Constraints

The node-key constraints below are created automatically when the sample data is loaded via the Import app from `GRAPH_MODEL.json` — do **not** recreate them (or `UNIQUE` variants of them) on an imported database. If you seed the graph another way, create them first:

```cypher
// Node-key constraints matching GRAPH_MODEL.json. For non-Import loads only.
CREATE CONSTRAINT identityId_Identity_key IF NOT EXISTS
  FOR (i:Identity) REQUIRE i.identityId IS NODE KEY;
CREATE CONSTRAINT fullName_PersonName_key IF NOT EXISTS
  FOR (n:PersonName) REQUIRE n.fullName IS NODE KEY;
CREATE CONSTRAINT phoneNumber_Phone_key IF NOT EXISTS
  FOR (p:Phone) REQUIRE p.phoneNumber IS NODE KEY;
CREATE CONSTRAINT email_Email_key IF NOT EXISTS
  FOR (e:Email) REQUIRE e.email IS NODE KEY;
CREATE CONSTRAINT ssn_SSN_key IF NOT EXISTS
  FOR (s:SSN) REQUIRE s.ssn IS NODE KEY;
CREATE CONSTRAINT addressId_Address_key IF NOT EXISTS
  FOR (a:Address) REQUIRE a.addressId IS NODE KEY;
CREATE CONSTRAINT dateHash_DOB_key IF NOT EXISTS
  FOR (d:DOB) REQUIRE d.dateHash IS NODE KEY;
CREATE CONSTRAINT ip_IPAddress_key IF NOT EXISTS
  FOR (ip:IPAddress) REQUIRE ip.ip IS NODE KEY;
CREATE CONSTRAINT locationId_Location_key IF NOT EXISTS
  FOR (l:Location) REQUIRE l.locationId IS NODE KEY;
```
