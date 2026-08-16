# Implementation Guidance

## Operationalising the pattern

1. Confirm the source schema and map each system's record to `Identity`, tagging `sourceSystem` per feed.
2. Confirm which attribute fields each source system actually captures. Missing attributes are expected, not an error.
3. Decide on a masking and normalisation policy for sensitive identifiers — SSN, phone, DOB — before import, and keep it consistent with the sample data so demos and real data behave the same way. For any field where matching only needs equality rather than string similarity, consider the `DOB`/`dateHash` pattern: hash the precise value instead of masking it, so only a coarser display value needs to be stored in readable form at all.
4. Standardise formats before matching. Strip whitespace, lowercase emails, normalise phone country and area codes consistently. Validate where possible — no US area code in the 100–199 range, SSNs never start `000`, `666`, or `900`–`999` — and exclude invalid values from candidate matching rather than silently matching on them.
5. Catalogue each source system's placeholder conventions and run `Placeholder & Invalid Identifier Detection` before any matching query. A one-time setup cost that prevents an entire class of false positives.
6. Start with `Shared Identifier Fan-out`, then move to `Confidence-Scored Identity Matches` once the basic pattern is validated.
7. Layer in `Near-Duplicate SSN` only after exact-match resolution is trusted. Fuzzy matching produces more false positives and needs a higher review bar.
8. Never run fuzzy or descriptor scoring as a blind population-wide scan. Always block on a real shared identifier first. This isn't optional at real scale: an unblocked scan's false-positive rate grows with population size, while a blocked scan's candidate set grows only with the number of genuine near-matches.
9. Create constraints and indexes for every attribute node's key property — **required**, not optional, once the graph reaches meaningful size. Without a backing index, `MERGE` on an attribute value label-scans every existing node of that type to check for a duplicate; at thousands of nodes that turns a fast load into a slow one. Create them before loading data, not after.

The sample-data Import flow creates the nine key constraints itself from `GRAPH_MODEL.json` — never recreate them on an imported database. The fulltext index is not created by Import; it is the required statement of `SETUP.md` and `Near-Duplicate SSN` fails without it. Constraints for non-Import loads are at the end of `QUERIES.md`.

## Loading data

Prefer the bundled sample-data Import flow. Every CSV under `sample-data/` resolves from `GRAPH_MODEL.json`, so the assistant can preview the model and load it directly.

This package deliberately ships no write-based data seed. An earlier version included a self-contained `demo-seed.cypher` that recreated all 500 profiles via `UNWIND` over embedded row lists; at roughly 3,600 lines and 250KB it exceeded the format's 50,000-character limit for a single supporting file. If you need a Cypher-only path — a locked-down environment with no import access, for instance — generate the seed from the CSVs and keep it outside the use-case folder, or seed a smaller subset. Whichever route you take, create the constraints first and load via batched `UNWIND` statements rather than one `MERGE` per row.

## Geocoding in a real deployment

Populate `Location` from an actual geocoding provider. The sample data uses jittered real-city coordinates specifically so the package needs no external API.

Whatever provider you use, keep the same shape. `Address` stays keyed on the raw string so source-system detail like a suite number isn't lost to normalisation, and `Location` carries only what the geocoder resolved to, linked via `GEOCODED_TO`. An address the provider can't resolve should get no `GEOCODED_TO` relationship at all — that absence is what `Implausible Address Detection` looks for, rather than trying to enumerate every way an address can be malformed.

`Nearby Address` constructs its points inline from `latitude` and `longitude`, so it runs on imported data with no extra step. For radius or bounding-box queries at scale, materialise a `coordinates` point property and add a point index; the optional section of `SETUP.md` has both statements, since they write to loaded data.

## Property values vs. graph topology

Most of the matching power in this model comes from _topology_ — whether two `Identity` nodes converge on the same attribute node — not from attribute values being human-readable.

