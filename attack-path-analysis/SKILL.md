---
name: attack-path-analysis
description: Cybersecurity exposure management and offensive-informed defence. Models the estate as a traversable graph of internet-facing endpoints, compute instances, vulnerabilities, workload identities, IAM policies, cloud services and business applications, so multi-hop routes from an external foothold to a high-value asset become paths rather than inferences across separate inventories. Use for attack path analysis, kill-chain reconstruction, lateral movement simulation, crown-jewel and blast-radius assessment, choke-point identification for network segmentation, and vulnerability prioritisation by reachability rather than severity alone. Provides a graph model, sample data for a synthetic estate with reachable and deliberately unreachable targets, and Cypher for finding exploitable footholds, tracing routes to critical applications and restricted data, quantifying what a compromised identity reaches, and reporting which crown jewels no route touches.
metadata:
  neo4j-card-title: Attack Path Analysis
  neo4j-card-category: Cybersecurity
  neo4j-card-description: Trace the multi-hop routes an attacker would take from an internet-facing foothold to a crown-jewel application or restricted cloud data, and find the single hosts and permissions most of those routes depend on.
  neo4j-graph-spec-version: 4.0.0-alpha.25
---

# Attack Path Analysis

Use this skill for security teams doing exposure management, attack surface
reduction and offensive-informed defence: the work of deciding which of
thousands of findings actually matter, on the basis of where an attacker could
get from each one rather than how severe each looks in isolation.

Source references:

- <https://neo4j.com/developer/industry-use-cases/cybersecurity/attack-path-analysis/>
- <https://neo4j.com/developer/industry-use-cases/cybersecurity/vulnerability-prioritization-exposure-management/>

The bundled data is synthetic. CVE identifiers in it are real, but the scores,
exploitation flags and dates attached to them are illustrative and are not a
live feed — never present this package as a source of vulnerability
intelligence, and never quote a score from it as current. Every result is an
analytical lead requiring human review, not a security conclusion: a returned
path asserts that network permission and an exploitable entry point exist, not
that an attacker holds the credentials each hop needs, and not that an intrusion
has occurred or would succeed. Nothing here substitutes for penetration testing,
threat hunting or incident investigation.

## Introducing this package

When the user first opens this package, greet them with a short introduction in
your own words — don't recite this file. Convey:

- The core idea: a breach is a path, not a finding. No single system holds the
  whole route — the exposure register, the vulnerability scanner, the firewall
  rules and the IAM console each hold one segment of it, so a chain that is
  obvious once drawn is invisible to every one of them alone. Joining them makes
  the question "can anything outside reach anything that matters" a traversal.
- Why that changes priorities: severity ranks findings, reachability ranks
  risks, and the two orders disagree. The most alarming vulnerability in an
  estate is often on a host that leads nowhere, while the route to the crown
  jewels starts somewhere unremarkable.
- What the sample data contains: a small synthetic estate, deliberately built so
  that complete routes from the internet to critical assets exist and can be
  walked, alongside high-severity findings that lead nowhere and a critical
  asset that no route reaches — so the queries can be seen distinguishing the
  cases rather than just finding hits.
- What you can help with: explaining the model, walking through the query
  patterns, importing the sample data or their own, and running Cypher once a
  database is connected.

End with a clear next step, such as asking whether they'd like to see the model
or start importing data.

## Model

- `Endpoint` is the outside edge: one listening service, keyed by public DNS
  name and port. It carries no vulnerability itself — the exposure it creates
  belongs to the `ComputeInstance` it `RESOLVES_TO`.
- `ComputeInstance` is the unit of lateral movement and the only node that
  carries vulnerabilities. Applications do not: compromise is of the host, and
  reaches whatever the host runs.
- `CAN_REACH` is the pivot of the whole model. It is **directed and asymmetric**
  — the source instance is permitted to open a connection to the target on the
  stated port — so mutual reachability is two rows and every path query
  traverses it directionally. It asserts network permission only, not
  credentials and not a working exploit on the target.
- `CVE` carries three different signals that must not be conflated:
  `cvssScore` is severity in isolation, `epssScore` is the probability of
  exploitation in the wild, and `knownExploited` records observed exploitation
  via the CISA KEV catalogue. The queries filter on KEV and CVSS together
  because either alone over-selects.
- The identity half of the model — `RUNS_AS` to an `Identity`, `ASSUMES` to an
  `IAMPolicy`, `HAS_ACCESS_TO` to a `CloudService` or `Application` — is what
  converts a host compromise into a data exposure. It needs no network path, so
  a well-segmented estate can still have a wide blast radius. `IAMPolicy` is its
  own node rather than collapsed into the identity precisely because one policy
  is typically attached to many identities, which makes an over-permissive grant
  a single node many paths cross.
- `HAS_ACCESS_TO` is used between two different node pairs and means something
  different in each: to a `CloudService` it is the data-exfiltration hop, to an
  `Application` it is control-plane access that reaches the application without
  compromising its host. Read the direction, not just the type.
- Design rationale: the source pages describe `CAN_REACH` as bidirectional. This
  model makes it directed, because firewall and security-group rules are
  asymmetric and an undirected edge yields routes an attacker could not walk;
  mutual reachability is expressed as two rows instead. The model also names
  `ComputeInstance` for the internal host role rather than overloading
  `Endpoint`, so that "exposed to the internet" is a relationship rather than a
  property. Otherwise the labels and relationship types follow the source pages.
