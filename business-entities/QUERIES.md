# Business Entities: Ownership and Control — Query Guidance

Cypher for the `business-entities` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database.

## Prerequisites

- Neo4j 5.x and Cypher 5, at a release that supports `COUNT {}` and `COLLECT {}` subqueries (5.6 or later). No APOC or Graph Data Science required.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology.
- `OWNS.percentage` is a FLOAT in percent (0–100) of the owned entity's equity held directly. **Effective ownership** along a chain is the product of the percentages on it (60% of 70% of 80% is 33.6%), and a person's effective ownership of an entity is the sum over every distinct chain from them to it. The queries compute it with `reduce()` over the relationships of each path.
- Variable-length `OWNS` paths are bounded (six hops for ownership, eight for corporate trees and connections) and filtered to paths that visit each node once, so circular ownership neither loops nor double counts.
- **Control** in these queries means a chain of `OWNS` links each above `$controlPct` percent (50 by default — a majority stake), or a `general partner interest`, which controls a partnership whatever its percentage. Board seats (`DIRECTOR_OF`) and offices (`OFFICER_OF`) are control without ownership.
- Dates are ZONED DATETIME at midnight UTC; only the calendar date carries meaning. Wrap a value in `date()` to display it, and compare against `datetime(...)`, never `date(...)`.
- No `SETUP.md` statements are needed, and no query creates a label, relationship type, or property.
- Queries run from single-entity lookups, through ownership and control analysis for one entity, to portfolio-wide pattern searches and the connection between two entities.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Entity overview

```cypher
/*
 * @name           Entity overview
 * @description    Gathers what the reference ontology holds about one legal
 *                 entity into a single row: identity and legal form,
 *                 jurisdiction of incorporation, registered address, direct
 *                 owners with percentage and interest type, directors,
 *                 officers, direct holdings, and reported parents.
 * @params         entityId - LegalEntity.entityId of the entity to describe.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: entity fields, jurisdiction, registeredAddress,
 *                 directOwners as "name (percentage%, interestType)",
 *                 directors as "name (role)", officers as "name (title)",
 *                 directHoldings (entities it owns directly), and
 *                 reportedDirectParent / reportedUltimateParent (null when
 *                 not reported). No row when the entityId does not exist.
 * @usage          The starting point for any question about one entity. It
 *                 shows one hop only; use Ownership structure for the chain
 *                 above it and Ultimate beneficial owners for who stands at
 *                 the top.
 * @tags           entity, lookup, overview
 * @sample         Bundled sample data only: $entityId = 'E-0218' (Larkspur
 *                 Freight Ltd) returns 1 row — private limited company,
 *                 United Kingdom; owners Saint Ouen Investments Ltd (80.0%),
 *                 Daniel Kershaw (12.0%), Takumi Lehmann (8.0%); directors
 *                 Daniel Kershaw and Niamh Halvorsen; officer Daniel Kershaw
 *                 (chief executive officer); no reported parents.
 */
MATCH (e:LegalEntity {entityId: $entityId})
OPTIONAL MATCH (e)-[:INCORPORATED_IN]->(j:Jurisdiction)
OPTIONAL MATCH (e)-[:REGISTERED_AT]->(a:Address)
OPTIONAL MATCH (e)-[:DIRECTLY_CONSOLIDATED_BY]->(dp:LegalEntity)
OPTIONAL MATCH (e)-[:ULTIMATELY_CONSOLIDATED_BY]->(up:LegalEntity)
RETURN e.entityId AS entityId, e.name AS name, e.legalForm AS legalForm, e.status AS status,
       e.lei AS lei, e.registrationNumber AS registrationNumber,
       date(e.incorporationDate) AS incorporationDate, j.name AS jurisdiction,
       a.street + ', ' + a.city + ', ' + a.countryCode AS registeredAddress,
       COLLECT { MATCH (o)-[r:OWNS]->(e)
                 RETURN o.name + ' (' + toString(r.percentage) + '%, ' + r.interestType + ')' } AS directOwners,
       COLLECT { MATCH (p:Person)-[d:DIRECTOR_OF]->(e) RETURN p.name + ' (' + d.role + ')' } AS directors,
       COLLECT { MATCH (p:Person)-[o:OFFICER_OF]->(e) RETURN p.name + ' (' + o.title + ')' } AS officers,
       COUNT { (e)-[:OWNS]->(:LegalEntity) } AS directHoldings,
       dp.name AS reportedDirectParent, up.name AS reportedUltimateParent
```

