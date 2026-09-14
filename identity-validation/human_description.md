# Identity Validation

Resolve one person across systems and channels, and surface the near-duplicate identifiers that signal synthetic identity fraud.

## Overview

### Identity resolution

Identity resolution is the problem of recognising that several records — captured at different times, through different channels, or in different systems — describe the same real person. "Robert J. Smith" in one system, "Bob Smith" in another and "R.J. Smith" in a third may all be one customer. Until they are recognised as one, that person's history stays fragmented across systems that know nothing about each other.

Two quite different needs sit on top of that problem. One is simply getting the record right: a single view of a customer for service, compliance or risk. The other is fraud detection, and it inverts the question — rather than proving two records are the same person, it looks for identifiers being reused in ways a genuine population does not produce.

There are three broad approaches. **Deterministic** matching applies exact rules: same national insurance number, same email. Simple, and brittle against ordinary real-world variation. **Probabilistic** matching scores how likely two records are to be the same, weighting rarer values more heavily. **Graph-based** matching follows connections between records to find indirect links, weighing several shared attributes and their combined strength at once. This reference ontology implements the third.

The difference shows up where the others fail. Consider three accounts: A and B share a phone number, B and C share an IP address, and no two of them share a name. No pairwise rule connects A to C, and no scoring of A against C finds anything — but following the connections does.

A related distinction runs through everything here. An **identifier** — a phone number, an email, a national identity number — is specific enough that sharing one is real evidence. A **descriptor** — a name, a city, an age — is far too common to mean anything alone. A property that would connect a large number of unrelated records is a descriptor, and its proper job is to corroborate a candidate found some other way, never to generate candidates itself.

### What it helps with

Modelling each attribute value as something records converge on turns matching into a traversal, and makes the fraud patterns visible alongside the genuine ones.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Records describing one person sit unconnected across systems | Let records that share an attribute value converge on it, so the connection between them exists in the data rather than having to be computed pairwise |
| Chains of shared attributes connect records that no direct comparison links | Follow attributes outward from one record and back down to others, finding records two or more steps away |
| Not all shared attributes are equally meaningful | Traverse through genuine identifiers to find candidates and bring descriptors in only to corroborate, rather than letting a common name generate matches |
| A single shared attribute is weak evidence on its own | Count and weight the several attributes two records share at once, and rank candidates by their combined strength |
| Synthetic identities are built by perturbing a real identity slightly | Look for near-duplicate identifiers — a national identity number differing by one character — alongside a reused contact detail, the combination that characterises a fabricated identity |
| Placeholder values pollute matching by connecting everything | Surface the attribute values shared by implausibly many records, so defaults and test data can be excluded before they generate thousands of false matches |
| The same place is written differently in different systems | Resolve addresses to a geographic point, so differently written forms of one address converge even though their text does not |
| Addresses that are not real are hard to enumerate | Treat failure to resolve to a point as the signal, rather than trying to list every way an address can be malformed |
| A candidate match needs human judgement | Return the cluster of records and the attributes joining them as a picture, so a reviewer can see what the evidence actually is |

Everything here produces ranked candidates, not confirmed identities. Shared attributes have innocent explanations — families share addresses, households share IP addresses, colleagues share phone numbers — and the ranking says where to look first rather than what is true. Convergence also depends on exact equality of values, so the same phone number written three ways makes three separate values and matches nothing; normalising before the data arrives matters more to the quality of the results than anything the ontology does afterwards.

## Ontology

The reference ontology is a hub and spokes: one kind of record, seven kinds of attribute it can carry, and one derived attribute a step further out.

The central entity is an **identity** — a single raw profile record exactly as one source system captured it, explicitly *not* yet resolved to a real person. Resolution is the outcome being looked for, never something the data asserts.

Each attribute value is an entity rather than a field. That is the whole mechanism. Two records carrying the same phone number do not merely hold equal text — they connect to the same phone value, and that convergence *is* the match signal. Nothing else needs modelling for it to work.

Two consequences follow. Convergence depends on exact equality, so anything not normalised beforehand silently fails to converge. And a missing attribute is represented by the absence of a connection rather than by an empty value, which is normal: a signup with no national identity number and a call-centre record with no email are ordinary, and their gaps carry no meaning.

Three of the entities are shaped by considerations worth knowing:

- **Name** is modelled like the others but is a descriptor, not an identifier. It is kept out of candidate generation deliberately and used only to corroborate.
- **Date of birth** is keyed on a hash of the full date rather than on the year-only value that gets displayed. Keying on the year would converge everyone born in the same year onto one value — a coincidence, not a match.
- **Address** carries a derived single-value identifier built from the street, town, region and postcode together, because the entity needs one identifying value and an address's real identity is composite. Keeping the raw street text preserves a suite or apartment number that a standardising step would discard.

