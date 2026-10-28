# Business Entities: Ownership and Control — Tests

Expected results of every query in `QUERIES.md` on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it.

## How to run

1. Use a disposable Neo4j 5.6+ database (Aura or local). No APOC or GDS is needed.
2. Import the sample data through the Import flow from `ONTOLOGY.json`: all sixteen CSVs in `sample-data/`. Every node and relationship is mapped; nothing needs adding by hand.
3. No `SETUP.md` statements exist; run the queries straight after the import.
4. Run each query in `QUERIES.md` with the parameters below and compare against the section of the same name. Check the invariant first: it is the contract. The expected values are a convenience that holds for the CSVs as committed.
5. `SHOW CONSTRAINTS` should list at least the five node keys at the end of `QUERIES.md`. The reference ontology also flags `OWNS.percentage`, `OWNS.interestType`, `DIRECTOR_OF.role` and `OFFICER_OF.title` as required; note whether Import creates existence constraints for them.

## Sample-data profile

### Counts

| Label | Nodes |
| ----- | ----- |
| `Person` | 1,010 |
| `LegalEntity` | 528 |
| `Trust` | 25 |
| `Jurisdiction` | 27 (9 with `isOffshoreCentre` true: KY, VG, BM, JE, GG, IM, SC, BS, PA) |
| `Address` | 1,382 |

| Relationship | Count | Source |
| ------------ | ----- | ------ |
| `OWNS` (Person → LegalEntity) | 557 | `person_ownership.csv` |
| `OWNS` (LegalEntity → LegalEntity) | 268 | `entity_ownership.csv` |
| `OWNS` (Trust → LegalEntity) | 25 | `trust_ownership.csv` |
| `DIRECTOR_OF` | 1,113 | `directorships.csv` |
| `OFFICER_OF` | 191 | `officers.csv` |
| `TRUSTOR_OF` | 25 | `trustors.csv` |
| `BENEFICIARY_OF` | 52 | `trust_beneficiaries.csv` |
| `TRUSTEE_OF` (Person → Trust) | 18 | `person_trustees.csv` |
| `TRUSTEE_OF` (LegalEntity → Trust) | 12 | `entity_trustees.csv` |
| `INCORPORATED_IN` | 528 | `legal_entities.csv` |
| `REGISTERED_AT` | 528 | `legal_entities.csv` |
| `ESTABLISHED_IN` | 25 | `trusts.csv` |
| `RESIDES_AT` | 1,010 | `persons.csv` |
| `DIRECTLY_CONSOLIDATED_BY` | 181 | `direct_parents.csv` |
| `ULTIMATELY_CONSOLIDATED_BY` | 181 | `ultimate_parents.csv` |

No CSV repeats an endpoint pair, so every row becomes one relationship. Legal forms: 414 private limited companies, 49 privately held, 40 LLCs, 11 publicly held, 5 general partnerships, 4 limited partnerships, 3 not-for-profit corporations, 2 LLPs. 263 entities carry an LEI; 10 are inactive. Seven people are politically exposed. Some addresses were created for accountants that ended up hosting no company, so a few `Address` nodes have no relationships.

### How the data was generated

A seeded, deterministic script (`business-entities-gen.py`, kept outside the package; seed `20261028`) builds a background and then adds each seeded pattern by hand. Names, LEIs (well-formed, with valid ISO 7064 check digits) and registration numbers are synthetic; formation-agent building names are invented.

**Background**

- **18 corporate groups** (6 listed, 12 private) across GB, US, DE, FR, NL, JP, CH, SG, IE, CA, ES and IT, each a top company with 4–12 subsidiaries to depth 4. Subsidiaries are 100% owned 70% of the time, otherwise 51–90% with a local minority holder. About 5% sit in Bermuda or the Cayman Islands (captives) and 10% in LU, NL or IE (intermediate holdings). Every group member has an LEI and reports its direct and ultimate parent correctly. Group executives sit on subsidiary boards, and up to five subsidiaries share the group headquarters address (at most six entities per headquarters).
- **Six investment managers** holding 3–9.5% of listed tops; listed tops also have 2–4 individual holders of 0.4–5.5%. Private tops are owned by one to three family members at 30% or more each, so no family member falls below 25%.
- **Six cross-group minority stakes** of 15%, always from a lower-numbered group to a higher one, so the background contains no cycles.
- **170 small companies** (private limited, LLC, partnerships) owned in splits of 100, 50/50, 60/40, 70/30, 75/25, 34/33/33 or 40/30/30; 15% through a one-person holding company; 25% with an LEI (never those owned through a holding company). Couples share a home address only in 50/50 splits. Thirty percent are registered at one of ten accountants' addresses, each hosting at most six.
- **24 family trusts** (revocable, irrevocable, testamentary) under GB, US-DE, JE, GG, IM, BS or BM law, each owning 100% of a holding company. Trusts under Channel Islands or Bahamas law use one of three trust companies as corporate trustee; the others use one or two individual trustees.
- **47 formation-agent shells** at three addresses (see S7), each 100% owned by one person and directed by one or two of three nominee directors; nine hold a 20–45% stake in an onshore company.
- **Eight private-wealth structures**: a person owns a Jersey, Guernsey or Isle of Man holding company that owns 60–100% of a UK company — one offshore layer each.

