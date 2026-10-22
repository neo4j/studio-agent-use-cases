# Configurable Bill of Materials — Tests

What each query in `QUERIES.md` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run: the resolution figures come from a Python reference implementation that mirrors the queries step for step — resolve, score-and-prune, garbage-collect, roll up — run over the CSVs.

## How to run

1. **Use a disposable Neo4j database.** Four queries write, and the pruning and
   clearing queries delete. Nothing writes to the configurable structure itself,
   but a shared database will accumulate `RESOLVED_LINK` relationships.
2. **Neo4j 2025.06 or later.** The resolve and prune queries open with
   `CYPHER 25` and use query chaining (`NEXT`) and scoped call subqueries. They
   will not parse on an earlier version. No APOC or GDS.
3. **Import the CSVs in `sample-data/` through the Import flow, using
   `ONTOLOGY.json` as the import definition.** This also creates the four
   node-key constraints; do not create them by hand. Check after import: 60
   nodes, 61 relationships, 0 relationships of type `RESOLVED_LINK`.
4. **Run `SETUP.md`'s single statement** — the relationship property index on
   `RESOLVED_LINK.idVariant`. It is recommended, not required: results are
   identical without it. Run it before timing anything.
5. **Clear a variant before re-resolving it.** Resolution merges rather than
   replaces, so re-running over an existing variant name merges the new result
   into the old and the two cannot afterwards be told apart. The scenarios below
   use three distinct variant names so all three can coexist.
6. Run each query in `QUERIES.md` with the parameters given in its section
   below, in the order the sections appear, and compare the result with the
   Invariant first and the Expected values second.

## Sample-data profile

A single configurable mountain bike, deliberately built so that all three of the
source page's constraint scenarios are reachable from the same structure.

### Nodes and relationships

**Nodes** — 60 in total.

| Label | Count | Notes |
| ----- | ----: | ----- |
| `Product` | 1 | `MB1`, from `products.csv` |
| `Assembly` | 6 | Three structural (`A-DRIVETRAIN`, `A-FRAMESET`, `A-BRAKESET`) and three wheel assemblies offered as options (`A-WHEEL-26`, `A-WHEEL-275`, `A-WHEEL-29`), from `assemblies.csv` |
| `ConfigGroup` | 13 | 9 categories; `rim` and `tire` each span three decisions, from `config_groups.csv` |
| `Part` | 40 | 11 fixed parts and 29 options, from `parts.csv` |

**Relationships** — 61 in total, before any variant is resolved.

| Type | Count | Notes |
| ---- | ----: | ----- |
| `REQUIRES` | 16 | 3 product → assembly (`product_requires_assembly.csv`), 1 product → decision (`product_requires_config_group.csv`, `qty` 2), 12 assembly → decision (`assembly_requires_config_group.csv`) |
| `HAS_PART` | 13 | `assembly_has_part.csv` |
| `HAS_OPTION` | 32 | 29 decision → part (`config_group_has_option_part.csv`), 3 decision → assembly (`config_group_has_option_assembly.csv`) |
| `RESOLVED_LINK` | 0 | Created only by the resolve query |

### Structure

```text
MB1
├── REQUIRES x1  A-DRIVETRAIN
│     ├── REQUIRES x1  CG-GEARING      3 options  (gearSystem)
│     ├── REQUIRES x1  CG-SHIFTER      3 options  (gearSystem)
│     ├── REQUIRES x1  CG-DERAILLEUR   3 options  (gearSystem)
│     └── HAS_PART     P-CHAIN x1, P-PEDAL x2, P-CRANKSET x1
├── REQUIRES x1  A-FRAMESET
│     ├── REQUIRES x1  CG-FRAME        3 options  (material)
│     ├── REQUIRES x1  CG-FINISH       3 options  (color)
│     └── HAS_PART     P-SEATPOST x1, P-SADDLE x1
├── REQUIRES x1  A-BRAKESET
│     ├── REQUIRES x2  CG-CALIPER      2 options  (brakeType)
│     └── HAS_PART     P-BRAKE-LEVER x2, P-BRAKE-HOSE x2
└── REQUIRES x2  CG-WHEELSET           3 options  (wheelSize)
      ├── A-WHEEL-26  ─ REQUIRES x1 CG-RIM-26 (2), CG-TIRE-26 (2)
      │                ─ HAS_PART P-HUB x1, P-SPOKE-26 x32
      ├── A-WHEEL-275 ─ REQUIRES x1 CG-RIM-275 (2), CG-TIRE-275 (2)
      │                ─ HAS_PART P-HUB x1, P-SPOKE-275 x32
      └── A-WHEEL-29  ─ REQUIRES x1 CG-RIM-29 (2), CG-TIRE-29 (2)
                       ─ HAS_PART P-HUB x1, P-SPOKE-29 x32
```

