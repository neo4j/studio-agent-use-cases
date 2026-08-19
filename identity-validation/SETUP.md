# Post-Import Setup

Statements to offer right after importing `sample-data/`, before any matching query. Three statements: one required, two recommended, plus one clearly optional section that should only be raised if the user asks about spatial indexing at scale.

Rules for the agent:

- Present each statement with its purpose **before** running it — the explanation accompanies the approval request, never follows the result.
- Every statement writes (schema or labels), so confirm the target database and connection first.
- If the user declines a statement, tell them which queries are affected (listed per statement below) and that you can no longer guarantee those queries will run or return accurate results. Repeat that caveat whenever an affected query comes up later in the conversation.
- Do **not** create node-key constraints here. The Import flow creates them from `GRAPH_MODEL.json`; recreating them — or `UNIQUE` variants of them — is at best redundant and at worst rejected as conflicting with the existing `KEY` constraints. Constraints for non-Import loads are documented at the end of `QUERIES.md`.

## 1. Required — fulltext index for fuzzy SSN matching

```cypher
// Purpose: let Lucene's fuzzy operator (~1) measure edit distance across the whole
//   masked SSN value. The 'keyword' analyzer is not optional: the default analyzer
//   tokenizes on the hyphens and fuzzy matching silently degrades instead of
//   failing loudly.
// Needed by: Near-Duplicate SSN — the synthetic-identity signal. That query FAILS
//   without this index.
// If skipped: near-duplicate SSN detection is unavailable; running the query
//   returns an error, not weaker results.
CREATE FULLTEXT INDEX ssnFuzzyIndex IF NOT EXISTS
FOR (s:SSN) ON EACH [s.ssn]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'keyword' } };
```

## 2. Recommended — flag placeholder emails

```cypher
// Purpose: flag filler/placeholder email values with a :Placeholder label so they
//   cannot act as a shared identifier in any matching query.
// Inputs: the knownPlaceholderEmails list below; extend per source system.
// Needed by: every matching query (they all exclude :Placeholder).
// If skipped: placeholder values falsely link unrelated identities — on the sample
//   data, Shared Identifier Fan-out returns 22 pairs instead of 17, and every
//   scored result downstream inherits the 5 false positives.
// Expected: 2 rows against the sample data — "none@none.com" (shared by ID-4002
//   and ID-5001) and "test@test.com" (shared by ID-8004 and ID-8005).
WITH ['none@none.com', 'n/a', 'test@test.com', 'unknown@unknown.com'] AS knownPlaceholderEmails
MATCH (e:Email)
WHERE toLower(e.email) IN knownPlaceholderEmails
   OR e.email =~ '(?i).*\\b(none|n/a|test|unknown)\\b.*'
SET e:Placeholder
RETURN e.email AS flaggedEmail
ORDER BY flaggedEmail;
```

## 3. Recommended — flag placeholder phones

```cypher
// Purpose: flag filler/placeholder phone values with a :Placeholder label.
// Inputs: the knownPlaceholderPhones list below; extend per source system.
// Needed by: every matching query (they all exclude :Placeholder).
// If skipped: same failure mode as placeholder emails — "999-999-9999" alone
//   falsely links three otherwise-unrelated identities (ID-8001/8002/8003).
// Expected: 1 row against the sample data — "999-999-9999".
WITH ['999-999-9999', '000-000-0000', '555-555-5555'] AS knownPlaceholderPhones
MATCH (p:Phone)
WHERE p.phoneNumber IN knownPlaceholderPhones
SET p:Placeholder
RETURN p.phoneNumber AS flaggedPhone
ORDER BY flaggedPhone;
```

These two flagging statements also appear in `QUERIES.md` as reference templates. Run them once — here or there, not both.

## Optional — spatial point index (only if asked about scale)

Not needed for any bundled template: `Nearby Address` constructs points inline from `latitude` and `longitude`. Offer this only if the user plans radius or bounding-box queries at scale, and note it writes a property to every `Location` node.

```cypher
// Purpose: materialise a real point property so a POINT index can serve
//   radius/bounding-box queries at scale.
// Needed by: nothing bundled. After running, substitute l.coordinates for the
//   inline point() construction in Nearby Address.
// If skipped: no effect on any bundled query.
// Expected: 405 Location nodes updated against the bundled sample data.
MATCH (l:Location)
WHERE l.coordinates IS NULL
SET l.coordinates = point({latitude: l.latitude, longitude: l.longitude})
RETURN count(l) AS locationsUpdated;
```

```cypher
// Purpose: index the materialised point property. Run only after the statement above.
CREATE POINT INDEX locationCoordinatesIndex IF NOT EXISTS
FOR (l:Location) ON (l.coordinates);
```
