# Query Patterns

Runnable Cypher is in `QUERIES.md`. This file explains which to reach for and why each is shaped the way it is.

## Recommended running order

| Template                                     | Role                                                                                                       |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `Placeholder & Invalid Identifier Detection` | Run first, always. Flags filler values with `:Placeholder` so they can't create false-positive matches.    |
| `Shared Identifier Fan-out (Basic)`          | Every pair sharing any single strong attribute. The simplest pattern here — start here.                    |
| `Confidence-Scored Identity Matches`         | Same pairs, grouped and ranked by _how many_ distinct attribute types they share.                          |
| `Match Cluster as a Graph`                   | One cluster as paths, for a visual demo rather than a table.                                               |
| `Implausible Address Detection`              | Flags addresses geocoding couldn't resolve, by absence of `GEOCODED_TO`. Run before both location queries. |
| `Location Match`                             | Two different address strings that geocode to the same place.                                              |
| `Descriptor Similarity`                      | Fuzzy name matching as corroboration once identifier candidates exist.                                     |
| `Nearby Address`                             | Geographic proximity as a second corroboration signal.                                                     |
| `Weighted Composite Match Score`             | Blends identifier confidence with descriptor similarity into one ranked score.                             |
| `Near-Duplicate SSN`                         | Fuzzy SSN match via fulltext index, for deliberately altered identifiers.                                  |
| `Cross-Channel Profile Assembly`             | The operational query: assemble a full profile from one known identifier.                                  |

`Confidence-Scored Identity Matches` is the right default first query for a demo. It immediately separates strong matches (3+ shared attributes) from weak ones (a single shared address) with no extra explanation.

## Corroboration is not optional

`Descriptor Similarity`, `Weighted Composite Match Score`, `Nearby Address`, and `Near-Duplicate SSN` all require corroboration by a real identifier — phone, email, SSN, or address — before they trust a fuzzy or descriptor-based signal. None of them run as blind population-wide scans.

This isn't only a performance choice. Against the bundled 500 profiles:

- An unblocked fuzzy name scan at the same 0.80 threshold returns 2,264 pairs. Blocked, it returns 3.
- An unblocked SSN edit-distance scan returns 244 coincidental value pairs. Blocked, it returns 3.

Both numbers grow with population size, because masked identifiers and common names have limited entropy, while a blocked scan's candidate set grows only with the number of genuine near-matches. Blocking by a real identifier first and scoring descriptors as corroboration is the fix, and it matches the source deck's methodology: block via shared identifiers, then score candidates, never the reverse.

`Nearby Address` additionally excludes `HAS_ADDRESS` from its own blocking set, since address plausibility is exactly what it's corroborating.

## Why `HAS_DOB` and `HAS_IP` aren't blocking signals

Neither counts as a blocking signal for the corroboration queries.

For `DOB` this is a scope choice rather than an entropy necessity. Because `DOB` is keyed on `dateHash` — the full unmasked date, hashed — a shared `DOB` node means two identities share an exact birthdate: 408 distinct values across the 416 sample identities with a birthdate, versus 56 when the node was keyed on year alone. That's real signal at this scale. It's left out to keep the corroboration queries anchored to identifiers a source system captures directly, rather than a derived value. A real deployment with `dateHash` in place could reasonably add `HAS_DOB` to the blocking set.

`HAS_IP` stays excluded on merit: shared network infrastructure — a household router, a corporate NAT — is a much weaker same-person signal than a shared birthdate.

## Query construction notes

**Filter relationship types inside the pattern.** `Shared Identifier Fan-out` and `Confidence-Scored Identity Matches` use `[r1:HAS_PHONE|HAS_EMAIL|...]` rather than post-filtering with `WHERE type(r1) IN [...]`. This lets the planner use the relationship-type index during traversal instead of expanding every relationship off `Identity` and discarding the wrong ones afterwards. Prefer this style for any new template.

**The `type(r1) = type(r2)` check is safe to omit** given this model: each attribute label only ever receives one relationship type, so the graph structure already guarantees `r1` and `r2` match. If you extend the model so an attribute label can receive more than one relationship type, reintroduce the check.

**Return paths, not just fields.** `Shared Identifier Fan-out`, `Match Cluster as a Graph`, `Location Match`, and the graph variants of `Near-Duplicate SSN` and `Cross-Channel Profile Assembly` all return path values, which render directly as a graph in Neo4j Browser. For a live demo that's a better default than a table of isolated nodes.

**Widen the type lists** if you add new attribute types such as `HAS_DEVICE_ID` to your own model.

## Dependencies

| Template                                      | Requires                                                   |
| --------------------------------------------- | ---------------------------------------------------------- |
| `Descriptor Similarity`, `Weighted Composite` | APOC (`apoc.text.jaroWinklerDistance`)                     |
| `Near-Duplicate SSN`                          | `ssnFuzzyIndex` fulltext index with the `keyword` analyzer |
| `Nearby Address`                              | Built-in `point.distance()` — no APOC, no plugin           |
| Fan-out, Confidence-Scored, Match Cluster     | Neo4j 5.x for the `:!Placeholder` negated label expression |

Without the `keyword` analyzer, the default analyzer tokenizes on the hyphens and fuzzy SSN matching stops working across the whole value — it degrades silently rather than failing. The required statement of `SETUP.md` creates the index correctly.

Run `Placeholder & Invalid Identifier Detection` and `Implausible Address Detection` before any matching query, not just once at setup. New placeholder conventions and geocoding failure modes arrive with every new source system.