### Seeded properties of the structure

These are the design decisions the queries depend on. They are what an invariant
below means when it refers to "the seeded structure".

- **Nested decisions.** `CG-WHEELSET` offers whole assemblies, each of which
  carries two further decisions. This is the only reason the bottom-up pruning
  query has anything to do: rim and tire must be settled before the wheelset
  they sit inside can be costed. Without it, pruning would converge in one pass
  and `maxIterations` would be untestable.
- **A shared category across separate decisions.** `CG-RIM-26`, `CG-RIM-275`
  and `CG-RIM-29` all carry `category = "rim"`, so one constraint entry governs
  all three. The same holds for the three `tire` groups.
- **A shared option property across different categories.** `material` is the
  option property of both the `rim` and `frame-material` categories, whose value
  sets do not overlap (`Alloy`/`Carbon` against `Aluminum`/`Carbon`/`Steel`).
  This is deliberate: it proves that constraints are scoped by category and not
  by property name. A constraint denying `Carbon` on `rim` leaves the carbon
  frame untouched.
- **Three components that must agree.** `CG-GEARING`, `CG-SHIFTER` and
  `CG-DERAILLEUR` are separate decisions whose options carry the same
  `gearSystem` values. They are separate categories, so keeping them in step
  takes three constraint entries — which is the honest behaviour and worth
  seeing, since a reader may expect one entry to do it.
- **A part shared by several assemblies.** `P-HUB` is used by all three wheel
  assemblies. It exercises the merge on a repeated endpoint and means the
  structure is a directed acyclic graph rather than a tree.
- **A quantity that multiplies through a decision.** `MB1 -REQUIRES {qty:2}->
  CG-WHEELSET` means everything under the chosen wheel counts twice, including
  the 32 spokes, which reach 64 in the rollup. Nothing else in the structure
  multiplies across more than one level, so this is the only row that would
  catch a rollup that forgot to accumulate quantities down the path.
- **An option node offered by exactly one decision**, and **every decision
  required by exactly one parent**. Both hold throughout, and both are asserted
  in the reference ontology's relationship descriptions and counts.

### Deliberate background

- **`wheelSize`, `material`, `pattern`, `gearSystem`, `color` and `brakeType`
  are sparse.** Each is set only on the option nodes of the decision that varies
  along it, and empty in every other row of the CSV. Import is expected to skip
  empty values rather than set an empty string, and it matters, because
  `NOT y[prop.name] IN prop.allowList` evaluates differently against `null` and
  against `""`. Check it straight after the import:
  `MATCH (p:Part) WHERE p.material = "" RETURN count(*)` must return 0.
- **Three fixed parts hang off every branch** (chain/pedals/crankset,
  seatpost/saddle, levers/hoses, hub/spokes) so no query is a clean detector of
  decisions alone — a query that accidentally returned only option nodes would
  still look plausible.
- **Cost and weight do not rank together.** Steel is the cheapest frame and the
  heaviest; carbon is the lightest and by far the dearest. The scoring query
  therefore has a genuine trade-off to make, and its answer changes with the
  factors it is given. Had cheapest also been lightest, scoring would look
  correct under every parameter and prove nothing.
- **One decision is dominated.** `A-WHEEL-26` is both the cheapest and the
  lightest wheel, so no combination of negative scoring factors will choose
  another wheel size. This is deliberate and is noted under the pruning query's
  sensitivity: it is the case where scoring cannot express a preference and a
  constraint is the only lever.

### The three scenarios

Named variants so all three can coexist in one database.

**Scenario A — well-constrained**, variant `V-WELL`. One option allowed per
category; resolution alone settles everything and pruning has nothing to do.

