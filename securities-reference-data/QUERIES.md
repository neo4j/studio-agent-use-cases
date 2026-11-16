# Securities Reference Data — Queries

Runnable Cypher for the reference ontology in `ONTOLOGY.json`, simplest first.

## Prerequisites

- Neo4j 5.23 or later (including Aura and 2025.x releases), Cypher 5. The queries use `COLLECT {}` subqueries and the `CALL (x) { … }` variable-scope clause. No APOC or GDS.
- The reference ontology imported through the Import flow, either from the bundled sample CSVs or from the user's own data mapped onto it. No post-import setup is needed, and no query writes to the database.
- Dates are `ZONED DATETIME` values at midnight UTC. Date parameters (`$asOf`) are ISO strings such as `'2026-10-30'`, converted with `datetime()` before comparison.
- Weights (`HOLDS.weightPct`) are percentages of a fund's total net assets, 0–100. Look-through weight multiplies the weights along a chain of fund units.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit. Identifiers held as properties on the security (an `isin` column) rather than as `Identifier` nodes still support resolution, but not the shared-identifier check.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Resolve a security by identifier

```cypher
/*
 * @name           Resolve a security by identifier
 * @description    Finds the security carrying a market identifier (ISIN,
 *                 CUSIP, SEDOL, Valoren, Common Code, FIGI or any other
 *                 scheme), with its issuer, the issuer's ultimate parent,
 *                 every other identifier the security carries and its active
 *                 exchange listings.
 * @params         scheme - Identification scheme, spelled as in
 *                     Identifier.scheme, e.g. 'ISIN' or 'CUSIP'.
 *                 value - The identifier exactly as issued, upper case,
 *                     no separators.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per security carrying the identifier: securityId,
 *                 security, type, currency, issuer, ultimateParent,
 *                 identifiers (scheme and value), activeListings (MIC and
 *                 ticker). More than one row means the identifier is shared
 *                 by several securities — a data-quality defect.
 * @usage          The entry point for any question that starts from an
 *                 identifier in a trade, a holdings file or a vendor feed.
 *                 Matching on scheme and value scans Identifier nodes; on a
 *                 large database match on identifierId (scheme, a colon, the
 *                 value), which the node key indexes. The ultimate-parent
 *                 walk is bounded at eight levels of DIRECTLY_CONSOLIDATED_BY.
 * @tags           identifier, isin, cusip, sedol, security master, lookup
 * @sample         Bundled sample data only: $scheme = 'ISIN', $value =
 *                 'CH0713286208' returns 1 row: SEC-00426, Ingleby
 *                 Communications Ordinary Shares, with 3 identifiers
 *                 (FIGI, ISIN, Valoren 71328620) and 2 active listings,
 *                 XLON:IC and XSWX:IC.
 */
MATCH (i:Identifier {scheme: $scheme, value: $value})<-[:IDENTIFIED_BY]-(s:Security)-[:ISSUED_BY]->(issuer:LegalEntity)
OPTIONAL MATCH (issuer)-[:DIRECTLY_CONSOLIDATED_BY*1..8]->(top:LegalEntity)
  WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
RETURN s.securityId AS securityId, s.name AS security, s.securityType AS type, s.currency AS currency,
       issuer.name AS issuer, coalesce(top.name, issuer.name) AS ultimateParent,
       COLLECT { MATCH (s)-[:IDENTIFIED_BY]->(o:Identifier) RETURN o.scheme + ' ' + o.value ORDER BY o.scheme, o.value } AS identifiers,
       COLLECT { MATCH (x:Exchange)<-[:LISTED_ON]-(l:Listing)-[:LISTS]->(s) WHERE l.delistingDate IS NULL
                 RETURN x.mic + ':' + coalesce(l.ticker, '') ORDER BY x.mic } AS activeListings
ORDER BY securityId
```

## Ticker at a date

