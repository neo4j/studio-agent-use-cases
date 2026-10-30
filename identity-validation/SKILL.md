---
name: identity-validation
description: Resolve the same person, account, or device across systems and channels using shared and near-duplicate identifiers. Covers cross-channel identity resolution, golden-record/MDM matching, synthetic identity fraud, household linking, and address geocoding with spatial functions.
metadata:
  neo4j-card-title: Identity Validation
  neo4j-card-category: Industry Agnostic
  neo4j-card-description: Resolve one person across systems and channels, and surface near-duplicate identifiers that signal synthetic identity fraud.
---

# Identity Validation

Use this skill for graph-based identity resolution and operational query design: matching the same real-world person or account across source systems, and detecting near-duplicate identifiers that suggest synthetic identity fraud.

Source references:

- <https://neo4j.com/blog/graph-database/what-is-entity-resolution/>
- "A Graph Entity Resolution Playbook" — Nathan Smith, NODES 2024: <https://www.youtube.com/watch?v=MfZR_ZrLSDw>

This package implements a lightweight starter subset of that talk's process (shared-identifier matching, placeholder detection, descriptor-based corroboration, weighted scoring). The talk's GDS techniques (WCC blocking, node similarity, FastRP+KNN, entity merging) are documented as a graduation path in `implementation-guidance.md`, not built into the demo.

This is graph-modelling and query-pattern guidance, not legal, regulatory, or compliance advice. Treat every match as an investigative lead for human review, never an automatic merge.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: the same customer arrives as different records across systems — a CRM row, a mobile signup, a call-centre note — with no single field matching cleanly. A graph turns that from a string-comparison problem into a traversal: each shared phone, email, or address is a node both records point at, so a genuine cluster looks visibly different from a weak, coincidental link — and from a synthetic identity.
- The bundled sample data is synthetic, masked profiles from several source systems, deliberately seeded with the patterns the queries look for: genuine multi-channel clusters, synthetic-identity pairs, placeholder collisions, and addresses that only match once geocoded, against a non-matching background. Identifiers are masked display forms (SSNs show only their last four digits, phones use the reserved 555 area code, IPs come from documentation ranges), and coordinates are jittered city centres rather than real geocoder output.
- What you can help with: explaining the reference ontology and why each attribute is keyed as it is, walking through the query patterns from shared-identifier fan-out to weighted scoring, importing the sample data or mapping their own source systems, showing how synthetic identity fraud differs from a genuine match, outlining the production-scale Graph Data Science path, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Nodes: `Identity {identityId, sourceSystem}` — one raw profile record as one source system captured it, not yet resolved to a person — and the attribute nodes it carries, each keyed on its value: `PersonName {fullName, firstName, lastName}`, `Phone {phoneNumber}`, `Email {email}`, `SSN {ssn}`, `Address {addressId, address, city, state, zipcode}`, `DOB {dateHash, dob}`, `IPAddress {ip}`. `Location {locationId, latitude, longitude}` sits one hop past `Address`.
- Relationships: `(Identity)-[:HAS_NAME|HAS_PHONE|HAS_EMAIL|HAS_SSN|HAS_ADDRESS|HAS_DOB|HAS_IP]->(attribute)`, at most one of each per identity; `(Address)-[:GEOCODED_TO]->(Location)`, at most one per address.
- Convergence is the match signal. Attribute nodes deduplicate on their own key, so two records carrying the same value point at the same node — no extra modelling. A missing attribute is the absence of a relationship, never a null. Convergence is exact equality, so the same value written in two formats forms two nodes and matches nothing.
- Identifiers and descriptors. `Phone`, `Email`, `SSN`, `Address`, `DOB` and `IPAddress` generate candidates. `PersonName` and geographic distance are descriptors — too common to mean anything alone — and only corroborate a pair already blocked by a real identifier. `firstName` and `lastName` are loaded for display and future name decomposition; no query scores them.
- Keying. Import needs a single identifying property, so `Address` and `Location`, whose identities are composite, carry derived keys (`addressId`, `locationId`) built from exactly the values they stand for. `Address` is keyed on the raw street text so a suite or apartment number is not normalised away. `DOB` is keyed on `dateHash`, a keyed hash of the full birthdate, not on the masked year it displays — keying on the year would converge everyone born in the same year. Geocoding has its own node and relationship, so an address that failed to geocode simply has no `GEOCODED_TO`, and that absence is the implausible-address signal.
- Two entities are created by queries rather than loaded, so they are absent from a freshly imported database and absent from `ONTOLOGY.json` by design — neither has source data, and declaring one would leave the import definition unloadable:

  | Entity | On | Shape | Written by | Removed by |
  | ------ | -- | ----- | ---------- | ---------- |
  | `:Placeholder` label | `Email` and `Phone` nodes holding a filler value (extendable to other attribute labels) | A label, no properties | `Placeholder Email Detection` and `Placeholder Phone Detection` in `QUERIES.cypher`, or `SETUP.md` statements 2 and 3 — the same statements | No bundled query. Every matching query excludes nodes carrying it |
  | `coordinates` property | `Location` | `POINT` (WGS-84), built from `latitude` and `longitude` | The optional `SETUP.md` statement `Materialise Location.coordinates`; indexed by `Location coordinates point index` | No bundled query. No bundled query reads it either — `Nearby Address` builds its points inline |

- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.cypher`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus `aliases` and relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data (an alias such as `Social Security number` or `Date of birth` often names the user's equivalent label), and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Source record | `Identity` | One node per record per source system, with a stable key and its source system — never pre-merged, since resolution is the output, not the input |
| Shared identifier | `Phone`, `Email`, `SSN`, `Address`, `DOB`, `IPAddress` | One node per exact, normalised value that every record carrying it points at; a per-record copy of the value breaks every convergence pattern |
| Fuzzy-comparable identifier | `SSN` | A fixed-format string whose content, not just its equality, can be compared by edit distance through a fulltext index |
| Descriptor | `PersonName` | A value too common to generate candidates on its own, reachable from each record and comparable by string similarity |
| Resolved place | `Location` | A node that differently written addresses converge on, with numeric latitude and longitude; an address that failed to resolve has no link to one |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.cypher`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Supporting files

| File | Load when |
| ---- | --------- |
| `implementation-guidance.md` | The user is adapting the package to their own source systems — normalisation, placeholder conventions, masking and hashing policy, real geocoding, tokenising sensitive values — or asks what a production deployment or the Graph Data Science graduation path adds |

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- Right after a sample-data import, offer the statements in `SETUP.md` — 3 statements, 1 required and 2 recommended, plus 2 optional spatial statements to raise only if the user asks about spatial indexing at scale. Explain each before running; if the user declines one, name the affected queries and caveat their results thereafter. Never recreate node-key constraints after Import.
- Neo4j 5.x and Cypher 5 — the matching queries use negated label expressions (`:!Placeholder`). APOC (`apoc.text.jaroWinklerDistance`) only for the two queries marked "(requires APOC)". The two near-duplicate SSN queries need the `ssnFuzzyIndex` fulltext index from `SETUP.md`. `Nearby Address` uses the built-in `point.distance()`. No GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- The thresholds and weights written into the queries, each named in its `@usage`, are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of the `@sample` anchor (for example its `$identityId`) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- Work broad to narrow, in the order of `QUERIES.cypher`: flag placeholders; find every pair sharing a strong identifier; rank pairs by how many identifier types they share; flag addresses that failed to geocode; find addresses that differ in text but resolve to one place; for ambiguous pairs, corroborate with near-miss names and nearby addresses; optionally blend everything into one weighted score; separately, look for near-duplicate SSNs and cross-reference them against shared contact identifiers; and assemble a full profile only for clusters that pass review. Treat three or more shared identifier types as a strong same-person candidate, and a single shared attribute — an address alone especially — as a weak lead.
- Never run fuzzy or descriptor scoring as a population-wide scan. Always block on a real shared identifier first: an unblocked scan's coincidental hits grow with population size, and masked identifiers make them worse.
- Placeholder flagging runs once — `SETUP.md` statements 2 and 3, or the equivalent detection queries in `QUERIES.cypher`, not both — and again whenever a new source system is onboarded. Run the read-only `Implausible Address Detection` before either location query.
- Every result is a ranked candidate, not a confirmed identity. Shared attributes have innocent explanations — households share addresses, family members share phone plans, colleagues share IP ranges — and a near-duplicate SSN can be an honest typo. Confidence is a count of shared identifier types, not a probability.
- When mapping the user's own data, normalise formats before import: convergence is exact equality, and unnormalised values silently miss matches. Never generate unmasked identifiers; a user's own data needs their organisation's real PII policy, not this package's demo masking.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this detects
Tuning options
Validation approach
```