## Ownership structure

```cypher
/*
 * @name           Ownership structure
 * @description    Draws every ownership chain above one entity — people,
 *                 trusts and intermediate holding companies — and, for any
 *                 trust in those chains, the people and companies standing
 *                 behind it as trustor, trustee or beneficiary.
 * @params         entityId - LegalEntity.entityId of the entity to draw.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths for Browser or Bloom to draw, one per row: each
 *                 OWNS chain ending at the entity, and each trust's
 *                 TRUSTOR_OF / TRUSTEE_OF / BENEFICIARY_OF link. UNION
 *                 removes duplicates.
 * @usage          Visual, not tabular: the picture that shows why a register
 *                 of direct shareholders is not the answer. Chains are
 *                 limited to six hops and to paths that visit each entity
 *                 once. A widely held entity draws many chains; read Entity
 *                 overview first to see how many direct owners it has.
 * @tags           visualisation, ownership, chain, trust
 * @sample         Bundled sample data only: $entityId = 'E-0218' (Larkspur
 *                 Freight Ltd) returns 8 paths, the longest running Rodrigo
 *                 Valente → Ashgrove Ventures Ltd (VG) → Blue Lantern
 *                 Holdings Ltd (KY) → Saint Ouen Investments Ltd (JE) →
 *                 Larkspur Freight Ltd; no trusts.
 */
MATCH path = (owner)-[:OWNS*1..6]->(:LegalEntity {entityId: $entityId})
WHERE all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
RETURN path
UNION
MATCH (:LegalEntity {entityId: $entityId})<-[:OWNS*1..6]-(t:Trust)
MATCH path = (t)<-[:TRUSTOR_OF|TRUSTEE_OF|BENEFICIARY_OF]-()
RETURN path
```

## Corporate group

```cypher
/*
 * @name           Corporate group
 * @description    Lists every entity a parent controls through a chain of
 *                 majority stakes, at any depth, with the depth, the
 *                 parent's effective ownership, the intermediate holding
 *                 companies, and where each is incorporated.
 * @params         entityId - LegalEntity.entityId of the parent at the top.
 *                 controlPct - OWNS.percentage each link must exceed. Start
 *                     at 50, a majority stake; lower it to include
 *                     significant minority holdings.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per controlled entity: entityId, name, depth (1 =
 *                 directly owned), effectivePct (product of the percentages
 *                 down the chain), via (intermediate entities, top first),
 *                 jurisdiction, offshore (the jurisdiction's
 *                 isOffshoreCentre flag). Ordered by depth, then name.
 * @usage          Follows OWNS downward up to eight hops — deep enough for
 *                 most groups; raise the bound if the deepest rows sit at
 *                 the limit. Control here is ownership-based; a fund
 *                 controlled through a general partner interest appears
 *                 only from the fund downward.
 * @tags           group, subsidiary, hierarchy, control
 * @sample         Bundled sample data only: $entityId = 'E-0176' (Wealdmoor
 *                 Group plc), $controlPct = 50 returns 12 rows to depth 4,
 *                 including the acquired Fenmarsh Industries Ltd and its
 *                 subsidiaries, two of them in KY.
 */
MATCH path = (:LegalEntity {entityId: $entityId})-[:OWNS*1..8]->(sub:LegalEntity)
WHERE all(r IN relationships(path) WHERE r.percentage > $controlPct)
  AND all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
OPTIONAL MATCH (sub)-[:INCORPORATED_IN]->(j:Jurisdiction)
RETURN sub.entityId AS entityId, sub.name AS name, length(path) AS depth,
       round(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0), 2) AS effectivePct,
       [n IN nodes(path)[1..-1] | n.name] AS via,
       j.jurisdictionId AS jurisdiction, j.isOffshoreCentre AS offshore
ORDER BY depth, name
```

