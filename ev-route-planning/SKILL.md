---
name: ev-route-planning
description: Plan electric vehicle routes across a logistics network with Neo4j — battery state-of-charge, charging stops, time-of-day travel, and Cypher 25 stateful path patterns across cities, charging stations, roads, and fleet vehicles.
metadata:
  neo4j-card-title: EV Route Planning
  neo4j-card-category: Manufacturing
  neo4j-card-description: Plan electric vehicle routes across logistics networks with battery, charging and time constraints modeled as a connected graph.
---

# EV Route Planning

Use this skill for supply chain and automotive logistics analysis: planning EV routes that respect battery range and shift length, finding where a fleet can charge, spotting charging coverage gaps, and answering which vehicles can serve a lane today.

Source reference:

- <https://neo4j.com/developer/industry-use-cases/manufacturing/supply-chain-management/ev-route-planning/>

This is a graph-modelling and query-pattern aid, not dispatch or transport-regulatory guidance. Treat computed routes as planning inputs requiring operational validation. The bundled sample data is synthetic: city names and coordinates are real French communes, but all roads, charging stations, operators and vehicle models are generated and represent nothing real.

## Introducing this package

When the user first opens this package, greet them with a short introduction in your own words — don't recite this file. Convey:

- The core idea: working out which electric vehicles can actually make a delivery run, and what the route looks like once charging stops are part of the plan. Battery range, charger power, dwell time and traffic interact, so roads, chargers and vehicles are best treated as one connected network — traverse from a depot carrying state of charge and elapsed time, dropping into charging stations where the battery needs them.
- The bundled sample data is a synthetic French logistics network with a mixed fleet of vans, cars and rigid trucks. It is small enough to read and seeded so the answers aren't obvious: few vehicles can cover a long lane without stopping, and some cities sit beyond easy reach of any charger.
- What you can help with: explaining the reference ontology, walking through the query patterns from a single vehicle's range to fleet-wide lane feasibility, finding charging coverage gaps, importing the sample data or mapping their own depots, chargers and telematics onto the reference ontology, and running Cypher once a database is connected.

End with a clear next step, such as asking whether they'd like to explore the reference ontology or start importing data.

## Reference ontology

- Nodes: `Geo {name, lat, lon, region}` — a city, depot or delivery point, keyed on `name`; `ChargingStation {name, lat, lon, region, operator, power_kw}` — a charging site on the road network, keyed on `name`; `Car {id, model, vehicle_class, battery_capacity_kwh, efficiency_kwh_per_km, max_charge_power_kw, current_soc_percent}` — a fleet vehicle, keyed on `id`, with no connection to the network: it supplies the energy model a route is evaluated against.
- Relationships: `(Geo)-[:ROAD]->(Geo)`, `(Geo)-[:ROAD]->(ChargingStation)` and `(ChargingStation)-[:ROAD]->(Geo)` — one road-segment type declared once per endpoint pairing, each segment stored once and read in both directions; `(ChargingStation)-[:CHARGE]->(ChargingStation)` — a self-loop per charge option, distinguished by `tier`, so a route passes through a charging stop as an ordinary hop.
- Departures from the source page, by design: the page gives charging stations a `Geo` sub-label, while here each node has a single label, so cities and stations share none and "any location" is the union `(:Geo|ChargingStation)`; the page stores roads in both directions, while here each segment is stored once and traversed undirected; the page carries an hourly speed profile per road, while here each segment has a free-flow and a peak speed. The `Express` road class is a modelling device — one hop standing in for a long motorway run whose intermediate junctions are not decision points — not a real road category.
- The source demo page's `(x:Geo)` queries assume a shared label this reference ontology does not use: adapt them to `(:Geo|ChargingStation)` rather than relabelling the graph.
- Every node, relationship and property the queries use is loaded by Import; no query creates anything.
- The full reference ontology, with its import mappings, is in `ONTOLOGY.json`; runnable Cypher is in `QUERIES.md`.
- Call it the reference ontology. Users may say "model", "graph model", "data model" or "ontology" — treat these as the same thing.
- Treat its annotations as the authoritative meaning of each term — `description` above all, plus relationship counts. Quote them when explaining the reference ontology, rely on them when adapting queries to the user's own data, and never contradict them.

