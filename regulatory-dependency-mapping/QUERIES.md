# Regulatory Dependency Mapping — Cypher

Runnable Cypher for the model in `GRAPH_MODEL.json`.

## Prerequisites

- Neo4j 5.x, Cypher 5. No APOC.
- The model imported through the Import flow, either from the bundled
  `sample-data/` CSVs or from the user's own data mapped onto the same model.
- Every query up to *Most-referenced sections by inbound citation count* needs
  nothing beyond the imported model.
- The queries prefixed **GDS —** need the GDS plugin (2.x) installed on the
  target database. GDS is not available on every Aura tier or self-managed
  install; the plain-Cypher queries cover the same analytical ground, with
  *Most-referenced sections by inbound citation count* standing in for
  PageRank as a degree-based measure of a section's influence.
- The optional range indexes in `SETUP.md` speed up the two date-filtered
  queries. They are not required for correctness.

## Adapting these queries

These queries assume the model in `GRAPH_MODEL.json`. When the user's schema
differs — their own model, a modified one, or a database that predates this
package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`)
   rather than assuming this model applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no
   counterpart means the pattern below it has no analogue — say so rather
   than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what
   the rewritten query actually does.

One constraint that survives every rewrite: Cypher does not accept a
parameter as the bound of a variable-length pattern. Where a traversal depth
is described below as tunable, it is tuned by editing the literal bound in
the Cypher, not by passing a parameter.

## Explore a standard's section hierarchy

```cypher
/*
 * @name           Explore a standard's section hierarchy
 * @description    Returns every section beneath a standard, with the depth at
 *                 which it sits, by following DEPENDS_ON from the standard
 *                 down through top-level sections to their child sections.
 * @params         standardId - Identifier of the standard to expand, as the
 *                     regulator publishes it and as Standard.id records it.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per section: the standard, section identifier,
 *                 title, in-force date of its current text, and its depth
 *                 below the standard.
 * @usage          The orientation query — run it first to see how deep and
 *                 how wide a handbook is before analysing it. The traversal
 *                 is bounded at four hops, which reaches a chapter, section,
 *                 subsection and one level below that; deepen the literal
 *                 bound only if the handbook nests further, since every extra
 *                 level multiplies the result. A section of the standard
 *                 that does not appear is either detached from it — an import
 *                 or data-quality finding — or nested below the bound; check
 *                 which before reporting either.
 * @tags           hierarchy, standard, section, orientation
 * TODO(review): unproven query
 */
MATCH path = (standard:Standard {id: $standardId})<-[:DEPENDS_ON*1..4]-(section:Section)
RETURN standard.id      AS standard,
       section.id       AS sectionId,
       section.title    AS title,
       section.lastUpdated AS lastUpdated,
       length(path)     AS depth
ORDER BY depth, sectionId
```

## Cross-references into and out of a section

```cypher
/*
 * @name           Cross-references into and out of a section
 * @description    Returns the sections a given section cites and the sections
 *                 that cite it, in both cases with the specific rule within
 *                 the cited section that the reference points at.
 * @params         sectionId - Identifier of the section to examine, as
 *                     Section.id records it.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per cross-reference: direction ('cites' or 'cited
 *                 by'), the section at the other end with its title and
 *                 in-force date, the rule reference carried on the
 *                 relationship, and how many obligations that section drives.
 * @usage          Run this before assessing a proposed change to a section:
 *                 the 'cited by' rows are the text that silently changes
 *                 meaning when this section moves. Direction matters — a
 *                 section with many outbound citations is dependent, one with
 *                 many inbound citations is load-bearing, and only the second
 *                 makes a change expensive. Returns no rows when the section
 *                 identifier does not exist, so check the identifier before
 *                 concluding a section is unreferenced.
 * @tags           cross-reference, change-assessment, section
 * TODO(review): unproven query
 */
MATCH (section:Section {id: $sectionId})
OPTIONAL MATCH (section)-[cites:RELATED]->(cited:Section)
WITH section,
     collect(DISTINCT {direction: 'cites', related: cited, rule: cites.subsection}) AS outbound
OPTIONAL MATCH (citing:Section)-[citedBy:RELATED]->(section)
WITH section, outbound,
     collect(DISTINCT {direction: 'cited by', related: citing, rule: citedBy.subsection}) AS inbound
