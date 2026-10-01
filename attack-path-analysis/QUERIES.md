# Attack Path Analysis — Queries

Runnable Cypher for the model in `GRAPH_MODEL.json`. The queries move outward
from a single exposure to a whole route: which exposed hosts are worth
attacking, where an attacker could go from one, what the route terminates at,
and which hosts most routes depend on.

## Prerequisites

- **Neo4j 5.x or later, Cypher 5.** No APOC and no GDS: every query below is
  plain Cypher. Graph Data Science would be the better tool for choke-point
  ranking on a large estate — see the `@usage` note on *Choke points on
  crown-jewel attack paths* — but nothing here requires it.
- The model imported from `GRAPH_MODEL.json`, either with the bundled CSVs or
  with the user's own data mapped onto the same model.
- The index in `SETUP.md` is recommended, not required. Without it the
  crown-jewel queries scan the `Application` label instead of seeking; results
  are identical.
- **Temporal properties are `ZONED DATETIME`.** `CVE.publishedDate` and
  `HAS_VULNERABILITY.detectedOn` both carry a zoned datetime whose time is always
  midnight UTC, because the Import tool does not accept a bare date for local CSV
  loads. Only the calendar date is meaningful. No query below filters on either,
  but one you add should compare with `datetime($value)`, not `date($value)`.
- **Variable-length bounds cannot be parameterised in Cypher.** Every traversal
  below carries a literal ceiling in the pattern and a `$maxLateralHops` filter
  inside it. The parameter tunes the bound; the literal is the hard limit. To
  search beyond the ceiling, edit the literal in the pattern — and expect the
  cost to climb steeply when you do.

## Adapting these queries

