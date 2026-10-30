// # Identity Validation — Query Guidance

// Cypher for the `identity-validation` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`), plus the query-created `:Placeholder` label defined in `SKILL.md`. The two placeholder-detection queries write that label; every other query is read-only.

// ## Prerequisites

// - Neo4j 5.x, Cypher 5. The matching queries use negated label expressions (`:!Placeholder`).
// - APOC for the two queries marked "(requires APOC)" — `apoc.text.jaroWinklerDistance`. No other query needs it. No GDS.
// - The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology.
// - The node keys in `ONTOLOGY.json` make every attribute value unique per label, so records sharing a value converge on one node and every anchored lookup is an index seek.
// - `SETUP.md` run post-import: its required statement creates the `ssnFuzzyIndex` fulltext index that the two near-duplicate SSN queries depend on, and its two recommended statements apply the placeholder flags every matching query excludes.
// - `:Placeholder` is a label the placeholder-detection queries (or `SETUP.md` statements 2 and 3) add to attribute nodes holding filler values. It does not exist in a freshly imported database, and it is not part of the reference ontology. Until it is applied, the `:Placeholder` exclusions have nothing to exclude and filler values create false matches. Likewise, the optional `SETUP.md` spatial statements write a `Location.coordinates` point property that no query here depends on.
// - Anchors are parameters, never hardcoded IDs. Ask the user which identity or phone number they want, or offer one from the results of **Confidence-Scored Identity Matches**. Do not invent IDs.
// - Run order matters: the two flagging queries first, then matching, then corroboration. The queries below are in that order, so the APOC queries are labelled in place rather than moved.

// ## Adapting these queries

// These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

// 1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
// 2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
// 3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

// ## Placeholder Email Detection

/*
 * @name           Placeholder Email Detection
 * @description    Flags filler email values — the non-null junk a source
 *                 system stores when the real value is unknown, such as
 *                 "none@none.com" — with a :Placeholder label, so they
 *                 cannot act as a shared identifier in any matching query.
 *                 Left alone, one filler value links every unrelated record
 *                 that carries it.
 * @params         None
 * @prerequisites  Writes a label (no data change): confirm the target
 *                 database first. Equivalent to SETUP.md statement 2 — run it
 *                 once, here or there, not both.
 * @returns        One row per flagged Email: flaggedEmail, in order.
 * @usage          Run before any matching query, and again whenever a new
 *                 source system is onboarded. The literal list
 *                 knownPlaceholderEmails and the word-boundary pattern are
 *                 illustrative, not exhaustive: extend both with each source
 *                 system's own filler conventions.
 * @tags           placeholder, data-quality, email, setup
 * @sample         Bundled sample data only: returns 2 rows — none@none.com
 *                 and test@test.com, each shared by two otherwise-unrelated
 *                 identities.
 */
WITH ['none@none.com', 'n/a', 'test@test.com', 'unknown@unknown.com'] AS knownPlaceholderEmails
MATCH (e:Email)
WHERE toLower(e.email) IN knownPlaceholderEmails
   OR e.email =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*'
SET e:Placeholder
RETURN e.email AS flaggedEmail
ORDER BY flaggedEmail;

// ## Placeholder Phone Detection

/*
 * @name           Placeholder Phone Detection
 * @description    Flags filler phone values such as "999-999-9999" with a
 *                 :Placeholder label, so they cannot act as a shared
 *                 identifier in any matching query.
 * @params         None
 * @prerequisites  Writes a label (no data change): confirm the target
 *                 database first. Equivalent to SETUP.md statement 3 — run it
 *                 once, here or there, not both.
 * @returns        One row per flagged Phone: flaggedPhone, in order.
 * @usage          Run before any matching query, alongside Placeholder Email
 *                 Detection. Extend the literal list knownPlaceholderPhones
 *                 per source system. Add an equivalent check for SSN where
 *                 the data holds unmasked values: numbers starting 000, 666
 *                 or 900–999 are never issued.
 * @tags           placeholder, data-quality, phone, setup
 * @sample         Bundled sample data only: returns 1 row — 999-999-9999,
 *                 shared by three otherwise-unrelated identities.
 */
WITH ['999-999-9999', '000-000-0000', '555-555-5555'] AS knownPlaceholderPhones
MATCH (p:Phone)
WHERE p.phoneNumber IN knownPlaceholderPhones
SET p:Placeholder
RETURN p.phoneNumber AS flaggedPhone
ORDER BY flaggedPhone;