```cypher
/*
 * @name           Ticker at a date
 * @description    Resolves a ticker symbol on one exchange to the security
 *                 it identified on a given date. Tickers are unique within an
 *                 exchange at any one time but reassignable, so the same
 *                 ticker can name different securities in different periods.
 * @params         mic - ISO 10383 Market Identifier Code of the exchange,
 *                     e.g. 'XNYS'.
 *                 ticker - Ticker symbol as used on that exchange.
 *                 asOf - Date to resolve at, as an ISO string 'YYYY-MM-DD'.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per listing active on the date (normally one):
 *                 securityId, security, issuer, listed, delisted, and
 *                 otherHolders — every other security that has held the
 *                 ticker on this exchange, with its listing period.
 * @usage          A listing is active from listingDate up to, but not
 *                 including, delistingDate. Use the trade date or position
 *                 date of the record being resolved, never today's date, when
 *                 reconciling historical data. An empty result means no
 *                 listing used the ticker on that date; otherHolders on a
 *                 non-empty result shows the ticker has been reassigned.
 * @tags           ticker, listing, point in time, exchange, reconciliation
 * @sample         Bundled sample data only: $mic = 'XNYS', $ticker = 'KVR',
 *                 $asOf = '2017-05-01' returns 1 row: SEC-00543, Kestrel
 *                 Vale Resources Common Stock (listed 2008-04-14, delisted
 *                 2019-06-28), with Korvara Robotics Common Stock as the
 *                 other holder. With $asOf = '2023-01-01' it returns Korvara
 *                 Robotics instead.
 */
MATCH (x:Exchange {mic: $mic})<-[:LISTED_ON]-(l:Listing {ticker: $ticker})-[:LISTS]->(s:Security)-[:ISSUED_BY]->(e:LegalEntity)
WHERE l.listingDate <= datetime($asOf)
  AND (l.delistingDate IS NULL OR l.delistingDate > datetime($asOf))
RETURN s.securityId AS securityId, s.name AS security, e.name AS issuer,
       date(l.listingDate) AS listed, date(l.delistingDate) AS delisted,
       COLLECT { MATCH (x)<-[:LISTED_ON]-(o:Listing {ticker: $ticker})-[:LISTS]->(os:Security) WHERE o <> l
                 RETURN os.name + ' (' + toString(date(o.listingDate)) + ' to ' +
                        coalesce(toString(date(o.delistingDate)), 'present') + ')' ORDER BY o.listingDate } AS otherHolders
```

## Listings of a security

```cypher
/*
 * @name           Listings of a security
 * @description    Every exchange listing of one security, past and present:
 *                 exchange, ticker, whether it is the home (primary) market,
 *                 and the listing period.
 * @params         securityId - The security's identifier, e.g. one returned
 *                     by Resolve a security by identifier.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per listing: mic, exchange, ticker, isPrimary,
 *                 listed, delisted, status ('active' or 'delisted'), primary
 *                 listing first.
 * @usage          A security normally has at most one active primary
 *                 listing; more than one, or none while secondary listings
 *                 are active, is worth raising with whoever maintains the
 *                 security master. Bond listings often carry no ticker.
 * @tags           listing, exchange, ticker, mic, home exchange
 * @sample         Bundled sample data only: $securityId = 'SEC-00105'
 *                 (Tsukimi Foods Ordinary Shares) returns 2 rows: XTKS
 *                 ticker 5592, primary, active; XLON ticker TF, secondary,
 *                 active.
 */
MATCH (s:Security {securityId: $securityId})<-[:LISTS]-(l:Listing)-[:LISTED_ON]->(x:Exchange)
RETURN x.mic AS mic, x.name AS exchange, l.ticker AS ticker, l.isPrimary AS isPrimary,
       date(l.listingDate) AS listed, date(l.delistingDate) AS delisted,
       CASE WHEN l.delistingDate IS NULL THEN 'active' ELSE 'delisted' END AS status
ORDER BY isPrimary DESC, listed
```

## Identifiers shared by several securities