## Ultimate beneficial owners

```cypher
/*
 * @name           Ultimate beneficial owners
 * @description    Finds the natural persons whose effective ownership of an
 *                 entity reaches a threshold, summing every distinct chain
 *                 from the person to the entity — direct holdings and
 *                 holdings through any number of intermediate companies.
 * @params         entityId - LegalEntity.entityId of the entity examined.
 *                 minPct - Minimum effective ownership, in percent. Start at
 *                     25, the threshold many beneficial-ownership regimes
 *                     use; lower it to see who sits just below.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per qualifying person: personId, name,
 *                 nationality, politicallyExposed, effectivePct (summed over
 *                 chains), chains (how many), and via (each chain's
 *                 intermediate entities, nearest the person first; an empty
 *                 list is a direct holding). Ordered by effectivePct
 *                 descending.
 * @usage          Ownership only: trusts are handled by Trust look-through,
 *                 and people who control without owning by Control without
 *                 ownership — a full beneficial-ownership answer reads all
 *                 three. A person can pass the threshold only through the
 *                 sum of several chains each below it, which a chain-by-
 *                 chain review misses. Chains are limited to six hops.
 * @tags           beneficial ownership, UBO, KYC, effective ownership
 * @sample         Bundled sample data only: $entityId = 'E-0275'
 *                 (Kestrelwerk Komponenten GmbH), $minPct = 25 returns 2
 *                 rows — Niklas Brunner 30.0 (1 chain) and Maarten Visser
 *                 27.0 (2 chains: 15.0 direct plus 12.0 through Dommelstroom
 *                 Beheer B.V.).
 */
MATCH path = (p:Person)-[:OWNS*1..6]->(:LegalEntity {entityId: $entityId})
WHERE all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
WITH p, collect(path) AS chains,
     sum(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0)) AS effectivePct
WHERE effectivePct >= $minPct
RETURN p.personId AS personId, p.name AS name, p.nationality AS nationality,
       p.isPoliticallyExposed AS politicallyExposed, round(effectivePct, 2) AS effectivePct,
       size(chains) AS chains,
       [c IN chains | [n IN nodes(c)[1..-1] | n.name]] AS via
ORDER BY effectivePct DESC
```

## Trust look-through

```cypher
/*
 * @name           Trust look-through
 * @description    Finds every trust in the ownership chains above an entity,
 *                 with its effective ownership, governing law, and the
 *                 parties behind it: trustors, trustees (people or trust
 *                 companies), beneficiaries, and the directors of any
 *                 corporate trustee.
 * @params         entityId - LegalEntity.entityId of the entity examined.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per trust: trustId, name, trustType, governingLaw,
 *                 effectivePct (summed over chains), trustors, trustees,
 *                 beneficiaries, and corporateTrusteeDirectors as
 *                 "name (trust company)".
 * @usage          No threshold is applied: many beneficial-ownership
 *                 regimes treat a trust's trustor, trustees and
 *                 beneficiaries as beneficial owners whatever the
 *                 percentage held. A professional trust company is trustee
 *                 of many unrelated trusts, so read its directors as the
 *                 people administering the trust, not owning it. Chains are
 *                 limited to six hops.
 * @tags           trust, beneficial ownership, look-through, KYC
 * @sample         Bundled sample data only: $entityId = 'E-0283' (Coastway
 *                 Hotels Ltd) returns 1 row — Calloway Family Trust
 *                 (irrevocable trust, Jersey), 45.0 through Calloway
 *                 Holdings Ltd; trustor Edmund Calloway; trustee Saltmarsh
 *                 Trust Company Ltd (directors Priya Kapoor, Mateo Nyberg);
 *                 beneficiaries Harriet and Thomas Calloway.
 */
MATCH path = (t:Trust)-[:OWNS*1..6]->(:LegalEntity {entityId: $entityId})
WHERE all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
WITH t, sum(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0)) AS effectivePct
OPTIONAL MATCH (t)-[:ESTABLISHED_IN]->(j:Jurisdiction)
RETURN t.trustId AS trustId, t.name AS name, t.trustType AS trustType, j.name AS governingLaw,
       round(effectivePct, 2) AS effectivePct,
       COLLECT { MATCH (p:Person)-[:TRUSTOR_OF]->(t) RETURN p.name } AS trustors,
       COLLECT { MATCH (x)-[:TRUSTEE_OF]->(t) RETURN x.name } AS trustees,
       COLLECT { MATCH (p:Person)-[:BENEFICIARY_OF]->(t) RETURN p.name } AS beneficiaries,
       COLLECT { MATCH (tc:LegalEntity)-[:TRUSTEE_OF]->(t)
                 MATCH (d:Person)-[:DIRECTOR_OF]->(tc)
                 RETURN d.name + ' (' + tc.name + ')' } AS corporateTrusteeDirectors
ORDER BY effectivePct DESC
```