**Seeded signals**

| Id | Pattern | Entities and people |
| -- | ------- | ------------------- |
| S1 | Layered offshore chain to a politically exposed person | Rodrigo Valente (PEP, P-0475) 100% → Ashgrove Ventures Ltd (VG, at Coralstone Chambers) 60% → Blue Lantern Holdings Ltd (KY, at Seagrape Place) 70% → Saint Ouen Investments Ltd (JE) 80% → Larkspur Freight Ltd (GB, E-0218, LEI). Valente's effective share is 33.6%. Near misses: Gareth Holloway owns 40% of Blue Lantern (effective 22.4%); Fiona Marchetti owns 30% of Saint Ouen (effective 24.0%). Daniel Kershaw 12% and Takumi Lehmann 8% hold Larkspur directly. |
| S2 | Ownership reached only by summing chains | Kestrelwerk Komponenten GmbH (E-0275): Dommelstroom Beheer B.V. 40%, Niklas Brunner 30%, Maarten Visser 15%, Pieter Dekker 15%. Dommelstroom: Katrin Vogel 60%, Visser 30%, Dekker 10%. Visser reaches 27.0% only by adding 15.0 direct and 12.0 indirect. Near misses: Vogel 24.0% (one chain), Dekker 19.0% (two chains). |
| S3 | Household collective ownership | Bramblefinch Bakeries Ltd (E-0277): the Hartigans at 14 Orchard Lane, Bristol — Margaret 12%, Colin 11% through Hartigan Holdings Ltd, Owen 9% — together 32%. Near miss: the Pembertons at 3 Abbey Place, Bristol, 10% + 9% = 19%. Imogen Radcliffe 30% is a beneficial owner alone; one more holder has 19%. |
| S4 | Trust in the chain | Calloway Family Trust (T-001, irrevocable, Jersey) owns 100% of Calloway Holdings Ltd (GG), which owns 45% of Coastway Hotels Ltd (E-0283). Trustor Edmund Calloway; corporate trustee Saltmarsh Trust Company Ltd (E-0279, directors Priya Kapoor and Mateo Nyberg, trustee of eight trusts); beneficiaries Harriet and Thomas Calloway. Other Coastway owners: Victoria Lockhart 35%, a third person 20%. |
| S5 | Control without ownership through a general partner | Jonathan Whitlock owns 100% of Ironwell Capital GP LLC (E-0308) and is its managing member. The GP holds a 1% general partner interest in Ironwell Capital Partners III LP (E-0309); three not-for-profit endowments and one investment manager hold 99% as limited partners. The fund owns 100% of Calderbrook Precision Engineering Ltd (E-0313) and 85% of Pennmoor Fluid Systems Inc. Whitlock controls Calderbrook while owning 1.0% of it. |
| S6 | Circular ownership | Ventaglio Holding S.p.A. (E-0201) owns 40% of Ventaglio Tessuti S.r.l., which owns 35% of Ventaglio Logistica S.r.l., which owns 30% of Ventaglio Holding. Separately, listed Hoshikawa Industries K.K. (E-0204) and Minatogawa Electric K.K. (E-0210) hold 8% and 6% of each other. |
| S7 | Formation-agent addresses | Coralstone Chambers, Road Town, VG (A-0627, 24 entities), Takamaka House, Victoria, SC (A-0628, 14), Seagrape Place, George Town, KY (A-0629, 11). Nominee directors Andreas Christodoulou (27 seats overall), Marie-Claire Pillay (22) and Desmond Ellery (19) sit on almost every board there. Near misses: group headquarters (at most six entities) and accountants' addresses (at most six). |
| S8 | Reported parent disagrees with ownership | Wealdmoor Group plc (E-0176) owns 100% of Fenmarsh Industries Ltd (E-0183), whose five subsidiaries still report Fenmarsh as ultimate parent and which reports none itself. Eichenfeld Medizintechnik GmbH is 45% owned by Eichenfeld Industrie AG but still reports it. Lavandière Iberia S.L. (60% owned by Groupe Lavandière SAS) and Larkspur Freight Ltd (80% owned by Saint Ouen) have LEIs and report no parent. |
| S9 | Buyer–supplier connection | Gareth Holloway is chief financial officer and an executive director of Pellingham Retail Group plc (E-0168) and owns 40% of Blue Lantern Holdings Ltd, two links above supplier Larkspur Freight Ltd. |