```cypher
/*
 * @name           Identifiers shared by several securities
 * @description    Finds market identifiers attached to more than one
 *                 security. An identifier is expected to identify exactly
 *                 one security, so each hit is a security-master defect: a
 *                 vendor mapping error, a CUSIP keyed against the wrong
 *                 tranche, a local share's SEDOL copied onto its depositary
 *                 receipt.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per shared identifier: scheme, value, and
 *                 securities (securityId, name, type and issuer of each
 *                 security carrying it), ordered by scheme and value.
 * @usage          The same value under two different schemes is two
 *                 identifiers and is not reported. Fix the mapping at its
 *                 source rather than in the graph, then re-import.
 * @tags           identifier, data quality, reconciliation, security master
 * @sample         Bundled sample data only: returns 2 rows — CUSIP
 *                 240345520 on two Ostrander Energy senior notes (SEC-00548,
 *                 SEC-00549) and SEDOL HBX4BB7 on Wexcombe Breweries
 *                 Ordinary Shares (SEC-00055) and its depositary receipt
 *                 (SEC-00528).
 */
MATCH (i:Identifier)<-[:IDENTIFIED_BY]-(s:Security)
WITH i, collect(s) AS secs
WHERE size(secs) > 1
UNWIND secs AS s
MATCH (s)-[:ISSUED_BY]->(e:LegalEntity)
WITH i, s, e ORDER BY s.securityId
RETURN i.scheme AS scheme, i.value AS value,
       collect(s.securityId + ' ' + s.name + ' (' + s.securityType + ', ' + e.name + ')') AS securities
ORDER BY scheme, value
```

## ISIN inconsistent with national number

```cypher
/*
 * @name           ISIN inconsistent with national number
 * @description    Checks each ISIN against the national number carried by
 *                 the same security. An ISIN embeds, in characters 3 to 11,
 *                 the national number of the country in its prefix,
 *                 zero-padded on the left to nine characters: a CUSIP for US
 *                 and CA ISINs, a SEDOL for GB and IE, a Valoren for CH and
 *                 LI, and the Common Code for international XS ISINs. A
 *                 mismatch means one of the two identifiers is wrong.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per security and disagreeing national number:
 *                 securityId, security, isin, nsinInIsin (characters 3 to 11
 *                 of the ISIN), nationalScheme, nationalNumber.
 * @usage          Only the national scheme that matches the ISIN's prefix
 *                 is compared: a Regulation S bond's CINS, or a share's
 *                 SEDOL on a US ISIN, is ignored. ISINs from other countries
 *                 (DE, FR, JP, NL …) embed national numbers this reference
 *                 ontology does not name, so they are not checked; add a
 *                 CASE branch for each scheme the user's data carries (WKN
 *                 for DE). A security carrying two national numbers of the
 *                 same scheme is reported once for the one its ISIN does not
 *                 embed.
 * @tags           isin, cusip, sedol, data quality, reconciliation
 * @sample         Bundled sample data only: returns 3 rows — SEC-00054
 *                 Hollis & Crane Ordinary Shares (ISIN embeds a different
 *                 SEDOL), SEC-00552 Varnell Aerospace senior notes (ISIN
 *                 embeds a CUSIP with two digits transposed), and SEC-00549
 *                 Ostrander Energy senior notes (it also carries the shared
 *                 CUSIP 240345520, which its ISIN does not embed).
 */
MATCH (s:Security)-[:IDENTIFIED_BY]->(isin:Identifier {scheme: 'ISIN'})
WITH s, isin, substring(isin.value, 2, 9) AS embedded,
     CASE left(isin.value, 2)
       WHEN 'US' THEN 'CUSIP' WHEN 'CA' THEN 'CUSIP'
       WHEN 'GB' THEN 'SEDOL' WHEN 'IE' THEN 'SEDOL'
       WHEN 'CH' THEN 'Valoren' WHEN 'LI' THEN 'Valoren'
       WHEN 'XS' THEN 'Common Code'
     END AS nationalScheme
WHERE nationalScheme IS NOT NULL
MATCH (s)-[:IDENTIFIED_BY]->(n:Identifier {scheme: nationalScheme})
WHERE right('000000000' + n.value, 9) <> embedded
RETURN s.securityId AS securityId, s.name AS security, isin.value AS isin, embedded AS nsinInIsin,
       n.scheme AS nationalScheme, n.value AS nationalNumber
ORDER BY securityId, nationalNumber
```