## Collective ownership by household

```cypher
/*
 * @name           Collective ownership by household
 * @description    Searches the whole portfolio for entities where people
 *                 sharing a residential address each hold effective
 *                 ownership below the threshold but together reach it — a
 *                 stake split across a household so that no one appears as
 *                 a beneficial owner.
 * @params         minPct - Effective-ownership threshold, in percent. Each
 *                     member is below it and the household's combined stake
 *                     reaches it. Start at the threshold used for Ultimate
 *                     beneficial owners (25).
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per entity and shared address: entityId, name,
 *                 sharedAddress, members as "name (effectivePct%)", and
 *                 combinedPct. Ordered by combinedPct descending.
 * @usage          Portfolio-wide: it computes every person's effective
 *                 ownership of every entity, so on a large graph anchor it
 *                 to one entity or a list of entities. A shared address is
 *                 a lead, not proof of a family or of acting in concert;
 *                 flats in one building and care homes share addresses too,
 *                 so check the address before drawing conclusions.
 * @tags           beneficial ownership, household, structuring, address
 * @sample         Bundled sample data only: $minPct = 25 returns 1 row —
 *                 Bramblefinch Bakeries Ltd, 14 Orchard Lane, Bristol:
 *                 Margaret (12.0), Colin (11.0, through Hartigan Holdings
 *                 Ltd) and Owen Hartigan (9.0), combined 32.0.
 */
MATCH path = (p:Person)-[:OWNS*1..6]->(e:LegalEntity)
WHERE all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
WITH p, e, sum(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0)) AS effectivePct
WHERE effectivePct < $minPct
MATCH (p)-[:RESIDES_AT]->(home:Address)
WITH e, home, sum(effectivePct) AS combinedPct, count(p) AS people,
     collect(p.name + ' (' + toString(round(effectivePct, 2)) + '%)') AS members
WHERE people >= 2 AND combinedPct >= $minPct
RETURN e.entityId AS entityId, e.name AS name,
       home.street + ', ' + home.city AS sharedAddress, members,
       round(combinedPct, 2) AS combinedPct
ORDER BY combinedPct DESC
```

## Control without ownership

