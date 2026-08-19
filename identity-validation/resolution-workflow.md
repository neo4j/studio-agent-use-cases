# Resolution Workflow

Start broad, then progressively constrain.

1. Flag placeholder and filler values first, so junk data can't masquerade as a shared identifier.
2. Find every pair of identities sharing any single strong attribute. The simplest pattern in this package, and the right place to start.
3. Group by pair and count distinct shared attribute types. That count is the confidence score.
4. Treat 3+ shared attributes as a high-confidence same-person match. Treat 1 shared attribute as a weak signal needing more context — especially address alone, since households legitimately share addresses.
5. Flag addresses the geocoder couldn't resolve, so a missing `Location` doesn't get misread as a non-signal in the next step.
6. Separately, check for `Address` pairs that differ in text but geocode to the same `Location`. The attribute-sharing steps above miss these entirely, since they only catch identical strings.
7. For ambiguous single-signal pairs, pull in descriptor-based corroboration — near-miss name spelling, nearby geographic distance — rather than deciding on one signal alone.
8. Optionally combine identifier confidence and descriptor similarity into one weighted score to triage a large candidate list, treating the weights as a starting point rather than a finished formula.
9. Separately, run near-duplicate matching on SSN, or another fixed-format identifier, to catch deliberately altered values.
10. Cross-reference near-duplicate identifier hits against shared contact identifiers. A near-duplicate SSN _plus_ a reused phone number is a much stronger synthetic-identity signal than either alone.
11. Assemble the full resolved profile only for clusters that pass a confidence threshold, to avoid presenting unreviewed low-confidence merges as fact.

The shape of the result is the point. Against the bundled sample data, `Confidence-Scored Identity Matches` returns 17 pairs out of 124,750 possible pairings — a small, legible result set rather than a wall of noise — with the six seeded multi-channel clusters at the top, the three fraud pairs in an ambiguous middle band, and only two coincidental pairs anywhere in the list. See the Sample data section of `SKILL.md` for the full expected-result table.

Two of those 17 pairs are coincidental `DOB`-only matches. That number is small only because `DOB` is keyed on `dateHash` rather than the masked year: the same 416 people produce 1,566 coincidental pairs when the node is keyed on year alone. `graph-model.md` explains the keying decision; `caveats.md` covers the general principle, which is that every masked field trades match precision for disclosure risk, and the queries have to be designed around whichever trade you made.