## Active listings of matured securities

```cypher
/*
 * @name           Active listings of matured securities
 * @description    Finds listings with no delisting date whose security
 *                 matured on or before a given date. A matured bond has been
 *                 repaid and should have been delisted; an active listing for
 *                 it is a stale record that can misprice holdings or route
 *                 orders to an instrument that no longer exists.
 * @params         asOf - Date to test against, as an ISO string
 *                     'YYYY-MM-DD'. Start at the date of the data snapshot
 *                     being checked.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per stale listing: securityId, security, matured
 *                 (the maturity date), mic, listingId, ordered by maturity.
 * @usage          Securities with no maturity date (shares, fund units,
 *                 perpetuals) are never reported. Allow a few days' grace
 *                 after maturity before treating a hit as a defect: exchanges
 *                 delist on their own timetable.
 * @tags           listing, maturity, data quality, stale data, bonds
 * @sample         Bundled sample data only: $asOf = '2026-10-30' returns
 *                 2 rows — Tessaly Water senior notes matured 2024-07-15
 *                 (XLON) and Rostova Shipping Finance senior notes matured
 *                 2025-03-03 (XLUX).
 */
MATCH (x:Exchange)<-[:LISTED_ON]-(l:Listing)-[:LISTS]->(s:Security)
WHERE l.delistingDate IS NULL
  AND s.maturityDate IS NOT NULL
  AND s.maturityDate <= datetime($asOf)
RETURN s.securityId AS securityId, s.name AS security, date(s.maturityDate) AS matured,
       x.mic AS mic, l.listingId AS listingId
ORDER BY matured, securityId
```

## Issuer group capital structure

```cypher
/*
 * @name           Issuer group capital structure
 * @description    Climbs from any entity to its group's ultimate parent,
 *                 then lists every outstanding security issued anywhere in
 *                 the group — by the parent, financing subsidiaries and
 *                 their subsidiaries — ranked by claim in liquidation:
 *                 senior secured, senior unsecured, subordinated and junior
 *                 subordinated debt, then preferred and common shares.
 * @params         entityId - Any entity in the group: the parent, a
 *                     subsidiary or a financing vehicle.
 *                 asOf - Date at which a security counts as outstanding
 *                     (not yet matured), as an ISO string 'YYYY-MM-DD'.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per outstanding security: ultimateParent, issuer,
 *                 securityId, security, type, seniority, currency,
 *                 faceAmountOutstanding (debt, in units of its currency),
 *                 maturity; ranked by seniority, then maturity.
 * @usage          Both walks are bounded at eight levels of
 *                 DIRECTLY_CONSOLIDATED_BY, deeper than most corporate
 *                 groups. Face amounts are in each security's own currency
 *                 and are not summed across currencies. Depositary receipts
 *                 on the group's shares are issued by the depositary, not the
 *                 group: use Routes to an issuer group to include them.
 * @tags           issuer, capital structure, seniority, corporate group, debt
 * @sample         Bundled sample data only: $entityId = 'LE-0480'
 *                 (Halvorsen Capital LLC) and $asOf = '2026-10-30' return 7
 *                 rows for Halvorsen Industrie AG: 1 senior secured, 2 senior
 *                 unsecured, 1 subordinated and 1 junior subordinated note,
 *                 then the preferred and the ordinary shares, issued by three
 *                 group entities.
 */
MATCH (e:LegalEntity {entityId: $entityId})-[:DIRECTLY_CONSOLIDATED_BY*0..8]->(top:LegalEntity)
WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
MATCH (top)<-[:DIRECTLY_CONSOLIDATED_BY*0..8]-(member:LegalEntity)<-[:ISSUED_BY]-(s:Security)
WHERE s.maturityDate IS NULL OR s.maturityDate > datetime($asOf)
RETURN top.name AS ultimateParent, member.name AS issuer, s.securityId AS securityId, s.name AS security,
       s.securityType AS type, s.seniority AS seniority, s.currency AS currency,
       s.faceAmountOutstanding AS faceAmountOutstanding, date(s.maturityDate) AS maturity
ORDER BY CASE s.seniority
           WHEN 'senior secured' THEN 1 WHEN 'senior unsecured' THEN 2
           WHEN 'subordinated' THEN 3 WHEN 'junior subordinated' THEN 4
           ELSE CASE s.securityType WHEN 'preferred share' THEN 5 ELSE 6 END
         END, maturity, securityId
```