```cypher
/*
 * @name           Control without ownership
 * @description    Finds the people who control an entity through a board
 *                 seat, an office, or a controlling stake in any entity on
 *                 the chain of control above it, yet whose own effective
 *                 ownership of it is below the threshold — the senior
 *                 managers of a subsidiary's parents, or the partners who
 *                 run a fund's general partner.
 * @params         entityId - LegalEntity.entityId of the entity examined.
 *                 controlPct - OWNS.percentage above which a stake controls.
 *                     Start at 50, a majority stake. A general partner
 *                     interest controls whatever its percentage.
 *                 minPct - Effective ownership at or above which a person
 *                     is already a beneficial owner by ownership and is left
 *                     out. Use the Ultimate beneficial owners threshold (25).
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per person: personId, name, controlRoutes (each
 *                 seat as "role or title of entity", or "interestType
 *                 percentage% of entity" for a controlling stake),
 *                 levelsAbove (0 = a seat on the entity itself; higher =
 *                 further up the chain), and effectivePct. Ordered by
 *                 levelsAbove descending.
 * @usage          The chain of control is walked up to five entities
 *                 above. Every director and officer of every controlling
 *                 parent is returned, so a large group's subsidiary lists
 *                 the parent's whole board — read the routes rather than
 *                 the count. Where no one passes the ownership threshold,
 *                 many regimes fall back to a senior managing official,
 *                 and this list is where to find one.
 * @tags           control, beneficial ownership, directors, general partner
 * @sample         Bundled sample data only: $entityId = 'E-0313'
 *                 (Calderbrook Precision Engineering Ltd), $controlPct = 50,
 *                 $minPct = 25 returns 3 rows — Jonathan Whitlock (managing
 *                 member and 100.0% member of Ironwell Capital GP LLC, two
 *                 levels above, effectivePct 1.0), then Rebecca Ashworth
 *                 and James Jansen (seats on the entity itself, 0.0).
 */
MATCH chain = (c:LegalEntity)-[:OWNS*0..5]->(:LegalEntity {entityId: $entityId})
WHERE all(r IN relationships(chain) WHERE r.percentage > $controlPct OR r.interestType = 'general partner interest')
  AND all(n IN nodes(chain) WHERE single(m IN nodes(chain) WHERE m = n))
MATCH (p:Person)-[seat:DIRECTOR_OF|OFFICER_OF|OWNS]->(c)
WHERE type(seat) <> 'OWNS' OR seat.percentage > $controlPct OR seat.interestType = 'general partner interest'
WITH p, min(length(chain)) AS levelsAbove,
     collect(DISTINCT CASE type(seat)
       WHEN 'DIRECTOR_OF' THEN seat.role + ' of ' + c.name
       WHEN 'OFFICER_OF' THEN seat.title + ' of ' + c.name
       ELSE seat.interestType + ' ' + toString(seat.percentage) + '% of ' + c.name END) AS controlRoutes
CALL {
  WITH p
  OPTIONAL MATCH own = (p)-[:OWNS*1..6]->(:LegalEntity {entityId: $entityId})
  WHERE all(n IN nodes(own) WHERE single(m IN nodes(own) WHERE m = n))
  RETURN sum(reduce(x = 100.0, r IN relationships(own) | x * r.percentage / 100.0)) AS effectivePct
}
WITH p, levelsAbove, controlRoutes, effectivePct
WHERE effectivePct < $minPct
RETURN p.personId AS personId, p.name AS name, controlRoutes, levelsAbove,
       round(effectivePct, 2) AS effectivePct
ORDER BY levelsAbove DESC, name
```

## Circular ownership

```cypher
/*
 * @name           Circular ownership
 * @description    Finds chains of corporate ownership that return to where
 *                 they started — A owns B owns C owns A, or two companies
 *                 holding each other's shares — anywhere in the portfolio.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per cycle: cycle (entity names in ownership
 *                 order, starting from the lowest entityId), entities
 *                 (cycle length), percentages (each link in order), and
 *                 selfOwnershipPct (the product round the cycle — the share
 *                 of itself the first entity holds through the loop).
 * @usage          Cycles of two to six entities. Each cycle is reported
 *                 once, from its lowest entityId. Cross-shareholdings
 *                 between listed companies are lawful in many markets;
 *                 circular ownership in a private structure obscures who
 *                 owns it and inflates apparent capital, so review the
 *                 private ones first.
 * @tags           circular ownership, cycle, cross-shareholding, structure
 * @sample         Bundled sample data only: returns 2 rows — Ventaglio
 *                 Holding S.p.A. → Ventaglio Tessuti S.r.l. → Ventaglio
 *                 Logistica S.r.l. (40.0, 35.0, 30.0; 4.2), and Hoshikawa
 *                 Industries K.K. ⇄ Minatogawa Electric K.K. (8.0, 6.0;
 *                 0.48).
 */
MATCH path = (e:LegalEntity)-[:OWNS*2..6]->(e)
WHERE all(n IN nodes(path)[1..] WHERE single(m IN nodes(path)[1..] WHERE m = n))
  AND all(n IN nodes(path)[1..-1] WHERE n.entityId > e.entityId)
RETURN [n IN nodes(path)[..-1] | n.name] AS cycle, length(path) AS entities,
       [r IN relationships(path) | r.percentage] AS percentages,
       round(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0), 2) AS selfOwnershipPct
ORDER BY entities DESC
```