- Full schema and mappings are in `GRAPH_MODEL.json`; runnable Cypher is in
  `QUERIES.md`.
- Treat the model's `description` annotations as the authoritative meaning of
  each term — quote them when explaining the model, rely on them when adapting
  queries to the user's own data, and never contradict them.

### Roles

| Role | In this model | What a substitute needs |
| ---- | ------------- | ----------------------- |
| External entry point | `Endpoint` via `RESOLVES_TO` | A node an unauthenticated outsider could connect to, joined to the asset that serves it. Without one there is no way to tell an exposed asset from an internal one, and every foothold query degrades to "all vulnerable hosts" |
| Traversable asset | `ComputeInstance` | The node an attacker executes code on, and the endpoint of the reachability edge. Must be the thing vulnerabilities attach to, not the software running on it |
| Directed reachability | `CAN_REACH` | A directed edge asserting that one asset may open a connection to another. The role with no workable substitute: co-membership of a segment, subnet or tag is not reachability, and treating it as such overstates routes in both directions |
| Exploitability signal | `knownExploited` and `cvssScore` on `CVE` | Something that separates flaws observed in active use from flaws that are merely severe. A severity score alone cannot do it — it is the signal the graph exists to contextualise, not to replace |
| Value anchor | `Application.tier`, `CloudService.dataClassification` | A band assigned by the business or by data governance, on the node a path terminates at, so routes can be ranked by what they reach. A value derived from the graph itself is circular and useless here |
| Inherited credential and its grants | `Identity` via `RUNS_AS`, then `IAMPolicy` via `ASSUMES` | A chain from an asset to the permissions its processes hold to the resources those permissions reach, with the grant shared across credentials. Collapsing it to a direct asset-to-resource edge loses the shared grant, and with it every choke point on the identity side |

When the user's schema differs from this model, map their labels onto these
roles before rewriting anything from `QUERIES.md`. A role with no counterpart in
their data means the patterns resting on it have no analogue — say so plainly
rather than forcing a fit. Check directed reachability first: without it none of
the path questions can be answered at all, and a model that records only network
topology or segment membership needs that edge derived, and reviewed, before any
result from it means anything.

## Operational Constraints

- **Neo4j 5.x or later, Cypher 5. No APOC and no GDS** — every bundled query is
  plain Cypher. Graph Data Science betweenness centrality over a `CAN_REACH`
  projection is the better tool for ranking choke points on a large estate, and
  is deliberately not shipped here: it would add a plugin dependency, and the
  bundled choke-point query covers the use case without one. Offer it as a next
  step if the user already has GDS, and say plainly that the Cypher for it is
  not part of this package.
- Data loads through the bundled `sample-data/` Import flow, and only through
  it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a
  `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and
  confirm with the user before running anything that writes. **No bundled query
  writes.** The only writing statements in the package are the optional index in
  `SETUP.md` and the constraint reference at the end of `QUERIES.md`, both of
  which change schema rather than data.
- Right after a sample-data import, offer the statement in `SETUP.md` — 1
  statement, 0 required, 1 recommended. Explain it before running; if the user
  declines it, say that no query result changes and only the crown-jewel anchor
  lookup is slower, then do not raise it again.
- **Variable-length bounds cannot be parameterised in Cypher.** Each path query
  carries a literal ceiling in its pattern plus a `$maxLateralHops` filter. The
  parameter tunes within the ceiling; going beyond it means editing the literal,
  and the cost climbs steeply when you do. Say this when a user asks for a
  deeper search rather than silently returning a truncated answer.
- **A path is a lead, not a breach.** Every returned route asserts network
  permission plus an exploitable entry point. It does not assert that an
  attacker holds credentials for each hop, that the exploit works in this
  configuration, or that any of it has happened. Frame results in those terms
  every time; the failure mode of this package is a confident-sounding attack
  path presented as an incident.
- **Absence of a path is not safety.** A crown jewel no route reaches may simply
  be beyond the current hop bound or severity threshold, and may in any case be
  exposed through an IAM grant that needs no network path at all. Re-run with a
  wider bound and check the blast-radius query before describing anything as
  isolated.
- **Read the environment and tier columns before escalating.** An exploitable,
  internet-facing host in a non-production environment is only material if a
  route leads from it into production, and severity ordering will put exactly
  that kind of host at the top of the list.
- The choke-point query is the one whose cost is combinatorial rather than
  linear in the hop bound, because it enumerates every route instead of the
  shortest. Start its bound lower than the others and raise it one hop at a
  time.
- Queries open with a `/* @... */` annotation block. Keep the block with the
  query when showing or running it — it exists to help the user understand the
  query — and treat it as context, not ground truth: on any conflict, the Cypher
  logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that
  fit any dataset. The hop bounds in particular depend on how densely the
  estate's reachability is recorded, which varies enormously between a
  firewall-rule export and an inferred topology. Read the result and retune
  before presenting anything as a finding.
- Several queries carry a `TODO(review): unproven query` marker in their
  annotation block, meaning they have not yet been executed against a database.
  If one errors, say so and fix it rather than presenting a rewritten query as
  though it were the packaged one.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this surfaces
Tuning options
Validation approach
```