UNWIND outbound + inbound AS reference
WITH section,
     reference.direction AS direction,
     reference.related   AS related,
     reference.rule      AS ruleReference
WHERE related IS NOT NULL
OPTIONAL MATCH (obligation:Obligation)-[:DERIVED_FROM]->(related)
RETURN direction,
       related.id          AS relatedSectionId,
       related.title       AS relatedTitle,
       related.lastUpdated AS relatedLastUpdated,
       ruleReference,
       count(DISTINCT obligation) AS obligationsDerived
ORDER BY direction, relatedSectionId
```

## Sections changed since a date and the obligations they drive

```cypher
/*
 * @name           Sections changed since a date and the obligations they drive
 * @description    Returns sections whose current text took effect on or after
 *                 a given date, with the standard they belong to, the
 *                 obligations derived from them, and the units accountable
 *                 for those obligations.
 * @params         changedSince - Earliest in-force date to include, as an
 *                     ISO 8601 date string (YYYY-MM-DD). Set it to the start
 *                     of the regulatory-change review cycle in hand, so the
 *                     query returns exactly what has not yet been assessed.
 *                     Where no fixed cycle exists, widen from the date of the
 *                     last assessment until the result stops being
 *                     reviewable.
 * @prerequisites  None beyond the imported model. Faster with the optional
 *                 range index on Section.lastUpdated in SETUP.md.
 * @returns        One row per changed section: standard, section identifier
 *                 and title, in-force date, the count of obligations derived
 *                 from it, and the accountable units, newest change first.
 *                 A null standard means the section did not resolve to one.
 * @usage          The standing regulatory-change sweep. A changed section
 *                 with no obligations derived from it is either genuinely out
 *                 of scope or a gap in the obligation register — worth
 *                 separating the two before reporting either. This query
 *                 finds the sections that changed; use the blast-radius query
 *                 to follow one of them through to business impact. The walk
 *                 up to the standard is bounded at four hops and deliberately
 *                 optional: missing a change is this query's one unacceptable
 *                 failure, so a section nested deeper than the bound, or
 *                 detached from any standard, is still reported — with a null
 *                 standard, which is itself a data-quality finding. Raise the
 *                 literal bound if the handbook nests deeper than four levels.
 * @tags           regulatory-change, section, obligation, accountability
 * TODO(review): unproven query
 */
MATCH (section:Section)
WHERE section.lastUpdated >= date($changedSince)
OPTIONAL MATCH (section)-[:DEPENDS_ON*1..4]->(standard:Standard)
OPTIONAL MATCH (obligation:Obligation)-[:DERIVED_FROM]->(section)
OPTIONAL MATCH (owner:BusinessUnit)-[:ACCOUNTABLE_FOR]->(obligation)
RETURN standard.id          AS standard,
       section.id           AS sectionId,
       section.title        AS title,
       section.lastUpdated  AS lastUpdated,
       count(DISTINCT obligation)   AS obligationsDerived,
       collect(DISTINCT owner.name) AS accountableUnits
ORDER BY lastUpdated DESC, sectionId
```

## Change-impact blast radius for a section

```cypher
/*
 * @name           Change-impact blast radius for a section
 * @description    Takes one section and returns everything a change to it
 *                 reaches: the section's own child sections, the sections
 *                 that cross-reference any of those, the obligations derived
 *                 from all of them, the business services those obligations
 *                 govern, and the units accountable.
 * @params         sectionId - Identifier of the section being changed, as
 *                     Section.id records it.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per affected obligation: the section it came from,
 *                 obligation identifier and title, its inherent risk score,
 *                 the accountable unit, every business service in scope, and
 *                 the subset of those formally designated important business
 *                 services. Highest inherent risk first.
 * @usage          The headline impact-assessment query, and the one to reach
 *                 for when the question is 'what breaks if this rule
 *                 changes'. Two bounds are literals in the Cypher rather than
 *                 parameters: three hops down the section hierarchy, and two
 *                 hops of cross-reference. Widen the cross-reference bound
 *                 only deliberately: citation graphs can fan out quickly, and
 *                 beyond two hops the affected set may grow faster than it
 *                 stays reviewable. Check the size before widening rather
 *                 than assuming either outcome. The important-business-service
 *                 column is the one to escalate on: those carry board-approved
 *                 impact tolerances.
 * @tags           impact-analysis, regulatory-change, obligation, service
 * TODO(review): unproven query
 */