## Offshore layering

```cypher
/*
 * @name           Offshore layering
 * @description    Searches the whole portfolio for ownership chains that
 *                 run from a person through companies in several offshore
 *                 financial centres before reaching an entity incorporated
 *                 onshore.
 * @params         minOffshoreLayers - Minimum number of intermediate
 *                     companies incorporated in a jurisdiction whose
 *                     isOffshoreCentre is true. Start at 2: one offshore
 *                     holding company is common in private wealth
 *                     planning, while each further layer adds opacity
 *                     with little ordinary purpose.
 * @prerequisites  Jurisdiction.isOffshoreCentre set according to the user's
 *                 own policy; the query is only as good as that flag.
 * @returns        One row per chain: person, politicallyExposed, entity
 *                 (the onshore entity at the end), chain (intermediate
 *                 companies as "name (jurisdictionId)", person's end
 *                 first), offshoreLayers, and effectivePct along the chain.
 *                 Ordered by offshoreLayers, then effectivePct, descending.
 * @usage          Chains of two to six OWNS links starting at a person;
 *                 chains starting at a trust are reached through Trust
 *                 look-through instead. A chain is a lead for enhanced due
 *                 diligence, not evidence of wrongdoing: structured
 *                 finance and some fund structures use offshore layers
 *                 for lawful reasons.
 * @tags           offshore, layering, AML, jurisdiction, chain
 * @sample         Bundled sample data only: $minOffshoreLayers = 2 returns 2
 *                 rows, both ending at Larkspur Freight Ltd — Rodrigo
 *                 Valente (politically exposed) through VG, KY and JE (3
 *                 layers, 33.6), and Gareth Holloway through KY and JE (2
 *                 layers, 22.4).
 */
MATCH path = (p:Person)-[:OWNS*2..6]->(e:LegalEntity)
WHERE all(n IN nodes(path) WHERE single(m IN nodes(path) WHERE m = n))
  AND EXISTS { (e)-[:INCORPORATED_IN]->(:Jurisdiction {isOffshoreCentre: false}) }
WITH p, e, path,
     [n IN nodes(path)[1..-1] | [(n)-[:INCORPORATED_IN]->(j:Jurisdiction) | j][0]] AS layerJurisdictions
WITH p, e, path, layerJurisdictions,
     size([j IN layerJurisdictions WHERE j.isOffshoreCentre]) AS offshoreLayers
WHERE offshoreLayers >= $minOffshoreLayers
RETURN p.name AS person, p.isPoliticallyExposed AS politicallyExposed, e.name AS entity,
       [i IN range(1, length(path) - 1) | nodes(path)[i].name + ' (' + layerJurisdictions[i - 1].jurisdictionId + ')'] AS chain,
       offshoreLayers,
       round(reduce(x = 100.0, r IN relationships(path) | x * r.percentage / 100.0), 2) AS effectivePct
ORDER BY offshoreLayers DESC, effectivePct DESC
```

## Shared registered addresses

