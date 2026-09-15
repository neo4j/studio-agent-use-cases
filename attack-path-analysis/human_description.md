# Attack Path Analysis

Finds the multi-hop routes an attacker could take from an internet-facing
foothold to a critical application or sensitive cloud data, and identifies the
individual machines and permissions that most of those routes depend on.

## Overview

### The industry

Security teams responsible for exposure management face a counting problem
before they face a security one. A mid-sized estate produces tens of thousands
of open vulnerability findings, thousands of identity permissions, and firewall
rules nobody has reviewed end to end in years. The team cannot fix all of it,
so the entire job becomes deciding what to fix first.

The instrument normally used for that decision is severity. Every vulnerability
arrives with a score describing how bad the flaw is in isolation — and in
isolation is precisely the wrong frame. A maximum-severity flaw on a machine
that can reach nothing is an administrative task. A moderate flaw on a machine
that can reach the payment estate is an incident waiting to happen. Severity
cannot tell these apart, because the difference is not a property of the
vulnerability at all. It is a property of where the machine sits.

What matters is reachability: whether anything outside the organisation can
reach anything the organisation cannot afford to lose, and by what steps. That
question spans four systems that rarely speak to one another:

- the external attack surface register, which knows what is exposed
- the vulnerability scanner, which knows what is exploitable
- the network and firewall configuration, which knows what can talk to what
- the identity provider and cloud console, which know who can read what

Each holds one link of a chain. A route made of four links is invisible in all
four, which is why real intrusions so often follow paths that were, in
hindsight, documented the whole time — just never in one place. Attackers work
in paths; defenders have historically worked in lists.

### What it helps with

Modelling the estate as connected entities turns each of these questions into a
traversal rather than a reconciliation exercise across separate inventories.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| "We have forty thousand findings and capacity for forty fixes. Which forty?" | Ranks exposures by where they lead rather than by severity in isolation, so the flaws that begin a viable route to something critical separate out from the much larger population that does not |
| "If this machine were compromised, what else would be?" | Walks permitted network connections outward from a single machine to produce the full set it could reach, with the number of steps to each and the applications and credentials waiting there |
| "Can anything outside the business reach our most critical applications?" | Joins exposure, exploitability and network reachability into a single route, and reports the specific intermediate machines it passes through |
| "This service account was exposed. What data did it have?" | Follows the permissions the account holds to every resource they reach, independently of network position, since permissions do not require a network path |
| "Where would one firewall change remove the most risk?" | Counts how many distinct routes to critical assets pass through each intermediate machine, identifying the few whose isolation removes many paths at once |
| "Which of our critical assets is genuinely unreachable?" | Reports critical applications that no viable route reaches, which a route-finding result cannot show — an unreachable target simply produces no result at all |
| "Is this permission grant over-scoped?" | Exposes permission grants shared across many accounts, where a single over-scoped grant sits on the routes of every account holding it |

The distinction the ontology is built to support is between a severe finding and
a consequential one. Those are different questions, and only the second can be
answered by looking at how things connect.

## Ontology

The ontology is arranged as a chain, because an attack is a chain. At one end
sits what the outside world can connect to; at the other, the applications and
data the business cares about. Between them run two parallel routes to the same
destination.

The first is the network route: an exposed entry point leads to a machine, that
machine carries vulnerabilities, and permitted network connections lead from it
to other machines, each of which runs applications of its own. The second is the
identity route: a machine runs as a credential, that credential holds permission
grants, and those grants reach cloud resources and applications directly. The
identity route needs no network connectivity at all, which is why a
well-segmented estate can still be widely exposed — and why both belong in the
same picture.

