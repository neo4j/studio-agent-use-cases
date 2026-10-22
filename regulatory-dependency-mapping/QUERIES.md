# Regulatory Dependency Mapping — Query Guidance

Cypher for the `regulatory-dependency-mapping` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the stored graph; the GDS queries create and drop an in-memory projection only.

## Prerequisites

- Neo4j 5.x, Cypher 5. No APOC.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the
  bundled `sample-data/` CSVs, or the user's own handbook mapped onto the
  reference ontology.
- The node keys in `ONTOLOGY.json` make `Standard.id` and `Section.id` unique,
  so every anchored lookup below is an index seek rather than a label scan.
- Every query outside the **Graph Data Science** section is plain Cypher and
  needs nothing beyond the imported reference ontology. No post-import setup
  is required.
- The queries prefixed **GDS —** need the Graph Data Science plugin (2.x) on
  the target database. GDS is absent on some Aura tiers and many self-managed
  installs; the plain-Cypher queries cover the same ground, with
  *Most-cited sections by inbound citation count* standing in for PageRank as
  a degree-based measure of influence.
- **Traversal depth cannot be parameterised.** Cypher requires a literal bound
  on a variable-length pattern, so there is no `$maxDepth` to pass. A bound of
  N returns the pattern to depth N and silently omits anything deeper: the
  result is not marked as truncated. Each query's `@usage` states its bound.
  Before trusting any of them on an unfamiliar handbook, check how deep it
  actually nests and raise the literal in the Cypher if it nests deeper than
  the bound allows.
- Anchors are parameters, never hardcoded identifiers. Before running an
  anchored query, ask the user which standard or section they mean, or offer
  real identifiers from the hierarchy query. Do not invent identifiers.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Explore a standard's section hierarchy

```cypher
/*
 * @name           Explore a standard's section hierarchy
 * @description    Returns every section beneath a standard, with the depth at
 *                 which it sits, by following DEPENDS_ON from the standard
 *                 down through top-level sections to their child sections.
 * @params         standardId - Identifier of the standard to expand, as the
 *                     regulator publishes it and as Standard.id records it.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per section: the standard, section identifier,
 *                 title, the in-force date of its current text, and its depth
 *                 below the standard.
 * @usage          The orientation query — run it first to see how deep and
 *                 how wide a handbook is before analysing it. The traversal
 *                 is bounded at four hops, a literal in the Cypher: sections
 *                 nested deeper than four levels are omitted with no
 *                 indication, so compare the row count against the number of
 *                 Section nodes in the standard before relying on it. A
 *                 section of the standard that does not appear is either
 *                 nested below the bound or detached from its hierarchy
 *                 altogether — the second is an import or data-quality
 *                 finding, and the two look identical here.
 * @tags           hierarchy, standard, section, orientation
 * @sample         Bundled sample data only: $standardId = 'MIFIDPRU' returns
 *                 48 rows — 9 at depth 1, 28 at depth 2 and 11 at depth 3.
 */
MATCH path = (std:Standard {id: $standardId})<-[:DEPENDS_ON*1..4]-(section:Section)
RETURN std.id             AS standard,
       section.id          AS sectionId,
       section.title       AS title,
       section.lastUpdated AS lastUpdated,
       length(path)        AS depth
ORDER BY depth, sectionId
```

## Cross-references into and out of a section