```cypher
/*
 * @name           Shared registered addresses
 * @description    Finds registered addresses used by many legal entities
 *                 and shows who directs them: the jurisdictions involved,
 *                 the number of distinct directors, and the directors who
 *                 hold the most seats among those entities.
 * @params         minEntities - Minimum number of entities registered at the
 *                     address. Start at 10 and lower it until the result is
 *                     no longer dominated by ordinary group headquarters.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per address: addressId, address, entities (count),
 *                 jurisdictions (of incorporation), directors (distinct),
 *                 and busiestDirectors as "name (seats here)", top three.
 *                 Ordered by entities descending.
 * @usage          Formation agents, virtual offices and group headquarters
 *                 all host many entities; what separates them is who sits
 *                 on the boards. Many unrelated entities sharing a handful
 *                 of directors points to nominee directors and shelf
 *                 companies. Addresses must be standardised so that one
 *                 building is one Address node.
 * @tags           address, formation agent, nominee director, shell company
 * @sample         Bundled sample data only: $minEntities = 10 returns 3 rows
 *                 — Coralstone Chambers, Road Town (24 entities, VG, 3
 *                 directors, Andreas Christodoulou on 19); Takamaka House,
 *                 Victoria (14, SC, Marie-Claire Pillay on 11); Seagrape
 *                 Place, George Town (11, KY, Desmond Ellery on 10).
 */
MATCH (a:Address)<-[:REGISTERED_AT]-(e:LegalEntity)
WITH a, collect(e) AS entities
WHERE size(entities) >= $minEntities
CALL {
  WITH entities
  UNWIND entities AS e
  MATCH (d:Person)-[:DIRECTOR_OF]->(e)
  WITH d, count(e) AS seatsHere
  ORDER BY seatsHere DESC, d.name
  RETURN count(d) AS directors, collect(d.name + ' (' + toString(seatsHere) + ')')[..3] AS busiestDirectors
}
RETURN a.addressId AS addressId, a.street + ', ' + a.city + ', ' + a.countryCode AS address,
       size(entities) AS entities,
       COLLECT { UNWIND entities AS x MATCH (x)-[:INCORPORATED_IN]->(j:Jurisdiction)
                 RETURN DISTINCT j.jurisdictionId } AS jurisdictions,
       directors, busiestDirectors
ORDER BY entities DESC
```

## Reported versus ownership-derived parent

```cypher
/*
 * @name           Reported versus ownership-derived parent
 * @description    Compares the ultimate parent each entity reports with the
 *                 top of its chain of majority ownership, and lists every
 *                 disagreement: a reported parent that differs from the
 *                 ownership chain, a reported parent with no majority owner
 *                 behind it, and an LEI-registered entity with a majority
 *                 corporate owner that reports no parent at all.
 * @params         controlPct - OWNS.percentage each link must exceed to
 *                     count as consolidating control. Start at 50, a
 *                     majority stake.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per disagreement: entityId, name,
 *                 reportedUltimateParent, ownershipUltimateParent, and issue
 *                 — 'differs', 'no majority owner' or 'not reported'.
 *                 Ordered by issue, then name.
 * @usage          Reported parents follow accounting consolidation, which
 *                 usually but not always tracks majority ownership, and they
 *                 go stale after acquisitions and disposals. Each row is a
 *                 record to check against filings, not a finding. The
 *                 ownership chain is followed up to eight hops.
 * @tags           LEI, consolidation, ultimate parent, data quality
 * @sample         Bundled sample data only: $controlPct = 50 returns 9 rows
 *                 — 5 'differs' (Fenmarsh Industries Ltd's subsidiaries,
 *                 which still report it although Wealdmoor Group plc owns
 *                 it), 1 'no majority owner' (Eichenfeld Medizintechnik
 *                 GmbH), and 3 'not reported' (Fenmarsh Industries Ltd,
 *                 Larkspur Freight Ltd, Lavandière Iberia S.L.).
 */
MATCH (e:LegalEntity)
WHERE EXISTS { (e)-[:ULTIMATELY_CONSOLIDATED_BY]->(:LegalEntity) }
   OR (coalesce(e.lei, '') <> ''
       AND EXISTS { (:LegalEntity)-[r:OWNS]->(e) WHERE r.percentage > $controlPct })
OPTIONAL MATCH (e)-[:ULTIMATELY_CONSOLIDATED_BY]->(reported:LegalEntity)
OPTIONAL MATCH chain = (top:LegalEntity)-[:OWNS*1..8]->(e)
WHERE all(r IN relationships(chain) WHERE r.percentage > $controlPct)
  AND all(n IN nodes(chain) WHERE single(m IN nodes(chain) WHERE m = n))
  AND NOT EXISTS { (:LegalEntity)-[o:OWNS]->(top) WHERE o.percentage > $controlPct }
WITH e, reported, top
WHERE reported IS NULL OR top IS NULL OR reported <> top
RETURN e.entityId AS entityId, e.name AS name,
       reported.name AS reportedUltimateParent, top.name AS ownershipUltimateParent,
       CASE WHEN reported IS NULL THEN 'not reported'
            WHEN top IS NULL THEN 'no majority owner'
            ELSE 'differs' END AS issue
ORDER BY issue, name
```

