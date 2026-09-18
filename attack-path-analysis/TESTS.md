# Attack Path Analysis — test oracle

Authoring-side reference for the bundled sample data. Never loaded by the
runtime and never shown to the consuming agent: everything here is a concrete
claim about the bundled CSVs, which would be false against a user's own estate.

## Status of these expectations

**No query in `QUERIES.md` has been executed against a Neo4j database.** No
database or container runtime was available in the authoring environment. Every
"Expected" figure below was instead derived by reimplementing each query's
semantics over the bundled CSVs in Python — BFS for `shortestPath`,
relationship-uniqueness (trail) enumeration for the unbounded path walk, and the
same predicates, grouping and ordering the Cypher uses.

What that does and does not establish:

- **Established:** the sample data really does contain the patterns the queries
  look for, the seeded signals separate from the noise as designed, and the
  result shapes and orderings are the intended ones.
- **Not established:** that the Cypher parses, that the planner behaves as
  expected, or that Neo4j's evaluation of the aggregations, list slices and
  `shortestPath` bounds matches the simulation in every corner. Three
  constructs are worth checking first on a real run — see *Constructs to verify
  first* below.

Every query therefore carries `TODO(review): unproven query` in its
`QUERIES.md` annotation block. Clear those markers, and replace "Expected" with
"Observed" plus a run date, once the queries have run.

### Constructs to verify first

| Where | Construct | What to check |
| ----- | --------- | ------------- |
| Every path query | `shortestPath((a)-[:CAN_REACH*0..8]->(b))` with a lower bound of 0 | That a zero-length path is returned when `a = b`, which is what makes a foothold that runs the crown jewel itself appear at zero hops. If the planner rejects `*0..` inside `shortestPath`, split the query on the zero-hop case. |
| Choke points | `UNWIND nodes(path)[1..-1]` and `count(DISTINCT path)` | That the slice excludes both endpoints and that distinct path counting behaves as assumed. Under relationship-uniqueness a path may revisit a node (see the `artifact-store-01` note in the profile), which the simulation reproduces deliberately. |
| Crown-jewel exposure summary | `collect({app: exposed, …})` over zero rows, then `[entry IN exposure WHERE entry.app = target][0]` | That the collect still yields one row with an empty list when no crown jewel is reachable at all, so unreached applications are still returned. This is the construct the whole negative case rests on. The comprehension variable is deliberately not named `row`, to avoid shadowing the alias it feeds. |

## Editing note: the reused relationship type

`HAS_ACCESS_TO` is declared twice — `policyAccessesService` and
`policyAccessesApplication` — and **neither entry carries any properties**. Keep
it that way unless you understand the consequence.

A `mustExist` on a relationship property generates an existence constraint
scoped to the *relationship type*, not to the node pair. Declaring the same
constrained property on both entries of a reused type therefore mints two
constraints with the same name, and the package fails to load. This is a real
defect that has already been fixed once in another package in this repository.

If a property is ever needed on `HAS_ACCESS_TO`, declare any `mustExist` on
exactly one of the two entries and say so in both descriptions, rather than
declaring it on each. The relationship-property constraints currently in the
model — `HAS_VULNERABILITY.detectedOn` and `CAN_REACH.port` — are safe because
both types are declared exactly once. No node label is reused.

## How to run

1. **Use a disposable database.** Every query here reads, but the schema
   statement in `SETUP.md` and the constraints at the end of `QUERIES.md` write.
   Never run this against anything but a throwaway target.
2. **Import the CSVs through the Import flow from `GRAPH_MODEL.json`.** That is
   the only supported loading route; there is no seed script, and none should be
   written. Import creates the seven node-key constraints from the model's key
   definitions.
3. **Optionally run the one statement in `SETUP.md`** — a range index on
   `Application.tier`. Nothing below depends on it: results are identical with
   and without, and only the crown-jewel anchor lookup changes speed. Run it if
   you want the package exercised as a user would see it.
4. **Run the queries with the parameters each section states.** Where a section
   gives more than one parameter set, the first is the headline case.