`Phone`, `Email`, `SSN` (for exact matching), `Address`, `IPAddress`, and `DOB` are only ever compared with equality: `MERGE` on a key, `=` in a `WHERE` clause, pattern matching. Equality works identically whether the key is plaintext or a deterministic encrypted or tokenised value, since the same input always produces the same output. Two records with the same real-world phone number still converge on the same `Phone` node even if what's stored is `HMAC(phoneNumber)`. `DOB.dateHash` is this package's worked example: the value driving matching is a keyed hash, and the actual birthdate never reaches the graph in readable form.

Three fields are exceptions, because they're compared by _content_:

- `PersonName.fullName` — `apoc.text.jaroWinklerDistance` computes character-level similarity. A hash or token has no meaningful distance to a similar-but-different name: a one-character edit produces a completely different hash by design, and the avalanche effect that makes hashing secure is exactly what breaks fuzzy matching.
- `SSN.ssn` — the fulltext index's Lucene fuzzy operator needs edit-distance locality in the stored string, for the same reason. A masked-but-legible value, or format-preserving encryption, both work; a plain hash doesn't.
- `Location.latitude` / `longitude` — `point.distance()` needs real numeric coordinates to compute a meaningful distance.

Everything else can be tokenised without losing matching power, which matters for any deployment where Neo4j shouldn't be a system of record for sensitive values. If you go that route for a field beyond `DOB`, use a keyed hash for any field with limited enough entropy that all possible values could be enumerated and hash-compared. See `caveats.md`.

## Beyond this starter pattern: Graph Data Science

Everything above is deliberately achievable in plain Cypher and APOC, so it works on any Neo4j deployment. At production scale, "A Graph Entity Resolution Playbook" (Nathan Smith, NODES 2024) recommends layering in Graph Data Science:

- **Weakly Connected Components** on shared-identifier relationships, to block candidate pairs before any expensive comparison. If two records share no identifiers at all, there's no reason to compare them.
- **Node similarity** (Jaccard, Overlap, Cosine) over each identity's set of shared neighbours, as a more nuanced alternative to the simple confidence count used here.
- **FastRP + filtered K-Nearest-Neighbors**, which embeds each node's neighbourhood into a vector and finds approximate nearest neighbours — much faster than node similarity at large scale.
- **Recording resolved results back into the graph**, via one of three approaches: run WCC over high-confidence `IS_SIMILAR`-style relationships and group each component into an `EntityGroup` node; use `apoc.refactor.mergeNodes()` to merge duplicates directly; or send matches back to the source system for human-in-the-loop merge and reingest the cleaned data.

Recommend this path once a user has outgrown the starter queries. GDS is a separate library and deployment consideration, so don't suggest it as step one.

## Beyond this starter pattern: name decomposition

The starter model treats `PersonName.fullName` as one opaque string, scored only as a whole. A common refinement: keep `fullName` as the node key so the rest of the model doesn't change, but carry `firstName`, `lastName`, and optionally `middleName` and `suffix` as separate properties on that node, populated from the source system's already-structured name fields rather than parsed out of a single string. That unlocks scoring first and last name independently, which surfaces two patterns a single full-name score can't distinguish:

- **Same last name, different first name** — possible family members, household or account-family linking, not necessarily the same person.
- **Same first name, different last name** — possible name change through marriage or divorce, worth lower confidence than an exact identifier but higher than a coincidental stranger.

`firstName` and `lastName` are already loaded in the sample data specifically so the properties are there to build against, but no template scores them, and that's deliberate. Building the family-link query against masked sample data doesn't work: masked surnames collapse to 143 distinct patterns across 500 profiles, so 1,267 pairs of unrelated people share an exact masked surname by chance and 645 share an exact first name. A blocking query built on either would be mostly noise — the same problem `DOB` had before it was rekeyed.

This technique needs real, unmasked or much more lightly masked surnames to carry enough entropy, which is exactly the trade this package's masking convention exists to avoid. Recommend building the scoring query once a user has real data loaded.