## Routes to an issuer group

```cypher
/*
 * @name           Routes to an issuer group
 * @description    Every security that carries economic exposure to an issuer
 *                 group: the securities the group's entities issued; the
 *                 depositary receipts that represent the group's shares,
 *                 issued by a depositary bank outside the group; and
 *                 convertible or exchangeable securities issued outside the
 *                 group that convert into the group's securities.
 * @params         entityId - Any entity in the group.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per security and route: ultimateParent, route
 *                 ('issued by group', 'depositary receipt' or 'convertible
 *                 from outside the group'), securityId, security, type,
 *                 issuer, via (the group security a receipt or convertible
 *                 links to), ordered by route.
 * @usage          This is the instrument universe to screen when the group
 *                 is restricted, sanctioned or under credit watch: an
 *                 issuer-name screen misses the second and third routes,
 *                 whose issuer is someone else. Matured securities are
 *                 included; filter on maturityDate if only live ones matter.
 *                 Both walks are bounded at eight levels.
 * @tags           issuer, exposure, depositary receipt, convertible, sanctions
 * @sample         Bundled sample data only: $entityId = 'LE-0482' (Kairo
 *                 Denki Holdings K.K.) returns 5 rows: 3 issued by the group
 *                 (ordinary shares, a Kairo Denki Finance B.V. note, a
 *                 convertible bond), the depositary receipt issued by
 *                 Harrowgate Depositary Trust Company, and the Sakuragi
 *                 Capital exchangeable bond.
 */
MATCH (e:LegalEntity {entityId: $entityId})-[:DIRECTLY_CONSOLIDATED_BY*0..8]->(top:LegalEntity)
WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
MATCH (top)<-[:DIRECTLY_CONSOLIDATED_BY*0..8]-(:LegalEntity)<-[:ISSUED_BY]-(gs:Security)
WITH top, collect(gs) AS groupSecs
UNWIND groupSecs AS gs
CALL (gs, groupSecs) {
  RETURN gs AS s, 'issued by group' AS route, null AS via
  UNION
  MATCH (dr:Security)-[:REPRESENTS]->(gs)
  RETURN dr AS s, 'depositary receipt' AS route, gs.name AS via
  UNION
  MATCH (cv:Security)-[:CONVERTIBLE_INTO]->(gs)
  WHERE NOT cv IN groupSecs
  RETURN cv AS s, 'convertible from outside the group' AS route, gs.name AS via
}
MATCH (s)-[:ISSUED_BY]->(issuer:LegalEntity)
RETURN top.name AS ultimateParent, route, s.securityId AS securityId, s.name AS security,
       s.securityType AS type, issuer.name AS issuer, via
ORDER BY route, securityId
```

## Fund look-through holdings