### Roles

| Role | In the reference ontology | What a substitute needs |
| ---- | ------------------------- | ----------------------- |
| Network place | `Geo` | A keyed node with latitude and longitude that road segments join; the corridor prune and route endpoints need the coordinates |
| Charging point | `ChargingStation` | A place on the same road network, reachable by road like any other, carrying the maximum power it can deliver |
| Road segment | `ROAD` | A link between two places carrying driving distance and a free-flow and a peak speed, traversable in either direction |
| Charge option | `CHARGE` | A per-option record at a charging point with dwell minutes and power, that a route can take as a step without leaving the site |
| Vehicle energy profile | `Car` | Usable battery capacity, consumption per kilometre, maximum charging power and current state of charge — no position on the network |

When the user's database differs from the reference ontology, map their labels onto these roles before rewriting anything from `QUERIES.md`. A role with no counterpart in their data means the patterns resting on it have no analogue — say so plainly rather than forcing a fit.

## Operational Constraints

For runnable examples:

- Data loads through the bundled `sample-data/` Import flow, and only through it. Never ship or offer a write-based data seed, a `LOAD CSV` statement, or a `CREATE` script as an alternative loading route.
- Clarify the intended target database and connection before executing, and confirm with the user before running anything that writes.
- No post-import setup is required — do not improvise indexes, constraints or labels after Import. The queries use only the three labels the import creates.
- Neo4j 5.x and Cypher 5 for most queries; the stateful route queries (`allReduce`, `REPEATABLE ELEMENTS`) need Cypher 25 on Neo4j 2025.08+. Confirm the version before offering them. No APOC or GDS.
- Queries open with a `/* @... */` annotation block. Keep the block with the query when showing or running it — it exists to help the user understand the query — and treat it as context, not ground truth: on any conflict, the Cypher logic wins. When adapting a query, update its annotations to match.
- Starting parameter values in `@params` are starting points, not defaults that fit any dataset. Read the result and retune before presenting anything as a finding.
- `@sample` describes the bundled sample data only. Use it only when the connected database holds that sample — you imported it in this conversation, or a lookup of the `@sample` anchor (for example its `$carId`) finds it. Then use its values as starting parameters, and treat a result that differs from it as a sign the import went wrong. Otherwise ignore it: never present it, or anything derived from it, as an expectation of the user's own data.
- `Geo` and `ChargingStation` share **no** label. Any traversal meaning "any location" must use `(:Geo|ChargingStation)`. A bare `(x:Geo)` is valid Cypher that returns rows while silently excluding every charging station, producing routes that never charge.
- `ROAD` is stored once per segment. Always traverse it undirected as `-[:ROAD]-`, never `-[:ROAD]->`, and never create reverse edges.
- Anchors are parameters, never hardcoded IDs. Offer the user a real anchor from **Available anchors** in `QUERIES.md` rather than inventing one.
- Quantifier bounds like `{1,14}` are literals — Cypher rejects a parameter inside `{1,n}` — and charge stops count as hops. When a route query returns nothing, suspect the hop bound before the energy model.
- Inside the stateful accumulator, clamp state of charge at `$maxSoc` and cap delivered power at the vehicle's `max_charge_power_kw`. Omitting either produces routes the fleet cannot drive.
- Computed routes are optimistic planning inputs: consumption is constant per kilometre, with no allowance for load, gradient or weather; charging is a flat rate over a fixed dwell, with no taper; and there is no charger availability or queueing, live traffic or driver-hours rule.

## Response Shape

When returning guidance, keep output structured:

```text
Reference ontology assumptions
Cypher (if requested)
What this optimizes
Tuning options
Validation approach
```