MATCH (changed:Section {id: $sectionId})
OPTIONAL MATCH (descendant:Section)-[:DEPENDS_ON*1..3]->(changed)
WITH changed, collect(DISTINCT descendant) AS descendants
WITH [changed] + descendants AS inScope
UNWIND inScope AS scoped
OPTIONAL MATCH (citing:Section)-[:RELATED*1..2]->(scoped)
WITH inScope, collect(DISTINCT citing) AS citingSections
UNWIND inScope + citingSections AS affected
WITH DISTINCT affected
MATCH (obligation:Obligation)-[:DERIVED_FROM]->(affected)
MATCH (owner:BusinessUnit)-[:ACCOUNTABLE_FOR]->(obligation)
OPTIONAL MATCH (service:BusinessService)-[:GOVERNED_BY]->(obligation)
WITH affected, obligation, owner, collect(DISTINCT service) AS services
RETURN affected.id     AS affectedSection,
       obligation.id    AS obligationId,
       obligation.title AS obligation,
       obligation.inherentRiskScore AS inherentRiskScore,
       owner.name       AS accountableUnit,
       [s IN services | s.name] AS servicesInScope,
       [s IN services WHERE s.criticality = 'important-business-service' | s.name]
                        AS importantBusinessServices
ORDER BY inherentRiskScore DESC, affectedSection, obligationId
```

## Obligations with incomplete control coverage

```cypher
/*
 * @name           Obligations with incomplete control coverage
 * @description    Returns obligations whose controls, summed, address less
 *                 than the required share of the obligation's requirements,
 *                 including obligations with no control at all.
 * @params         minCoveragePercent - Assessed coverage an obligation must
 *                     reach to be treated as complete, 1-100. Start at 100:
 *                     coverage below full is a residual gap by definition, so
 *                     100 is the value that means 'show me every gap'. Lower
 *                     it only to triage a long list down to the worst cases.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per under-covered obligation: identifier, title,
 *                 category, inherent risk score, originating section,
 *                 accountable unit, summed assessed coverage, the number of
 *                 controls contributing, and how many business services are
 *                 exposed. Highest inherent risk first, then widest gap.
 * @usage          The control-gap register. Rows with a control count of zero
 *                 are uncontrolled obligations, not missing data — they are
 *                 the strongest finding this model produces, and they are why
 *                 the match on controls is optional. Read the coverage figure
 *                 as an assessment recorded by the firm, not a measurement:
 *                 it inherits whatever rigour the control-mapping exercise
 *                 had. Cross-check the highest-risk rows against the control
 *                 testing dates before treating covered obligations as safe.
 * @tags           control-coverage, gap-analysis, obligation, risk
 * TODO(review): unproven query
 */
MATCH (obligation:Obligation)-[:DERIVED_FROM]->(section:Section)
MATCH (owner:BusinessUnit)-[:ACCOUNTABLE_FOR]->(obligation)
OPTIONAL MATCH (control:Control)-[satisfies:SATISFIES]->(obligation)
WITH obligation, section, owner,
     sum(satisfies.coveragePercent) AS assessedCoverage,
     count(DISTINCT control)        AS controlCount
WHERE assessedCoverage < $minCoveragePercent
OPTIONAL MATCH (service:BusinessService)-[:GOVERNED_BY]->(obligation)
RETURN obligation.id       AS obligationId,
       obligation.title    AS obligation,
       obligation.category AS category,
       obligation.inherentRiskScore AS inherentRiskScore,
       section.id          AS sectionId,
       owner.name          AS accountableUnit,
       assessedCoverage,
       controlCount,
       count(DISTINCT service) AS servicesExposed