```cypher
/*
 * @name           Cross-references into and out of a section
 * @description    Returns every section a given section cites and every
 *                 section that cites it, each with the specific rule inside
 *                 the cited section that the reference points at.
 * @params         sectionId - Identifier of the section to examine, as
 *                     Section.id records it.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per cross-reference: direction ('cites' or 'cited
 *                 by'), the section at the other end with its title and
 *                 in-force date, and the rule reference carried on the
 *                 relationship. Two sections that cite each other produce one
 *                 row in each direction.
 * @usage          Run this before assessing a proposed change to a section:
 *                 the 'cited by' rows are the text that silently changes
 *                 meaning when this section moves. Direction is what matters
 *                 — a section with many outbound citations is dependent on
 *                 others, one with many inbound citations is load-bearing,
 *                 and only the second makes a change expensive. One hop only;
 *                 for text reached indirectly use the blast-radius query.
 *                 Returns no rows both when a section has no cross-references
 *                 and when the identifier does not exist, so confirm the
 *                 identifier before concluding a section is unreferenced.
 * @tags           cross-reference, change-assessment, section
 * @sample         Bundled sample data only: $sectionId = 'MIFIDPRU 4.12'
 *                 returns 7 rows, all 'cited by' — COBS 11.2, MIFIDPRU 1.2.1,
 *                 MIFIDPRU 4.1, MIFIDPRU 6.2, MIFIDPRU 7.1, MIFIDPRU 9.2 and
 *                 SYSC 7.3.
 */
MATCH (section:Section {id: $sectionId})-[ref:RELATED]-(related:Section)
RETURN CASE WHEN startNode(ref) = section THEN 'cites' ELSE 'cited by' END
                           AS direction,
       related.id          AS relatedSectionId,
       related.title       AS relatedTitle,
       related.lastUpdated AS relatedLastUpdated,
       ref.subsection      AS ruleReference
ORDER BY direction, relatedSectionId
```

## Sections changed since a date

```cypher
/*
 * @name           Sections changed since a date
 * @description    Returns sections whose current text took effect on or after
 *                 a given date, with the standard they belong to and how many
 *                 other sections cite them.
 * @params         changedSince - Earliest in-force date to include, as an
 *                     ISO 8601 date or zoned-datetime string (YYYY-MM-DD or
 *                     YYYY-MM-DDTHH:MM:SSZ). Set it to the start
 *                     of the regulatory-change review cycle in hand, so the
 *                     result is exactly what has not yet been assessed. Where
 *                     no fixed cycle exists, widen from the date of the last
 *                     assessment until the result stops being reviewable.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per changed section: standard, section identifier
 *                 and title, in-force date, and inbound citation count.
 *                 Newest change first. The standard reads '(unresolved)' where
 *                 the section does not reach one.
 * @usage          The standing regulatory-change sweep, and the entry point to
 *                 the other change queries: this finds what moved, the
 *                 blast-radius query follows one of them outwards. The walk up
 *                 to the standard is bounded at four hops and deliberately
 *                 optional — missing a change is this query's one unacceptable
 *                 failure, so a section nested deeper than the bound, or
 *                 detached from any hierarchy, is still returned, with
 *                 '(unresolved)' in the standard column rather than being
 *                 dropped. Treat those rows as a data-quality finding in their
 *                 own right.
 * @tags           regulatory-change, section, change-sweep
 * @sample         Bundled sample data only: $changedSince = '2026-06-01'
 *                 returns 2 rows — MIFIDPRU 4.12 (2026-07-15, 7 inbound
 *                 citations) and MIFIDPRU 4.12.1 (2026-06-30, 0).
 */
MATCH (section:Section)
WHERE section.lastUpdated >= datetime($changedSince)
OPTIONAL MATCH (section)-[:DEPENDS_ON*1..4]->(std:Standard)
OPTIONAL MATCH (citing:Section)-[:RELATED]->(section)
RETURN coalesce(std.id, '(unresolved)') AS standard,
       section.id          AS sectionId,
       section.title       AS title,
       section.lastUpdated AS lastUpdated,
       count(DISTINCT citing) AS inboundCitations
ORDER BY lastUpdated DESC, sectionId
```

## Change blast radius for a section