Expected totals after import: **88 nodes, 144 relationships.**

## Sample-data profile

A synthetic estate for a fictional retailer, sized so that every query returns a
reviewable result and no query is a clean detector on its own.

### Row counts

| Table | Rows | Becomes |
| ----- | ---- | ------- |
| `endpoints.csv` | 9 | `Endpoint` |
| `compute_instances.csv` | 23 | `ComputeInstance` |
| `cves.csv` | 14 | `CVE` |
| `applications.csv` | 9 | `Application` |
| `identities.csv` | 11 | `Identity` |
| `iam_policies.csv` | 12 | `IAMPolicy` |
| `cloud_services.csv` | 10 | `CloudService` |
| `endpoint_resolves_to.csv` | 11 | `RESOLVES_TO` |
| `instance_has_vulnerability.csv` | 18 | `HAS_VULNERABILITY` |
| `instance_can_reach.csv` | 34 | `CAN_REACH` |
| `instance_runs.csv` | 13 | `RUNS` |
| `instance_runs_as.csv` | 20 | `RUNS_AS` |
| `identity_assumes.csv` | 20 | `ASSUMES` |
| `policy_accesses_service.csv` | 15 | `HAS_ACCESS_TO` (to `CloudService`) |
| `policy_accesses_application.csv` | 13 | `HAS_ACCESS_TO` (to `Application`) |

88 nodes, 144 relationships.

### Topology

Instances sit in nine segments: `dmz` (CI-001 to CI-004), `web-tier` (CI-005 to
CI-007), `app-tier` (CI-008 to CI-012), `data-tier` (CI-013 to CI-015), `ci-cd`
(CI-016, CI-017), `mgmt` (CI-018, CI-019), `staging-web` (CI-020), `dev-tier`
(CI-021), `staging-app` (CI-022), and `hr-tier` (CI-023).

`CAN_REACH` is directed throughout. The edge that makes the package work is
`CI-007 → CI-016`: a low-tier legacy portal in the web tier permitted to reach
the CI/CD build runner. That single rule is what connects an unremarkable
internet-facing host to the production payment estate, and deleting that one row
should collapse most of the crown-jewel results.

Two hosts are deliberate hubs: `CI-016` (build-runner-01) reaches five app-tier
hosts because it deploys to them, and `CI-018` (bastion-01) reaches four hosts
plus CI-016. `CI-016 → CI-017 → CI-016` is a deliberate mutual pair, which under
relationship-uniqueness semantics creates a legitimate path that revisits
CI-016; this is why `artifact-store-01` shows up in the choke-point walk with a
single path.

### Seeded signals

**Four qualifying footholds** — internet-facing via `RESOLVES_TO`, carrying a
CISA-KEV-listed CVE at CVSS ≥ 9.0:

| Instance | Host | Env | CVE | CVSS | EPSS | Reaches a P0 app? |
| -------- | ---- | --- | --- | ---- | ---- | ----------------- |
| CI-007 | legacy-portal-01 | production | CVE-2023-4966 | 9.4 | 0.97 | yes, 2 hops |
| CI-016 | build-runner-01 | production | CVE-2024-27198 | 9.8 | 0.91 | yes, 1 hop |
| CI-016 | build-runner-01 | production | CVE-2024-23897 | 9.8 | 0.72 | yes, 1 hop |
| CI-003 | vpn-gateway-01 | production | CVE-2024-21762 | 9.8 | 0.94 | yes, 2 hops |
| CI-020 | staging-web-01 | **staging** | CVE-2024-3400 | **10.0** | 0.96 | **no** |

**Three crown jewels** (`tier = 'P0'`), two exposed and one not:

| App | Host | Exposure |
| --- | ---- | -------- |
| APP-002 Card Tokenization Service | CI-010 app-payments-01 | reachable from all three production footholds |
| APP-001 Payment Ledger | CI-014 db-payments-01 | reachable from all three production footholds |
| APP-009 HR Records | CI-023 hr-app-01 | **no inbound `CAN_REACH` at all** — unreachable at any bound |