ORDER BY inherentRiskScore DESC, assessedCoverage, obligationId
```

## Systems that concentrate compliance dependency

```cypher
/*
 * @name           Systems that concentrate compliance dependency
 * @description    Ranks systems by how much of the compliance estate rests on
 *                 them, counting the controls implemented in each system, the
 *                 obligations those controls satisfy, the standards those
 *                 obligations span, and the business services that depend on
 *                 the system directly.
 * @params         minObligations - Minimum obligations a system's controls
 *                     must touch for it to appear. No single value transfers
 *                     between estates: start at 1 to see the whole
 *                     distribution ordered by obligation count, then set the
 *                     threshold just above the point where the ranking
 *                     flattens. The systems above that point are the
 *                     concentrations worth documenting.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per system: identifier, name, criticality tier,
 *                 control count, obligation count, the number of distinct
 *                 standards reached, the regulators behind them, and the
 *                 count of business services depending on it. Most
 *                 obligations first.
 * @usage          Single-point-of-failure analysis for the control estate.
 *                 The interesting signal is a system whose obligation count
 *                 sits well clear of the next system down, especially where
 *                 the regulators column names more than one — a concentration
 *                 that no single standard's own review would surface. Counts
 *                 direct dependencies only: a system may support more
 *                 services through the system-to-system chain, which the
 *                 upstream-dependency query traverses. A high tier number
 *                 means a less critical system, opposite to the risk scales
 *                 elsewhere in the model. The walk from a section up to its
 *                 standard is a literal four hops: obligations whose section
 *                 nests deeper are dropped, understating both counts, so
 *                 raise the bound before trusting the ranking on a handbook
 *                 deeper than four levels.
 * @tags           concentration-risk, single-point-of-failure, system, control
 * TODO(review): unproven query
 */
MATCH (control:Control)-[:IMPLEMENTED_BY]->(system:System)
MATCH (control)-[:SATISFIES]->(obligation:Obligation)
MATCH (obligation)-[:DERIVED_FROM]->(:Section)-[:DEPENDS_ON*1..4]->(standard:Standard)
WITH system,
     count(DISTINCT control)    AS controlCount,
     count(DISTINCT obligation) AS obligationCount,
     count(DISTINCT standard)   AS standardCount,
     collect(DISTINCT standard.regulator) AS regulators
WHERE obligationCount >= $minObligations
OPTIONAL MATCH (service:BusinessService)-[:DEPENDS_ON]->(system)
RETURN system.id   AS systemId,
       system.name AS system,
       system.tier AS tier,
       controlCount,
       obligationCount,
       standardCount,
       regulators,
       count(DISTINCT service) AS dependentServices
ORDER BY obligationCount DESC, controlCount DESC, systemId
```

## Controls satisfying obligations across more than one standard

```cypher
/*
 * @name           Controls satisfying obligations across more than one standard
 * @description    Returns controls whose obligations trace back to sections
 *                 in two or more different standards, with the standards and
 *                 obligations each control reaches.
 * @params         None
 * @prerequisites  None beyond the imported model.
 * @returns        One row per control: identifier, name, automation level,
 *                 the number of standards it reaches and their identifiers,
 *                 the jurisdictions those standards belong to, the number of
 *                 obligations and their identifiers, and the system it is
 *                 implemented in. Widest reach first.
 * @usage          Finds the overlaps between regulations — the same control
 *                 doing duty under several rulebooks. Read it two ways. As an
 *                 efficiency finding, these are the controls where separate
 *                 compliance programmes are duplicating assurance effort. As
 *                 a risk finding, they are controls whose failure breaches
 *                 more than one regulator at once, which is rarely how a
 *                 single-standard control review scores them. Rows whose
 *                 jurisdictions column holds more than one entry deserve
 *                 particular attention, since two regimes may impose
 *                 requirements that cannot both be met by one design. The
 *                 walk from a section up to its standard is a literal four
 *                 hops: an obligation whose section nests deeper is dropped,
 *                 which can hide a genuine cross-standard control entirely.
 * @tags           overlap, duplication, control, cross-standard
 * TODO(review): unproven query
 */
MATCH (control:Control)-[:SATISFIES]->(obligation:Obligation)
MATCH (obligation)-[:DERIVED_FROM]->(:Section)-[:DEPENDS_ON*1..4]->(standard:Standard)
WITH control,
     collect(DISTINCT standard.id)           AS standards,
     collect(DISTINCT standard.jurisdiction) AS jurisdictions,
     collect(DISTINCT obligation.id)         AS obligations
WHERE size(standards) > 1
OPTIONAL MATCH (control)-[:IMPLEMENTED_BY]->(system:System)
RETURN control.id   AS controlId,
       control.name AS control,
       control.automationLevel AS automationLevel,
       size(standards)   AS standardCount,
       standards,
       jurisdictions,
       size(obligations) AS obligationCount,
       obligations,
       system.name AS implementedIn