```cypher
/*
 * @name           Change blast radius for a section
 * @description    Takes one section and returns everything a change to it
 *                 reaches: the section itself, the subsections beneath it, and
 *                 every section that cites any of those directly or through a
 *                 chain of citations.
 * @params         sectionId - Identifier of the section being changed, as
 *                     Section.id records it.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per affected section: how it was reached ('changed
 *                 text' for the section and its subsections, 'cites changed
 *                 text' for everything downstream), the standard it belongs
 *                 to, its identifier, title and in-force date. The standard
 *                 reads '(unresolved)' where the section does not reach one.
 * @usage          The impact-assessment query, and the reason the reference
 *                 ontology is a graph rather than a table — a citation chain
 *                 three deep is invisible to any per-section review. Three
 *                 literal bounds sit in the Cypher and none can be
 *                 parameterised: three hops down the subsection hierarchy,
 *                 three hops of citation, and four hops up to the standard —
 *                 a section nested deeper than four levels is still
 *                 returned, but shows '(unresolved)' in place of its
 *                 standard.
 *                 The citation bound is the one that changes the answer, and
 *                 it is a genuine trade-off rather than a safe default — each
 *                 extra hop reaches text with a progressively weaker claim to
 *                 being affected, and the result stops being an impact
 *                 assessment once it stops being reviewable. Run it at one hop
 *                 first, then widen, and watch how fast the count grows;
 *                 anything omitted beyond the bound is omitted silently.
 * @tags           impact-analysis, regulatory-change, citation-chain
 * @sample         Bundled sample data only: $sectionId = 'MIFIDPRU 4.12'
 *                 returns 15 rows — 2 'changed text' (MIFIDPRU 4.12 and
 *                 MIFIDPRU 4.12.1) and 13 'cites changed text', spanning
 *                 COBS, MIFIDPRU and SYSC.
 */
MATCH (changed:Section {id: $sectionId})
OPTIONAL MATCH (descendant:Section)-[:DEPENDS_ON*1..3]->(changed)
WITH changed, collect(DISTINCT descendant) AS descendants
WITH [changed] + descendants AS core
UNWIND core AS coreSection
OPTIONAL MATCH (citing:Section)-[:RELATED*1..3]->(coreSection)
WITH core, collect(DISTINCT citing) AS citers
UNWIND core + citers AS affected
WITH core, collect(DISTINCT affected) AS affectedSections
UNWIND affectedSections AS affected
OPTIONAL MATCH (affected)-[:DEPENDS_ON*1..4]->(std:Standard)
RETURN CASE WHEN affected IN core THEN 'changed text'
            ELSE 'cites changed text' END AS reachedVia,
       coalesce(std.id, '(unresolved)') AS standard,
       affected.id          AS sectionId,
       affected.title       AS title,
       affected.lastUpdated AS lastUpdated
ORDER BY reachedVia, standard, sectionId
```

## Most-cited sections by inbound citation count

```cypher
/*
 * @name           Most-cited sections by inbound citation count
 * @description    Ranks sections by how many other sections cite them, with
 *                 their outbound citation count alongside for contrast.
 * @params         limit - Maximum sections to return. Start at 20, roughly a
 *                     screen a reader can take in at once, and raise it only
 *                     once the top of the ranking has been dealt with.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per cited section: standard, identifier, title,
 *                 in-force date, inbound citation count and outbound citation
 *                 count. Most cited first. The standard reads '(unresolved)'
 *                 where the section does not reach one.
 * @usage          The plain-Cypher measure of which text is expensive to
 *                 change, and the one to use when GDS is unavailable. It
 *                 counts direct citations only, so it credits a section cited
 *                 by many peripheral sections the same as one cited by a few
 *                 load-bearing ones; the PageRank query separates those, and
 *                 comparing the two rankings is more informative than either
 *                 alone. Read the two columns together: high inbound with low
 *                 outbound is foundational text that other rules rest on, and
 *                 the most expensive thing in a handbook to amend. Sections
 *                 that nothing cites are absent rather than returned with a
 *                 zero. The walk up to the standard is a literal four hops and
 *                 optional, so a section nested deeper is still ranked but
 *                 shows '(unresolved)' in place of its standard.
 * @tags           centrality, cross-reference, section, change-cost
 * @sample         Bundled sample data only: $limit = 20 returns 20 rows, led
 *                 by MIFIDPRU 4.12 (7 inbound, 0 outbound), then SYSC 15A.1
 *                 (5 inbound, 4 outbound).
 */
MATCH (citing:Section)-[:RELATED]->(cited:Section)
WITH cited, count(DISTINCT citing) AS inboundCitations
OPTIONAL MATCH (cited)-[:DEPENDS_ON*1..4]->(std:Standard)
OPTIONAL MATCH (cited)-[:RELATED]->(outbound:Section)
RETURN coalesce(std.id, '(unresolved)') AS standard,
       cited.id          AS sectionId,
       cited.title       AS title,
       cited.lastUpdated AS lastUpdated,
       inboundCitations,
       count(DISTINCT outbound) AS outboundCitations
ORDER BY inboundCitations DESC, sectionId
LIMIT $limit
```

## Citations that cross standards