**Four restricted cloud services**, three reachable and one not: CS-004
`payment-card-vault`, CS-005 `customer-pii-db` and CS-007 `db-backups` all sit
on kill chains; CS-009 `hr-records-db` is reachable only through POL-011, held
only by ID-011, held only by CI-023, which nothing reaches.

**One over-privileged identity.** ID-006 `role-ci-deployer` holds five policies
and reaches twelve resources — three of the four restricted services and both
exposed P0 applications. ID-002 `svc-legacy-portal` is the deliberate contrast:
two policies, two resources, nothing restricted. A second broad identity, ID-008
`role-platform-admin` on the bastion, provides the alternative route from the
VPN foothold.

**One shared policy.** POL-012 `shared-config-read` is attached to six
identities, so that the model exercises a policy-level hub as well as
host-level ones.

### Deliberate background noise

The point of each of these is that a query relying on one signal alone gets the
wrong answer.

| Noise | Why it is there |
| ----- | --------------- |
| CI-020 staging-web-01 carries the **highest-scoring KEV CVE in the data** (10.0) and is internet-facing, but its segment reaches only CI-022 and CI-021 — never production | Defeats severity ranking. Sorting the foothold query by CVSS puts this host first, and it is the least urgent of the five rows. |
| CI-021 and CI-022 carry KEV CVEs at 10.0 and 9.8 but have **no inbound `RESOLVES_TO`** | Defeats vulnerability-first triage: critical and exploited, but not externally reachable. |
| CI-001, CI-002, CI-004, CI-019 are internet-facing but carry only **non-KEV** CVEs (8.1, 8.1, 8.1, 5.5) | Defeats exposure-first triage: reachable, but nothing known-exploited on them. |
| CI-005, CI-008, CI-010, CI-013, CI-014, CI-018 carry mid-range non-KEV CVEs | Background vulnerability volume, so the KEV filter has something to exclude. |
| CI-023 hr-app-01 runs a P0 app and has **no `CAN_REACH` edges in either direction** | The correctly isolated crown jewel; makes the exposure summary's zero row meaningful. |
| CI-006, CI-009, CI-011, CI-012, CI-015, CI-017, CI-023 carry **no CVEs at all** | Keeps `HAS_VULNERABILITY` sparse rather than universal. |
| CI-020, CI-021, CI-022 have **no `RUNS_AS`** | Unmanaged non-production hosts, so the staging foothold yields no identity and no kill chain. |
| APP-006 Legacy Supplier Portal is granted by **no policy** | Exercises the "or none" side of the policy-to-application grant. |

### Multiplicity claims, as checked against these rows

| Relationship | Claim | Holds because |
| ------------ | ----- | ------------- |
| `RESOLVES_TO` | each endpoint resolves to ≥1 instance; several where load balanced; an instance may serve many or none | all 9 endpoints resolve; EP-001 and EP-005 resolve to 2 each; CI-004 serves 2 endpoints; 13 instances serve none |
| `HAS_VULNERABILITY` | an instance may carry many or none; one CVE may affect many instances | max 2 per instance; 7 instances carry none; CVE-2024-6387, CVE-2024-2961 and CVE-2023-29491 each affect 2–3 |
| `CAN_REACH` | directed; mutual reachability is two rows; may reach many or none | CI-016↔CI-017 is the only mutual pair, present as two rows; CI-013, CI-014, CI-015, CI-021, CI-023 reach nothing |
| `RUNS` | an instance may run many or none; an app may run on many instances | 10 instances run nothing; APP-003 runs on 5 |
| `RUNS_AS` | **at most one** workload identity per instance | every instance appears at most once in the table; ID-001, ID-003, ID-004, ID-006, ID-007 and ID-009 are each shared by 2–3 instances |
| `ASSUMES` | an identity may hold many; a policy may be attached to many identities | ID-006 holds 5; POL-004, POL-006, POL-007 and POL-012 are each attached to 2–6 identities |
| `HAS_ACCESS_TO` → `CloudService` | may grant many, or none | all 12 policies grant at least one service, so the "none" branch is an allowance this data does not exercise |
| `HAS_ACCESS_TO` → `Application` | may grant many, or none; an app may be granted by none | POL-006 grants 5; POL-001, POL-002, POL-004, POL-007 and POL-012 grant none; APP-006 is granted by none |

