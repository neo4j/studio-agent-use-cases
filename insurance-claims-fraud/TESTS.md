# Insurance Claims Fraud — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j 5.x database — the import writes the whole sample.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. No `SETUP.md` statements are needed.
4. The Graph Data Science queries need the GDS library on the database. Run them in their listed order: project, then Louvain and PageRank, then drop.
5. Run each query in `QUERIES.md` with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second.

## Sample-data profile

Synthetic data seeded with three overlapping fraud signals — repeat claimants, three outlier medical professionals, and vehicles reused across claims — against a background of ordinary single claims.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Claimant` | 4000 | Every claimant has at least one claim. Names are unique |
| `MedicalProfessional` | 50 | Every professional is attached to at least 93 claims |
| `Claim` | 5000 | `date` 2024-01-01 to 2025-12-31, no blanks. `amountClaimed` 802 to 59652 (median 8943.5) |
| `Vehicle` | 4500 | Every vehicle has an owner and appears in at least one claim |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `HAS_CLAIM` | 5000 | Exactly one per claim. Claims per claimant: 3400 with 1, 500 with 2, 80 with 5, 20 with 10 |
| `TREATED_BY` | 5000 | Exactly one per claim. 3 professionals with 200 claims each; the other 47 have 93 or 94 |
| `OWNS` | 4500 | Exactly one owner per vehicle. Vehicles per claimant: 47 own none, 3630 one, 234 two, 23 three, 34 four, 14 five, 7 six, 5 seven, 4 eight, 2 nine |
| `INVOLVED_IN` | 5000 | Exactly one vehicle per claim. 100 vehicles in 6 claims each; the other 4400 in exactly one |
| `TREATS` | 4896 | Exactly the distinct professional–claimant pairs implied by `HAS_CLAIM` and `TREATED_BY`: no care link without a claim link, and none missing. 91 to 178 claimants per professional |

**Seeded signals.**

- **Outlier medical professionals.** Dr. Ruth Butler (200 claims, total 8135003), Dr. Jason Brown (200, 8001365) and Dr. Eric Robinson (200, 7701383). Every one of their 600 claims has `amountClaimed` between 20000 and 59652. Every other professional has 93–94 claims, totals from 679710 to 848139, and claims between 802 and 14994 — so the two populations do not overlap on any claim amount.
- **Reused vehicles (crash for cash).** 100 vehicles each appear in exactly 6 claims. Those 600 claims are exactly the 600 claims of the three outlier professionals; each vehicle's claims are split across 2 (27 vehicles) or 3 (73 vehicles) of them. Each vehicle's 6 claims are filed by 6 different claimants (98 vehicles) or 5 (2 vehicles), and the vehicle's owner is always one of them — so 500 claims name a vehicle the filer does not own, all on these vehicles. The 100 vehicles belong to 93 owners (7 own two).
- **Repeat claimants.** 600 claimants have more than one claim: 20 with 10, 80 with 5, 500 with 2. Every claim on a reused vehicle is filed by a repeat claimant — 402 of them (all 20 ten-claim claimants, 73 five-claim, 309 two-claim). The other 198 repeat claimants (7 five-claim, 191 two-claim) are background: their claims are ordinary-value and on unshared vehicles.

**Background noise.** 3400 claimants with a single ordinary claim (802–14994) on their own vehicle, spread across the 47 ordinary professionals; 47 claimants own no vehicle; and the 198 repeat claimants above, who repeat but touch no other signal. Repeat claiming alone is therefore not a clean detector of the ring.

**Reference anchors.** Used throughout:

- Professionals: Dr. Ruth Butler, Dr. Jason Brown, Dr. Eric Robinson (seeded); Dr. Christopher Hernandez, the highest-total ordinary professional (94 claims, 848139).
- Vehicle `01LFPWL6TK1VMTNE7`, owned by Julie Garcia, in claims CL-001142, CL-002074, CL-002606, CL-002680, CL-002773 and CL-003178 — filed by six different claimants and attached to all three seeded professionals.
- Ten-claim claimants include Angela Watson, Carl Ward and Andrea Rogers; their claim totals range from 138029 to 271010 across the 20.

**Editing notes.**

- The source page's thresholds (more than 1 claim, or a total above 5000, per professional) suit its four-row demo; at this volume they flag all 50 professionals.
- Medical professionals with unusual patterns was parameterised in the migration (`$minClaims`, `$minTotal`). Its test values, 150 and 3,000,000, are the literals the package shipped before: they were chosen by the original author against this sample (the median professional here has 94 claims and a total of 742256, and the largest ordinary total is 848139), not derived from any general rule. They stay as the `@sample` values because they separate the seeded professionals cleanly; the data-agnostic starting point in `@params` is twice the portfolio's medians, which on this sample is 188 claims and 1484512 and returns the same three.
- The `@params` starting point uses the median rather than a high percentile because the seeded outliers are 3 of 50 professionals (6%). Here a 95th-percentile cut with `percentileDisc` lands on a seeded value (200 claims, 7701383) and misses Dr. Eric Robinson, and a 90th-percentile cut admits two ordinary professionals. That is why the procedure reads the median, which the outliers do not move, and not because the factor of two was tuned: any common multiple of the medians from 1.15 to 10.3 returns exactly the three.
- The legacy Louvain expectation said a "John Doe / Dr. House / VIN-12345" cluster would fall in one community. Those are the source page's demo entities and do not exist in this sample; the expectation has been replaced below.
- The legacy comment on the vehicle-claims graph view said dropping its LIMIT shows "all 100 reused vehicles"; that is a fact about this sample and now lives here.
- Before migration, two description samples in the reference ontology named seeded entities (`Angela Watson`, a ten-claim claimant, and `Dr. Ruth Butler`, a seeded professional). They now use unremarkable rows (`Richard Sanders`, one claim; `Dr. Steven Fisher`, 93 ordinary claims).
- Louvain and PageRank were changed in the migration to bound their output: PageRank now ends `LIMIT $limit`, and Louvain aggregates each community (size and members per label) and returns the largest `$limit`. Before, both streamed one row per projected node (13550 rows).
- GDS results below were computed offline from the CSVs: projection counts exactly; PageRank with GDS defaults (damping 0.85, 20 iterations); Louvain with a standard modularity implementation over six random orderings. GDS's own Louvain will not reproduce those communities, so the Louvain section fixes only what is deterministic and marks the rest as indicative.

## Claimants with multiple claims

- **Parameters:** none.
- **Invariant:** exactly the claimants with two or more `HAS_CLAIM` rows — every seeded repeat claimant (ring and background alike) — and no single-claim claimant. Ordered by numClaims descending.
- **Expected:** 600 rows — 20 claimants with numClaims 10, then 80 with 5, then 500 with 2. Order within each tie is not fixed.

## Claim subgraphs of the most frequent repeat claimants

- **Parameters:** none.
- **Invariant:** paths only from the claimants with the highest claim counts, at most 20 claimants, each with all of their claims.
- **Expected:** 200 paths — the 20 ten-claim claimants, 10 claims each. The cut-off falls between 10 and 5 claims, so the set of claimants is fixed.

## Medical professionals with unusual patterns

- **Parameters:** `$minClaims = 150`, `$minTotal = 3000000`.
- **Invariant:** exactly the three seeded professionals and no ordinary professional.
- **Expected:** 3 rows, ordered by totalAmount — Dr. Ruth Butler 200 / 8135003, Dr. Jason Brown 200 / 8001365, Dr. Eric Robinson 200 / 7701383.
- **Sensitivity:** with `$minTotal` left at 3000000, any `$minClaims` from 94 to 199 returns the same three; with `$minClaims` left at 150, any `$minTotal` of 848139 or more does. The `@params` procedure (twice the medians) gives `$minClaims = 188`, `$minTotal = 1484512` and returns the same three. A 95th-percentile cut with `percentileDisc` (200, 7701383) returns only Dr. Ruth Butler and Dr. Jason Brown; with `percentileCont` (152.3, 4617423.2) all three. At the source page's 1 / 5000, all 50 professionals are returned.

## Medical professionals ranked by total claim value

- **Parameters:** none.
- **Invariant:** the three seeded professionals occupy the top three rows, followed by ordinary professionals in descending total.
- **Expected:** 10 rows — Dr. Ruth Butler 200 / 8135003, Dr. Jason Brown 200 / 8001365, Dr. Eric Robinson 200 / 7701383, Dr. Christopher Hernandez 94 / 848139, Dr. Shirley Collins 94 / 818141, Dr. Keith Roberts 94 / 817706, Dr. Paul Walker 93 / 807524, Dr. Jack Robinson 94 / 798192, Dr. Paul Thomas 94 / 794993, Dr. Jeremy Miller 94 / 788452.

## Potential "crash for cash" scams

- **Parameters:** none.
- **Invariant:** exactly the 100 seeded reused vehicles, and no vehicle with a single claim.
- **Expected:** 100 rows, each claimCount 6. Order among them is not fixed.

## Claim subgraphs of vehicles involved in more than one claim

- **Parameters:** none.
- **Invariant:** every path starts at a seeded reused vehicle, at most 10 vehicles, each with all six of its claims.
- **Expected:** 60 paths — 10 vehicles × 6 claims. All 100 reused vehicles tie at 6, so which 10 appear is not fixed.
- **Sensitivity:** without the LIMIT, 600 paths covering all 100 vehicles.

## Project the fraud-graph

- **Parameters:** none.
- **Invariant:** every node of the four labels is projected, and every `HAS_CLAIM`, `TREATED_BY`, `OWNS` and `INVOLVED_IN` relationship, undirected. `TREATS` is not projected.
- **Expected:** nodeCount 13550 (4000 + 50 + 5000 + 4500); relationshipCount 39000 — 19500 relationships (5000 + 5000 + 4500 + 5000), each counted in both directions. The projected graph is one connected component.
- **Sensitivity:** fails if a projection named `fraud-graph` already exists; drop it first.

## Louvain communities in the fraud-graph

- **Parameters:** `$limit = 10`; requires the projection.
- **Invariant:** at most `$limit` rows, ordered by size descending; on every row, claimants + professionals + claims + vehicles = size. With `$limit` at least the number of communities (for example 1000), sizes sum to 13550 and the label columns to 4000, 50, 5000 and 4500. `communityId` values are arbitrary and differ between runs; compare compositions, never IDs.
- **Expected:** 10 rows. Indicative only — from six offline runs of a standard Louvain, not GDS: 70–73 communities in total. Each of the 50 professionals anchors a community: ordinary ones hold one professional, about 230–260 members, and claims, claimants and vehicles in near-equal numbers (claims per vehicle 1.0–1.07). The communities holding a seeded professional are larger (343–418 members, or 614–641 when two seeded professionals fall into one community) with about twice as many claims as vehicles (2.0–2.4). In every run the largest community held a seeded professional. 20–25 small communities (10–115 members) hold no professional.
- **Sensitivity:** whether two seeded professionals merge into one community changed from run to run (3 of 6 offline runs), so the number of large, high-claims-per-vehicle rows at the top is 2 or 3. That is Louvain's non-determinism, not an import fault.

## PageRank centrality in the fraud-graph

- **Parameters:** `$limit = 20`; requires the projection.
- **Invariant:** `$limit` rows ordered by score descending; the three seeded professionals have the three highest scores, and all 50 professionals rank above every claimant, claim and vehicle.
- **Expected:** 20 rows, all medical professionals. Approximate scores: the three seeded professionals about 43.3–43.5 (Dr. Jason Brown, Dr. Eric Robinson, Dr. Ruth Butler, in that order offline — order among the three may differ in GDS), then 17 ordinary professionals about 27.
- **Sensitivity:** ordinary professionals span about 26.3–27.5, so `$limit = 50` returns every professional and nothing else. From `$limit = 51` the first non-professional appears: a ten-claim claimant (Sarah Chavez, about 4.7). Claims score 0.7–1.05 and vehicles 0.58–1.72.

## Drop the fraud-graph projection

- **Parameters:** none.
- **Invariant:** `fraud-graph` is removed from the GDS graph catalog; afterwards `CALL gds.graph.list()` does not list it.
- **Expected:** 1 row describing `fraud-graph` (graphName `fraud-graph`, nodeCount 13550, relationshipCount 39000).
- **Sensitivity:** run twice, the second call fails because the projection no longer exists.