```json
[
  {"category": "wheelset",       "properties": [{"name": "wheelSize",  "allowList": ["29"]}]},
  {"category": "gearing",        "properties": [{"name": "gearSystem", "allowList": ["9-Speed"]}]},
  {"category": "shifter",        "properties": [{"name": "gearSystem", "allowList": ["9-Speed"]}]},
  {"category": "derailleur",     "properties": [{"name": "gearSystem", "allowList": ["9-Speed"]}]},
  {"category": "rim",            "properties": [{"name": "material",   "allowList": ["Alloy"]}]},
  {"category": "tire",           "properties": [{"name": "pattern",    "allowList": ["Trail"]}]},
  {"category": "frame-material", "properties": [{"name": "material",   "allowList": ["Aluminum"]}]},
  {"category": "finish",         "properties": [{"name": "color",      "allowList": ["Black"]}]},
  {"category": "caliper",        "properties": [{"name": "brakeType",  "allowList": ["Hydraulic Disc"]}]}
]
```

**Scenario B — loose**, variant `V-LOOSE`. Deny lists only, on four categories;
the other five categories (`wheelset`, `frame-material`, `finish`, `caliper`,
`tire`) are left open entirely, and scoring settles what remains.

```json
[
  {"category": "rim",        "properties": [{"name": "material",   "denyList": ["Carbon"]}]},
  {"category": "gearing",    "properties": [{"name": "gearSystem", "denyList": ["7-Speed"]}]},
  {"category": "shifter",    "properties": [{"name": "gearSystem", "denyList": ["7-Speed"]}]},
  {"category": "derailleur", "properties": [{"name": "gearSystem", "denyList": ["7-Speed"]}]}
]
```

with `scoring = [{"field": "cost", "factor": -1.0}, {"field": "weight", "factor": -50.0}]`
and `maxIterations = 10`.

**Scenario C — over-constrained**, variant `V-OVER`. Scenario A with the gearing
allow list changed to `["11-Speed"]`, a value no option carries.

### Reference anchors

- Product `MB1` — the only product, and the `productId` for every scenario.
- Variants `V-WELL`, `V-LOOSE` and `V-OVER`, resolved with the constraint sets
  above.

### Editing notes

- **On `RESOLVED_LINK` and the reference ontology.** The reference ontology
  declares only the six structural relationships. It does not declare
  `RESOLVED_LINK`, and must not: Import validates that every relationship the
  reference ontology declares has a source table and a complete column mapping,
  including both node ID columns. A query-created relationship has no source
  data to point at, so declaring it puts the import definition into a permanent
  error state — the six entries this package originally carried produced six
  unmappable relationships and blocked the import outright. The definition of
  `RESOLVED_LINK` lives in `SKILL.md` instead. This is a deliberate, documented
  exception to the rule that every relationship type a query references
  resolves in the reference ontology.
- **The existence constraint on `REQUIRES.qty`.** `ONTOLOGY.json` sets
  `must_exist` on `qty` for the `productRequiresAssembly` entry only. The
  existence constraint is scoped to the relationship type, not to a node pair,
  so that one declaration covers the other two `REQUIRES` entries as well. Do
  not add `must_exist` to them: under the legacy format, redeclaring it minted a
  duplicate constraint name and the package failed to load. This note used to
  sit in the `qty` property descriptions and moved here in the migration to the
  current package format, so the descriptions carry only the domain meaning.