Two claims are allowances the data does not exercise: an application running on
no instance, and an identity held by no instance. Both are legitimate for a
template model and neither can fail.

## Exposed hosts carrying an exploited vulnerability

**Parameters** — `minCvss: 9.0`.

**Invariant** — returns exactly the internet-facing instances carrying a
KEV-listed CVE at or above the threshold, one row per instance and CVE. The
staging foothold appears, and its row sorts first on CVSS despite leading
nowhere. No instance without an inbound `RESOLVES_TO` appears, and no non-KEV
CVE appears, whatever the generator produces.

**Expected (hand-traced, not executed)** — 5 rows over 4 distinct instances, in
this order:

| # | instanceId | hostname | environment | cveId | cvssScore | epssScore |
| - | ---------- | -------- | ----------- | ----- | --------- | --------- |
| 1 | CI-020 | staging-web-01 | staging | CVE-2024-3400 | 10.0 | 0.96 |
| 2 | CI-003 | vpn-gateway-01 | production | CVE-2024-21762 | 9.8 | 0.94 |
| 3 | CI-016 | build-runner-01 | production | CVE-2024-27198 | 9.8 | 0.91 |
| 4 | CI-016 | build-runner-01 | production | CVE-2024-23897 | 9.8 | 0.72 |
| 5 | CI-007 | legacy-portal-01 | production | CVE-2023-4966 | 9.4 | 0.97 |

Excluded and worth confirming: CI-021 and CI-022 (KEV at 10.0 and 9.8 but not
internet-facing), CI-001, CI-002, CI-004 and CI-019 (internet-facing, non-KEV).

**Sensitivity** — at `minCvss: 7.0` the result is unchanged, because every
KEV-listed CVE in the data already scores 9.4 or above; the widening only starts
to matter on data with mid-scoring KEV entries. At `minCvss: 10.0` only CI-020
and its dead-end finding survive, which is the sharpest illustration in the
package of why a score threshold alone is the wrong instrument. The 9.0 shipped
in `@params` is the published lower bound of the CVSS v3.1 CRITICAL band, not a
value tuned to these rows.

## Attack paths from an exposed foothold to a crown-jewel application

**Parameters** — `minCvss: 9.0`, `crownJewelTier: 'P0'`, `maxLateralHops: 4`.

**Invariant** — returns one shortest route per foothold, foothold CVE and crown
jewel, for the three production footholds only. APP-009 HR Records never
appears, because CI-023 has no inbound `CAN_REACH`. CI-020 staging-web-01 never
appears, because its segment reaches no crown-jewel host. Every returned route
is directed and traversable end to end.

**Expected (hand-traced, not executed)** — 8 rows, ordered by hops then CVSS
then crown jewel:

| # | foothold | via CVE | crown jewel | crown-jewel host | hops |
| - | -------- | ------- | ----------- | ---------------- | ---- |
| 1 | build-runner-01 | CVE-2024-27198 | Card Tokenization Service | app-payments-01 | 1 |
| 2 | build-runner-01 | CVE-2024-23897 | Card Tokenization Service | app-payments-01 | 1 |
| 3 | vpn-gateway-01 | CVE-2024-21762 | Card Tokenization Service | app-payments-01 | 2 |
| 4 | build-runner-01 | CVE-2024-27198 | Payment Ledger | db-payments-01 | 2 |
| 5 | build-runner-01 | CVE-2024-23897 | Payment Ledger | db-payments-01 | 2 |
| 6 | vpn-gateway-01 | CVE-2024-21762 | Payment Ledger | db-payments-01 | 2 |
| 7 | legacy-portal-01 | CVE-2023-4966 | Card Tokenization Service | app-payments-01 | 2 |
| 8 | legacy-portal-01 | CVE-2023-4966 | Payment Ledger | db-payments-01 | 3 |