```cypher
/*
 * @name           Fund look-through holdings
 * @description    Expands a fund's holdings through the units of every fund
 *                 it holds, down to the underlying securities, and gives
 *                 each its look-through weight: the product of the weights
 *                 along the chain, summed where a security is reached by
 *                 several chains.
 * @params         fundId - The fund to look through.
 *                 limit - Maximum rows to return. Start at 25, the size of
 *                     a top-holdings page, and raise it for a full listing.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per underlying security, largest first:
 *                 securityId, security, type, issuer, lookThroughPct (percent
 *                 of the fund's net assets), directPct (held by the fund
 *                 itself), and minFundLayers (0 when the fund holds it
 *                 directly, 1 when only through another fund's units, and so
 *                 on).
 * @usage          The walk is bounded at seven relationships — three layers
 *                 of fund units below the fund — which covers funds of funds
 *                 and pension funds that hold them. Look-through weights are
 *                 only as current as the oldest reportingDate in the chain;
 *                 check the underlying funds' dates before relying on the
 *                 result. Depositary receipts are shown as held; Look-through
 *                 exposure by issuer group maps them to the underlying issuer.
 * @tags           fund, look-through, holdings, fund of funds, exposure
 * @sample         Bundled sample data only: $fundId = 'FND-002' (Aldermoor
 *                 Global Allocation Fund of Funds), $limit = 25 returns 25
 *                 rows led by Kairo Denki Holdings Ordinary Shares at 7.1%
 *                 (3.5% direct plus 60% of the Aldermoor Japan Equity ETF's
 *                 6.0%).
 */
MATCH p = (f:Fund {fundId: $fundId})-[:HOLDS|UNIT_OF*1..7]->(s:Security)
WHERE NOT (s)-[:UNIT_OF]->(:Fund)
WITH s, size(relationships(p)) AS hops,
     reduce(w = 100.0, r IN relationships(p) |
       CASE WHEN type(r) = 'HOLDS' THEN w * r.weightPct / 100.0 ELSE w END) AS pct
MATCH (s)-[:ISSUED_BY]->(issuer:LegalEntity)
RETURN s.securityId AS securityId, s.name AS security, s.securityType AS type, issuer.name AS issuer,
       round(sum(pct), 4) AS lookThroughPct,
       round(sum(CASE WHEN hops = 1 THEN pct ELSE 0.0 END), 4) AS directPct,
       min((hops - 1) / 2) AS minFundLayers
ORDER BY lookThroughPct DESC, securityId
LIMIT $limit
```

## Look-through exposure by issuer group

```cypher
/*
 * @name           Look-through exposure by issuer group
 * @description    Aggregates a fund's look-through holdings by the ultimate
 *                 parent of each security's issuer, so that shares, bonds of
 *                 financing subsidiaries, depositary receipts (mapped to the
 *                 underlying share's issuer) and holdings inside other funds
 *                 all count toward the same issuer group.
 * @params         fundId - The fund to analyse.
 *                 limit - Maximum issuer groups to return. Start at 10, the
 *                     usual length of a top-exposures report.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per issuer group, largest first: groupId,
 *                 issuerGroup, sector, lookThroughPct (percent of the fund's
 *                 net assets), directPct (the part held by the fund itself),
 *                 securities (distinct securities contributing).
 * @usage          A group whose lookThroughPct is far above its directPct is
 *                 reached mostly through other funds and is invisible in the
 *                 fund's own holdings report. Convertibles count toward their
 *                 issuer's group, not the group they convert into. Bounded at
 *                 seven relationships of HOLDS and UNIT_OF and eight levels of
 *                 DIRECTLY_CONSOLIDATED_BY.
 * @tags           fund, look-through, issuer, concentration, exposure
 * @sample         Bundled sample data only: $fundId = 'FND-002', $limit =
 *                 10 returns 10 rows led by Kairo Denki Holdings K.K. at 10.7%
 *                 look-through against 3.5% direct, from 4 securities.
 */
MATCH p = (f:Fund {fundId: $fundId})-[:HOLDS|UNIT_OF*1..7]->(s:Security)
WHERE NOT (s)-[:UNIT_OF]->(:Fund)
WITH s, size(relationships(p)) AS hops,
     reduce(w = 100.0, r IN relationships(p) |
       CASE WHEN type(r) = 'HOLDS' THEN w * r.weightPct / 100.0 ELSE w END) AS pct
OPTIONAL MATCH (s)-[:REPRESENTS]->(u:Security)
WITH s, hops, pct, coalesce(u, s) AS exposed
MATCH (exposed)-[:ISSUED_BY]->(issuer:LegalEntity)
OPTIONAL MATCH (issuer)-[:DIRECTLY_CONSOLIDATED_BY*1..8]->(top:LegalEntity)
  WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
WITH coalesce(top, issuer) AS grp, s, hops, pct
RETURN grp.entityId AS groupId, grp.name AS issuerGroup, grp.sector AS sector,
       round(sum(pct), 4) AS lookThroughPct,
       round(sum(CASE WHEN hops = 1 THEN pct ELSE 0.0 END), 4) AS directPct,
       count(DISTINCT s) AS securities
ORDER BY lookThroughPct DESC, groupId
LIMIT $limit
```

