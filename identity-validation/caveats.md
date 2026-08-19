# Caveats

## Interpreting matches

- Shared attributes have legitimate explanations. Households share addresses, family members share phone plans, coworkers share IP ranges on corporate networks.
- A single shared attribute is a weak signal. Treat it as a lead, not a match.
- Near-duplicate matching can flag genuine data-entry typos as false positives. Cross-reference with at least one other shared signal before treating it as fraud.
- Treat all matches as investigative leads for human or downstream-system review, never automatic merges.

## Masking trades precision for disclosure risk

Masking strategy affects match quality directly. Masking too aggressively — showing only 2 SSN digits — increases false-positive collisions between unrelated people. Masking too little risks exposing real PII in a demo or a screenshot.

This isn't theoretical. Building the 500-profile sample data surfaced it three times over:

- Masked SSN, with 4 visible digits and therefore 10,000 possible values, produces **244 coincidental edit-distance-1 pairs** across 500 unrelated people.
- Unrestricted name-similarity scoring produces **2,264 coincidental hits** at a 0.80 threshold.
- Masked surnames collapse to only **143 distinct patterns**, so **1,267 pairs** of unrelated people share an exact masked surname by chance, and **645 pairs** share an exact first name.

The fix used throughout this package is corroboration — require a real shared identifier before trusting a fuzzy or descriptor signal — not tighter masking. Tighter masking simply trades this problem for the PII-exposure problem masking exists to solve.

`DOB` needed a different fix, because corroboration doesn't help a field that's _supposed_ to establish matches on its own. Keying `DOB` on `dateHash` rather than the masked year-only `dob` cut coincidental same-node pairs from 1,566 to 10. See `graph-model.md`.

A masked key is also a weaker key. Five pairs of unrelated people in the original sample data masked to an identical `fullName`, which — since `fullName` is the `PersonName` node key — would have merged them onto one node whose `firstName` and `lastName` depended on load order. Watch for this whenever masked values are used as keys.

## Hashing low-entropy fields

`DOB.dateHash` is computed with `HMAC(secretKey, fullDate)`, not a plain hash. This matters specifically because a birthdate has very little entropy — roughly 30,000 possible values across a realistic age range — so a plain hash is trivially reversible by anyone who precomputes the hash of every possible date and looks up a match. No cracking required. The secret key is what makes that attack infeasible.

The key embedded in the script that generated this sample data is an obviously-fake demo value, not a real secret. A real deployment needs its own, held outside source control and never reused across deployments.

If you extend this approach to other low-entropy fields — a 4-digit PIN, anything with a small enumerable value space — the same requirement applies. Higher-entropy fields (a full SSN, phone number, email) are reasonably safe with a plain hash, since there's no feasible way to precompute every possible value.

## Fulltext and fuzzy matching

- The `ssnFuzzyIndex` fulltext index must use the `keyword` analyzer, or fuzzy matching silently degrades. The default analyzer tokenizes on hyphens and fuzzes each token independently instead of the whole masked value.
- Lucene's fuzzy operator caps supported edit distance at 2 (`~1` or `~2`). It isn't a general-purpose string-distance function.
- Reserved Lucene characters, including `-`, must be escaped in the query string before it reaches `db.index.fulltext.queryNodes`.

## Jaro-Winkler

`apoc.text.jaroWinklerDistance` returns exactly what its name says — a **distance** (0 = identical, larger = more different) — not a similarity. The mistake is easy to make anyway, since most Jaro-Winkler implementations elsewhere conventionally return a similarity score. Every query in this package converts with `1 - apoc.text.jaroWinklerDistance(...)`.

Using the raw value as if it were a similarity doesn't error. It silently sorts and thresholds backwards. Worth double-checking against the APOC docs, or against a known identical-string test case where the function should return `0`, any time this function appears in a new query.

`apoc.text.jaroWinklerDistance` also favours matching prefixes, which suits Western given-name/surname conventions but may perform worse where the most distinguishing information sits elsewhere in the string — patronymics, some transliterated names.

## Scoring weights

The weighted composite score's 0.7/0.3 split is an illustrative starting point, not a tuned value. The source deck recommends adjusting weights with domain expertise, or training a model to learn them from a dataset you're already confident is deduplicated.

## Normalisation

Attribute nodes deduplicate globally by key, so inconsistent formatting in real source data (`555-201-8823` vs `(555) 201-8823`) causes missed matches until it's normalised on ingest. See `graph-model.md` for which fields this applies to.

The known-placeholder list (`"none@none.com"`, `"n/a"`, and so on) is illustrative, not exhaustive. Every source system invents its own filler conventions, and an unflagged placeholder will silently create false-positive matches. Revisit the list whenever a new source system is onboarded.

## Spatial

- `Location` coordinates in the sample data are not the output of a real geocoder. They are real ZIP-centroid coordinates for the 12 cities in this dataset, jittered a few hundred metres per address, so no external geocoding API is needed. Distances and "same place, different spelling" convergences are directionally realistic, but don't present the coordinates as geocoded output from any specific provider.
- `point.distance()` returns metres directly for geographic (`latitude`/`longitude`) points, so no unit conversion is needed. That only holds for points constructed as geographic, which is the default for `point({latitude, longitude})`. A `point({x, y})` cartesian point returns distance in whatever unit `x` and `y` are in.
- `Nearby Address` is deliberately narrow — 500m, blocked by a real identifier — for this sample data's density. A real deployment's address density will be much higher: tune the threshold down and keep the identifier-blocking requirement, or the query will surface large volumes of coincidentally-nearby strangers.

## Property values vs. topology

Most matching in this model runs on equality, not string content, so most attribute values could be encrypted or tokenised in production with no loss of matching power — the way `DOB.dateHash` already is. The exceptions are the three fields actually compared by content: `PersonName.fullName` (Jaro-Winkler), `SSN.ssn` (Lucene fuzzy edit distance), and `Location` coordinates (`point.distance()`). All three need real, comparable values, not hashes. See "Property values vs. graph topology" in `implementation-guidance.md`.
