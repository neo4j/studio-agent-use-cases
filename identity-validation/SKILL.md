---
name: identity-validation
description: Resolve the same person, account, or device across systems and channels using shared and near-duplicate identifiers. Covers cross-channel identity resolution, golden-record/MDM matching, synthetic identity fraud, household linking, and address geocoding with spatial functions.
metadata:
  neo4j-card-title: Identity Validation
  neo4j-card-category: General
  neo4j-card-description: Resolve one person across systems and channels, and surface near-duplicate identifiers that signal synthetic identity fraud.
  neo4j-icon-category: general
---

# Identity Graph

Use this skill for graph-based identity resolution and operational query design: matching the same real-world person or account across source systems, and detecting near-duplicate identifiers that suggest synthetic identity fraud.

Source references:

- <https://neo4j.com/blog/graph-database/what-is-entity-resolution/>
- "A Graph Entity Resolution Playbook" — Nathan Smith, NODES 2024: <https://www.youtube.com/watch?v=MfZR_ZrLSDw>

This package implements a lightweight starter subset of that talk's process (shared-identifier matching, placeholder detection, descriptor-based corroboration, weighted scoring). The talk's GDS techniques (WCC blocking, node similarity, FastRP+KNN, entity merging) are documented as a graduation path in `implementation-guidance.md`, not built into the demo.

This is graph modelling and query-pattern guidance, not legal, regulatory, or compliance advice. Treat every match as an investigative lead for human review, never an automatic merge.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: the same customer arrives as different records across systems — a CRM row, a mobile signup, a call-centre note — with no single field matching cleanly. A graph turns that from a string-comparison problem into a traversal: each shared phone, email, or address is a node both records point at, so a genuine cluster looks visibly different from a weak, coincidental link — and from a synthetic identity.
- The bundled sample data is 500 masked profiles, deliberately seeded so every query returns a meaningful result: six legitimate multi-channel clusters, three synthetic-identity fraud pairs, two address pairs that only match once geocoded, and a realistic non-matching background.
- What you can help with: explaining the model and why each attribute is keyed as it is, walking through the query patterns from shared-identifier fan-out to weighted scoring, importing the sample data or mapping their own source systems, showing how synthetic identity fraud differs from a genuine match, and outlining the production-scale Graph Data Science path.

End with a clear next step, such as asking whether they'd like to explore the model or start importing data.

## Supporting files

| File                         | Use it for                                                  |
| ---------------------------- | ----------------------------------------------------------- |
| `overview.md`                | Identity resolution concepts; identifiers vs descriptors    |
| `graph-model.md`             | Labels, relationships, and why each node is keyed as it is  |
| `resolution-workflow.md`     | The ordered workflow, broad to constrained                  |
| `query-patterns.md`          | Which query to run when, and why each is shaped that way    |
| `QUERIES.md`                 | Runnable Cypher, each with an expected-result comment       |
| `SETUP.md`                   | Post-import setup: 3 statements (1 required, 2 recommended) |
| `implementation-guidance.md` | Adapting to real data; GDS graduation path                  |
| `caveats.md`                 | Limitations, false-positive modes, entropy traps            |

## Key rules

- Sample data is masked, not randomised (`XXX-XX-4821`, `555-201-8823`, `203.0.113.x`). Preserve that convention when editing it; see the Sample data section below. Never add real or fully unmasked identifiers.
- Never run fuzzy or descriptor scoring as a population-wide scan. Always block on a real shared identifier first. Unblocked scans return thousands of coincidental hits against this dataset.
- Placeholder flagging runs as `SETUP.md` steps 2–3 (or the equivalent templates in `QUERIES.md` — once, not both). Run the read-only `Implausible Address Detection` before any location query.
- A user's own data needs their organisation's real PII policy, not this package's demo masking.

## Sample data

500 masked profiles under `sample-data/`, deliberately seeded so every query template returns a meaningful result.

| File               | Rows | Produces               |
| ------------------ | ---- | ---------------------- |
| `identities.csv`   | 500  | 500 `Identity` nodes   |
| `names.csv`        | 500  | 484 `PersonName` nodes |
| `phones.csv`       | 439  | 428 `Phone` nodes      |
| `emails.csv`       | 390  | 386 `Email` nodes      |
| `ssns.csv`         | 367  | 366 `SSN` nodes        |
| `addresses.csv`    | 416  | 410 `Address` nodes    |
| `dobs.csv`         | 416  | 408 `DOB` nodes        |
| `ip_addresses.csv` | 487  | 482 `IPAddress` nodes  |
| `locations.csv`    | 407  | 405 `Location` nodes   |

Every attribute file also carries `identityId`, which supplies the relationship from `Identity`. `locations.csv` is the exception: it carries `addressId` and supplies `GEOCODED_TO` from `Address` rather than from `Identity`.

Every node is keyed on a single property, as the Import flow requires. Seven labels have a natural one — `identityId`, `fullName`, `phoneNumber`, `email`, `ssn`, `dateHash`, `ip`. The two with composite identities carry a derived key instead: `addressId` (in `addresses.csv` and `locations.csv`, of the form `"1210 Foxglove Dr, Austin, TX 78701"`) and `locationId` (in `locations.csv`, of the form `"30.2686,-97.7411"`). Both are derived from exactly the values they stand in for, so dedup is unchanged: 416 address rows produce 410 `Address` nodes, and 407 geocoded addresses produce 405 `Location` nodes. Both contain commas and are therefore CSV-quoted throughout.