- **Where the shipped values came from.** The scoring factor −50 was not derived
  from the catalog (see the pruning query's sensitivity). `maxIterations = 10`
  is the source page's figure; the sample needs 2 passes. The explore query's
  depth bound of 8 is generous for a structure 4 hops deep.
- **Corrections made in the migration to the current package format.** The
  legacy scenario A invariant said every one of the 13 decisions ends with one
  link; only the 9 decisions scenario A reaches do — the rim and tire decisions
  under the two rejected wheels are never reached. The legacy scenario B text
  said four categories were left open; five are (`wheelset`, `frame-material`,
  `finish`, `caliper`, `tire`), and `rim` resolves to alloy alone. The legacy
  explore expectation said "within 5 hops"; the deepest route is 4. The weight
  factor crossovers are given exactly (−76.92 and −771.43) rather than rounded.
  The pruning and garbage-collection deletion counts (13 and 12) are new. Every
  other figure is unchanged and was re-derived from the CSVs.

## Explore the configurable structure of a product

- **Parameters:** `$productId = 'MB1'`.
- **Invariant:** returns paths covering every structural relationship reachable
  from the product, and only those: all 61 relationships in the seeded
  structure lie on at least one returned path, because every branch terminates
  in a part within the depth bound. No `RESOLVED_LINK` appears, whether or not a
  variant has been resolved.
- **Expected:** 61 paths — one ending at each structural relationship, because
  every node above the parts is reached by exactly one route from `MB1`. Path
  length runs from 1 to 4 hops; the deepest routes are
  `MB1 → CG-WHEELSET → A-WHEEL-* → CG-RIM-* / CG-TIRE-* → option`. `P-HUB`
  ends three paths, one per wheel assembly.
- **Sensitivity:** a bound of 3 truncates every route through a wheel assembly,
  losing rims and tires while still returning a plausible-looking graph. This is
  the failure mode to watch for on a deeper catalog: the query does not report
  that it truncated.

## List the configuration decisions and their options

- **Parameters:** none.
- **Invariant:** one row per `ConfigGroup` in the catalog, each listing exactly
  the options that decision offers, with `optionValue` non-null on every option.
  A null `optionValue` means a group's `optionProperty` does not match the
  property actually carried by its options, which would silently break every
  constraint written against that category.
- **Expected:** 13 rows, ordered by category then `configGroupId`. Option counts
  per row: 3 for `CG-WHEELSET`, `CG-GEARING`, `CG-SHIFTER`, `CG-DERAILLEUR`,
  `CG-FRAME` and `CG-FINISH`; 2 for `CG-CALIPER` and for each of the three rim
  and three tire groups. Rows for `CG-RIM-26`, `CG-RIM-275` and `CG-RIM-29` all
  report `category = "rim"`, and `CG-WHEELSET`'s options are assemblies, so their
  `optionId` comes from `assemblyId` rather than `partId` (values `26`, `27.5`,
  `29`).
- **Sensitivity:** this query is the check that the sparse option properties
  imported as intended. If Import writes empty strings instead of skipping empty
  cells, `optionValue` is still non-null here and the fault shows up only as a
  resolution that silently rejects everything.

## Resolve a variant against constraints

- **Parameters:** scenario A: `$productId = 'MB1'`, `$idVariant = 'V-WELL'`,
  `$constraints` as listed above. Scenario B: `$idVariant = 'V-LOOSE'` with the
  loose constraints. Scenario C: `$idVariant = 'V-OVER'` with the
  over-constrained set.
- **Invariant:**
  - Scenario A: every decision the variant reaches ends with exactly one
    outgoing `RESOLVED_LINK`, and the options selected are precisely those the
    allow lists name. The rim and tire decisions under the rejected wheels are
    never reached. No decision is left open and none is unsatisfied.
  - Scenario B: the decisions in the five categories with no constraint entry,
    plus the three partially denied drivetrain decisions, end with more than one
    surviving option; the `rim` decisions under every wheel keep only alloy,
    and no drivetrain component keeps a 7-Speed option.
  - Scenario C: `CG-GEARING` ends with no outgoing `RESOLVED_LINK` at all, and
    no `A-DRIVETRAIN → CG-GEARING` link is created, while every other decision
    resolves exactly as in scenario A.
  - In all three: no `RESOLVED_LINK` is created that is not reachable from
    `MB1`, and the structural relationships are untouched.
- **Expected:** `RESOLVED_LINK` counts for the variant: 30 for scenario A, 55 for
  scenario B, 28 for scenario C.
  - Scenario A's 30: 4 from the product, 8 from assemblies to decisions, 9 from
    assemblies to fixed parts, and 9 from decisions to their single chosen
    option (`A-WHEEL-29`, `P-CASSETTE-9S`, `P-SHIFTER-9S`, `P-DERAILLEUR-9S`,
    `P-FRAME-ALU`, `P-PAINT-BLACK`, `P-CALIPER-HYD`, `P-RIM-29-ALLOY`,
    `P-TIRE-29-TRAIL`).
  - Scenario B's 55: 4 from the product, 12 from assemblies to decisions, 13 to
    fixed parts and 26 option links. Ten decisions are open afterwards —
    `CG-WHEELSET` (3 options), `CG-FRAME` and `CG-FINISH` (3 each),
    `CG-GEARING`, `CG-SHIFTER`, `CG-DERAILLEUR` and `CG-CALIPER` (2 each), and
    the three tire decisions (2 each); the three rim decisions are settled to
    alloy.
  - Scenario C's 28: scenario A minus the cassette's option link and the
    `A-DRIVETRAIN → CG-GEARING` link.
- **Sensitivity:** scenario C differs from A only in one allow-list value, and
  its link count differs by 2. A count-only check would barely distinguish
  them, which is why the invariant is stated in terms of which decision is
  empty.

## Show a resolved bill of materials

- **Parameters:** `$idVariant = 'V-WELL'`, then `'V-LOOSE'`, then `'V-OVER'`.
- **Invariant:** returns exactly the resolved links of the named variant and
  nothing belonging to another variant. Run against `V-LOOSE` before and after
  pruning, the second result is a strict subset of the first.
- **Expected:** path counts equal the link counts above: 30, 55 and 28
  respectively; `V-LOOSE` drops to 30 after pruning and garbage collection.
- **Sensitivity:** a misspelt variant name returns zero rows rather than an
  error, which is indistinguishable from a variant that resolved to nothing.
  Check the count against the resolve step.

## Prune undecided decisions by scoring

- **Parameters:** `$idVariant = 'V-LOOSE'`,
  `$scoring = [{"field": "cost", "factor": -1.0}, {"field": "weight", "factor": -50.0}]`,
  `$maxIterations = 10`.
- **Invariant:** after the query, no decision reachable from the product has
  more than one outgoing `RESOLVED_LINK` for the variant. Nested decisions are
  settled before the decision containing them: the rim and tire groups under a
  wheel are decided before `CG-WHEELSET` chooses between the wheels, and the
  wheel branch chosen is the one whose total score over its entire sub-branch is
  highest. Run on `V-WELL`, the query changes nothing, because no decision has
  more than one option.
- **Expected:** on `V-LOOSE`, 2 passes (rim and tire, then wheelset) delete 13
  option links — 2 from `CG-WHEELSET`, `CG-FRAME` and `CG-FINISH` each, 1 from
  `CG-GEARING`, `CG-SHIFTER`, `CG-DERAILLEUR` and `CG-CALIPER` each, and 1 from
  each tire decision — taking the variant from 55 links to 42. Selections:
  `A-WHEEL-26`, `P-RIM-26-ALLOY`, `P-TIRE-26-TRAIL`, `P-CASSETTE-9S`,
  `P-SHIFTER-9S`, `P-DERAILLEUR-9S`, `P-FRAME-STEEL`, `P-PAINT-BLACK`,
  `P-CALIPER-MECH`. After garbage collection the variant holds 30 links and
  rolls up to cost 1015.60, weight 9.294 kg.
- **Sensitivity:** the weight factor is the interesting one, and the frame is
  where it bites. Against cost factor −1.0:

  | Weight factor | Frame chosen | Why |
  | ---: | --- | --- |
  | −50 | `P-FRAME-STEEL` | 190 + 50×2.60 = 320 beats aluminum's 337.50 |
  | −76.92 | crossover | steel and aluminum score equally (50 / 0.65) |
  | −100 | `P-FRAME-ALU` | 435 beats steel's 450 |
  | −771.43 | crossover | aluminum and carbon score equally (540 / 0.70) |
  | −800 | `P-FRAME-CARBON` | 1780 beats aluminum's 1800 |

  At −100 the rollup after pruning is cost 1065.60, weight 8.644 kg; at −800 it
  is cost 1605.60, weight 7.944 kg.

  The shipped starting value of −50 was **not** derived from the catalog: it is
  the round figure nearest a plausible willingness to pay to save a kilogram on
  a bicycle, chosen before the crossovers above were computed. It happens to
  select the cheapest frame, which is the least interesting of the three
  outcomes — an engineer demonstrating the package may prefer −100, where
  scoring visibly trades cost against weight rather than simply minimising cost.
  `QUERIES.md` states the factor as an exchange rate and gives no
  catalog-derived justification, which is correct.

  `maxIterations` needs only 2 passes here (rim and tire, then wheelset); 10 is
  the source page's figure and leaves headroom. Setting it to 1 leaves
  `CG-WHEELSET` undecided and is the cheapest way to check that the bottom-up
  ordering is really doing the work.

  The wheelset cannot be steered by scoring at all: `A-WHEEL-26` is both cheapest
  and lightest, so it wins under every negative factor pair. Use a `wheelset`
  constraint, not scoring, to demonstrate choosing a larger wheel.

## Remove resolved links detached from the product

- **Parameters:** `$idVariant = 'V-LOOSE'`, after pruning.
- **Invariant:** after the query, every remaining `RESOLVED_LINK` of the variant
  lies on a path from the product. Running it a second time deletes nothing.
  Running it on a variant that needed no pruning deletes nothing.
- **Expected:** on `V-LOOSE`, 12 links deleted, leaving 30 — for each of the two
  discarded wheel assemblies (`A-WHEEL-275`, `A-WHEEL-29`), its links to its rim
  and tire decisions, to `P-HUB` and to its spokes, and the surviving option
  link of each of those two decisions. On `V-WELL` and `V-OVER`: zero deletions.
- **Sensitivity:** the reference implementation collects garbage after each
  pruning pass rather than only at the end. Doing it once at the end reaches the
  same final state here, because the discarded branches are never re-examined;
  on a structure where a decision sits beneath two different options this would
  not hold, and the sample data does not cover that case.

## Roll up weight and cost of a resolved variant

- **Parameters:** `$idVariant = 'V-WELL'`, then `'V-LOOSE'` after pruning and
  garbage collection, then `'V-OVER'`.
- **Invariant:** the total is the sum over every part at the bottom of the
  resolved structure of its per-unit value times the product of the quantities
  on the path from the product down to it. The `qty = 2` on the wheelset
  decision must multiply through: 32 spokes must be counted 64 times, and the
  chosen rim, tire and hub twice each. A rollup that ignored path quantities
  would return a noticeably lighter, cheaper bike and would not otherwise look
  wrong.
- **Expected:**

  | Variant | Weight (kg) | Cost |
  | --- | ---: | ---: |
  | `V-WELL` | 8.948 → reported as 8.95 | 1164.80 |
  | `V-LOOSE` after pruning | 9.294 → reported as 9.29 | 1015.60 |
  | `V-OVER` | 8.678 → reported as 8.68 | 1112.80 |

  Floating-point accumulation may make the last digits differ before rounding;
  the query rounds to two decimals, which absorbs it.

  `V-OVER` is the point of this section: it totals cleanly and reports a bike
  with no cassette. Exactly 52.00 and 0.27 kg below `V-WELL` — the missing part
  — and nothing in the result says so.
- **Sensitivity:** run on `V-LOOSE` before pruning and the figure is a sum over
  every surviving option at once — cost 3458.00, weight 24.938 kg, far beyond
  any buildable bike — and still returned without complaint.

## Find configuration decisions the constraints could not satisfy

- **Parameters:** `$productId = 'MB1'`, `$idVariant = 'V-OVER'`; then the same
  for `'V-WELL'` and `'V-LOOSE'`.
- **Invariant:** returns exactly the decisions that the variant reaches through
  resolved links but never resolves. For `V-OVER` that is `CG-GEARING` and
  nothing else; for a variant whose constraints are all satisfiable it returns
  nothing. Every returned path starts at the product, so the branch containing
  the contradiction is visible rather than just the decision.
- **Expected:** one path for `V-OVER` (`MB1 → A-DRIVETRAIN → CG-GEARING`), zero
  rows for `V-WELL`, zero rows for `V-LOOSE` both before and after pruning.
- **Sensitivity:** run against a variant name that was never resolved, the query
  returns zero rows, which reads identically to a satisfiable configuration.
  Guard it by confirming the variant has resolved links at all.

## Clear a resolved variant

- **Parameters:** `$idVariant = 'V-LOOSE'`.
- **Invariant:** deletes every `RESOLVED_LINK` carrying the named variant and no
  other relationship. Node and structural relationship counts are unchanged:
  60 nodes and 61 structural relationships before and after. Other variants'
  links survive untouched.
- **Expected:** on `V-LOOSE` before pruning: 55 relationships deleted; after
  pruning and garbage collection: 30. Clearing all three variants returns the
  database to `RESOLVED_LINK` count 0.
- **Sensitivity:** the merge in the resolve query keys on `idVariant` and
  `relType` only, so re-resolving without clearing first produces a union of two
  constraint sets with no record of which link came from which. There is no
  query that detects this afterwards; it is the reason the clear step is listed
  as a prerequisite of re-resolution rather than as an optional tidy-up.