Two design points are worth stating plainly. Network connectivity is recorded as
**directed**: one machine being permitted to connect to another says nothing
about the reverse, because firewall rules are asymmetric, and mutual
connectivity is recorded as two separate connections. And vulnerabilities attach
to machines, never to applications — compromise is of the host, and reaches
whatever that host happens to run.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Endpoint` | A network entry point reachable from the public internet: one listening service, identified by the public name and port an unauthenticated attacker would connect to. Carries no vulnerability of its own — the exposure it creates belongs to the machines behind it |
| `ComputeInstance` | A machine an attacker can execute code on: a virtual machine, physical server or container host. The unit of lateral movement, and the only entity vulnerabilities attach to |
| `CVE` | A published software vulnerability record with the severity and exploitation signals used to judge it. Describes the flaw in isolation; whether it matters here is what the surrounding connections establish |
| `Application` | A deployed business application, owned by a business unit and ranked by criticality. The business end of a route: what makes a route matter is the criticality of what it terminates at, not its length |
| `Identity` | A permission-holding principal whose access an attacker inherits on compromising something — the credential a machine's processes run as, or a role that can be assumed |
| `IAMPolicy` | A named permission grant held by an identity, standing between the identity and the resources it can act on. Modelled separately because one grant is typically held by many identities, making an over-scoped grant a single point many routes cross |
| `CloudService` | A managed cloud resource holding or moving data — object store, database, secret store or message queue — reached through permissions rather than through the network. The exfiltration end of a route |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Endpoint` | `endpointId` | String | Unique identifier for the entry point, stable across scans of the external attack surface |
| `Endpoint` | `dnsName` | String | Public name an external attacker resolves to reach this entry point. Not unique: the same name exposed on two ports is two entry points |
| `Endpoint` | `port` | Integer | The port on which this entry point accepts connections from the public internet. One port each, not a range and not a list |
| `Endpoint` | `protocol` | String | Application-layer protocol served on that port, lower case |
| `ComputeInstance` | `instanceId` | String | Unique identifier for the machine, expected to be the cloud or asset-register identifier and stable for its lifetime |
| `ComputeInstance` | `hostname` | String | Operational hostname, for human recognition. Expected to be unique in practice but not relied on as an identifier |
| `ComputeInstance` | `environment` | String | Deployment environment — production, staging or development. Governs how seriously an exposure reads: an exploitable machine outside production matters only if a route leads from it into production |
| `ComputeInstance` | `networkSegment` | String | Label of the network zone or subnet the machine sits in, at the granularity segmentation is controlled at. Two machines sharing a segment are not thereby able to reach each other |
| `CVE` | `cveId` | String | The published vulnerability identifier |
| `CVE` | `cvssScore` | Float | Severity of the flaw in isolation, from 0.0 to 10.0, taking no account of this estate's exposure, compensating controls or asset value — the context the connections supply separately |
| `CVE` | `severity` | String | Qualitative severity band derived from the score, upper case. Carried for readability alongside the numeric value |
| `CVE` | `epssScore` | Float | Probability from 0.0 to 1.0 that the vulnerability will be exploited in the wild within the next 30 days. A likelihood, not a severity: a high likelihood on a weak flaw means something actually being used |
| `CVE` | `knownExploited` | Boolean | True when exploitation has been observed in the wild rather than merely predicted. The strongest single signal for prioritising an entry point |
| `CVE` | `publishedDate` | Date | Date the vulnerability record was first published — first publication, not last modification, and not when the flaw was introduced or discovered |
| `Application` | `applicationId` | String | Unique identifier in the application portfolio |
| `Application` | `name` | String | Business name of the application |
| `Application` | `tier` | String | Business criticality band, where the number ascends as criticality descends: the lowest-numbered band is the crown-jewel set whose compromise is materially damaging. Assigned by the business, never derived from the connections |
| `Application` | `businessUnit` | String | Business unit accountable for the application, used to route a finding to an owner |
| `Identity` | `identityId` | String | Unique identifier for the principal, expected to be the identity provider's own |
| `Identity` | `name` | String | Principal name as it appears in the identity provider |
| `Identity` | `identityType` | String | Kind of principal: a workload credential bound to a machine, an assumable role, or an interactive user account |
| `IAMPolicy` | `policyId` | String | Unique identifier for the permission grant |
| `IAMPolicy` | `name` | String | Grant name as it appears in the identity provider |
| `IAMPolicy` | `permissionLevel` | String | Coarse level of access granted — read, write or administrative. States the **highest** action permitted on any resource in its scope, not the typical one, so it reads as an upper bound |
| `CloudService` | `serviceId` | String | Unique identifier for the resource, expected to be the provider's own |
| `CloudService` | `name` | String | Resource name as it appears in the provider console |
| `CloudService` | `serviceType` | String | Kind of resource: object store, relational database, secret store or message queue |
| `CloudService` | `dataClassification` | String | Sensitivity of the data held, in ascending order from public through internal and confidential to restricted. Assigned by data governance, never derived from the connections |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `RESOLVES_TO` | `Endpoint` → `ComputeInstance` | The entry point resolves to this machine, making it directly reachable from outside. Each entry point resolves to at least one machine, and to several where traffic is load balanced; a machine may serve many entry points, or none if it is purely internal |
| `HAS_VULNERABILITY` | `ComputeInstance` → `CVE` | A scan confirmed the vulnerability present on this machine. Presence only — it asserts nothing about whether the flaw is reachable or exploitable in context. A machine may carry many vulnerabilities or none; one vulnerability may affect many machines |
| `CAN_REACH` | `ComputeInstance` → `ComputeInstance` | The source machine is permitted to open a network connection to the target on the stated port. Directed and asymmetric — reaching a machine does not imply the reverse, and mutual reachability is two separate connections. A claim about network permission only, not about credentials or a working exploit |
| `RUNS` | `ComputeInstance` → `Application` | The machine hosts the application, so compromise of the machine is compromise of the application. A machine may run many applications or none; an application may run on many machines where it is horizontally scaled |
| `RUNS_AS` | `ComputeInstance` → `Identity` | The credential the machine's processes execute as, and therefore the access an attacker inherits the moment they run code on it. Each machine runs as at most one such credential; a credential may be shared by many machines |
| `ASSUMES` | `Identity` → `IAMPolicy` | The identity holds this permission grant, so everything the grant allows is available to whoever controls the identity. An identity may hold many grants; a grant may be held by many identities, which is what makes one over-scoped grant a shared choke point |
| `HAS_ACCESS_TO` | `IAMPolicy` → `CloudService` | The grant reaches a cloud resource at the level it permits. The data-exfiltration hop: it needs no network path, so any identity holding the grant reaches the resource wherever it sits. One grant may reach many resources, or none; one resource may be reached by many grants |
| `HAS_ACCESS_TO` | `IAMPolicy` → `Application` | The grant reaches an application through its control plane at the level it permits. Distinct from reaching a cloud resource: this touches an application without compromising the machine running it, so a crown-jewel application can be exposed by a permission grant alone, with no lateral movement involved |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `HAS_VULNERABILITY` | `detectedOn` | Date | The date a scan **last confirmed** the vulnerability still present on this machine — last confirmation rather than first detection, so a recent date means the finding is current and an old one means the machine has not been rescanned. Distinct from the vulnerability's own publication date |
| `CAN_REACH` | `port` | Integer | The port on the target machine the source is permitted to connect to. One port per connection, not a range: a rule opening several ports between the same pair is several connections |
| `CAN_REACH` | `protocol` | String | Application-layer protocol permitted on that port, lower case, from the same set as an entry point's protocol |