## How two entities are connected

```cypher
/*
 * @name           How two entities are connected
 * @description    Finds the shortest connections between two legal entities
 *                 through ownership, board seats, offices, trust roles and
 *                 shared addresses, in either direction — the link between
 *                 a buyer and a supplier, or between two counterparties
 *                 that should be independent.
 * @params         fromEntityId - LegalEntity.entityId of the first entity.
 *                 toEntityId - LegalEntity.entityId of the second entity.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per shortest path: the path (for Browser or Bloom
 *                 to draw), hops, and via (every node's name, or street and
 *                 city for an address, in order).
 * @usage          All shortest paths up to eight hops, ignoring direction.
 *                 INCORPORATED_IN and ESTABLISHED_IN are left out because a
 *                 shared jurisdiction connects almost everything. A short
 *                 path through a person who is an officer of one entity and
 *                 an owner of the other is a conflict of interest to check;
 *                 a path through a formation agent's address or a trust
 *                 company is usually not meaningful on its own.
 * @tags           connection, shortest path, conflict of interest, related party
 * @sample         Bundled sample data only: $fromEntityId = 'E-0168'
 *                 (Pellingham Retail Group plc), $toEntityId = 'E-0218'
 *                 (Larkspur Freight Ltd) returns 2 paths of 4 hops, one
 *                 through each of Gareth Holloway's seats at Pellingham
 *                 (executive director, chief financial officer): he owns
 *                 40.0% of Blue Lantern Holdings Ltd, which owns Saint Ouen
 *                 Investments Ltd, which owns Larkspur Freight Ltd.
 */
MATCH (a:LegalEntity {entityId: $fromEntityId}), (b:LegalEntity {entityId: $toEntityId})
MATCH path = allShortestPaths((a)-[:OWNS|DIRECTOR_OF|OFFICER_OF|TRUSTOR_OF|TRUSTEE_OF|BENEFICIARY_OF|REGISTERED_AT|RESIDES_AT*..8]-(b))
RETURN path, length(path) AS hops,
       [n IN nodes(path) | coalesce(n.name, n.street + ', ' + n.city)] AS via
```

## Node-key constraints

Import creates these from the `key: true` properties in `ONTOLOGY.json`. They are listed here to check the live database (`SHOW CONSTRAINTS`), not to be run: recreating them conflicts with the constraints Import already made.

```cypher
CREATE CONSTRAINT person_personId_key IF NOT EXISTS FOR (n:Person) REQUIRE n.personId IS NODE KEY;
CREATE CONSTRAINT legal_entity_entityId_key IF NOT EXISTS FOR (n:LegalEntity) REQUIRE n.entityId IS NODE KEY;
CREATE CONSTRAINT trust_trustId_key IF NOT EXISTS FOR (n:Trust) REQUIRE n.trustId IS NODE KEY;
CREATE CONSTRAINT jurisdiction_jurisdictionId_key IF NOT EXISTS FOR (n:Jurisdiction) REQUIRE n.jurisdictionId IS NODE KEY;
CREATE CONSTRAINT address_addressId_key IF NOT EXISTS FOR (n:Address) REQUIRE n.addressId IS NODE KEY;
```