These queries assume the model in `GRAPH_MODEL.json`. When the user's schema
differs — their own model, a modified one, or a database that predates this
package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`)
   rather than assuming this model applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart
   means the pattern below it has no analogue — say so rather than forcing a
   fit.
3. Rewrite from the pattern, and update the annotation block to describe what
   the rewritten query actually does.

The role to check first is the reachability edge. A model that records network
topology as shared-segment membership rather than as a directed permission
between two hosts cannot answer any of the path questions below without first
deriving that edge, and deriving it from segment membership alone overstates
reachability in both directions.

## Exposed hosts carrying an exploited vulnerability

```cypher
/*
 * @name           Exposed hosts carrying an exploited vulnerability
 * @description    Returns compute instances that are reachable from the public
 *                 internet through an endpoint and carry a CVE that is listed
 *                 in the CISA Known Exploited Vulnerabilities catalogue at or
 *                 above a CVSS v3.1 base score threshold. These are the
 *                 candidate footholds every other query in this file starts
 *                 from.
 * @params         minCvss - Minimum CVSS v3.1 base score, 0.0 to 10.0. Start at
 *                     9.0, the lower bound of the CRITICAL band, and lower it
 *                     if the result is too small to be interesting. The query
 *                     already restricts to observed-in-the-wild exploitation,
 *                     so the score is a second filter on an already narrow set
 *                     and 7.0 is often a reasonable widening.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per exposed instance and qualifying CVE: instance
 *                 identifier, hostname, environment, network segment, the
 *                 public names and ports it is exposed on, the CVE identifier
 *                 with its CVSS and EPSS scores, and the date a scan last
 *                 confirmed the finding.
 * @usage          The starting point for triage, and deliberately not a
 *                 conclusion. A host appearing here is exposed and carries a
 *                 vulnerability known to be exploited; whether that matters
 *                 depends on where the host can go next, which this query does
 *                 not ask. Read the environment column before escalating: an
 *                 exploitable host outside production is only material if a
 *                 path leads from it into production, which the crown-jewel and
 *                 kill-chain queries below test directly. EPSS is a likelihood
 *                 and CVSS a severity — a low CVSS with a high EPSS is a weak
 *                 flaw actively being used, and belongs in the queue.
 * @tags           exposure, foothold, vulnerability, kev, triage
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (e:Endpoint)-[:RESOLVES_TO]->(i:ComputeInstance)-[f:HAS_VULNERABILITY]->(v:CVE)
WHERE v.knownExploited = true
  AND v.cvssScore >= $minCvss
RETURN i.instanceId     AS instanceId,
       i.hostname       AS hostname,
       i.environment    AS environment,
       i.networkSegment AS networkSegment,
       collect(DISTINCT e.dnsName + ':' + toString(e.port)) AS exposedOn,
       v.cveId          AS cveId,
       v.cvssScore      AS cvssScore,
       v.epssScore      AS epssScore,
       v.severity       AS severity,
       f.detectedOn     AS lastConfirmed
ORDER BY cvssScore DESC, epssScore DESC, instanceId
```

## Attack paths from an exposed foothold to a crown-jewel application

```cypher
/*
 * @name           Attack paths from an exposed foothold to a crown-jewel application
 * @description    For every exposed instance carrying an exploited
 *                 vulnerability, returns the shortest directed CAN_REACH route
 *                 to an instance running an application in the given
 *                 criticality tier. A zero-hop result means the exposed host
 *                 runs the crown jewel itself.
 * @params         minCvss - Minimum CVSS v3.1 base score for the foothold
 *                     vulnerability. Start at 9.0, as in the foothold query.
 *                 crownJewelTier - Criticality tier that counts as a crown
 *                     jewel. Start at 'P0', the most critical band in this
 *                     model's encoding; substitute the top band of whatever
 *                     scheme the portfolio uses.
 *                 maxLateralHops - Maximum CAN_REACH hops between foothold and
 *                     crown-jewel host. Start at 4 and raise one hop at a time.
 *                     Each extra hop multiplies the routes considered by the
 *                     out-degree of the hosts at that depth, so both cost and
 *                     result size climb sharply; stop at the point where the
 *                     output is no longer reviewable by hand. The pattern's
 *                     literal ceiling is 8.
 * @prerequisites  None beyond the imported model. The Application.tier index in
 *                 SETUP.md improves the anchor lookup.
 * @returns        One row per foothold, foothold CVE and crown jewel: the
 *                 public name the foothold is exposed on, the foothold host and
 *                 its CVE, the crown-jewel application with its tier and host,
 *                 the number of lateral hops, and the route as a list of
 *                 hostnames.
 * @usage          The core kill-chain query, and the one whose output is worth
 *                 taking to an owner: it names an exposure, a target that
 *                 matters to the business, and the specific hosts in between.
 *                 CAN_REACH is directed, so a returned route is traversable in
 *                 the direction shown and says nothing about the reverse. It
 *                 asserts network permission and an exploitable entry point,
 *                 not that an attacker holds credentials for each hop — treat
 *                 the route as the maximum an attacker could attempt, not as a
 *                 completed intrusion. A foothold with several qualifying CVEs
 *                 produces a row per CVE, which is what tells you which flaw to
 *                 fix to break the path. Compare the result with the
 *                 crown-jewel exposure summary: a crown jewel absent from this
 *                 result is not necessarily safe, only unreached within the
 *                 current bound and threshold.
 * @tags           kill-chain, lateral-movement, crown-jewel, path, prioritisation
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (e:Endpoint)-[:RESOLVES_TO]->(entry:ComputeInstance)-[:HAS_VULNERABILITY]->(v:CVE)
WHERE v.knownExploited = true
  AND v.cvssScore >= $minCvss
MATCH (host:ComputeInstance)-[:RUNS]->(target:Application {tier: $crownJewelTier})
MATCH path = shortestPath((entry)-[:CAN_REACH*0..8]->(host))
WHERE length(path) <= $maxLateralHops
RETURN e.dnsName        AS exposedVia,
       entry.instanceId AS footholdInstanceId,
       entry.hostname   AS footholdHost,
       v.cveId          AS footholdCve,
       v.cvssScore      AS footholdCvss,
       target.name      AS crownJewel,
       target.tier      AS tier,
       target.businessUnit AS businessUnit,
       host.hostname    AS crownJewelHost,
       length(path)     AS lateralHops,
       [n IN nodes(path) | n.hostname] AS route
ORDER BY lateralHops ASC, footholdCvss DESC, crownJewel
```

## Lateral reachability from a compromised host

```cypher
/*
 * @name           Lateral reachability from a compromised host
 * @description    Returns every compute instance reachable from one named
 *                 instance by following CAN_REACH in its permitted direction,
 *                 with the fewest hops to each, the applications each reached
 *                 host runs, and the workload identity an attacker would
 *                 inherit on landing there.
 * @params         instanceId - The instance to treat as compromised. No default
 *                     applies: this is a selector, taken from the foothold
 *                     query's output or from an incident ticket.
 *                 maxLateralHops - Maximum CAN_REACH hops to follow. Start at 4
 *                     and raise one hop at a time, watching the result size;
 *                     the reachable set grows with the out-degree at each
 *                     depth. The pattern's literal ceiling is 8.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per reachable instance, ordered by hop distance: the
 *                 hop count, instance identifier, hostname, network segment,
 *                 the applications it runs with their tiers, and the identities
 *                 inheritable there. The origin instance is not returned.
 * @usage          Use during live response to answer what a confirmed
 *                 compromise puts at risk, and during design review to test
 *                 whether a segment boundary does what it is supposed to. The
 *                 hop count is the shortest route, so it is the optimistic
 *                 reading from the defender's point of view — a host at four
 *                 hops may also be reachable by several shorter-lived routes
 *                 that closing one rule will not remove. The identities column
 *                 is where network analysis stops being enough: an inherited
 *                 identity reaches whatever its policies allow with no further
 *                 lateral movement, so feed any identity returned here into the
 *                 blast-radius query rather than assuming the damage ends at
 *                 the host.
 * @tags           lateral-movement, blast-radius, incident-response, segmentation
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (origin:ComputeInstance {instanceId: $instanceId})
MATCH path = shortestPath((origin)-[:CAN_REACH*1..8]->(reached:ComputeInstance))
WHERE length(path) <= $maxLateralHops
WITH reached, length(path) AS hops
OPTIONAL MATCH (reached)-[:RUNS]->(app:Application)
OPTIONAL MATCH (reached)-[:RUNS_AS]->(identity:Identity)
RETURN hops,
       reached.instanceId     AS instanceId,
       reached.hostname       AS hostname,
       reached.networkSegment AS networkSegment,
       reached.environment    AS environment,
       collect(DISTINCT app.name + ' (' + app.tier + ')') AS applications,
       collect(DISTINCT identity.name) AS inheritableIdentities
ORDER BY hops ASC, hostname
```

## Blast radius of a compromised identity

```cypher
/*
 * @name           Blast radius of a compromised identity
 * @description    Returns every cloud service and business application one
 *                 identity can act on through the policies it holds, with the
 *                 highest permission level any of those policies grants and the
 *                 policies responsible.
 * @params         identityId - The identity to treat as compromised. No default
 *                     applies: this is a selector, taken from the reachability
 *                     query's inheritable-identities column or from the identity
 *                     provider.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per reachable resource, most sensitive first: the
 *                 identity name, whether the resource is a cloud service or an
 *                 application, its name, its data classification or criticality
 *                 tier as applicable, the highest permission level granted, and
 *                 the policies granting it.
 * @usage          This is the query that reframes a host compromise as a data
 *                 exposure. Nothing here depends on network reachability: an
 *                 identity reaches everything its policies allow, wherever the
 *                 resources sit, so a tightly segmented estate can still have a
 *                 wide blast radius. permissionLevel states the highest action a
 *                 policy permits on any resource it covers, so an 'admin' row
 *                 means the policy allows at least one administrative action
 *                 somewhere in its scope, not that every action on this
 *                 resource is administrative — read it as an upper bound and
 *                 confirm against the policy document before reporting it.
 *                 Comparing two identities' results is usually more informative
 *                 than either alone, since it shows which credential is the
 *                 over-privileged one.
 * @tags           blast-radius, identity, iam, exfiltration, least-privilege
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (identity:Identity {identityId: $identityId})-[:ASSUMES]->(policy:IAMPolicy)
MATCH (policy)-[:HAS_ACCESS_TO]->(resource)
WHERE resource:CloudService OR resource:Application
WITH identity, resource,
     collect(DISTINCT policy.name) AS grantedByPolicies,
     min(CASE policy.permissionLevel
           WHEN 'admin' THEN 0
           WHEN 'write' THEN 1
           ELSE 2 END) AS highestGrantRank,
     CASE resource.dataClassification
       WHEN 'restricted'   THEN 0
       WHEN 'confidential' THEN 1
       WHEN 'internal'     THEN 2
       WHEN 'public'       THEN 3
       ELSE 9 END AS sensitivityRank
RETURN identity.name               AS identityName,
       head(labels(resource))      AS resourceKind,
       resource.name               AS resourceName,
       resource.dataClassification AS dataClassification,
       resource.tier               AS applicationTier,
       CASE highestGrantRank
         WHEN 0 THEN 'admin'
         WHEN 1 THEN 'write'
         ELSE 'read' END           AS highestGrant,
       grantedByPolicies
ORDER BY sensitivityRank ASC, highestGrantRank ASC, resourceName
```

## Full kill chain from the internet to sensitive cloud data

```cypher
/*
 * @name           Full kill chain from the internet to sensitive cloud data
 * @description    Joins the network and identity halves of the model into one
 *                 route: from a public endpoint, to an exposed host carrying an
 *                 exploited vulnerability, across CAN_REACH to a pivot host, to
 *                 the workload identity that host runs as, through that
 *                 identity's policies, to a cloud service in one of the given
 *                 data classifications.
 * @params         minCvss - Minimum CVSS v3.1 base score for the entry
 *                     vulnerability. Start at 9.0, as in the foothold query.
 *                 maxLateralHops - Maximum CAN_REACH hops between the entry
 *                     host and the pivot host. Start at 4 and raise one hop at
 *                     a time. The pattern's literal ceiling is 8.
 *                 classifications - List of data classifications that count as
 *                     sensitive. Start at ['restricted'], the most sensitive
 *                     band in this model's encoding, which keeps the result to
 *                     chains ending somewhere reportable. Widen to
 *                     ['restricted','confidential'] when the question is what
 *                     an attacker could see at all rather than what would
 *                     trigger a disclosure obligation.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per complete chain: the public name and entry host,
 *                 the entry CVE, the hop count and route to the pivot host, the
 *                 identity inherited there, the policy granting access, its
 *                 permission level, and the target resource with its type and
 *                 classification.
 * @usage          The most complete statement the model can make, and the one
 *                 to lead with when explaining why connected data is worth the
 *                 trouble: no single inventory holds all four of exposure,
 *                 vulnerability, network permission and IAM grant, so this
 *                 chain is invisible to each of them separately. A zero-hop
 *                 result is the worst case — the exposed host itself runs as an
 *                 identity that reaches sensitive data, with no lateral movement
 *                 required. Expect several rows per entry host where more than
 *                 one pivot or policy reaches the same resource; aggregate on
 *                 the target resource when the question is what is exposed
 *                 rather than how many ways. Breaking any single link breaks
 *                 the chain, which is what makes the route more actionable than
 *                 its endpoints: the cheapest fix is often the policy, not the
 *                 patch.
 * @tags           kill-chain, exfiltration, identity, cloud, end-to-end
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (e:Endpoint)-[:RESOLVES_TO]->(entry:ComputeInstance)-[:HAS_VULNERABILITY]->(v:CVE)
WHERE v.knownExploited = true
  AND v.cvssScore >= $minCvss
MATCH path = shortestPath((entry)-[:CAN_REACH*0..8]->(pivot:ComputeInstance))
WHERE length(path) <= $maxLateralHops
MATCH (pivot)-[:RUNS_AS]->(identity:Identity)-[:ASSUMES]->(policy:IAMPolicy)
MATCH (policy)-[:HAS_ACCESS_TO]->(svc:CloudService)
WHERE svc.dataClassification IN $classifications
RETURN e.dnsName        AS exposedVia,
       entry.hostname   AS entryHost,
       v.cveId          AS entryCve,
       length(path)     AS lateralHops,
       [n IN nodes(path) | n.hostname] AS lateralRoute,
       pivot.hostname   AS pivotHost,
       identity.name    AS inheritedIdentity,
       policy.name      AS viaPolicy,
       policy.permissionLevel AS permissionLevel,
       svc.name         AS targetResource,
       svc.serviceType  AS resourceType,
       svc.dataClassification AS dataClassification
ORDER BY lateralHops ASC, entryHost, targetResource
```

## Choke points on crown-jewel attack paths

```cypher
/*
 * @name           Choke points on crown-jewel attack paths
 * @description    Enumerates the bounded CAN_REACH routes from every exposed,
 *                 exploitable foothold to every crown-jewel host, then counts
 *                 how many of those routes pass through each intermediate host.
 *                 Footholds and crown-jewel hosts are excluded from the count:
 *                 only hosts strictly in between can be a choke point.
 * @params         minCvss - Minimum CVSS v3.1 base score for the foothold
 *                     vulnerability. Start at 9.0, as in the foothold query.
 *                 crownJewelTier - Criticality tier that counts as a crown
 *                     jewel. Start at 'P0'.
 *                 maxLateralHops - Maximum route length considered. Start at 3
 *                     here, one lower than elsewhere: this query enumerates
 *                     every route rather than the shortest one, so the work
 *                     grows far faster with the bound. Raise it one hop at a
 *                     time and stop as soon as the query slows noticeably. The
 *                     pattern's literal ceiling is 6.
 *                 minPathsThrough - Minimum number of distinct routes a host
 *                     must carry to be reported. Start at 2: a host on exactly
 *                     one route is not a choke point, it is simply on the
 *                     route. Raise it until the result names a handful of hosts
 *                     whose re-segmentation could actually be justified.
 * @prerequisites  None beyond the imported model.
 * @returns        One row per intermediate host meeting the threshold, busiest
 *                 first: instance identifier, hostname, network segment, the
 *                 number of distinct crown-jewel routes through it, and the
 *                 crown jewels those routes lead to.
 * @usage          Answers where to spend a segmentation budget. A host carrying
 *                 many routes is a single change that removes many paths at
 *                 once, which is usually cheaper than patching every foothold
 *                 feeding it. Two cautions. First, route counts are a
 *                 popularity measure over the routes this query enumerated, not
 *                 a centrality measure over the estate — they shift with the
 *                 bound and the threshold, so compare hosts within one run and
 *                 not across runs. Second, this is the one query here whose
 *                 cost is combinatorial rather than linear in the bound; on a
 *                 large estate prefer a betweenness-centrality computation over
 *                 a CAN_REACH projection in Graph Data Science, which answers
 *                 the same question without enumerating routes. That is a
 *                 deliberate omission from this package rather than an
 *                 oversight: it would add a plugin dependency, and this query
 *                 covers the use case without one.
 * @tags           choke-point, segmentation, remediation, prioritisation
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (e:Endpoint)-[:RESOLVES_TO]->(entry:ComputeInstance)-[:HAS_VULNERABILITY]->(v:CVE)
WHERE v.knownExploited = true
  AND v.cvssScore >= $minCvss
WITH DISTINCT entry
MATCH (host:ComputeInstance)-[:RUNS]->(target:Application {tier: $crownJewelTier})
MATCH path = (entry)-[:CAN_REACH*1..6]->(host)
WHERE length(path) <= $maxLateralHops
WITH path, target
UNWIND nodes(path)[1..-1] AS chokePoint
WITH chokePoint,
     count(DISTINCT path) AS pathsThrough,
     collect(DISTINCT target.name) AS gatesAccessTo
WHERE pathsThrough >= $minPathsThrough
RETURN chokePoint.instanceId     AS instanceId,
       chokePoint.hostname       AS hostname,
       chokePoint.networkSegment AS networkSegment,
       pathsThrough,
       gatesAccessTo
ORDER BY pathsThrough DESC, hostname
```

## Crown-jewel exposure summary

```cypher
/*
 * @name           Crown-jewel exposure summary
 * @description    Lists every application in the given criticality tier
 *                 alongside how many exposed, exploitable footholds reach it
 *                 within the hop bound and the fewest hops any of them needs.
 *                 Crown jewels that no qualifying foothold reaches are returned
 *                 with a count of zero rather than omitted.
 * @params         minCvss - Minimum CVSS v3.1 base score for a foothold to
 *                     count. Start at 9.0, as in the foothold query.
 *                 crownJewelTier - Criticality tier to summarise. Start at
 *                     'P0'.
 *                 maxLateralHops - Maximum CAN_REACH hops from foothold to
 *                     crown-jewel host. Start at 4. The pattern's literal
 *                     ceiling is 8.
 * @prerequisites  None beyond the imported model. The Application.tier index in
 *                 SETUP.md improves the anchor lookup.
 * @returns        One row per crown-jewel application, most exposed first:
 *                 application identifier, name, owning business unit, the count
 *                 of distinct footholds reaching it, the fewest lateral hops
 *                 required, and the foothold hostnames. Unreached crown jewels
 *                 return a count of zero, a null hop count and an empty list.
 * @usage          The reporting view over the path queries, and the honest
 *                 counterpart to them: it shows the crown jewels no route
 *                 reaches as well as the ones it does, which a path query
 *                 cannot do because unreached targets simply produce no rows. A
 *                 zero is a statement about this threshold and this bound, not
 *                 a clean bill of health — re-run with a lower minCvss or a
 *                 higher maxLateralHops before describing anything as isolated,
 *                 and remember that a crown jewel unreachable across the
 *                 network may still be exposed through an IAM grant, which the
 *                 blast-radius query is what tests. Use the hop count as a
 *                 rough ranking only; one hop from a trivially exploitable
 *                 foothold is worse than three from a hard one, and this
 *                 summary does not weigh that.
 * @tags           reporting, crown-jewel, coverage, exposure, prioritisation
 * TODO(review): unproven query — not executed against a live database.
 */