**Location** sits one step beyond address and is where standardisation earns its keep: two differently written addresses that resolve to the same point converge there even though the address entities stay distinct.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Identity` | A single raw profile record exactly as one source system captured it, not yet resolved to a real person. The hub of the ontology — every attribute hangs off it |
| `PersonName` | A person's name as captured, shared by every record under exactly that name. A descriptor, not an identifier: kept out of candidate generation and used only to corroborate |
| `Phone` | A telephone number, shared by every record carrying exactly that number. A strong identifier and the most productive match signal here |
| `Email` | An email address, shared by every record carrying exactly that address. A strong identifier |
| `SSN` | A national identity number, shared by every record carrying exactly that value. The strongest identifier when it matches exactly — and, when two differ by a single character, the near-miss that most often marks a synthetic identity |
| `Address` | A postal address, shared by every record at exactly that address. Identified by the raw street text together with town, region and postcode, so detail a standardising step would discard is preserved |
| `DOB` | A date of birth, shared by every record with exactly that birthdate. Keyed on a hash of the full date rather than the value displayed |
| `IPAddress` | An address a profile was seen from. A device or channel signal rather than a property of a person — shared infrastructure explains a match here far more often than a shared phone number |
| `Location` | A geographic point one or more addresses resolve to. Where differently written forms of one place converge |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Identity` | `identityId` | String | Identifier for the profile record, unique across every source system rather than within one |
| `Identity` | `sourceSystem` | String | Name of the system the record was captured in. Agreement between records from *different* systems is what makes a match cross-channel rather than a duplicate within one feed |
| `PersonName` | `fullName` | String | The full name as captured, in masked display form, and the value records converge on. A masked key is weaker than the name behind it — two different people whose masks collide would share one value — so masks are expected to be disambiguated beforehand |
| `PersonName` | `firstName` | String | Given name, held for display and for future name-decomposition work. Not read by any matching logic |
| `PersonName` | `lastName` | String | Family name, held for display and for future name-decomposition work. Not read by any matching logic |
| `Phone` | `phoneNumber` | String | The telephone number in one fixed format. Convergence is exact-equality only, so the same number punctuated differently forms a separate value — normalising beforehand is expected |
| `Email` | `email` | String | The email address in masked display form. Exact equality only: no case folding and no handling of provider-specific aliasing |
| `SSN` | `ssn` | String | The national identity number, masked to its final digits in one fixed format. A near-miss is deliberately a separate value, since detecting near-misses is a query rather than a merge |
| `Address` | `addressId` | String | Canonical concatenation of the street, town, region and postcode, and the value records converge on. Exists because the entity needs a single identifying value; being derived from exactly those four, it behaves identically to a composite key |
| `Address` | `address` | String | Street portion as captured, including any suite or apartment detail |
| `Address` | `city` | String | Town or city portion. A descriptor — far too common to be evidence on its own |
| `Address` | `state` | String | Region portion, as a two-letter postal abbreviation. A descriptor |
| `Address` | `zipcode` | String | Postal code portion as captured, not extended to a longer form |
| `DOB` | `dateHash` | String | Keyed hash of the full unmasked birthdate, computed once when data is loaded and never displayed. Because it is keyed, values converge only within one deployment's secret |
| `DOB` | `dob` | String | The birthdate in masked, year-only display form. Display only, and deliberately not the key: its entropy is far too low to identify a person |
| `IPAddress` | `ip` | String | The address as captured. Exact equality only, with no normalisation between notations and no grouping into subnets |
| `Location` | `locationId` | String | Canonical form of the coordinate pair, and the value addresses converge on. With a real resolution provider its own stable place identifier is preferable, since repeated lookups of one place can differ in the last decimal and then fail to converge |
| `Location` | `latitude` | Float | Latitude of the point in decimal degrees, positive northwards. This and longitude are what proximity queries read |
| `Location` | `longitude` | Float | Longitude of the point in decimal degrees, positive eastwards |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `HAS_NAME` | `Identity` → `PersonName` | Attaches the name captured on this record. At most one per record, with absence rather than an empty value where there is none; a name may be shared by several records, but corroborates a match rather than generating one |
| `HAS_PHONE` | `Identity` → `Phone` | Attaches a telephone number captured on this record. At most one per record; a number may be shared by several records, and that convergence is the match signal |
| `HAS_EMAIL` | `Identity` → `Email` | Attaches an email address captured on this record. At most one per record; an address may be shared by several |
| `HAS_SSN` | `Identity` → `SSN` | Attaches a national identity number captured on this record. At most one per record; a value may be shared by several records — legitimately where they genuinely match, and suspiciously where they do not |
| `HAS_ADDRESS` | `Identity` → `Address` | Attaches a postal address captured on this record. At most one per record; an address may be shared by several, which is expected at a household and unremarkable alone |
| `HAS_DOB` | `Identity` → `DOB` | Attaches the date of birth captured on this record. At most one per record; a birthdate may be shared by several, so it corroborates a match rather than establishing one |
| `HAS_IP` | `Identity` → `IPAddress` | Attaches an address the record was seen from. At most one per record; an address may be shared by several |
| `GEOCODED_TO` | `Address` → `Location` | Resolves a postal address to the point it was placed at. At most one point per address; a point may be shared by several addresses, which is what makes differently written forms of one place converge. An address that failed to resolve carries none, and that absence is the implausible-address signal |
