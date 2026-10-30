# Regulatory Dependency Mapping — Tests

What each query in `QUERIES.cypher` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j 5.x database. The GDS queries create an in-memory projection; everything else is read-only.
2. Import the three CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints on `Standard.id` and `Section.id`; confirm them with `SHOW CONSTRAINTS`.
3. No `SETUP.md` statements are needed. No query depends on schema the Import flow does not create, and none needs an index to be correct at this size.
4. The four GDS queries need the GDS plugin 2.x. Run the projection query before the PageRank and WCC queries, and the drop query last.
5. Run each query in `QUERIES.cypher` with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second.

## Sample-data profile

Synthetic, generated with `seed=20260909` and a reference date of 2026-09-09; the generator is not part of the package. Standard codes, section identifiers, titles and rule references imitate the shape of published FCA handbook material; none of it is real regulatory text.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Standard` | 3 | All FCA sourcebooks: MIFIDPRU (48 sections), SYSC (49), COBS (40) |
| `Section` | 137 | 26 chapters at depth 1, 81 subsections at depth 2, 30 third-level sections at depth 3 — most branches stop at two. In-force dates (`lastUpdated`) run 2020-05-03 to 2026-07-15, always midnight UTC |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `DEPENDS_ON` `Section` → `Standard` | 26 | One per chapter |
| `DEPENDS_ON` `Section` → `Section` | 111 | Child to parent. Every section carries exactly one `DEPENDS_ON`, to a standard or to a parent, never both |
| `RELATED` `Section` → `Section` | 85 | Citing to cited. 54 sections cite at least one other; 47 are cited at least once |

Citation distribution, by inbound count: 90 sections cited by nothing, 30 cited once, 7 twice, 3 three times, 5 four times, 1 five times, 1 seven times.

**Seeded signals**

- **A — the expensive change.** `MIFIDPRU 4.12` ("K-DTF daily trading flow requirement") has an in-force date of 2026-07-15 and one child, `MIFIDPRU 4.12.1` (2026-06-30). Five sections were seeded to cite it — `MIFIDPRU 4.1`, `MIFIDPRU 9.2`, `MIFIDPRU 7.1`, `SYSC 7.3`, `COBS 11.2` — two of them from other standards; background citation brought the total to seven, the highest in the data. It has no outbound citations at all, so it is unambiguously load-bearing rather than dependent. It is the only substantial recent change, so it is what every change query surfaces.
- **B — the mutual cluster.** The five `SYSC 15A` operational-resilience sections (`SYSC 15A.1`, `SYSC 15A.1.1`, `SYSC 15A.2`, `SYSC 15A.3`, `SYSC 15A.3.1`) cite each other in both directions, twenty edges in all. This is the densest neighbourhood in the citation graph and produces all ten of the mutually-citing pairs in the data.
- **C — cross-standard citations.** Background citation is generated within-standard only, so every cross-standard citation is deliberate: six seeded pairs, three incidental ones, plus three that arrive with signals A and D. Twelve in total, covering all six ordered pairs of the three standards. This is the single most important generator choice in the package — an earlier draft drew background citations uniformly at random, which made two-thirds of all citations cross-standard and rendered the cross-standard query meaningless.
- **D — the citation chain.** `COBS 16A.2` → `COBS 11.4` → `SYSC 7.3` → `MIFIDPRU 4.12`, a three-link inbound chain terminating at the changed section. It exists so the blast-radius bound genuinely changes the answer rather than saturating at one hop.

**Background noise**

- Background citation fires for roughly 30% of subsections; with the seeded signals on top, 41 of the 81 second-level subsections make at least one citation, most of them exactly one. So signal A's citers are not the only inbound edges, and the blast radius picks up sections nobody seeded.
- Chapter and section in-force dates are spread across roughly six years, so the change sweep has a realistic tail rather than a clean break.

**What the sample does not exercise.** Several invariants below hold only because of how this data happens to be shaped. Do not tighten them around properties of the generator:

- **No bound is ever exceeded, so truncation is never demonstrated.** The hierarchy is at most three levels deep and every walk up to a `Standard` is bounded at four hops, so those bounds are never reached. The blast-radius citation bound of three *is* reached exactly — three citers sit at hop three — but nothing lies beyond it. The silent-truncation behaviour the `@usage` notes warn about is real and is not demonstrated anywhere in this data; a curator wanting to see it must add a deeper handbook or a longer citation chain.
- **No section is detached, and none carries both a standard and a parent.** Two behaviours therefore go unexercised. First, the `'(unresolved)'` branch in the change sweep, blast radius, most-cited and prioritisation queries is never taken — and the three queries that walk to a `Standard` with a non-optional `MATCH` (cross-standard citations, PageRank, WCC) would silently *drop* such a section rather than label it, which is equally unexercised. Second, a section carrying both a standard and a parent would emit duplicate rows from the queries that do not aggregate over the standard walk (hierarchy, blast radius, cross-standard citations); the reference ontology's `DEPENDS_ON` descriptions rule this out, but no constraint enforces it.
- **No self-citations, no duplicate citation pairs**, and every rule reference is prefixed by the identifier of the section it points into. No citation is to a section as a whole, so `subsection` never equals the cited section's own identifier.
- **All cycling is confined to the signal-B clique.** Those five sections form a complete directed graph — all twenty edges present — containing 10 two-, 20 three-, 30 four- and 24 five-cycles. There is no directed cycle anywhere else in the citation graph. The blast-radius traversal is therefore exercised against cycling only from a `SYSC 15A` starting section; include one in manual testing, because no other starting point tests that path at all.
- **All three standards come from one regulator.** The reference ontology carries no regulator or jurisdiction property, so nothing is lost, but "cross-standard" here never means "cross-regulator".

**Reference anchors.** Used throughout:

- Standard `MIFIDPRU`.
- Section `MIFIDPRU 4.12` — signal A.
- Section `SYSC 15A.1` — signal B.
- Section `COBS 3.2` — an ordinary section with a single outbound citation (to `COBS 2.2`).

**Editing notes.**

- The expected figures below were computed by re-implementing each query's semantics over the CSVs. They agree with the figures in the previous revision of this file, which was produced the same way.
- PageRank scores depend on the implementation's initialisation, normalisation and convergence settings, so the scores quoted below are indicative only; the ranking is the part to check. The previous revision quoted four-decimal scores from a separate power iteration (for example `SYSC 8.3` 0.8991); a recomputation with damping 0.85, 20 iterations, base score 0.15 and no sink redistribution gives slightly different scores (`SYSC 8.3` 0.8978) and the same ranking.
- Every literal variable-length bound is acknowledged in its query's `@usage`, and every query that can emit `'(unresolved)'` says so in its `@returns`. An earlier draft miscounted the blast-radius query's bounds and omitted the most-cited query's entirely; both were corrected.
- `@params` starting values (`$limit` 20, `$minInboundCitations` 2, `$minCommunitySize` 2) are argued from what each number means, not fitted to this data; the Sensitivity notes below show what the data does at other values. The change-date parameters ship no starting date at all — `@params` tells the reader to use their own review cycle.
- In the migration to the current package format, the "Observed" figures became "Expected", the status-of-oracle section was removed, and the query headings are unchanged.

## Explore a standard's section hierarchy

- **Parameters:** `$standardId = 'MIFIDPRU'`.
- **Invariant:** returns every section belonging to the named standard, exactly once each, with `depth` 1 for chapters, 2 for subsections and 3 for third-level sections. No section of another standard appears. Summed across the three standards the row count equals the `Section` total, because every section attaches to exactly one standard.
- **Expected:** MIFIDPRU 48 rows (9 at depth 1, 28 at 2, 11 at 3); SYSC 49 (9 / 29 / 11); COBS 40 (8 / 24 / 8). Total 137, matching the `Section` count exactly.
- **Sensitivity:** the bound is a literal. At `*1..2` the third-level sections disappear: 37 / 38 / 32 rows, 30 sections lost with nothing in the result saying so. At `*1..8` nothing changes, because the data is three deep. This query is the cheapest way to detect that truncation — compare its row count against `MATCH (s:Section) RETURN count(s)`.

## Cross-references into and out of a section

- **Parameters:** `$sectionId = 'MIFIDPRU 4.12'`.
- **Invariant:** returns all five seeded signal-A citers as `cited by` rows, each carrying a rule reference prefixed with the cited section's own identifier, plus any background citers. `MIFIDPRU 4.12` has no outbound citations, so no `cites` row appears for it. For a section in the signal-B cluster, every cluster neighbour appears twice, once in each direction.
- **Expected:** `MIFIDPRU 4.12`: 7 rows, all `cited by` — `COBS 11.2`, `MIFIDPRU 1.2.1`, `MIFIDPRU 4.1`, `MIFIDPRU 6.2`, `MIFIDPRU 7.1`, `MIFIDPRU 9.2`, `SYSC 7.3`. Two of the seven (`MIFIDPRU 1.2.1`, `MIFIDPRU 6.2`) are background, not seeded. `$sectionId = 'SYSC 15A.1'`: 9 rows — 4 `cites` and 5 `cited by`, the fifth citer being `MIFIDPRU 7.2` from outside the cluster. `$sectionId = 'COBS 3.2'`: 1 row, `cites` `COBS 2.2` — the ordinary case.
- **Sensitivity:** none; the query has no threshold and no bound. A section identifier that does not exist returns zero rows rather than an error, which is indistinguishable from a section with no cross-references. That ambiguity is called out in `@usage` and is worth a curator's judgement: an `OPTIONAL MATCH` variant would separate the two cases at the cost of a messier result shape.

## Sections changed since a date

- **Parameters:** `$changedSince = '2026-06-01'`.
- **Invariant:** returns exactly the signal-A sections at this cutoff and nothing else, newest first, each resolving to its standard. Every row's `inboundCitations` matches the citation count for that section. No row shows `'(unresolved)'`, because no section in this data is detached.
- **Expected:** 2 rows: `MIFIDPRU 4.12` (2026-07-15, 7 inbound citations) and `MIFIDPRU 4.12.1` (2026-06-30, 0 inbound).
- **Sensitivity:** 2 rows at 2026-06-01, 4 at 2026-03-09, 14 at 2025-09-09, 41 at 2024-09-09. The seeded signal is clean only inside roughly a three-month window; past that the background in-force dates take over, which is realistic and deliberately left alone.

## Change blast radius for a section

- **Parameters:** `$sectionId = 'MIFIDPRU 4.12'`.
- **Invariant:** the affected set contains the section and its child as `changed text`, all five seeded citers as `cites changed text`, and the full signal-D chain (`SYSC 7.3` at one hop, `COBS 11.4` at two, `COBS 16A.2` at three). It spans more than one standard. The affected set is a strict superset of the section-plus-descendants set, and every member appears exactly once however many citation paths reach it.
- **Expected:** 15 rows: 2 `changed text` (`MIFIDPRU 4.12`, `MIFIDPRU 4.12.1`) and 13 `cites changed text`, spanning all three standards. By first citation hop: 7 at one hop (`COBS 11.2`, `MIFIDPRU 1.2.1`, `MIFIDPRU 4.1`, `MIFIDPRU 6.2`, `MIFIDPRU 7.1`, `MIFIDPRU 9.2`, `SYSC 7.3`), 3 at two (`COBS 11.4`, `COBS 6.2`, `MIFIDPRU 8.3`), 3 at three (`COBS 16A.2`, `COBS 9A.3`, `MIFIDPRU 9.3`).
- **Sensitivity:** affected-section counts by citation bound: 2 at zero hops (the section and its child alone), 9 at one, 12 at two, 15 at three, and 15 at four and beyond. The neighbourhood closes at three hops, which is where the shipped bound sits — so on this data the bound is exactly sufficient and never truncates. That is a property of a 137-section sample with a deliberately three-link chain, not evidence that three hops is right for a real handbook. The `@usage` note deliberately frames the bound as a trade-off to be tested rather than a safe default, and a curator should confirm the growth curve against a real citation graph before treating three as settled. From `$sectionId = 'SYSC 15A.1'` (the cycling case) the result is 6 rows.

## Most-cited sections by inbound citation count

- **Parameters:** `$limit = 20`.
- **Invariant:** `MIFIDPRU 4.12` ranks first, clear of the field, with zero outbound citations. The signal-B cluster sections occupy much of the rest of the top, each showing both inbound and outbound counts. Sections with no inbound citation are absent rather than returned with a zero.
- **Expected:** 47 sections have at least one inbound citation, so `$limit = 20` truncates the result to 20 rows. Top seven: `MIFIDPRU 4.12` (7 in, 0 out), `SYSC 15A.1` (5 in, 4 out), `SYSC 15A.1.1` (4 in, 6 out), `SYSC 15A.2` (4 in, 6 out), `SYSC 15A.3` (4 in, 4 out), `SYSC 15A.3.1` (4 in, 4 out), `SYSC 8.3` (4 in, 0 out).
- **Sensitivity:** at `$limit = 7` the result is exactly the sections with four or more inbound citations, which is the natural break here; at `$limit = 47` every cited section is returned and raising it further adds nothing. The shipped starting value of 20 is a readability argument, not a fit to this distribution.

## Citations that cross standards

- **Parameters:** none.
- **Invariant:** returns every citation whose two ends resolve to different standards, and only those. All six seeded cross-standard pairs appear. No within-standard citation appears. Every row's rule reference is prefixed by the cited section's identifier.
- **Expected:** 12 rows, covering all six ordered pairs of the three standards: COBS→MIFIDPRU (2), COBS→SYSC (4), MIFIDPRU→COBS (1), MIFIDPRU→SYSC (1), SYSC→COBS (2), SYSC→MIFIDPRU (2). Two of them (`COBS 11.2`→`MIFIDPRU 4.12` and `SYSC 7.3`→`MIFIDPRU 4.12`) are also signal A.
- **Sensitivity:** no threshold to tune. The number that matters is the denominator: 12 of 85 citations cross a standard, about 14%. That ratio is entirely a generator choice — see signal C. An earlier draft that drew background citations uniformly produced roughly 65% cross-standard, at which point the query returns most of the graph and tells you nothing. If anyone regenerates the data, check this ratio before trusting the query.

## Recently changed sections that are heavily cited

- **Parameters:** `$changedSince = '2025-09-09'`, `$minInboundCitations = 2`.
- **Invariant:** `MIFIDPRU 4.12` ranks first and is the only row whose citing standards number more than one. Every row satisfies both conditions independently — recent enough and cited enough — and the result is a subset of what the change sweep returns at the same date.
- **Expected:** 4 rows: `MIFIDPRU 4.12` (2026-07-15, 7 citations, 3 citing standards), `SYSC 15A.3` (2025-10-26, 4 citations, 1 standard), `COBS 11.4` (2026-02-17, 3 citations, 1 standard), `MIFIDPRU 8.1` (2025-12-17, 2 citations, 1 standard).
- **Sensitivity:** row counts by (date, threshold 1 / 2 / 3): 2026-06-01 gives 1 / 1 / 1; 2025-09-09 gives 7 / 4 / 3; 2024-09-09 gives 19 / 9 / 6. The shipped starting threshold of 2 roughly halves the 2025-09-09 result, which is the behaviour the `@params` note describes — but that note argues from what the number means, not from these figures, and holds on any handbook.

## GDS — Project the section cross-reference graph

- **Parameters:** none.
- **Invariant:** projects every `Section` node, including the majority that carry no cross-reference, and only `RELATED` relationships. `nodeCount` equals the `Section` count; `relationshipCount` equals the `RELATED` count.
- **Expected:** `graphName: 'regulatorySections'`, `nodeCount: 137`, `relationshipCount: 85`.
- **Sensitivity:** running it twice without dropping fails on a name conflict, which is why the drop query exists.

## GDS — Rank section influence with PageRank

- **Parameters:** `$limit = 20`.
- **Invariant:** `MIFIDPRU 4.12` ranks first, consistent with its citation count. The ranking must not simply reproduce the inbound-count order: at least one section with few inbound citations ranks above sections with more, because it is cited by heavily-cited text. Sections nothing cites share the floor score and rank last. Ties are expected.
- **Expected:** 20 rows. Top eight, with indicative scores (see the editing notes): `MIFIDPRU 4.12` 1.14 (7 inbound), `SYSC 8.3` 0.90 (4), `SYSC 15A.1` 0.73 (5), `MIFIDPRU 1.2` 0.68 (1 inbound), `SYSC 15A.1.1` 0.67 (4), `SYSC 15A.2` 0.67 (4), `SYSC 15A.3` 0.63 (4), `SYSC 15A.3.1` 0.63 (4). Two rows carry the invariant: `MIFIDPRU 1.2` reaches fourth on a single inbound citation, and `SYSC 8.3` with four outranks `SYSC 15A.1` with five. Those inversions are precisely the PageRank-versus-degree difference the query's `@usage` claims, and if they are absent from a live run the projection has probably picked up the wrong relationship type.
- **Sensitivity:** diff this ranking against the inbound-count query's top 20; identical orderings mean something is wrong.

## GDS — Group cross-referencing sections into communities

- **Parameters:** `$minCommunitySize = 2`.
- **Invariant:** the signal-B `SYSC 15A` sections all fall in one component, as do `MIFIDPRU 4.12` and its citers. At least one component spans more than one standard. Every component returned has two or more members, and the member counts across all components — including the singletons filtered out — sum to the `Section` total.
- **Expected:** connected components are a plain graph fact independent of the algorithm: 72 components, 62 of them singletons. At `$minCommunitySize = 2`, 10 components are returned, sized 49, 6, 4, 4, 2, 2, 2, 2, 2, 2. The largest holds 49 sections, including both signal A and signal B, and spans all three standards.
- **Sensitivity:** 10 components at `$minCommunitySize = 2`, 4 at 3, 4 at 4, 2 at 5, 2 at 6, 1 at 7. Note the shape of this result: a single component of 49 against nine of six or fewer. Twelve cross-standard citations are enough to fuse most of the connected graph into one blob, which is exactly the degenerate case the query's `@usage` warns about — and it is visible here, so this one *is* exercised by the sample. Treat the giant component as a prompt to find the bridging citations, not as a meaningful grouping.

## GDS — Drop the section projection

- **Parameters:** none.
- **Invariant:** removes the named projection; a subsequent projection query then succeeds where it would otherwise fail on a name conflict. Does not change any stored node or relationship, so every non-GDS query returns identical results before and after.
- **Expected:** `graphName: 'regulatorySections'`, `nodeCount: 137`.
- **Sensitivity:** dropping a projection that does not exist raises an error rather than passing silently. That is deliberate, and stated in `@usage`; a curator who would rather it were tolerant can use `gds.graph.drop('regulatorySections', false)`, which returns an empty result instead of raising.