### Masked, not randomised

The sample data uses realistic-format but masked identifiers — `XXX-XX-4821` for SSN, `555-201-8823` using the reserved fake area code, `203.0.113.x` reserved documentation IPs — rather than opaque random strings or full plaintext PII. This lets an audience visually confirm exact and near-duplicate matches themselves during a demo, without ever showing anything resembling a real, complete identifier. Preserve this convention if you add or edit sample data. Don't anonymise into random tokens, and don't add full unmasked identifiers.

Two fields are exceptions:

- `Location.latitude` / `longitude` — there's no PII-equivalent to mask in a coordinate pair, so the data uses real ZIP-centroid coordinates for the 12 cities in this dataset, jittered a few hundred metres per address. Distances stay directionally realistic and no external geocoding API is needed to load or demo the package. This is not the output of an actual geocoder run against these addresses; don't present it as one.
- `DOB.dateHash` — the opposite of masking. `DOB` is keyed on a keyed hash of the full birthdate rather than the masked display value, so matching runs on real date precision without the real date ever being stored or shown. If you regenerate this field, keep using an HMAC with a secret key, not a plain hash: a birthdate has too little entropy for a plain hash to protect it. See `caveats.md`.

A masked value carries less entropy than the value it replaces, and that has consequences the queries have to be designed around. `caveats.md` covers each one.

### What's seeded

- **9 hand-curated identities** from the original design, including the three-channel Robert Anderson cluster (CRM, MobileApp, CallCenter).
- **10 more** across four additional multi-channel match clusters, varying which attributes each shares: phone+address+DOB+IP, phone+email, address+DOB, IP+phone.
- **3 synthetic-identity fraud pairs**, each corroborated by a shared phone, a near-duplicate SSN, and a near-miss name spelling.
- **5 identities** across two placeholder collisions (`none@none.com`, `test@test.com`), plus three sharing the placeholder phone `999-999-9999`.
- **4 identities** across two location-only match pairs: same geocoded coordinates, different address text, no other shared identifier.
- **3 identities** with addresses the geocoder couldn't resolve: two invalid zip formats, one zip/city mismatch.
- **~466 non-colliding noise profiles** with realistic capture gaps, roughly 10–30% missing per attribute.

### Expected results

Running the templates in order against this data produces:

| Query                                   | Result                                                      |
| --------------------------------------- | ----------------------------------------------------------- |
| Placeholder detection (email)           | 2 flagged values, 4 identities                              |
| Placeholder detection (phone)           | 1 flagged value, 3 identities                               |
| Shared Identifier Fan-out               | 39 rows across 17 distinct pairs                            |
| Confidence-Scored Matches               | 17 pairs: 5 at confidence 1, 7 at 2, 1 at 3, 3 at 4, 1 at 5 |
| Match Cluster as a Graph (`ID-1001`)    | 8 paths                                                     |
| Implausible Address Detection           | 3 addresses                                                 |
| Location Match                          | 2 pairs                                                     |
| Descriptor Similarity                   | 3 pairs (0.948, 0.923, 0.861)                               |
| Nearby Address                          | 1 pair, 241m apart                                          |
| Weighted Composite                      | 15 rows, 0.375–0.883                                        |
| Near-Duplicate SSN                      | 3 corroborated pairs                                        |
| Cross-Channel Assembly (`555-201-8823`) | 3 rows / 17 paths                                           |

Six legitimate multi-channel clusters rank at the top of both scored queries (confidence 2–5, scores 0.533–0.883). The three synthetic-identity pairs sit distinctly below them (confidence 1, scores 0.375–0.401), flagged only because three corroboration signals agree — and a fourth for one of the three, since David and Daniel Kim also land 241m apart. Two location-only pairs are invisible to every attribute-based query and are found only by `Location Match`. 476 of the 500 identities have no genuine match at all.

The counts above are a property of this dataset's random seed, not a guarantee. If you regenerate or extend the sample data, re-run every template and update both this section and the expected-result comments in `QUERIES.md`.

## Operational Constraints

- Data loads through the bundled sample-data Import flow, which is the only route. Never offer a write-based seed, `LOAD CSV`, or a `CREATE` script instead. Confirm the target database and connection before executing anything.
- Right after a sample-data import, offer the statements in `SETUP.md` — 3 statements, 1 required, 2 recommended, plus a clearly optional spatial section. Explain each statement's purpose when presenting it, before it runs. If the user declines one, state which queries it affects and that their accuracy can no longer be guaranteed, and repeat that caveat when an affected query is used later. Never recreate node-key constraints after Import — `GRAPH_MODEL.json` already created them.
- Requires Neo4j 5.x / Cypher 5. `Shared Identifier Fan-out` and `Confidence-Scored Identity Matches` use negated label expressions (`:!Placeholder`).
- `Descriptor Similarity` and `Weighted Composite Match Score` require APOC (`apoc.text.jaroWinklerDistance`). No other template needs it.
- `Near-Duplicate SSN` requires the `ssnFuzzyIndex` fulltext index with the `keyword` analyzer (the required statement of `SETUP.md`).
- `Nearby Address` uses the built-in `point.distance()`; no plugin needed.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