Routes: `legacy-portal-01 → build-runner-01 → app-payments-01`, extended by
`→ db-payments-01` for the ledger; `vpn-gateway-01 → bastion-01 → …` for both.

**Sensitivity** — `maxLateralHops: 1` leaves only the two build-runner rows to
the tokenization service. `2` drops row 8 only. `4` and above adds nothing: 3 is
the longest shortest-route in the data, so the bound stops mattering. No value
of the bound makes APP-009 appear.

## Lateral reachability from a compromised host

**Parameters** — `instanceId: 'CI-007'`, `maxLateralHops: 4`. CI-007 is the
headline case: the low-value legacy portal whose reach is the package's central
point.

**Invariant** — returns every instance reachable from the origin by directed
`CAN_REACH` within the bound, with the shortest hop count to each, and excludes
the origin itself. No DMZ, `mgmt`, staging, development or `hr-tier` host is
reachable from CI-007 at any bound, because no edge leads back out of the
application estate.

**Expected (hand-traced, not executed)** — 10 of the 22 other instances, at hop
distances 1 to 3:

| hops | instances |
| ---- | --------- |
| 1 | CI-012 app-crm-01, CI-016 build-runner-01 |
| 2 | CI-008 app-orders-01, CI-009 app-orders-02, CI-010 app-payments-01, CI-011 app-inventory-01, CI-015 db-analytics-01, CI-017 artifact-store-01 |
| 3 | CI-013 db-orders-01, CI-014 db-payments-01 |

Not reachable: CI-001 to CI-006, CI-018 to CI-023. Two reached hosts run P0
applications (CI-010 at 2 hops, CI-014 at 3). Five distinct identities are
inheritable across the reachable set, including `role-ci-deployer` at one hop —
the finding that should send the reader to the blast-radius query.

**Sensitivity** — the reachable set is complete at 3 hops; raising the bound to
4 or beyond adds nothing. At 1 hop the result is two hosts and still includes
`role-ci-deployer`, so even the tightest bound surfaces the important identity.
Running from `CI-003` instead returns a different 8-host set through
`bastion-01`; running from `CI-020` returns 2 hosts and no production host at
all.

## Blast radius of a compromised identity

**Parameters** — `identityId: 'ID-006'`. The contrast case is
`identityId: 'ID-002'`.

**Invariant** — returns one row per distinct resource the identity reaches
through any of its policies, cloud services before applications (applications
have no data classification and sort last), most sensitive first, with the
highest permission level any granting policy carries. Nothing in the result
depends on network reachability.

**Expected (hand-traced, not executed)** — ID-006 `role-ci-deployer`, 5
policies, **12 resources**: 6 cloud services and 6 applications.

| resourceKind | resourceName | classification / tier | highestGrant | via |
| ------------ | ------------ | --------------------- | ------------ | --- |
| CloudService | customer-pii-db | restricted | admin | ci-deploy-all-prod |
| CloudService | db-backups | restricted | write | backup-bucket-write |
| CloudService | payment-card-vault | restricted | read | payment-vault-read |
| CloudService | order-event-stream | confidential | admin | ci-deploy-all-prod |
| CloudService | build-artifacts | internal | admin | ci-artifact-admin |
| CloudService | shared-config | internal | read | shared-config-read |
| Application | Build Orchestrator | P1 | admin | ci-artifact-admin |
| Application | Card Tokenization Service | P0 | admin | ci-deploy-all-prod |
| Application | Customer CRM | P1 | admin | ci-deploy-all-prod |
| Application | Inventory Sync | P2 | admin | ci-deploy-all-prod |
| Application | Order Management | P1 | admin | ci-deploy-all-prod |
| Application | Payment Ledger | P0 | admin | ci-deploy-all-prod |