```cypher
/*
 * @name           Citations that cross standards
 * @description    Returns every cross-reference whose citing and cited
 *                 sections resolve to different standards, with the rule
 *                 referenced at the far end.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per cross-standard citation: citing standard and
 *                 section, cited standard and section, the rule reference, and
 *                 the in-force date of the cited text. Ordered by the pair of
 *                 standards involved.
 * @usage          Finds where one rulebook leans on another — the dependencies
 *                 a standard-by-standard review process is structurally blind
 *                 to, because each review sees only its own sourcebook. These
 *                 are the citations worth confirming by hand: a change
 *                 programme scoped to one standard will not notice that it has
 *                 moved text another standard relies on. Both walks up to a
 *                 standard are bounded at four literal hops, so a citation
 *                 whose either end nests deeper is omitted silently; on a
 *                 deeply nested handbook raise both bounds together, since
 *                 raising one alone biases the result. Read the direction:
 *                 citing to cited is the direction of dependency, and the
 *                 cited standard is the one whose changes propagate outward.
 * @tags           cross-standard, dependency, overlap, cross-reference
 * @sample         Bundled sample data only: returns 12 rows, covering all six
 *                 ordered pairs of the three standards COBS, MIFIDPRU and
 *                 SYSC.
 */
MATCH (citing:Section)-[ref:RELATED]->(cited:Section)
MATCH (citing)-[:DEPENDS_ON*1..4]->(citingStd:Standard)
MATCH (cited)-[:DEPENDS_ON*1..4]->(citedStd:Standard)
WHERE citingStd <> citedStd
RETURN citingStd.id      AS citingStandard,
       citing.id         AS citingSectionId,
       citedStd.id       AS citedStandard,
       cited.id          AS citedSectionId,
       ref.subsection    AS ruleReference,
       cited.lastUpdated AS citedLastUpdated
ORDER BY citingStandard, citedStandard, citingSectionId
```

## Recently changed sections that are heavily cited

```cypher
/*
 * @name           Recently changed sections that are heavily cited
 * @description    Returns sections whose text took effect on or after a given
 *                 date and which at least a stated number of other sections
 *                 cite, with the standards those citing sections belong to.
 * @params         changedSince - Earliest in-force date to include, as an
 *                     ISO 8601 date or zoned-datetime string (YYYY-MM-DD or
 *                     YYYY-MM-DDTHH:MM:SSZ). Set it to the start
 *                     of the review cycle in hand, as for the change sweep.
 *                 minInboundCitations - Minimum number of sections that must
 *                     cite the changed section. Start at 2: a threshold of 1
 *                     admits any changed section that anything cites at all,
 *                     while 2 is the first value that means more than one part
 *                     of the book leans on this text. Raise it until the list
 *                     is short enough to work through by hand.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per section: standard, identifier, title, in-force
 *                 date, inbound citation count, the number of distinct
 *                 standards citing it, and those standards. Most cited first.
 *                 The standard reads '(unresolved)' where the section does not
 *                 reach one.
 * @usage          The prioritisation query — where change and cost intersect,
 *                 and the shortlist to work through first when a handbook
 *                 update lands. A row whose citing standards include a
 *                 standard other than its own is the strongest signal here:
 *                 the change has already propagated outside the rulebook that
 *                 made it, so scoping the assessment to the amending standard
 *                 will miss it. The walks up to a standard are bounded at four
 *                 literal hops; a citing section nested deeper still counts
 *                 toward the citation total but contributes no standard, so
 *                 the standard count is a floor, not an exact figure.
 * @tags           regulatory-change, prioritisation, centrality, cross-standard
 * @sample         Bundled sample data only: $changedSince = '2025-09-09',
 *                 $minInboundCitations = 2 returns 4 rows — MIFIDPRU 4.12 (7
 *                 citations from 3 standards), SYSC 15A.3 (4), COBS 11.4 (3)
 *                 and MIFIDPRU 8.1 (2).
 */
MATCH (cited:Section)
WHERE cited.lastUpdated >= datetime($changedSince)
MATCH (citing:Section)-[:RELATED]->(cited)
OPTIONAL MATCH (cited)-[:DEPENDS_ON*1..4]->(std:Standard)
OPTIONAL MATCH (citing)-[:DEPENDS_ON*1..4]->(citingStd:Standard)
WITH cited, std,
     count(DISTINCT citing) AS inboundCitations,
     collect(DISTINCT citingStd.id) AS citingStandards
WHERE inboundCitations >= $minInboundCitations
RETURN coalesce(std.id, '(unresolved)') AS standard,
       cited.id          AS sectionId,
       cited.title       AS title,
       cited.lastUpdated AS lastUpdated,
       inboundCitations,
       size(citingStandards) AS citingStandardCount,
       citingStandards
ORDER BY inboundCitations DESC, lastUpdated DESC, sectionId
```