// ## Shared Identifier Fan-out (Basic)

/*
 * @name           Shared Identifier Fan-out (Basic)
 * @description    The simplest pattern in this package, and the place to
 *                 start: every pair of identities that converge on the same
 *                 phone, email, SSN, address, date of birth or IP address
 *                 node, with the connecting path. PersonName is left out
 *                 deliberately — a name is a descriptor, not an identifier.
 * @params         None
 * @prerequisites  Neo4j 5.x for the :!Placeholder negated label expression.
 *                 Placeholder flags applied first; until then the exclusion
 *                 has nothing to exclude.
 * @returns        One row per identity pair and shared attribute node:
 *                 identity1 and identity2 (identityId, identity1 the lower),
 *                 sharedSignal (the relationship type), shared (the
 *                 attribute node) and path, which renders as a graph in
 *                 Browser. A pair sharing several attributes appears once
 *                 per attribute.
 * @usage          The literal LIMIT 200 keeps the result browsable; on a
 *                 real population this returns far more, so filter to one
 *                 identity or attribute value under investigation rather
 *                 than raising it. Relationship types are filtered inside
 *                 the pattern so the planner never expands the wrong ones;
 *                 widen the type list if the data adds attribute types. No
 *                 type(r1) = type(r2) check is needed while each attribute
 *                 label receives only one relationship type; reintroduce it
 *                 if that stops being true.
 * @tags           matching, fan-out, shared-identifier, visualisation
 * @sample         Bundled sample data only: returns 39 rows across 17
 *                 identity pairs with the placeholder flags applied; 44 rows
 *                 across 22 pairs without them.
 */
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

// ## Confidence-Scored Identity Matches

/*
 * @name           Confidence-Scored Identity Matches
 * @description    Groups the fan-out by identity pair and ranks pairs by how
 *                 many distinct identifier types they share — a shared phone
 *                 is confidence 1, a shared phone and address confidence 2.
 * @params         None
 * @prerequisites  Neo4j 5.x for the :!Placeholder negated label expression.
 *                 Placeholder flags applied first.
 * @returns        One row per identity pair: identity1, identity2,
 *                 sharedSignals (the distinct relationship types shared) and
 *                 confidence (their count, 1–6), ordered by confidence
 *                 descending.
 * @usage          The right first query for a demo: it separates pairs that
 *                 share several identifier types from pairs that share one.
 *                 confidence is a count, not a probability — a triage
 *                 ranking, not a calibrated likelihood. Treat one shared
 *                 attribute, especially an address alone, as a weak lead.
 *                 Run it before and after the placeholder flags to show the
 *                 false positives filler values create. The literal LIMIT 50
 *                 caps the list. Offers anchors for Match Cluster as a Graph.
 * @tags           matching, confidence, ranking, triage
 * @sample         Bundled sample data only: returns 17 rows — 1 at
 *                 confidence 5 (ID-1001 / ID-1003), 3 at 4, 1 at 3, 7 at 2
 *                 and 5 at 1.
 */
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

// ## Match Cluster as a Graph

/*
 * @name           Match Cluster as a Graph
 * @description    The full match cluster around one identity as paths: the
 *                 seed, every attribute node it shares, and every other
 *                 identity on the far side. The confidence query answers
 *                 "which pairs?"; this answers "what does one cluster look
 *                 like?".
 * @params         identityId - Identity.identityId of the seed record. Ask
 *                     the user, or offer one from Confidence-Scored Identity
 *                     Matches.
 * @prerequisites  Neo4j 5.x for the :!Placeholder negated label expression.
 *                 Placeholder flags applied first.
 * @returns        Paths seed Identity → shared attribute ← matching
 *                 Identity, one per shared attribute and matching identity,
 *                 for Browser to draw as one cluster.
 * @usage          Visual, not tabular — the view to put on screen in a
 *                 demo. An identity with no shared attribute returns
 *                 nothing.
 * @tags           visualisation, cluster, matching
 * @sample         Bundled sample data only: $identityId = 'ID-1001' returns
 *                 8 paths — 5 shared attributes linking it to ID-1003 and 3
 *                 to ID-1002, the Robert A***n records across CRM, MobileApp
 *                 and CallCenter.
 */