**Deliberate noise.** Of the chains from a person to an onshore entity with at least one company in between, 59 pass through exactly one offshore company (private-wealth structures, formation-agent shells holding onshore stakes, Fenmarsh's Cayman subsidiaries) and 872 through none. Nineteen addresses are shared homes (couples in 50/50 companies, beneficiaries living with a trustor, the Hartigans and the Pembertons). Group executives hold up to 13 board seats each. A diamond (two 100% subsidiaries jointly owning a third) exists in several groups and is not a cycle.

## Entity overview

- **Parameters:** `$entityId = 'E-0218'`.
- **Invariant:** one row for Larkspur Freight Ltd whose direct owners are Saint Ouen Investments Ltd, Daniel Kershaw and one other person, with percentages summing to 100, and no reported parents.
- **Expected:** private limited company, active, LEI `RNDR00WY8XAEDRFTQJ11`, registration number `03655717`, incorporated 2011-10-05, United Kingdom; registered address 217 Ash Avenue, London, GB. directOwners: Saint Ouen Investments Ltd (80.0%, shares), Daniel Kershaw (12.0%, shares), Takumi Lehmann (8.0%, shares). directors: Daniel Kershaw (executive director), Niamh Halvorsen (executive director). officers: Daniel Kershaw (chief executive officer). directHoldings 0. reportedDirectParent and reportedUltimateParent null.
- **Sensitivity:** an unknown entityId returns no row.

## Ownership structure

- **Parameters:** `$entityId = 'E-0218'`.
- **Invariant:** every S1 chain appears — the direct holdings, Saint Ouen ← Fiona Marchetti, Saint Ouen ← Blue Lantern ← Gareth Holloway, and the full four-link chain from Rodrigo Valente — and nothing else.
- **Expected:** 8 paths: Saint Ouen → Larkspur; Kershaw → Larkspur; Lehmann → Larkspur; Blue Lantern → Saint Ouen → Larkspur; Marchetti → Saint Ouen → Larkspur; Ashgrove → Blue Lantern → Saint Ouen → Larkspur; Holloway → Blue Lantern → …; Valente → Ashgrove → …. The trust branch returns nothing.
- **Sensitivity:** `$entityId = 'E-0283'` (Coastway Hotels Ltd) returns 4 ownership paths plus 4 trust-party paths (Edmund Calloway, Saltmarsh Trust Company Ltd, Harriet and Thomas Calloway).

## Corporate group

- **Parameters:** `$entityId = 'E-0176'`, `$controlPct = 50`.
- **Invariant:** every entity below Wealdmoor through majority links, including Fenmarsh Industries Ltd and all five of its subsidiaries, and no entity outside the group.
- **Expected:** 12 rows. Depth 1: Fenmarsh Industries Ltd (100.0), Wealdmoor Instruments Ltd (100.0), Wealdmoor Trading G.K. (100.0, JP), Wealdmoor Trading Ltd (51.0). Depth 2: Fenmarsh Brewing Ltd (100.0, KY), Wealdmoor Chemicals Ltd (90.0), Wealdmoor Marine Ltd (100.0), Wealdmoor Pharma Ltd (51.0, IE). Depth 3: Fenmarsh Chemicals Ltd (100.0, IE), Fenmarsh Properties Ltd (100.0, KY), Fenmarsh Telecom Ltd (90.0). Depth 4: Fenmarsh Instruments SARL (90.0, FR).
- **Sensitivity:** the two Cayman subsidiaries show `offshore` true. `$controlPct = 60` returns 10 rows, dropping the two 51% subsidiaries (Wealdmoor Pharma Ltd, Wealdmoor Trading Ltd), which have nothing below them. Running from `E-0183` (Fenmarsh Industries Ltd) returns its five subsidiaries only.

## Ultimate beneficial owners

- **Parameters:** `$entityId = 'E-0275'`, `$minPct = 25`.
- **Invariant:** Niklas Brunner (one direct chain) and Maarten Visser (two chains, each below 25, summing above it); Katrin Vogel and Pieter Dekker are absent.
- **Expected:** 2 rows — Niklas Brunner 30.0, chains 1, via [[]]; Maarten Visser 27.0, chains 2, via [[] and [Dommelstroom Beheer B.V.]].
- **Sensitivity:** `$minPct = 20` adds Katrin Vogel 24.0 (via Dommelstroom). `$minPct = 15` adds Pieter Dekker 19.0 (two chains). For `$entityId = 'E-0218'` (Larkspur) at 25: Rodrigo Valente 33.6, politicallyExposed true, one chain via Ashgrove, Blue Lantern, Saint Ouen; at 20 Fiona Marchetti 24.0 and Gareth Holloway 22.4 join. The 25 starting point is the regulatory convention, not tuned; the seeded near misses (24.0, 22.4, 19.0) were placed just below it on purpose.

## Trust look-through

- **Parameters:** `$entityId = 'E-0283'`.
- **Invariant:** exactly the Calloway Family Trust, with its trustor, its one corporate trustee and that trustee's directors, and its two beneficiaries.
- **Expected:** 1 row — T-001, Calloway Family Trust, irrevocable trust, governingLaw Jersey, effectivePct 45.0; trustors [Edmund Calloway]; trustees [Saltmarsh Trust Company Ltd]; beneficiaries [Harriet Calloway, Thomas Calloway]; corporateTrusteeDirectors [Priya Kapoor (Saltmarsh Trust Company Ltd), Mateo Nyberg (Saltmarsh Trust Company Ltd)].
- **Sensitivity:** an entity with no trust above it (E-0218) returns no rows. Every background trust's holding company returns its own trust at 100.0.

## Collective ownership by household

- **Parameters:** `$minPct = 25`.
- **Invariant:** the Hartigan household at Bramblefinch Bakeries and nothing else; the Pembertons (combined 19) are absent.
- **Expected:** 1 row — E-0277 Bramblefinch Bakeries Ltd, 14 Orchard Lane, Bristol, members Margaret Hartigan (12.0%), Colin Hartigan (11.0%), Owen Hartigan (9.0%) in any order, combinedPct 32.0.
- **Sensitivity:** `$minPct` of 20 and 30 return the same single row. At 18 the Pembertons (19.0) appear. Background couples only co-own 50/50 companies, where each member passes the threshold alone and is excluded — a generator choice that keeps the background quiet rather than a property of real data.

## Control without ownership

- **Parameters:** `$entityId = 'E-0313'`, `$controlPct = 50`, `$minPct = 25`.
- **Invariant:** Jonathan Whitlock appears with routes through Ironwell Capital GP LLC and a level above 0, alongside the entity's own directors; no limited-partner investor or person behind one appears.
- **Expected:** 3 rows — Jonathan Whitlock, controlRoutes [managing member of Ironwell Capital GP LLC, membership interest 100.0% of Ironwell Capital GP LLC] (any order), levelsAbove 2, effectivePct 1.0; then James Jansen [executive director of Calderbrook Precision Engineering Ltd, chief executive officer of Calderbrook Precision Engineering Ltd], 0, 0.0; Rebecca Ashworth [non-executive director of Calderbrook Precision Engineering Ltd], 0, 0.0.
- **Sensitivity:** without the general-partner rule the chain stops at the fund and Whitlock disappears — the point of the query. For a subsidiary of a listed group, the whole board of the group top is returned at the top level.

## Circular ownership

- **Parameters:** none.
- **Invariant:** exactly the two seeded cycles, each once; no background cycle and no diamond.
- **Expected:** 2 rows — [Ventaglio Holding S.p.A., Ventaglio Tessuti S.r.l., Ventaglio Logistica S.r.l.], entities 3, percentages [40.0, 35.0, 30.0], selfOwnershipPct 4.2; [Hoshikawa Industries K.K., Minatogawa Electric K.K.], entities 2, percentages [8.0, 6.0], selfOwnershipPct 0.48.
- **Sensitivity:** none — the background is acyclic by construction.

## Offshore layering

- **Parameters:** `$minOffshoreLayers = 2`.
- **Invariant:** the two S1 chains ending at Larkspur Freight Ltd, and no chain with a single offshore layer.
- **Expected:** 2 rows — Rodrigo Valente, politicallyExposed true, Larkspur Freight Ltd, chain [Ashgrove Ventures Ltd (VG), Blue Lantern Holdings Ltd (KY), Saint Ouen Investments Ltd (JE)], offshoreLayers 3, effectivePct 33.6; Gareth Holloway, false, Larkspur Freight Ltd, [Blue Lantern Holdings Ltd (KY), Saint Ouen Investments Ltd (JE)], 2, 22.4.
- **Sensitivity:** `$minOffshoreLayers = 1` returns 61 rows (the 59 one-layer chains plus these two). `3` returns Valente only. The starting value of 2 rests on a domain judgement (one offshore holding company is common in wealth planning), and the background was built to match it: every background chain has at most one offshore layer.

## Shared registered addresses

- **Parameters:** `$minEntities = 10`.
- **Invariant:** the three formation-agent addresses, each dominated by the nominee directors; no group headquarters or accountant's address.
- **Expected:** 3 rows — A-0627 Coralstone Chambers, 7 Wharf Cay Road, Road Town, VG: 24 entities, [VG], 3 directors, busiest Andreas Christodoulou (19), Marie-Claire Pillay (8), Desmond Ellery (5). A-0628 Suite 12, Takamaka House, Francis Rachel Street, Victoria, SC: 14, [SC], 3, Marie-Claire Pillay (11), Andreas Christodoulou (5), Desmond Ellery (3). A-0629 Seagrape Place, 88 Harbour Drive, George Town, KY: 11, [KY], 3, Desmond Ellery (10), Andreas Christodoulou (3), Marie-Claire Pillay (2).
- **Sensitivity:** the next-busiest addresses host 6 entities, so any value from 7 to 11 returns the same three rows. `$minEntities = 6` adds seven group headquarters and accountants' addresses, where most directors hold one seat and none holds more than five — the contrast the query is meant to show. The starting value of 10 is a round number with no strong prior; the background was capped at six per address.

## Reported versus ownership-derived parent

- **Parameters:** `$controlPct = 50`.
- **Invariant:** all S8 records and Larkspur Freight Ltd, and no correctly reporting group member.
- **Expected:** 9 rows, ordered by issue then name. differs (reported Fenmarsh Industries Ltd, ownership Wealdmoor Group plc): Fenmarsh Brewing Ltd, Fenmarsh Chemicals Ltd, Fenmarsh Instruments SARL, Fenmarsh Properties Ltd, Fenmarsh Telecom Ltd. no majority owner: Eichenfeld Medizintechnik GmbH (reported Eichenfeld Industrie AG, ownership null). not reported: Fenmarsh Industries Ltd (ownership Wealdmoor Group plc), Larkspur Freight Ltd (ownership Ashgrove Ventures Ltd), Lavandière Iberia S.L. (ownership Groupe Lavandière SAS).
- **Sensitivity:** `$controlPct = 40` still returns 9 rows, but different ones: Eichenfeld Medizintechnik's 45% now counts as control, so its row disappears, and Coastway Hotels Ltd (LEI, 45% owned by Calloway Holdings Ltd) appears as 'not reported'. Background entities owned through one-person holding companies or offshore holdings carry no LEI and are not checked.

## How two entities are connected

- **Parameters:** `$fromEntityId = 'E-0168'`, `$toEntityId = 'E-0218'`.
- **Invariant:** the shortest connection runs through Gareth Holloway's office at Pellingham and his stake in Blue Lantern Holdings Ltd.
- **Expected:** 2 rows, both hops 4 with via [Pellingham Retail Group plc, Gareth Holloway, Blue Lantern Holdings Ltd, Saint Ouen Investments Ltd, Larkspur Freight Ltd]. They differ only in the first hop: Holloway is both an executive director (`DIRECTOR_OF`) and the chief financial officer (`OFFICER_OF`) of Pellingham, and `allShortestPaths` returns one path per relationship.
- **Sensitivity:** with `REGISTERED_AT` and `RESIDES_AT` removed from the type list the answer is unchanged.