## Graph Data Science (optional)

The four queries below need the **GDS plugin (2.x)** on the target database.
Check with `RETURN gds.version()` before offering them; if that errors, GDS is
not installed and the plain-Cypher queries above cover the same ground.

Run the projection first and drop it when finished. A GDS projection lives in
the graph catalog for the database and user until it is explicitly dropped or
the DBMS restarts — it does **not** go away when the client disconnects, so
leaving one behind holds memory indefinitely. None of the four writes to the
stored graph: scores and community identifiers are returned rather than saved
as properties, which keeps them safe to run against a database the user has
not agreed to modify.

## GDS — Project the section cross-reference graph

```cypher
/*
 * @name           GDS — Project the section cross-reference graph
 * @description    Creates the in-memory GDS projection of Section nodes and
 *                 RELATED relationships that the PageRank and community
 *                 queries below run against.
 * @params         None
 * @prerequisites  GDS plugin 2.x. Fails if a projection of the same name
 *                 already exists in the graph catalog for this database and
 *                 user, which outlives the client session.
 * @returns        The projection name with its node and relationship counts.
 * @usage          Run once before either analytic below, and drop the
 *                 projection afterwards — it is not released on disconnect.
 *                 The projection deliberately excludes the DEPENDS_ON
 *                 hierarchy: including it would let influence flow along
 *                 parent-child structure, which says only that a handbook has
 *                 chapters. Every Section node is projected, including those
 *                 nothing cross-references, so they appear as isolated nodes
 *                 with a floor PageRank score and as single-member
 *                 communities. Check the reported counts against the Section
 *                 and RELATED totals before trusting either analytic.
 * @tags           gds, projection, setup
 * @sample         Bundled sample data only: returns graphName
 *                 'regulatorySections', nodeCount 137, relationshipCount 85.
 */
CALL gds.graph.project('regulatorySections', 'Section', 'RELATED')
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
```

## GDS — Rank section influence with PageRank

```cypher
/*
 * @name           GDS — Rank section influence with PageRank
 * @description    Scores each section by PageRank over the citation graph, so
 *                 that a citation from a heavily-cited section counts for more
 *                 than one from an isolated section, and joins the scores back
 *                 to standards and raw citation counts.
 * @params         limit - Maximum sections to return. Start at 20, roughly a
 *                     screen a reader can take in at once, and raise it only
 *                     once the top of the ranking has been dealt with.
 * @prerequisites  GDS plugin 2.x, and the 'regulatorySections' projection
 *                 created by the projection query above.
 * @returns        One row per section: standard, identifier, title, PageRank
 *                 score rounded to four decimals, and inbound citation count.
 *                 Highest score first.
 * @usage          Use it to decide where regulatory-change effort is best
 *                 spent: a high score means a change here propagates through
 *                 the citation graph rather than staying local. The point of
 *                 running it alongside the inbound-count query is the
 *                 disagreement between them — a section that ranks high here
 *                 but low on raw count is cited by few sections that are
 *                 themselves heavily cited, which raw counting cannot see and
 *                 which is exactly the quietly structural text worth finding.
 *                 Scores are relative within one run and not comparable across
 *                 handbooks or across runs on different data, so read the
 *                 ranking, not the number. Ties are normal and the rounding
 *                 creates more of them. The walk up to the standard is bounded
 *                 at four literal hops: a section nested deeper is scored by
 *                 GDS but omitted from this result.
 * @tags           gds, pagerank, centrality, section, change-cost
 * @sample         Bundled sample data only: $limit = 20 ranks MIFIDPRU 4.12
 *                 first, then SYSC 8.3 (4 inbound) above SYSC 15A.1 (5
 *                 inbound), with MIFIDPRU 1.2 fourth on a single inbound
 *                 citation.
 */
CALL gds.pageRank.stream('regulatorySections')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS section, score
MATCH (section)-[:DEPENDS_ON*1..4]->(std:Standard)
OPTIONAL MATCH (citing:Section)-[:RELATED]->(section)
RETURN std.id          AS standard,
       section.id      AS sectionId,
       section.title    AS title,
       round(score, 4)  AS pageRankScore,
       count(DISTINCT citing) AS inboundCitations
ORDER BY pageRankScore DESC, sectionId
LIMIT $limit
```