MATCH path = (seed:Identity {identityId: $identityId})
             -[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
             (shared:!Placeholder)
             <-[:HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]-
             (match:Identity)
WHERE match <> seed
RETURN path;

// ## Implausible Address Detection

/*
 * @name           Implausible Address Detection
 * @description    The "flag junk before matching on it" idea applied to
 *                 addresses: surfaces every address the geocoding step could
 *                 not resolve. It flags by absence — an Address with no
 *                 GEOCODED_TO relationship — rather than by trying to
 *                 enumerate every way an address can be malformed.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per identity and unresolved address: identity,
 *                 address, city, state and zipcode, ordered by zipcode.
 * @usage          Read-only. Run it before the two location queries: an
 *                 unresolved address has no Location, so it is silently
 *                 absent from both. Re-run whenever a new source system
 *                 brings new failure modes.
 * @tags           data-quality, address, geocoding
 * @sample         Bundled sample data only: returns 3 rows — ID-8105 (zip
 *                 00000), ID-8106 (zip 99999) and ID-8107 (Seattle zip 98101
 *                 on an Austin address).
 */
MATCH (i:Identity)-[:HAS_ADDRESS]->(a:Address)
WHERE NOT (a)-[:GEOCODED_TO]->(:Location)
RETURN i.identityId AS identity,
       a.address AS address,
       a.city AS city,
       a.state AS state,
       a.zipcode AS zipcode
ORDER BY a.zipcode;

// ## Location Match: Same Coordinates, Different Address Text

/*
 * @name           Location Match: Same Coordinates, Different Address Text
 * @description    Finds identities whose address text differs but whose
 *                 addresses resolve to the same Location — "12 Main St" and
 *                 "12 Main Street". Convergence on Location is
 *                 a match signal in the same way convergence on a Phone is;
 *                 here Location is the identifier, not Address.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology. Review
 *                 Implausible Address Detection first.
 * @returns        One row per identity pair and shared Location: identity1,
 *                 address1, identity2, address2 (the street portions),
 *                 latitude, longitude and path.
 * @usage          The a1.address <> a2.address filter is what separates this
 *                 from the fan-out, which already catches identities sharing
 *                 the same Address node. It surfaces only what exact string
 *                 equality misses, so pairs found here may share nothing
 *                 else at all.
 * @tags           matching, location, geocoding, standardisation
 * @sample         Bundled sample data only: returns 2 rows — ID-8101 /
 *                 ID-8102 (215 Congress Ave / 215 Congress Avenue, Austin)
 *                 and ID-8103 / ID-8104 (900 16th St / 900 16th Street,
 *                 Denver).
 */
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

// ## Descriptor Similarity: Near-Miss Name Spelling (requires APOC)

/*
 * @name           Descriptor Similarity: Near-Miss Name Spelling (requires APOC)
 * @description    Corroborates an already-suspected match with a near-miss
 *                 name spelling. PersonName is a descriptor: plenty of
 *                 unrelated people share a name, so a name never establishes
 *                 a match. Only pairs that already share a phone, email, SSN
 *                 or address are scored, never all name pairs.
 * @params         None
 * @prerequisites  APOC (apoc.text.jaroWinklerDistance). Placeholder flags
 *                 applied first.
 * @returns        One row per blocked pair with different names scoring at
 *                 or above the threshold: identity1, name1, identity2, name2
 *                 and nameSimilarity (0–1, 1 identical), ordered by
 *                 nameSimilarity descending.
 * @usage          apoc.text.jaroWinklerDistance returns a distance (0 =
 *                 identical), not a similarity; the query converts with
 *                 1 - distance so the literal threshold 0.80 reads
 *                 naturally. Skipping the conversion does not error — it
 *                 sorts and thresholds backwards. 0.80 is a common starting
 *                 point for Jaro–Winkler name matching; raise it to tighten.
 *                 Jaro–Winkler rewards a shared prefix, so an unblocked scan
 *                 returns mostly coincidental first-name matches and grows
 *                 with population size — keep the blocking match. The
 *                 blocking set leaves out HAS_DOB (a scope choice) and
 *                 HAS_IP (shared infrastructure is weak evidence).
 * @tags           corroboration, descriptor, name, fuzzy, apoc
 * @sample         Bundled sample data only: returns 3 rows — Carlos M***z /
 *                 Carla M***z 0.948, Tyler B***n / Taylor B***n 0.923 and
 *                 David K** / Daniel K** 0.861.
 */
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

// ## Nearby Address (Geographic Distance as Descriptor)

/*
 * @name           Nearby Address (Geographic Distance as Descriptor)
 * @description    Corroborates an already-suspected match with geographic
 *                 proximity. Distance is a descriptor for the same reason a
 *                 name is: plenty of unrelated people live near each other.
 *                 Only pairs already sharing a phone, email or SSN are
 *                 scored; HAS_ADDRESS is deliberately left out of the
 *                 blocking set, since address plausibility is what is being
 *                 corroborated.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology — the built-in
 *                 point.distance(), no plugin. Placeholder flags applied
 *                 first; review Implausible Address Detection first.
 * @returns        One row per blocked pair whose addresses resolve to
 *                 different Locations within the threshold: identity1,
 *                 address1, identity2, address2 and metersApart (rounded
 *                 metres), nearest first.
 * @usage          point.distance() returns metres for geographic points,
 *                 built inline from Location.latitude and longitude; a
 *                 cartesian x/y point would return the units of x and y. The
 *                 literal 500 m threshold is a starting point with no strong
 *                 prior: lower it where addresses are dense, and keep the
 *                 identifier blocking or the query surfaces large numbers of
 *                 coincidentally nearby strangers. If the optional SETUP.md
 *                 statements have materialised Location.coordinates,
 *                 substitute l1.coordinates and l2.coordinates.
 * @tags           corroboration, descriptor, spatial, distance
 * @sample         Bundled sample data only: returns 1 row — ID-4001 /
 *                 ID-4002, about 242 m apart in Austin.
 */
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

// ## Weighted Composite Match Score (requires APOC)

/*
 * @name           Weighted Composite Match Score (requires APOC)
 * @description    Blends identifier confidence with name similarity into one
 *                 illustrative score, for triaging a large candidate list.
 *                 Pairs are blocked on a shared phone, email, SSN or address,
 *                 then scored on every identifier type they share.
 * @params         None
 * @prerequisites  APOC (apoc.text.jaroWinklerDistance). Placeholder flags
 *                 applied first.
 * @returns        One row per blocked pair where both identities carry a
 *                 name: identity1, identity2, sharedSignals,
 *                 identifierConfidence (1–6), nameSimilarity (0–1, two
 *                 decimals) and weightedScore (0–1), highest first.
 * @usage          size(sharedSignals) / 6.0 rescales the identifier count
 *                 into the same 0–1 range as nameSimilarity so the two can
 *                 be weighted and summed. The literal 0.7 / 0.3 weights are
 *                 an illustrative starting point, not tuned values: adjust
 *                 them with domain expertise, or learn them from a dataset
 *                 already known to be deduplicated. Read the middle band —
 *                 pairs held up by a single identifier and a near-miss name
 *                 — as the ambiguous cases a human should review. The
 *                 literal LIMIT 50 caps the list.
 * @tags           scoring, triage, composite, apoc
 * @sample         Bundled sample data only: returns 15 rows from 0.883
 *                 (ID-1001 / ID-1003) down to 0.375; the three near-miss-name
 *                 pairs score 0.375–0.401, below every exact-name pair
 *                 (0.533 and up).
 */
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

// ## Near-Duplicate SSN (Synthetic Identity Signal)

/*
 * @name           Near-Duplicate SSN (Synthetic Identity Signal)
 * @description    The synthetic-identity signature: two SSNs one edit apart,
 *                 held by identities that also share a genuine contact
 *                 identifier. A fraudster reuses a victim's contact details
 *                 so the application looks legitimate, but alters one digit
 *                 of the SSN so it never collides under exact-match
 *                 deduplication — which the fan-out and confidence queries
 *                 therefore cannot see.
 * @params         None
 * @prerequisites  The ssnFuzzyIndex fulltext index with the 'keyword'
 *                 analyzer (SETUP.md statement 1) — the query fails without
 *                 it. Placeholder flags applied first.
 * @returns        One row per near-duplicate SSN pair and corroborating
 *                 attribute: identity1, ssn1, identity2, ssn2 (ssn1 the
 *                 lower), score (the Lucene relevance score) and
 *                 corroboratingSignal (the shared relationship type).
 * @usage          The literal ~1 fuzzy operator allows one edit; ~2 widens
 *                 it, and Lucene caps it at 2. The - in each SSN is escaped
 *                 before it reaches the Lucene parser, where it is reserved.
 *                 The fuzzy lookup is cheap; the corroboration match is what
 *                 removes noise. SSNs masked to their last four digits have
 *                 only 10,000 possible values, so coincidental one-edit pairs
 *                 grow quickly with population size — never drop the
 *                 corroboration. A near-duplicate can also be an honest
 *                 typo: treat a hit as a lead for review.
 * @tags           synthetic-identity, fraud, fuzzy, ssn, fulltext
 * @sample         Bundled sample data only: returns 3 rows — XXX-XX-4508 /
 *                 XXX-XX-4598 (ID-7002 / ID-7001), XXX-XX-4821 / XXX-XX-4831
 *                 (ID-4001 / ID-4002) and XXX-XX-8017 / XXX-XX-8517 (ID-7004
 *                 / ID-7003), each corroborated by HAS_PHONE.
 */
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

// ## Near-Duplicate SSN as a Graph

/*
 * @name           Near-Duplicate SSN as a Graph
 * @description    The same synthetic-identity detection returned as paths:
 *                 the two identities, their near-duplicate SSNs, and the
 *                 shared contact attribute that corroborates the link.
 * @params         None
 * @prerequisites  As Near-Duplicate SSN (Synthetic Identity Signal): the
 *                 ssnFuzzyIndex fulltext index and the placeholder flags.
 * @returns        One row per near-duplicate SSN pair and corroborating
 *                 attribute: corroborationPath, ssnPath1 and ssnPath2, which
 *                 Browser merges into one picture per row.
 * @usage          Visual counterpart of the tabular query — the view for a
 *                 demo. Tuning and caveats are the same.
 * @tags           synthetic-identity, fraud, visualisation, ssn, fulltext
 * @sample         Bundled sample data only: returns 3 rows, one per pair
 *                 found by the tabular query, each corroborated by a shared
 *                 Phone.
 */
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

// ## Cross-Channel Profile Assembly

/*
 * @name           Cross-Channel Profile Assembly
 * @description    The operational query that follows matching: given one
 *                 known phone number, pulls every Identity that carries it
 *                 and assembles each record's attributes side by side across
 *                 source systems.
 * @params         phoneNumber - Phone.phoneNumber of the known identifier,
 *                     in the stored format. Ask the user, or take one from a
 *                     cluster that has passed review.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per identity carrying the phone: identity,
 *                 sourceSystem, name, email, ssn, address, dob and ip,
 *                 ordered by sourceSystem. A missing attribute returns null
 *                 rather than dropping the row.
 * @usage          Assemble a profile only for clusters that have passed a
 *                 confidence threshold and review — presenting an unreviewed
 *                 low-confidence merge as one person is the failure to avoid.
 *                 The nulls are the point: no single record is complete.
 * @tags           profile, assembly, cross-channel, operational
 * @sample         Bundled sample data only: $phoneNumber = '555-201-8823'
 *                 returns 3 rows — ID-1001 (CRM), ID-1003 (CallCenter) and
 *                 ID-1002 (MobileApp); ID-1002 has no SSN, address or DOB,
 *                 and ID-1003 no email.
 */
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

// ## Cross-Channel Profile as a Graph

/*
 * @name           Cross-Channel Profile as a Graph
 * @description    The assembled profile as paths: every record carrying the
 *                 phone number and every attribute each one holds, drawn as
 *                 one connected picture around the shared identifier.
 * @params         phoneNumber - Phone.phoneNumber of the known identifier,
 *                     in the stored format.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths Identity → attribute, one per attribute of each
 *                 identity carrying the phone, for Browser to draw.
 * @usage          Visual counterpart of Cross-Channel Profile Assembly; the
 *                 same review caveat applies. Shared attribute nodes are
 *                 drawn once, so convergence is visible at a glance.
 * @tags           profile, assembly, cross-channel, visualisation
 * @sample         Bundled sample data only: $phoneNumber = '555-201-8823'
 *                 returns 17 paths — 7 from ID-1001, 4 from ID-1002 and 6
 *                 from ID-1003.
 */
MATCH (:Phone {phoneNumber: $phoneNumber})<-[:HAS_PHONE]-(i:Identity)
MATCH path = (i)-[:HAS_NAME|HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->
             (attribute)
RETURN path;

// ## Node-key constraints

// Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

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