## Look-through concentration breaches

```cypher
/*
 * @name           Look-through concentration breaches
 * @description    Screens every fund for issuer groups whose look-through
 *                 exposure exceeds a single-issuer limit, aggregating shares,
 *                 bonds, depositary receipts and other funds' holdings to the
 *                 ultimate parent. Government issuers are excluded, as
 *                 diversification rules treat sovereign debt separately.
 * @params         limitPct - Single-issuer limit, in percent of a fund's net
 *                     assets. Start at 10, the ceiling diversified-fund
 *                     regimes such as UCITS set for one issuer, and lower it
 *                     to see what is approaching the limit.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per fund and issuer group over the limit, largest
 *                 first: fundId, fund, fundType, issuerGroup,
 *                 lookThroughPct, directPct (held by the fund itself,
 *                 already aggregated to the group), largestSecurityPct (the
 *                 largest single security's look-through weight) and
 *                 securities.
 * @usage          The breaches that matter most are those no single-line
 *                 check sees: directPct under the limit (exposure through
 *                 other funds), or largestSecurityPct well under it
 *                 (exposure split across shares, receipts and subsidiaries'
 *                 bonds). Treat results as a screen against the fund's own
 *                 limits, not a regulatory finding: actual rules differ by
 *                 regime, fund type and instrument. Scans every fund; anchor
 *                 it to a list of fundIds on a large database.
 * @tags           fund, concentration, limit, look-through, compliance
 * @sample         Bundled sample data only: $limitPct = 10 returns 2 rows —
 *                 FND-002 Aldermoor Global Allocation Fund of Funds in Kairo
 *                 Denki Holdings K.K. at 10.7% (3.5% direct) and FND-006
 *                 Northgate Global Leaders Fund in Calder Brennan plc at 10.5%
 *                 (largest security 4.0%).
 */
MATCH p = (f:Fund)-[:HOLDS|UNIT_OF*1..7]->(s:Security)
WHERE NOT (s)-[:UNIT_OF]->(:Fund)
WITH f, s, size(relationships(p)) AS hops,
     reduce(w = 100.0, r IN relationships(p) |
       CASE WHEN type(r) = 'HOLDS' THEN w * r.weightPct / 100.0 ELSE w END) AS pct
OPTIONAL MATCH (s)-[:REPRESENTS]->(u:Security)
WITH f, s, hops, pct, coalesce(u, s) AS exposed
MATCH (exposed)-[:ISSUED_BY]->(issuer:LegalEntity)
OPTIONAL MATCH (issuer)-[:DIRECTLY_CONSOLIDATED_BY*1..8]->(top:LegalEntity)
  WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
WITH f, coalesce(top, issuer) AS grp, s,
     sum(pct) AS secPct, sum(CASE WHEN hops = 1 THEN pct ELSE 0.0 END) AS secDirect
WHERE coalesce(grp.sector, '') <> 'Government'
WITH f, grp, sum(secPct) AS lookThrough, sum(secDirect) AS direct, max(secPct) AS largest, count(s) AS securities
WHERE lookThrough > $limitPct
RETURN f.fundId AS fundId, f.name AS fund, f.fundType AS fundType, grp.name AS issuerGroup,
       round(lookThrough, 4) AS lookThroughPct, round(direct, 4) AS directPct,
       round(largest, 4) AS largestSecurityPct, securities
ORDER BY lookThroughPct DESC, fundId
```