## GDS — Group cross-referencing sections into communities

```cypher
/*
 * @name           GDS — Group cross-referencing sections into communities
 * @description    Runs Weakly Connected Components over the citation graph to
 *                 find clusters of sections that reference one another, and
 *                 reports each cluster's size and the standards it spans.
 * @params         minCommunitySize - Smallest cluster to report. Start at 2: a
 *                     component of one is a section with no cross-reference in
 *                     either direction, which says nothing about clustering.
 *                     How many of those a handbook has depends entirely on how
 *                     completely its cross-references were captured. Raise it
 *                     to concentrate on the larger clusters.
 * @prerequisites  GDS plugin 2.x, and the 'regulatorySections' projection
 *                 created by the projection query above.
 * @returns        One row per component: component identifier, member count,
 *                 the number of standards it spans and their identifiers, and
 *                 up to ten member section identifiers. Largest first.
 * @usage          Finds the natural units of regulatory change — clusters that
 *                 have to be assessed together because their text is mutually
 *                 referential. A component spanning more than one standard is
 *                 the finding to pursue: a change in one rulebook propagates
 *                 into another, which is the dependency a per-sourcebook
 *                 review cannot see. Weakly connected components ignore
 *                 citation direction, so a single citation is enough to merge
 *                 two clusters, and one bridging reference can collapse most
 *                 of a handbook into a single component. Treat a very large
 *                 component as a prompt to find the bridging citation rather
 *                 than as one coherent group — and where that happens, prefer
 *                 the PageRank ranking, which degrades more gracefully. The
 *                 walk up to the standard is bounded at four literal hops, so
 *                 a member nested deeper contributes no standard and the
 *                 member count understates the true component size.
 * @tags           gds, wcc, community, cross-reference, section
 * @sample         Bundled sample data only: $minCommunitySize = 2 returns 10
 *                 components sized 49, 6, 4, 4, 2, 2, 2, 2, 2, 2; the
 *                 49-member component spans COBS, MIFIDPRU and SYSC.
 */
CALL gds.wcc.stream('regulatorySections')
YIELD nodeId, componentId
WITH componentId, gds.util.asNode(nodeId) AS section
MATCH (section)-[:DEPENDS_ON*1..4]->(std:Standard)
WITH componentId,
     collect(DISTINCT section.id)  AS sectionIds,
     collect(DISTINCT std.id) AS standardsSpanned
WITH componentId, sectionIds, standardsSpanned, size(sectionIds) AS communitySize
WHERE communitySize >= $minCommunitySize
RETURN componentId,
       communitySize,
       size(standardsSpanned) AS standardCount,
       standardsSpanned,
       sectionIds[0..10] AS sampleSections
ORDER BY communitySize DESC, componentId
```

## GDS — Drop the section projection

```cypher
/*
 * @name           GDS — Drop the section projection
 * @description    Releases the in-memory 'regulatorySections' projection.
 * @params         None
 * @prerequisites  GDS plugin 2.x, and an existing projection of that name.
 * @returns        The dropped projection's name and node count.
 * @usage          Run after finishing with the GDS queries. Leaving a
 *                 projection in place holds memory on the instance and makes
 *                 the projection query fail on its next run with a name
 *                 conflict. Dropping it does not touch the stored graph.
 *                 Dropping a projection that does not exist raises an error
 *                 rather than passing silently, which is deliberate — a
 *                 mistyped projection name should be noticed.
 * @tags           gds, projection, cleanup
 * @sample         Bundled sample data only: returns graphName
 *                 'regulatorySections' and nodeCount 137.
 */
CALL gds.graph.drop('regulatorySections')
YIELD graphName, nodeCount
RETURN graphName, nodeCount
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
CREATE CONSTRAINT standard_id IF NOT EXISTS
FOR (n:Standard) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (n:Section) REQUIRE n.id IS NODE KEY;
```