ORDER BY standardCount DESC, obligationCount DESC, controlId
```

## Upstream system dependencies for a business service

```cypher
/*
 * @name           Upstream system dependencies for a business service
 * @description    Returns every system a business service reaches, directly
 *                 or through the chain of system-to-system dependencies, with
 *                 the shortest number of hops from the service and how many
 *                 other services share each system.
 * @params         serviceId - Identifier of the business service to trace, as
 *                     BusinessService.id records it.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per reachable system: hops from the service,
 *                 system identifier and name, criticality tier, hosting
 *                 model, and the number of business services other than the
 *                 one being traced that depend on it directly. Nearest first.
 * @usage          Operational-resilience mapping for one service: what has to
 *                 be working for the service to run. The traversal is bounded
 *                 at four hops beyond the directly-dependent systems, a
 *                 literal in the Cypher rather than a parameter; raise it only
 *                 if dependency chains in the estate are known to run deeper,
 *                 and expect the far end of a long chain to be shared
 *                 infrastructure rather than anything service-specific. A
 *                 vendor-saas system several hops out with a high shared
 *                 count is the classic concentration a service-level review
 *                 misses. Hop count is topological, not a measure of how
 *                 quickly a failure propagates.
 * @tags           operational-resilience, dependency-chain, system, service
 * TODO(review): unproven query
 */
MATCH (service:BusinessService {id: $serviceId})-[:DEPENDS_ON]->(entry:System)
OPTIONAL MATCH path = (entry)-[:DEPENDS_ON*1..4]->(upstream:System)
WITH service,
     collect(DISTINCT {system: entry, hops: 1}) +
     collect(DISTINCT {system: upstream, hops: length(path) + 1}) AS reached
UNWIND reached AS reach
WITH service, reach.system AS system, reach.hops AS hops
WHERE system IS NOT NULL
WITH service, system, min(hops) AS hopsFromService
OPTIONAL MATCH (other:BusinessService)-[:DEPENDS_ON]->(system)
WHERE other <> service
RETURN service.name AS service,
       hopsFromService,
       system.id   AS systemId,
       system.name AS system,
       system.tier AS tier,
       system.hostingModel AS hostingModel,
       count(DISTINCT other) AS servicesSharingThisSystem
ORDER BY hopsFromService, tier, systemId
```

## Controls overdue for testing, weighted by obligation risk

```cypher
/*
 * @name           Controls overdue for testing, weighted by obligation risk
 * @description    Returns controls last tested before a given date, ordered
 *                 by the inherent risk of the obligations they support and by
 *                 how many obligations rest on them.
 * @params         staleBefore - Controls last tested before this date are
 *                     returned, as an ISO 8601 date string (YYYY-MM-DD). Set
 *                     it to today's date minus the control testing cycle in
 *                     policy — twelve months is the common cycle for key
 *                     controls, so use the firm's own period rather than a
 *                     round number.
 * @prerequisites  None beyond the imported model. Faster with the optional
 *                 range index on Control.lastTestedDate in SETUP.md.
 * @returns        One row per overdue control: identifier, name, last tested
 *                 date, months since that test, effectiveness score at that
 *                 test, the count of obligations it supports, the highest
 *                 inherent risk among them, and the system it runs in.
 *                 Highest obligation risk first.
 * @usage          Testing-backlog triage. The point of joining to obligations
 *                 is that a stale control is only as urgent as what depends
 *                 on it, and an unweighted overdue list buries the ones that
 *                 matter. Two rows deserve separate treatment: an overdue
 *                 control supporting no obligation at all may be an orphan
 *                 worth retiring rather than testing, and an overdue control
 *                 with a high effectiveness score is stale evidence, not
 *                 evidence of failure — the score describes the control as it
 *                 was at the last test and does not decay on its own.
 * @tags           control-testing, assurance, staleness, risk
 * TODO(review): unproven query
 */
MATCH (control:Control)
WHERE control.lastTestedDate < date($staleBefore)
OPTIONAL MATCH (control)-[:SATISFIES]->(obligation:Obligation)
OPTIONAL MATCH (control)-[:IMPLEMENTED_BY]->(system:System)
RETURN control.id   AS controlId,
       control.name AS control,
       control.lastTestedDate AS lastTestedDate,
       duration.inMonths(control.lastTestedDate, date()).months AS monthsSinceTest,
       control.effectivenessScore AS effectivenessScore,
       count(DISTINCT obligation) AS obligationsSupported,
       coalesce(max(obligation.inherentRiskScore), 0) AS highestInherentRisk,
       head(collect(DISTINCT system.name)) AS implementedIn