## Affiliated underwriting

```cypher
/*
 * @name           Affiliated underwriting
 * @description    Finds fund holdings of securities whose offering was
 *                 underwritten by an entity in the same corporate group as
 *                 the fund's manager. A manager buying the deals its own
 *                 group's bank underwrote is a conflict of interest that many
 *                 regimes restrict or require to be documented.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per holding, offering and affiliated underwriter:
 *                 fund, manager, group (their shared ultimate parent),
 *                 underwriter, role, offeringId, closed, securityId,
 *                 security, weightPct.
 * @usage          The holding records a position at the fund's reporting
 *                 date, not a purchase in the offering itself; confirm from
 *                 trade records whether the fund bought during the offering
 *                 before treating a hit as a breach. Affiliation is common
 *                 ultimate parent through DIRECTLY_CONSOLIDATED_BY, bounded
 *                 at eight levels; minority stakes and joint ventures are
 *                 not seen. Considers direct holdings only.
 * @tags           fund, underwriting, conflict of interest, affiliate, compliance
 * @sample         Bundled sample data only: returns 3 rows, all under
 *                 Brookline Financial Group plc — Brookline Sterling
 *                 Corporate Bond Fund holding a Larchmont Insurance
 *                 subordinated note and a Tessaly Water senior secured note
 *                 bookrun by Brookline Capital Markets Limited, and Brookline
 *                 Global Equity Fund holding Pellucid Health Common Stock
 *                 co-managed by Brookline Securities LLC.
 */
MATCH (f:Fund)-[:MANAGED_BY]->(m:LegalEntity)-[:DIRECTLY_CONSOLIDATED_BY*0..8]->(top:LegalEntity)
WHERE NOT (top)-[:DIRECTLY_CONSOLIDATED_BY]->()
MATCH (f)-[h:HOLDS]->(s:Security)<-[:OFFERS]-(o:Offering)-[u:UNDERWRITTEN_BY]->(uw:LegalEntity)
WHERE EXISTS { (uw)-[:DIRECTLY_CONSOLIDATED_BY*0..8]->(top) }
RETURN f.name AS fund, m.name AS manager, top.name AS group, uw.name AS underwriter, u.role AS role,
       o.offeringId AS offeringId, date(o.closingDate) AS closed,
       s.securityId AS securityId, s.name AS security, h.weightPct AS weightPct
ORDER BY fund, securityId, underwriter
```

## Node-key constraints

Import creates these from the `key: true` properties in `ONTOLOGY.json`. They are listed here to check the live database with `SHOW CONSTRAINTS`, not to be created by hand.

```cypher
CREATE CONSTRAINT entityId_LegalEntity_key IF NOT EXISTS FOR (n:LegalEntity) REQUIRE (n.entityId) IS NODE KEY;
CREATE CONSTRAINT securityId_Security_key IF NOT EXISTS FOR (n:Security) REQUIRE (n.securityId) IS NODE KEY;
CREATE CONSTRAINT identifierId_Identifier_key IF NOT EXISTS FOR (n:Identifier) REQUIRE (n.identifierId) IS NODE KEY;
CREATE CONSTRAINT mic_Exchange_key IF NOT EXISTS FOR (n:Exchange) REQUIRE (n.mic) IS NODE KEY;
CREATE CONSTRAINT listingId_Listing_key IF NOT EXISTS FOR (n:Listing) REQUIRE (n.listingId) IS NODE KEY;
CREATE CONSTRAINT fundId_Fund_key IF NOT EXISTS FOR (n:Fund) REQUIRE (n.fundId) IS NODE KEY;
CREATE CONSTRAINT offeringId_Offering_key IF NOT EXISTS FOR (n:Offering) REQUIRE (n.offeringId) IS NODE KEY;
```
