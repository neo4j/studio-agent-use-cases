# Post-Import Setup

Statements to offer right after an import, before any matching query. Three statements: one required, two recommended — plus one clearly optional section, to raise only if the user asks about spatial indexing at scale.

Rules for the agent:

- Present each statement with its purpose **before** running it — the explanation accompanies the approval request, never follows the result.
- Every statement writes (schema or labels), so confirm the target database and connection first.
- If the user declines a statement, tell them which queries are affected (named in each statement's `@usage`) and that you can no longer guarantee those queries will run or return accurate results. Repeat that caveat whenever an affected query comes up later in the conversation.
- Do **not** create node-key constraints here. The Import flow creates them from `ONTOLOGY.json`; recreating them — or `UNIQUE` variants of them — is at best redundant and at worst rejected as conflicting with the existing `KEY` constraints. The constraints are listed at the end of `QUERIES.md` as a reference only.

## 1. Required — fulltext index for fuzzy SSN matching

```cypher
/*
 * @name           SSN fuzzy-match fulltext index
 * @description    Creates the ssnFuzzyIndex fulltext index on SSN.ssn, so
 *                 Lucene's fuzzy operator (~1) measures edit distance across
 *                 the whole SSN value. The 'keyword' analyzer is not
 *                 optional: the default analyzer tokenizes on the hyphens
 *                 and fuzzes each token independently, so fuzzy matching
 *                 silently degrades instead of failing loudly.
 * @usage          Needed by Near-Duplicate SSN (Synthetic Identity Signal)
 *                 and Near-Duplicate SSN as a Graph. If skipped, both fail
 *                 with an error rather than returning weaker results, and
 *                 near-duplicate SSN detection is unavailable.
 */
CREATE FULLTEXT INDEX ssnFuzzyIndex IF NOT EXISTS
FOR (s:SSN) ON EACH [s.ssn]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'keyword' } };
```

## 2. Recommended — flag placeholder emails

```cypher
/*
 * @name           Flag placeholder emails
 * @description    Adds the :Placeholder label to filler email values, so
 *                 they cannot act as a shared identifier in any matching
 *                 query. Writes a label only; no data changes.
 * @params         None
 * @returns        One row per flagged Email: flaggedEmail.
 * @usage          Needed by every matching query — they all exclude
 *                 :Placeholder. If skipped, filler values falsely link
 *                 unrelated identities, and every scored result downstream
 *                 inherits those false positives. Extend the literal list
 *                 knownPlaceholderEmails per source system. The same
 *                 statement appears in QUERIES.md as Placeholder Email
 *                 Detection: run it once, here or there, not both.
 */
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
/*
 * @name           Flag placeholder phones
 * @description    Adds the :Placeholder label to filler phone values, so
 *                 they cannot act as a shared identifier in any matching
 *                 query. Writes a label only; no data changes.
 * @params         None
 * @returns        One row per flagged Phone: flaggedPhone.
 * @usage          Needed by every matching query — they all exclude
 *                 :Placeholder. If skipped, the same failure mode as
 *                 placeholder emails: one filler number falsely links every
 *                 unrelated identity that carries it. Extend the literal
 *                 list knownPlaceholderPhones per source system. The same
 *                 statement appears in QUERIES.md as Placeholder Phone
 *                 Detection: run it once, here or there, not both.
 */
WITH ['999-999-9999', '000-000-0000', '555-555-5555'] AS knownPlaceholderPhones
MATCH (p:Phone)
WHERE p.phoneNumber IN knownPlaceholderPhones
SET p:Placeholder
RETURN p.phoneNumber AS flaggedPhone
ORDER BY flaggedPhone;
```

## Optional — spatial point index (only if asked about scale)

Not needed by any bundled query: `Nearby Address` constructs points inline from `latitude` and `longitude`. Offer these two statements only if the user plans radius or bounding-box queries at scale, and say that the first writes a property to every `Location` node. `Location.coordinates` is query-created — see the Reference ontology section of `SKILL.md`.

```cypher
/*
 * @name           Materialise Location.coordinates
 * @description    Writes a POINT property, coordinates, onto every Location
 *                 from its latitude and longitude, so a point index can
 *                 serve radius and bounding-box queries at scale.
 * @params         None
 * @returns        One row: locationsUpdated, the number of Location nodes
 *                 written.
 * @usage          Optional. Needed by no bundled query; afterwards,
 *                 l1.coordinates and l2.coordinates can replace the inline
 *                 point() construction in Nearby Address. If skipped, no
 *                 bundled query is affected.
 */
MATCH (l:Location)
WHERE l.coordinates IS NULL
SET l.coordinates = point({latitude: l.latitude, longitude: l.longitude})
RETURN count(l) AS locationsUpdated;
```

```cypher
/*
 * @name           Location coordinates point index
 * @description    Creates the locationCoordinatesIndex POINT index on
 *                 Location.coordinates.
 * @usage          Optional. Run only after Materialise Location.coordinates;
 *                 needed by no bundled query. If skipped, no bundled query
 *                 is affected.
 */
CREATE POINT INDEX locationCoordinatesIndex IF NOT EXISTS
FOR (l:Location) ON (l.coordinates);
```