Three of the four restricted services and both exposed P0 applications. Within
the application block, ordering is by highest grant then name; all six are
`admin`, so they fall back to alphabetical.

ID-002 `svc-legacy-portal`, the contrast: **2 resources**, `shared-config`
(internal, read) then `portal-static-assets` (public, read). No restricted
service, no application, nothing at write or above. The pair is the package's
argument that the host an attacker lands on matters far less than the credential
it runs as.

**Sensitivity** — not threshold-driven; this query has no tunable parameter. The
informative variation is the identity chosen. ID-008 `role-platform-admin`
returns 6 resources including all three reachable restricted services at
`admin`; ID-011 `svc-hr-records` returns 2, including the otherwise unreachable
`hr-records-db`.

## Full kill chain from the internet to sensitive cloud data

**Parameters** — `minCvss: 9.0`, `maxLateralHops: 4`,
`classifications: ['restricted']`.

**Invariant** — returns only complete chains: public endpoint, exploitable
exposed host, directed lateral route, pivot host, inherited identity, granting
policy, restricted cloud service. CS-009 `hr-records-db` never appears at any
bound, because its only granting policy is held by an identity on an unreachable
host. CI-020 staging-web-01 never appears, because no host in its segment has a
`RUNS_AS` edge. At least one chain is zero-hop.

**Expected (hand-traced, not executed)** — **44 rows** across 3 entry hosts and
3 restricted services. The row count is high because the query deliberately does
not aggregate: each distinct combination of entry CVE, pivot host and granting
policy is its own row, which is what lets a reader see that there are many ways
to the same data rather than one.

Summary of the shape:

| entry host | hop range | restricted services reached | via identities |
| ---------- | --------- | --------------------------- | -------------- |
| build-runner-01 | 0–2 | payment-card-vault, customer-pii-db, db-backups | role-ci-deployer, svc-app-payments, svc-db-backup |
| legacy-portal-01 | 1–3 | payment-card-vault, customer-pii-db, db-backups | role-ci-deployer, svc-app-payments, svc-db-backup |
| vpn-gateway-01 | 1–4 | payment-card-vault, customer-pii-db, db-backups | role-platform-admin, role-ci-deployer, svc-app-payments, svc-db-backup |

The six zero-hop rows all belong to build-runner-01, whose own workload identity
`role-ci-deployer` reaches all three restricted services with no lateral
movement at all — the worst case in the data, and the one to lead with when
demonstrating the package.

The shortest chain from the *unremarkable* foothold is the more interesting
result: `legacy.northwind.example → legacy-portal-01 (CVE-2023-4966) →
build-runner-01 → role-ci-deployer → ci-deploy-all-prod → customer-pii-db`, one
lateral hop from a P3 portal to restricted customer data.

**Sensitivity** — at `maxLateralHops: 0` only the six build-runner rows survive.
At `1` the count reaches 21. Widening `classifications` to
`['restricted','confidential']` adds `order-event-stream` chains and roughly
half again as many rows. No setting of either parameter reaches
`hr-records-db`, which is the invariant worth protecting when the data is
regenerated.

## Choke points on crown-jewel attack paths

**Parameters** — `minCvss: 9.0`, `crownJewelTier: 'P0'`, `maxLateralHops: 3`,
`minPathsThrough: 2`. Note the hop bound is one lower than elsewhere: this query
enumerates every route rather than the shortest.

**Invariant** — returns only hosts strictly between a foothold and a
crown-jewel host, never a foothold and never a crown-jewel host itself, ranked
by the number of distinct enumerated routes through them. The two deliberate
hubs rank jointly first.

The walk enumerates **9 distinct routes** in total at this bound, from the three
production footholds (the `WITH DISTINCT entry` clause collapses CI-016's two
qualifying CVEs to one entry, so a foothold is not counted twice for carrying
two vulnerabilities — an easy thing to get wrong when reimplementing this).

**Expected (hand-traced, not executed)** — 3 rows above the threshold, ordered
by route count then hostname:

| instanceId | hostname | segment | pathsThrough | gates access to |
| ---------- | -------- | ------- | ------------ | --------------- |
| CI-018 | bastion-01 | mgmt | 4 | Card Tokenization Service, Payment Ledger |
| CI-016 | build-runner-01 | ci-cd | 4 | Card Tokenization Service, Payment Ledger |
| CI-010 | app-payments-01 | app-tier | 3 | Payment Ledger |

The two hubs tie on 4, so `bastion-01` sorts first on hostname. CI-017
`artifact-store-01` sits on exactly 1 route and is correctly excluded by the
threshold. That route —
`build-runner-01 → artifact-store-01 → build-runner-01 → app-payments-01` —
revisits CI-016 and is legal under relationship-uniqueness semantics. It is
deliberate: it is there so that a real run either reproduces it, confirming the
expected traversal semantics, or does not, telling you the semantics differ
from the simulation. Check this row first.

**Sensitivity** — this query is the most bound-sensitive in the package, and the
ranking itself moves, so treat the numbers as comparable only within one run.

| `maxLateralHops` | Route counts | Rows at `minPathsThrough: 2` |
| ---------------- | ------------ | ---------------------------- |
| 2 | bastion-01 2, app-payments-01 1, build-runner-01 1 | 1 |
| 3 | bastion-01 4, build-runner-01 4, app-payments-01 3, artifact-store-01 1 | 3 |
| 4 | build-runner-01 7, app-payments-01 5, bastion-01 5, artifact-store-01 3 | 4 |

At `minPathsThrough: 1` and a bound of 3, CI-017 joins the result with a count
of 1. The `minPathsThrough: 2` shipped in `@params` is definitional — one route
through a host is not a choke point — rather than reverse-engineered from these
counts. The `maxLateralHops: 3` shipped for this query is one lower than the
package default because the enumeration is combinatorial, not because 3
flatters the data.

## Crown-jewel exposure summary

**Parameters** — `minCvss: 9.0`, `crownJewelTier: 'P0'`, `maxLateralHops: 4`.

**Invariant** — returns every P0 application, whether or not any foothold
reaches it. APP-009 HR Records is always present with a foothold count of zero,
a null hop count and an empty host list; this is the single most important
expectation in the file, because it is the only check that the outer join
survives. The other two P0 applications are reached by all three production
footholds and never by the staging one.

**Expected (hand-traced, not executed)** — exactly 3 rows:

| applicationId | crownJewel | businessUnit | footholds | fewestHops | foothold hosts |
| ------------- | ---------- | ------------ | --------- | ---------- | -------------- |
| APP-002 | Card Tokenization Service | Finance | 3 | 1 | build-runner-01, legacy-portal-01, vpn-gateway-01 |
| APP-001 | Payment Ledger | Finance | 3 | 2 | build-runner-01, legacy-portal-01, vpn-gateway-01 |
| APP-009 | HR Records | People | 0 | null | (empty) |

**Sensitivity** — the row count is always 3; only the exposure figures move.

| Parameters | Card Tokenization Service | Payment Ledger | HR Records |
| ---------- | ------------------------- | -------------- | ---------- |
| `maxLateralHops: 1` | 1 foothold, 1 hop | **0 footholds, null** | 0, null |
| `maxLateralHops: 2` | 3 footholds, 1 hop | 2 footholds, 2 hops | 0, null |
| `maxLateralHops: 4` (shipped) | 3 footholds, 1 hop | 3 footholds, 2 hops | 0, null |
| `minCvss: 10.0` | 0 footholds, null | 0 footholds, null | 0, null |

At a bound of 1 the ledger joins HR Records on zero, which is the case to watch:
two zero rows for quite different reasons — one unreachable at any bound, one
merely beyond this one. That distinction is exactly what the `@usage` warning
about reading a zero as a clean bill of health is for. At `minCvss: 10.0` all
three rows read zero, since the only 10.0 KEV finding in the data sits on the
staging host that reaches nothing. APP-009's zero row is invariant under every
parameter combination.