ORDER BY highestInherentRisk DESC, obligationsSupported DESC, lastTestedDate
```

## Most-referenced sections by inbound citation count

```cypher
/*
 * @name           Most-referenced sections by inbound citation count
 * @description    Ranks sections by how many other sections cite them,
 *                 alongside the obligations derived from each and a sample of
 *                 the specific rule references pointing at it.
 * @params         limit - Maximum sections to return. Start at 20, roughly a
 *                     screen the reader can take in at once, and raise it only
 *                     once the top of the ranking has been dealt with.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per cited section: identifier, title, in-force
 *                 date, inbound citation count, obligations derived from it,
 *                 and up to five of the rule references that point at it.
 *                 Most cited first.
 * @usage          The plain-Cypher stand-in for PageRank, and the one to use
 *                 when GDS is unavailable. It measures direct citations only,
 *                 so it credits a section cited by many peripheral sections
 *                 the same as one cited by a few load-bearing ones; the
 *                 PageRank query in the GDS section separates those. Sections
 *                 near the top are the expensive ones to change, and a recent
 *                 in-force date on a heavily-cited section is a signal worth
 *                 acting on. Sections nothing cites are excluded rather than
 *                 returned with a zero.
 * @tags           centrality, cross-reference, section, change-cost
 * TODO(review): unproven query
 */
MATCH (cited:Section)<-[ref:RELATED]-(citing:Section)
WITH cited,
     count(DISTINCT citing) AS inboundReferences,
     collect(DISTINCT ref.subsection)[0..5] AS sampleRuleReferences
OPTIONAL MATCH (obligation:Obligation)-[:DERIVED_FROM]->(cited)
RETURN cited.id    AS sectionId,
       cited.title AS title,
       cited.lastUpdated AS lastUpdated,
       inboundReferences,
       count(DISTINCT obligation) AS obligationsDerived,
       sampleRuleReferences
ORDER BY inboundReferences DESC, obligationsDerived DESC, sectionId
LIMIT $limit
```

## Graph Data Science

The four queries below need the **GDS plugin (2.x)** on the target database.
Check with `RETURN gds.version()` before offering them; if it errors, GDS is
not installed and the plain-Cypher queries above cover the same ground.

Run the projection first and drop it when finished. A GDS projection lives in
the graph catalog for the database and user until it is explicitly dropped or
the DBMS restarts — it does **not** go away when the client disconnects, so
leaving one behind pins heap indefinitely. None of the four writes to the
stored graph: PageRank scores and community identifiers are returned rather
than saved as properties, which keeps them safe to run against a database the
user has not agreed to modify.

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
 *                 user — which outlives the client session.
 * @returns        The projection name with its node and relationship counts.
 * @usage          Run once before either analytic below, and drop the
 *                 projection afterwards — it is not released on disconnect. The projection deliberately excludes
 *                 the DEPENDS_ON hierarchy: including it would let influence
 *                 flow along parent-child structure, which says only that a
 *                 handbook has chapters. Every Section node is projected,
 *                 including sections nothing cross-references, so they appear
 *                 as isolated nodes with a floor PageRank score and as
 *                 single-member communities.
 * @tags           gds, projection, setup
 * TODO(review): unproven query
 */
CALL gds.graph.project('regulatorySections', 'Section', 'RELATED')
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
```

## GDS — Rank section influence with PageRank