MATCH (e:Endpoint)-[:RESOLVES_TO]->(entry:ComputeInstance)-[:HAS_VULNERABILITY]->(v:CVE)
WHERE v.knownExploited = true
  AND v.cvssScore >= $minCvss
MATCH (host:ComputeInstance)-[:RUNS]->(exposed:Application {tier: $crownJewelTier})
MATCH path = shortestPath((entry)-[:CAN_REACH*0..8]->(host))
WHERE length(path) <= $maxLateralHops
WITH exposed, entry, min(length(path)) AS hops
WITH exposed,
     count(DISTINCT entry) AS reachableFromFootholds,
     min(hops) AS fewestLateralHops,
     collect(DISTINCT entry.hostname) AS footholdHosts
WITH collect({
       app:       exposed,
       footholds: reachableFromFootholds,
       hops:      fewestLateralHops,
       hosts:     footholdHosts
     }) AS exposure
MATCH (target:Application {tier: $crownJewelTier})
WITH target, [entry IN exposure WHERE entry.app = target][0] AS hit
RETURN target.applicationId AS applicationId,
       target.name          AS crownJewel,
       target.businessUnit  AS businessUnit,
       coalesce(hit.footholds, 0) AS reachableFromFootholds,
       hit.hops             AS fewestLateralHops,
       coalesce(hit.hosts, []) AS footholdHosts
