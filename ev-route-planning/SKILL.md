---
name: ev-route-planning
description: Plan electric vehicle routes across a logistics network with Neo4j — battery state-of-charge, charging stops, time-of-day travel, and Cypher 25 stateful path patterns across cities, charging stations, roads, and fleet vehicles.
metadata:
  neo4j-card-title: EV Route Planning
  neo4j-card-category: Manufacturing & Supply Chain
  neo4j-card-description: Plan electric vehicle routes across logistics networks with battery, charging and time constraints modeled as a connected graph.
  neo4j-icon-category: supply-chain
---

# EV Route Planning

Use this skill for supply chain and automotive logistics analysis: planning EV routes that respect battery range and shift length, finding where a fleet can charge, spotting charging coverage gaps, and answering which vehicles can serve a lane today.

Source reference:

- <https://neo4j.com/developer/industry-use-cases/manufacturing/supply-chain-management/ev-route-planning/>

This is a graph-modelling and query-pattern aid, not dispatch or transport-regulatory guidance. Treat computed routes as planning inputs requiring operational validation. The bundled sample data is synthetic: city names and coordinates are real French communes, but all roads, charging stations, operators and vehicle models are generated and represent nothing real.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: working out which electric vehicles can actually make a delivery run, and what the route looks like once charging stops are part of the plan. Battery range, charger power, dwell time and traffic interact, so roads, chargers and vehicles are best treated as one connected network — traverse from a depot carrying state of charge and elapsed time, dropping into charging stations where the battery needs them.
- The bundled sample data is a synthetic French logistics network: 150 cities, 100 charging stations across five operators, 440 road segments, and a 30-vehicle mixed fleet. Small enough to read, dense enough that answers aren't obvious — exactly one of the 30 vehicles can cover 400 km without stopping, and 12 cities sit more than two road hops from any charger.
- What you can help with: explaining the model, walking through the query patterns from a single vehicle's range to fleet-wide lane feasibility, finding charging coverage gaps, importing the sample data or adapting the model to their own depots, chargers and telematics, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the model or start importing data.

## Model

- `Geo` — a city, keyed on `name`.
- `ChargingStation` — a charging site, keyed on `name`.
- `Car` — a fleet vehicle, keyed on `id`.
- `ROAD` — a road segment. Three graph-spec definitions, one per endpoint pair: `Geo→Geo`, `Geo→ChargingStation`, `ChargingStation→Geo`.
- `CHARGE` — a self-loop on `ChargingStation`, one per charge tier.
- Full schema, mappings, and sample CSVs are in `GRAPH_MODEL.json` and `sample-data/`; runnable Cypher with expected results is in `QUERIES.md`.

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, which is the only route. Never offer a write-based seed, `LOAD CSV`, or a `CREATE` script instead. Importing is sufficient — **no post-import setup is required**, so do not improvise indexes, constraints, or labels after Import. The queries use only the three labels the import creates; the write-based appendix in `QUERIES.md` is not setup.
- Clarify the intended target database and connection before executing anything.
- `Geo` and `ChargingStation` share **no** label; graph spec 4.0.0 declares one primary label per node. Any traversal meaning "any location" must use `(:Geo|ChargingStation)`. A bare `(x:Geo)` is valid Cypher that returns rows while silently excluding all 100 charging stations, producing routes that never charge.
- `ROAD` is stored once per segment. Always traverse it undirected as `-[:ROAD]-`, never `-[:ROAD]->`, and never create reverse edges.
- Anchors are parameters, never hardcoded IDs. Offer the user a real anchor from query 0 in `QUERIES.md` rather than inventing one.
- `allReduce` and `REPEATABLE ELEMENTS` need Cypher 25 on Neo4j 2025.08+; the rest of `QUERIES.md` runs on Neo4j 5.x. Confirm the version before offering the stateful templates.
- Quantifier bounds like `{1,14}` are literals — Cypher rejects a parameter inside `{1,n}`. When a route query returns nothing, suspect the hop bound before the energy model.
- Inside the stateful accumulator, clamp state of charge at `$maxSoc` and cap delivered power at the vehicle's `max_charge_power_kw`. Omitting either produces routes the fleet cannot drive.
- The appendix in `QUERIES.md` is a label and index workaround on an already-imported graph, not a data seed and not setup. Offer it only after explicit confirmation that database writes are wanted, and say that running it breaks two of the bundled queries.

## Response Shape

When returning guidance, keep output structured:

```text
Model assumptions
Cypher (if requested)
What this optimizes
Tuning options
Validation approach
```