```cypher
/*
 * @name           GDS — Rank section influence with PageRank
 * @description    Scores each section by PageRank over the cross-reference
 *                 graph, so that a citation from a heavily-cited section
 *                 counts for more than one from an isolated section, and
 *                 joins the scores back to standards and obligations.
 * @params         limit - Maximum sections to return. Start at 20, roughly a
 *                     screen the reader can take in at once, and raise it only
 *                     once the top of the ranking has been dealt with.
 * @prerequisites  GDS plugin 2.x, and the 'regulatorySections' projection
 *                 created by the projection query above.
 * @returns        One row per section: standard, section identifier and
 *                 title, PageRank score rounded to four decimals, and the
 *                 count of obligations derived from it. Highest score first.
 * @usage          Use it to decide where regulatory-change effort is best
 *                 spent: a high score means a change here propagates through
 *                 the citation graph rather than staying local. It differs
 *                 from the inbound-count query above by weighting citations
 *                 from influential sections more heavily, so compare the two
 *                 rankings — sections that rank high on PageRank but low on
 *                 raw count are the quietly structural ones. Scores are
 *                 relative within one run and not comparable across handbooks
 *                 or across runs on different data. Streams results without
 *                 writing a property to the graph. The walk from a section up
 *                 to its standard is a literal four hops, so a section nested
 *                 deeper is scored by GDS but dropped from this result.
 * @tags           gds, pagerank, centrality, section, change-cost
 * TODO(review): unproven query
 */
CALL gds.pageRank.stream('regulatorySections')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS section, score
MATCH (section)-[:DEPENDS_ON*1..4]->(standard:Standard)
OPTIONAL MATCH (obligation:Obligation)-[:DERIVED_FROM]->(section)
RETURN standard.id    AS standard,
       section.id     AS sectionId,
       section.title  AS title,
       round(score, 4) AS pageRankScore,
       count(DISTINCT obligation) AS obligationsDerived
ORDER BY pageRankScore DESC, sectionId
LIMIT $limit
```

## GDS — Group cross-referencing sections into communities

```cypher
/*
 * @name           GDS — Group cross-referencing sections into communities
 * @description    Runs Weakly Connected Components over the cross-reference
 *                 graph to find clusters of sections that reference each
 *                 other, and reports each cluster's size and the standards
 *                 it spans.
 * @params         minCommunitySize - Smallest cluster to report. Start at 2:
 *                     a component of one is a section with no cross-reference
 *                     in either direction, which says nothing about
 *                     clustering. How many of those a handbook has depends
 *                     entirely on how completely its cross-references were
 *                     captured. Raise it to concentrate on larger clusters.
 * @prerequisites  GDS plugin 2.x, and the 'regulatorySections' projection
 *                 created by the projection query above.
 * @returns        One row per component: component identifier, member count,
 *                 the number of standards it spans and their identifiers, and
 *                 up to ten member section identifiers. Largest first.
 * @usage          Finds the natural units of regulatory change — clusters
 *                 that have to be assessed together because their text is
 *                 mutually referential. A component spanning more than one
 *                 standard is the finding to pursue: it means a change in one
 *                 rulebook propagates into another, which is exactly the
 *                 dependency a standard-by-standard review process is blind
 *                 to. Weakly connected components ignore citation direction,
 *                 so a single citation is enough to merge two clusters; treat
 *                 a very large component as a hint to look at the citation
 *                 that bridges it rather than as one coherent group. The walk
 *                 from a section up to its standard is a literal four hops, so
 *                 a section nested deeper is dropped and communitySize then
 *                 understates the true component size.
 * @tags           gds, wcc, community, cross-reference, section
 * TODO(review): unproven query
 */
CALL gds.wcc.stream('regulatorySections')
YIELD nodeId, componentId
WITH componentId, gds.util.asNode(nodeId) AS section
MATCH (section)-[:DEPENDS_ON*1..4]->(standard:Standard)
WITH componentId,
     collect(DISTINCT section.id)  AS sectionIds,
     collect(DISTINCT standard.id) AS standardsSpanned
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
 *                 the projection query above fail on its next run with a name
 *                 conflict. Dropping it does not touch the stored graph.
 * @tags           gds, projection, cleanup
 * TODO(review): unproven query
 */
CALL gds.graph.drop('regulatorySections')
YIELD graphName, nodeCount
RETURN graphName, nodeCount
```

## Node-key constraints (schema reference)

The Import flow creates these from the `key: true` definitions in
`GRAPH_MODEL.json`. They are reproduced here so the expected schema can be
confirmed with `SHOW CONSTRAINTS` after an import — not to build it. Running
them against a database Import has already populated is unnecessary, and on a
database with differently-named equivalents it will add duplicates.

```cypher
CREATE CONSTRAINT standard_id IF NOT EXISTS
FOR (n:Standard) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (n:Section) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT obligation_id IF NOT EXISTS
FOR (n:Obligation) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT control_id IF NOT EXISTS
FOR (n:Control) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT business_service_id IF NOT EXISTS
FOR (n:BusinessService) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT system_id IF NOT EXISTS
FOR (n:System) REQUIRE n.id IS NODE KEY;

CREATE CONSTRAINT business_unit_id IF NOT EXISTS
FOR (n:BusinessUnit) REQUIRE n.id IS NODE KEY;
```