ORDER BY reachableFromFootholds DESC, fewestLateralHops ASC, crownJewel
```

## Node-key constraints implied by the model

Import creates these from the key definitions in `GRAPH_MODEL.json`. They are
listed here to verify the expected schema, not to build it — run them only
against a database whose data arrived by some other route and which needs
bringing into line with the model.

```cypher
CREATE CONSTRAINT endpoint_key IF NOT EXISTS
FOR (e:Endpoint) REQUIRE e.endpointId IS NODE KEY
```

```cypher
CREATE CONSTRAINT compute_instance_key IF NOT EXISTS
FOR (i:ComputeInstance) REQUIRE i.instanceId IS NODE KEY
```

```cypher
CREATE CONSTRAINT cve_key IF NOT EXISTS
FOR (v:CVE) REQUIRE v.cveId IS NODE KEY
```

```cypher
CREATE CONSTRAINT application_key IF NOT EXISTS
FOR (a:Application) REQUIRE a.applicationId IS NODE KEY
```

```cypher
CREATE CONSTRAINT identity_key IF NOT EXISTS
FOR (n:Identity) REQUIRE n.identityId IS NODE KEY
```

```cypher
CREATE CONSTRAINT iam_policy_key IF NOT EXISTS
FOR (p:IAMPolicy) REQUIRE p.policyId IS NODE KEY
```

```cypher
CREATE CONSTRAINT cloud_service_key IF NOT EXISTS
FOR (s:CloudService) REQUIRE s.serviceId IS NODE KEY
```
