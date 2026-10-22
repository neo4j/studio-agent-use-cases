# EV Route Planning — Query Guidance

Cypher for the `ev-route-planning` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database.

## Prerequisites

- Neo4j 5.x, Cypher 5 — except **Lane feasibility across the fleet — which vehicles can serve this lane today**, **Feasible routes under battery and time constraints** and **Best route, scored — one recommendation with the numbers behind it**, which need Cypher 25 on Neo4j 2025.08+ (`allReduce`, `REPEATABLE ELEMENTS`). Confirm the version before offering them. No APOC or GDS.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology. No post-import setup is required.
- The node keys in `ONTOLOGY.json` make `Geo.name`, `ChargingStation.name` and `Car.id` unique, so every anchored lookup is an index seek rather than a label scan.
- `Geo` and `ChargingStation` share no label: "any location" is the union `(:Geo|ChargingStation)`. A bare `(x:Geo)` is valid Cypher that silently excludes every charging station, so its routes never charge — and nothing errors.
- `ROAD` is stored once per segment: always traverse it undirected, `-[:ROAD]-`. `CHARGE` is a self-loop on `ChargingStation`; a station name repeated on consecutive hops of a route is a charge stop, not a bug.
- Bounds such as `*1..2` and `{1,14}` are literals — Cypher rejects a parameter inside them — and charge stops count as hops. When a route query returns nothing, suspect the bound before the energy model.
- Anchors are parameters, never hardcoded IDs. Ask the user which entity they want, or offer a real one from **Available anchors**. Do not invent IDs.
- Point and tabular queries come first, then the graph and visualisation queries, which return nodes, relationships, and paths for Neo4j Browser or Bloom to draw. Keep visualisation results bounded with `$limit`.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Available anchors

```cypher
/*
 * @name           Available anchors
 * @description    Enumerates the valid anchor values for the parameterised
 *                 queries — every city, charging station and vehicle — so
 *                 the agent never has to guess or hardcode an ID.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per Geo, ChargingStation and Car node: kind
 *                 ('city', 'station' or 'vehicle'), id (the node key) and a
 *                 descriptive label.
 * @usage          Run before any anchored query when the user has not named
 *                 an entity, and offer a few real anchors. On a large
 *                 network, filter or page the rows.
 * @tags           anchors, orientation, city, station, vehicle
 * @sample         Bundled sample data only: returns 280 rows — 150 cities,
 *                 100 stations and 30 vehicles.
 */
MATCH (c:Geo)
RETURN 'city' AS kind, c.name AS id, c.region AS label
UNION
MATCH (s:ChargingStation)
RETURN 'station' AS kind, s.name AS id,
       toString(s.power_kw) + ' kW ' + s.operator AS label
UNION
MATCH (v:Car)
RETURN 'vehicle' AS kind, v.id AS id,
       v.model + ' (' + v.vehicle_class + ', ' + toString(v.current_soc_percent) + '%)' AS label;
```

## Reference ontology sanity check — node and relationship counts

```cypher
/*
 * @name           Reference ontology sanity check — node and relationship counts
 * @description    Counts every node label and relationship type to confirm
 *                 the import completed and that every ROAD table loaded.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: cities (Geo nodes), charging_stations, cars,
 *                 road_segments (ROAD relationships, each counted once) and
 *                 charge_options (CHARGE self-loops).
 * @usage          Run straight after an import. road_segments should equal
 *                 the road rows across all three ROAD tables — near the
 *                 place-to-place table alone means routes will never
 *                 charge. charge_options of one per station means the
 *                 parallel tiers merged on import.
 * @tags           sanity-check, import, orientation
 * @sample         Bundled sample data only: returns 1 row — cities 150,
 *                 charging_stations 100, cars 30, road_segments 440,
 *                 charge_options 200.
 */
MATCH (c:Geo)
WITH count(c) AS cities
MATCH (s:ChargingStation)
WITH cities, count(s) AS charging_stations
MATCH (v:Car)
WITH cities, charging_stations, count(v) AS cars
MATCH ()-[r:ROAD]->()
WITH cities, charging_stations, cars, count(r) AS road_segments
MATCH ()-[ch:CHARGE]->()
RETURN cities, charging_stations, cars, road_segments, count(ch) AS charge_options;
```

## Road network by class — the four-tier hierarchy

```cypher
/*
 * @name           Road network by class — the four-tier hierarchy
 * @description    Shows how segment count, distance and speed are
 *                 distributed across the road classes (road_class).
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per road_class: segments, avg_km (mean
 *                 distance_km, 1 dp), total_km and top_free_flow_kph (the
 *                 highest free_flow_speed_kph in the class), ordered by
 *                 segments descending.
 * @usage          Orientation before route planning: a class of few, long
 *                 segments is the long-haul tier routes lean on.
 * @tags           road, network, orientation
 * @sample         Bundled sample data only: returns 4 rows — Motorway 162
 *                 (avg 67.9 km), Trunk 162 (avg 71.4), Local 63 (avg 43.4),
 *                 Express 53 (avg 158.5, top free-flow 130 kph).
 */
MATCH ()-[r:ROAD]->()
RETURN r.road_class                 AS road_class,
       count(*)                     AS segments,
       round(avg(r.distance_km), 1) AS avg_km,
       round(sum(r.distance_km))    AS total_km,
       max(r.free_flow_speed_kph)   AS top_free_flow_kph
ORDER BY segments DESC;
```

## Vehicle range — one vehicle's usable range from telemetry

```cypher
/*
 * @name           Vehicle range — one vehicle's usable range from telemetry
 * @description    Turns a vehicle's current state of charge into the
 *                 distance it can cover before dropping to the reserve:
 *                 the usable kWh above the reserve over
 *                 efficiency_kwh_per_km.
 * @params         carId - Car.id of the vehicle. Ask the user, or offer one
 *                     from Available anchors.
 *                 reserveSoc - The do-not-drop-below floor, as a percentage
 *                     of battery capacity. Start at 10, a common operational
 *                     reserve, and raise it for conservative planning.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: car_id, model, vehicle_class, battery_kwh,
 *                 soc_percent, max_charge_kw, usable_kwh (1 dp) and
 *                 range_km (rounded). No row for an unknown carId.
 * @usage          Constant consumption, with no allowance for load,
 *                 gradient, weather or speed — an upper bound on real range.
 *                 A negative range means the vehicle is already below the
 *                 reserve.
 * @tags           vehicle, range, state-of-charge
 * @sample         Bundled sample data only: $carId = 'EV-013', $reserveSoc
 *                 = 10.0 returns 1 row — Aurex Estate 77, Fleet Car, 77.0
 *                 kWh, 95.0% SoC, max charge 150.0 kW, usable 65.5 kWh,
 *                 range_km 385.
 */
MATCH (c:Car {id: $carId})
WITH c, c.battery_capacity_kwh * (c.current_soc_percent - $reserveSoc) / 100.0 AS usable_kwh
RETURN c.id                   AS car_id,
       c.model                AS model,
       c.vehicle_class        AS vehicle_class,
       c.battery_capacity_kwh AS battery_kwh,
       c.current_soc_percent  AS soc_percent,
       c.max_charge_power_kw  AS max_charge_kw,
       round(usable_kwh, 1)   AS usable_kwh,
       round(usable_kwh / c.efficiency_kwh_per_km) AS range_km;
```

## Charging station detail — one station, its charge tiers and the roads that reach it

```cypher
/*
 * @name           Charging station detail — one station, its charge tiers and the roads that reach it
 * @description    Inspects a single charging site before routing through
 *                 it: its power, operator and region, the charge options
 *                 (CHARGE self-loops) it offers, and every road segment
 *                 joining it to the network.
 * @params         stationName - ChargingStation.name of the site. Ask the
 *                     user, or offer one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: station, site_power_kw, operator, region,
 *                 charge_tiers ('<tier> (<time_in_minutes> min)', in tier
 *                 order) and connected_roads ('<neighbour> via <road_ref>
 *                 (<distance_km> km)', in no fixed order).
 * @usage          Two roads means a mid-corridor site; one, an urban spur.
 *                 A vehicle draws the lower of power_kw and its
 *                 max_charge_power_kw.
 * @tags           station, charging, inspection
 * @sample         Bundled sample data only: $stationName = 'CS-A7-01'
 *                 returns 1 row — 300.0 kW, ElectraRoute,
 *                 Auvergne-Rhone-Alpes, tiers ['full (40 min)', 'top-up (15
 *                 min)'], roads to Lyon via A7 (159.8 km) and Marseille via
 *                 A7 (155.2 km).
 */
MATCH (s:ChargingStation {name: $stationName})
OPTIONAL MATCH (s)-[ch:CHARGE]->(s)
WITH s, ch ORDER BY ch.tier
WITH s, collect(DISTINCT ch.tier + ' (' + toString(ch.time_in_minutes) + ' min)') AS charge_tiers
OPTIONAL MATCH (s)-[r:ROAD]-(n:Geo|ChargingStation)
RETURN s.name     AS station,
       s.power_kw AS site_power_kw,
       s.operator AS operator,
       s.region   AS region,
       charge_tiers,
       collect(n.name + ' via ' + r.road_ref + ' (' + toString(r.distance_km) + ' km)') AS connected_roads;
```

## Charging options near a city — stations within two road hops, by depth

```cypher
/*
 * @name           Charging options near a city — stations within two road hops, by depth
 * @description    Finds where a vehicle leaving a city can charge: every
 *                 charging station within two ROAD hops, with the fewest
 *                 hops needed to reach it.
 * @params         cityName - Geo.name of the city. Ask the user, or offer
 *                     one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per reachable station: station, hops (1 or 2),
 *                 power_kw and operator, ordered by hops, then power_kw
 *                 descending.
 * @usage          The 1..2 hop bound is a literal; widen it on a sparse
 *                 network. Hops are not distance — one long express hop can
 *                 be farther than two short ones.
 * @tags           charging, city, coverage
 * @sample         Bundled sample data only: $cityName = 'Lyon' returns 10
 *                 rows — 7 stations at 1 hop (CS-A89-01, CS-A7-01,
 *                 CS-A89-02, CS-A36-01, CS-A31-02, CS-A6-01, CS-LYON-02)
 *                 and 3 at 2 hops (CS-A72-01, CS-GRENOBLE-15, CS-N79-01).
 */
MATCH (hub:Geo {name: $cityName})
MATCH p = (hub)-[:ROAD*1..2]-(cs:ChargingStation)
WITH cs, min(length(p)) AS hops
RETURN cs.name     AS station,
       hops,
       cs.power_kw AS power_kw,
       cs.operator AS operator
ORDER BY hops, power_kw DESC;
```

## Charging capacity by region

```cypher
/*
 * @name           Charging capacity by region
 * @description    Compares installed charging capacity across regions to
 *                 spot thin coverage.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per ChargingStation.region: sites, total_kw (sum
 *                 of power_kw), avg_kw (1 dp) and best_kw, ordered by
 *                 total_kw descending.
 * @usage          Capacity does not necessarily track connectivity: compare
 *                 a region's total_kw with how many road links its hubs
 *                 carry, since a well-connected region with little
 *                 installed power is a likely bottleneck. Regions with no
 *                 station at all do not appear.
 * @tags           charging, capacity, region, coverage
 * @sample         Bundled sample data only: returns 12 rows, led by
 *                 Nouvelle-Aquitaine with 16 sites and 4050 kW; last is
 *                 Ile-de-France with 4 sites and 725 kW.
 */
MATCH (cs:ChargingStation)
RETURN cs.region                   AS region,
       count(*)                    AS sites,
       round(sum(cs.power_kw))     AS total_kw,
       round(avg(cs.power_kw), 1)  AS avg_kw,
       max(cs.power_kw)            AS best_kw
ORDER BY total_kw DESC;
```

## Operator footprint

```cypher
/*
 * @name           Operator footprint
 * @description    Shows how each charging operator is spread across the
 *                 network: site count, installed power, regions covered and
 *                 high-power sites.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per ChargingStation.operator: sites, total_kw,
 *                 regions_covered and high_power_sites (sites with power_kw
 *                 of 300 or more), ordered by sites, then total_kw,
 *                 descending.
 * @usage          The 300 kW high-power cut-off is a literal; set it to
 *                 what the fleet's heaviest vehicles can accept. Operator
 *                 matters for access and tariffs, not routing.
 * @tags           charging, operator, coverage
 * @sample         Bundled sample data only: returns 5 rows — ElectraRoute
 *                 22 sites / 5750 kW, NordVolt 22 / 5000, ChargeLine 19 /
 *                 4550, AmperGrid 19 / 4300, VoltWay 18 / 3575; each covers
 *                 10 or 11 of the 12 regions.
 */
MATCH (cs:ChargingStation)
RETURN cs.operator                AS operator,
       count(*)                   AS sites,
       round(sum(cs.power_kw))    AS total_kw,
       count(DISTINCT cs.region)  AS regions_covered,
       count(CASE WHEN cs.power_kw >= 300 THEN 1 END) AS high_power_sites
ORDER BY sites DESC, total_kw DESC;
```

## Charge tiers — what each dwell time delivers

```cypher
/*
 * @name           Charge tiers — what each dwell time delivers
 * @description    Quantifies the core routing trade-off, dwell time against
 *                 energy: for each charge tier, how many options exist and
 *                 the energy an option offers over its dwell (power_kw ×
 *                 time_in_minutes / 60).
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per tier and dwell: tier, options, dwell_minutes,
 *                 avg_kwh_delivered and best_kwh_delivered (1 dp), ordered
 *                 by dwell_minutes.
 * @usage          Figures are what the site offers; a vehicle draws the
 *                 lower of power_kw and its max_charge_power_kw. Charging is
 *                 modelled as linear, but real charge curves taper sharply
 *                 above roughly 80% state of charge, so a long dwell
 *                 delivers less than shown. Informs whether a longer dwell
 *                 beats an extra stop.
 * @tags           charging, tier, energy, trade-off
 * @sample         Bundled sample data only: returns 2 rows — top-up: 100
 *                 options, 15 min, avg 57.9 kWh, best 87.5; full: 100
 *                 options, 40 min, avg 154.5 kWh, best 233.3.
 */
MATCH (cs:ChargingStation)-[ch:CHARGE]->(cs)
RETURN ch.tier            AS tier,
       count(*)           AS options,
       ch.time_in_minutes AS dwell_minutes,
       round(avg(ch.power_kw * ch.time_in_minutes / 60.0), 1) AS avg_kwh_delivered,
       round(max(ch.power_kw * ch.time_in_minutes / 60.0), 1) AS best_kwh_delivered
ORDER BY dwell_minutes;
```

## Charging coverage gaps — cities with no station within two road hops

```cypher
/*
 * @name           Charging coverage gaps — cities with no station within two road hops
 * @description    Finds the planning blind spots: cities with no charging
 *                 station reachable within two ROAD hops, and how many road
 *                 links each has.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per stranded city: stranded_city, region and
 *                 road_links (its ROAD count), ordered by road_links
 *                 descending, then name.
 * @usage          Depth-sensitive: the 1..2 bound is a literal inside the
 *                 EXISTS subquery, and widening it closes gaps, so always
 *                 state the hop count alongside the number. A city with no
 *                 road links at all does not appear.
 * @tags           coverage, charging, gap, city
 * @sample         Bundled sample data only: returns 12 rows — Belfort,
 *                 Besancon, Mulhouse, Albertville, Annecy, Annemasse,
 *                 Cambrai, Digne-les-Bains, La Rochelle, Montelimar,
 *                 Saint-Louis, Vesoul.
 */
MATCH (city:Geo)
WHERE NOT EXISTS {
  MATCH (city)-[:ROAD*1..2]-(:ChargingStation)
}
MATCH (city)-[r:ROAD]-()
RETURN city.name   AS stranded_city,
       city.region AS region,
       count(r)    AS road_links
ORDER BY road_links DESC, stranded_city;
```

## Fleet composition and reach

```cypher
/*
 * @name           Fleet composition and reach
 * @description    Shows how much of the fleet is mission-ready without
 *                 charging, by vehicle_class: average battery, state of
 *                 charge and range, and how many vehicles reach the
 *                 required range on their current charge.
 * @params         reserveSoc - The do-not-drop-below floor, as a percentage
 *                     of battery capacity. Start at 10, a common operational
 *                     reserve.
 *                 requiredRangeKm - The distance a vehicle must cover
 *                     without charging to count as mission-ready. Set it to
 *                     the length of the lane or shift being planned.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per vehicle_class: vehicles, avg_battery_kwh,
 *                 avg_soc_percent, avg_range_km and ready_without_charging,
 *                 ordered by vehicles descending.
 * @usage          A vehicle that cannot cover a lane on one charge may
 *                 still serve it with charging planned in — the case for
 *                 the route queries. Efficiency is constant, ignoring
 *                 payload, gradient and temperature; cold-weather
 *                 consumption on a van can run 30% above nominal.
 * @tags           fleet, range, vehicle, readiness
 * @sample         Bundled sample data only: $reserveSoc = 10.0,
 *                 $requiredRangeKm = 400 returns 3 rows — Light Van 12
 *                 vehicles, avg range 151 km, 0 ready; Fleet Car 10, avg
 *                 range 280 km, 1 ready; Rigid Truck 8, avg range 205 km, 0
 *                 ready.
 */
MATCH (c:Car)
WITH c, c.battery_capacity_kwh * (c.current_soc_percent - $reserveSoc)
        / 100.0 / c.efficiency_kwh_per_km AS range_km
RETURN c.vehicle_class                   AS vehicle_class,
       count(*)                          AS vehicles,
       round(avg(c.battery_capacity_kwh)) AS avg_battery_kwh,
       round(avg(c.current_soc_percent))  AS avg_soc_percent,
       round(avg(range_km))               AS avg_range_km,
       count(CASE WHEN range_km >= $requiredRangeKm THEN 1 END) AS ready_without_charging
ORDER BY vehicles DESC;
```

## Inline corridor stations — sites with no bypass

```cypher
/*
 * @name           Inline corridor stations — sites with no bypass
 * @description    Separates mid-corridor stations, where an outage forces a
 *                 full reroute, from urban spurs, where it only costs a
 *                 short detour: lists stations joined to the network by
 *                 exactly two road segments.
 * @params         limit - Maximum number of stations returned. Start at 50
 *                     for a readable list.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per inline station: station, power_kw, region and
 *                 between (the names of its two neighbours), ordered by
 *                 power_kw ascending, then station, at most $limit rows.
 * @usage          The links = 2 test is a literal: one link is a spur, more
 *                 than two a junction, and neither matches. Low-power
 *                 inline stations come first because they are the weakest
 *                 links on a corridor.
 * @tags           station, corridor, resilience
 * @sample         Bundled sample data only: $limit = 50 returns 50 of the
 *                 70 inline stations; the first rows are the 150 kW sites
 *                 CS-A10-02, CS-A26-01, CS-A29-01, CS-A6-01.
 */
MATCH (cs:ChargingStation)-[r:ROAD]-(n:Geo|ChargingStation)
WITH cs, collect(DISTINCT n.name) AS between, count(DISTINCT r) AS links
WHERE links = 2
RETURN cs.name     AS station,
       cs.power_kw AS power_kw,
       cs.region   AS region,
       between
ORDER BY power_kw ASC, station
LIMIT $limit;
```

## Corridor preview — how hard the spatial prune bites, before paying for traversal

```cypher
/*
 * @name           Corridor preview — how hard the spatial prune bites, before paying for traversal
 * @description    The cheapest check on a lane: counts the places and
 *                 charging stations inside the corridor the route queries
 *                 search. The corridor is an ellipse — a node is in it when
 *                 the detour through it stays within $detourRatio of the
 *                 direct distance. Points are built inline from lat/lon.
 * @params         sourceName - Name of the start location (Geo.name or
 *                     ChargingStation.name).
 *                 targetName - Name of the destination location.
 *                 detourRatio - Corridor width as a multiple of the direct
 *                     distance. Start at 1.35, around the upper end of
 *                     typical road circuity, then tighten it while the
 *                     corridor still contains charging stations.
 * @prerequisites  None beyond the imported reference ontology; Neo4j 5.x
 *                 is sufficient.
 * @returns        One row: corridor_nodes, corridor_stations and direct_km
 *                 (great-circle distance between source and target,
 *                 rounded). No row when either name is unknown.
 * @usage          Run before the stateful route queries. An empty or
 *                 charger-free corridor means no route exists. A tighter
 *                 ratio shrinks the search the route queries pay for; if
 *                 the best route survives it, use it.
 * @tags           corridor, spatial, pruning, route-planning
 * @sample         Bundled sample data only: $sourceName = 'Paris',
 *                 $targetName = 'Marseille', $detourRatio = 1.35 returns 1
 *                 row — corridor_nodes 162, corridor_stations 62, direct_km
 *                 661.
 */
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
WITH a, b,
     point({latitude: a.lat, longitude: a.lon}) AS pa,
     point({latitude: b.lat, longitude: b.lon}) AS pb
WITH pa, pb, point.distance(pa, pb) AS direct_m
MATCH (x:Geo|ChargingStation)
WITH pa, pb, direct_m, x, point({latitude: x.lat, longitude: x.lon}) AS px
WHERE point.distance(pa, px) + point.distance(px, pb) < $detourRatio * direct_m
RETURN count(x)                                      AS corridor_nodes,
       count(CASE WHEN x:ChargingStation THEN 1 END) AS corridor_stations,
       round(direct_m / 1000.0)                      AS direct_km;
```

## Lane feasibility across the fleet — which vehicles can serve this lane today

```cypher
/*
 * @name           Lane feasibility across the fleet — which vehicles can serve this lane today
 * @description    How many of the fleet can do this run, not the best route
 *                 for one vehicle. For every Car, checks whether some route
 *                 of ROAD and CHARGE hops inside the corridor reaches the
 *                 target with state of charge within $minSoc..$maxSoc and
 *                 elapsed time within $maxMins at every step.
 * @params         sourceName - Name of the start location.
 *                 targetName - Name of the destination location.
 *                 detourRatio - Corridor width as a multiple of the direct
 *                     distance; use the value Corridor preview confirmed.
 *                 minSoc - Lowest state of charge allowed at any step, in
 *                     percent. Start at 10, a common operational reserve.
 *                 maxSoc - State-of-charge ceiling and post-charge clamp, in
 *                     percent. Start at 100; 80 avoids the charge taper.
 *                 maxMins - Shift length in minutes for the run.
 *                 departureHour - Departure hour, 0–23; hours 7–9 and 16–18
 *                     use peak_speed_kph.
 * @prerequisites  Cypher 25 on Neo4j 2025.08+. Run Corridor preview first
 *                 to confirm a corridor exists.
 * @returns        One row per vehicle_class: vehicles, can_serve_lane and
 *                 blocked, ordered by vehicles descending.
 * @usage          EXISTS stops at the first feasible route, so this is far
 *                 cheaper than enumerating paths per vehicle. The {1,14}
 *                 bound is a literal counting charge stops as hops: a
 *                 blocked vehicle may be hop-bound rather than range-bound,
 *                 so raise the bound before concluding it cannot serve the
 *                 lane.
 * @tags           fleet, feasibility, route-planning, stateful, cypher-25
 * @sample         Bundled sample data only: $sourceName = 'Paris',
 *                 $targetName = 'Marseille', $detourRatio = 1.35, $minSoc =
 *                 10.0, $maxSoc = 100.0, $maxMins = 900.0, $departureHour =
 *                 6 returns 3 rows — Light Van 12 vehicles, 10 can serve, 2
 *                 blocked; Fleet Car 10 of 10; Rigid Truck 8 of 8.
 */
CYPHER 25
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
WITH a, b,
     point({latitude: a.lat, longitude: a.lon}) AS pa,
     point({latitude: b.lat, longitude: b.lon}) AS pb
WITH a, b, pa, pb, point.distance(pa, pb) AS direct_m
MATCH (c:Car)
WITH c, EXISTS {
  MATCH REPEATABLE ELEMENTS (a)
  ((:Geo|ChargingStation) -[rels:ROAD|CHARGE]- (x:Geo|ChargingStation
      WHERE point.distance(pa, point({latitude: x.lat, longitude: x.lon}))
          + point.distance(point({latitude: x.lat, longitude: x.lon}), pb)
          < $detourRatio * direct_m
  )){1,14}
  (b)
  WHERE allReduce(
    state = {soc: c.current_soc_percent, time_in_min: 0.0},
    r IN rels |
      CASE
        WHEN r:ROAD THEN {
          soc: state.soc
               - (r.distance_km * c.efficiency_kwh_per_km * 100.0) / c.battery_capacity_kwh,
          time_in_min: state.time_in_min
               + 60.0 * r.distance_km /
                 CASE
                   WHEN ($departureHour + toInteger(state.time_in_min / 60.0)) % 24
                        IN [7, 8, 9, 16, 17, 18]
                   THEN toFloat(r.peak_speed_kph)
                   ELSE toFloat(r.free_flow_speed_kph)
                 END
        }
        ELSE {
          soc: CASE
                 WHEN state.soc
                      + (CASE WHEN r.power_kw < c.max_charge_power_kw
                              THEN r.power_kw ELSE c.max_charge_power_kw END)
                        * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
                      > $maxSoc
                 THEN $maxSoc
                 ELSE state.soc
                      + (CASE WHEN r.power_kw < c.max_charge_power_kw
                              THEN r.power_kw ELSE c.max_charge_power_kw END)
                        * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
               END,
          time_in_min: state.time_in_min + r.time_in_minutes
        }
      END,
    state.soc >= $minSoc
    AND state.soc <= $maxSoc
    AND state.time_in_min <= $maxMins
  )
} AS can_reach
RETURN c.vehicle_class                           AS vehicle_class,
       count(*)                                  AS vehicles,
       count(CASE WHEN can_reach THEN 1 END)     AS can_serve_lane,
       count(CASE WHEN NOT can_reach THEN 1 END) AS blocked
ORDER BY vehicles DESC;
```

## Location ego network — everything one hop from a city

```cypher
/*
 * @name           Location ego network — everything one hop from a city
 * @description    Visualises a hub and its road neighbourhood, cities and
 *                 charging stations together. This is the query that makes
 *                 the label rule visible: drop the union and every station
 *                 disappears from the picture without any error.
 * @params         cityName - Geo.name of the city. Ask the user, or offer
 *                     one from Available anchors.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Rows of hub (the Geo node), r (a ROAD) and n (the
 *                 neighbouring Geo or ChargingStation), for Browser or Bloom
 *                 to draw as one subgraph.
 * @usage          Visual, not tabular. With (n:Geo) instead of the union the
 *                 same query returns only the city neighbours — a quick
 *                 demonstration of why the union matters.
 * @tags           visualisation, city, neighbourhood, label-rule
 * @sample         Bundled sample data only: $cityName = 'Lyon' draws Lyon
 *                 and 14 neighbours, 7 of them ChargingStation; nearest is
 *                 Villeurbanne at 5.3 km on the N383, farthest CS-A89-01 at
 *                 318.5 km.
 */
MATCH (hub:Geo {name: $cityName})-[r:ROAD]-(n:Geo|ChargingStation)
RETURN hub, r, n;
```

## Fewest-hop route between two locations

```cypher
/*
 * @name           Fewest-hop route between two locations
 * @description    Returns the fewest-hop path across the road network
 *                 between two locations, cities or charging stations.
 * @params         sourceName - Name of the start location (Geo.name or
 *                     ChargingStation.name). Offer values from Available
 *                     anchors.
 *                 targetName - Name of the destination location.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One path p of ROAD hops, or no row when none exists
 *                 within the bound.
 * @usage          The 1..12 bound is a literal. Fewest hops is not least
 *                 distance — long express segments make a few-hop route
 *                 attractive and long — so compare with Least-distance
 *                 routes. When several paths tie on hop count, one is
 *                 returned arbitrarily. Ignores battery and time entirely.
 * @tags           visualisation, route, shortest-path
 * @sample         Bundled sample data only: $sourceName = 'Paris',
 *                 $targetName = 'Nice' returns 1 path — 6 hops, 980.0 km,
 *                 via Paris - CS-A6-01 - Lyon - CS-A7-01 - Marseille -
 *                 CS-A8-01 - Nice.
 */
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
MATCH p = shortestPath((a)-[:ROAD*1..12]-(b))
RETURN p;
```

## Least-distance routes — ranked by driving distance, not hop count

```cypher
/*
 * @name           Least-distance routes — ranked by driving distance, not hop count
 * @description    Shows that fewest hops and least distance give different
 *                 answers: enumerates road paths between two locations and
 *                 ranks them by total distance_km, so both can be drawn.
 * @params         sourceName - Name of the start location.
 *                 targetName - Name of the destination location.
 *                 limit - Number of paths returned, shortest first. Start at
 *                     5 to compare the leading alternatives.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Up to $limit rows of p (the path) and total_km (1 dp),
 *                 ordered by total_km ascending.
 * @usage          The 1..8 bound is a literal; enumeration grows
 *                 exponentially with it, so raise it cautiously. Ignores
 *                 battery and time.
 * @tags           visualisation, route, distance, hops-vs-distance
 * @sample         Bundled sample data only: $sourceName = 'Paris',
 *                 $targetName = 'Nice', $limit = 5 returns 5 paths — best
 *                 899.1 km over 8 hops via Paris - CS-A6-01 - Lyon -
 *                 Grenoble - Gap - Digne-les-Bains - Draguignan - Cannes -
 *                 Nice, then the 6-hop route at 980.0 km.
 */
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
MATCH p = (a)-[:ROAD*1..8]-(b)
WITH p, reduce(d = 0.0, r IN relationships(p) | d + r.distance_km) AS total_km
ORDER BY total_km ASC
LIMIT $limit
RETURN p, round(total_km, 1) AS total_km;
```

## Charging catchment of a city — the paths out to reachable stations

```cypher
/*
 * @name           Charging catchment of a city — the paths out to reachable stations
 * @description    Visualises how a city reaches its charging options,
 *                 including roads shared by several stations — useful for
 *                 spotting a single road that all of a city's charging
 *                 depends on.
 * @params         cityName - Geo.name of the city. Ask the user, or offer
 *                     one from Available anchors.
 *                 limit - Maximum number of paths returned. Start at 50 for
 *                     a readable graph.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Up to $limit paths from the city to charging stations
 *                 within two ROAD hops.
 * @usage          The 1..2 hop bound is a literal. A city listed by
 *                 Charging coverage gaps returns no paths at all, which is
 *                 the result worth showing for it.
 * @tags           visualisation, charging, catchment, city
 * @sample         Bundled sample data only: $cityName = 'Lyon', $limit = 50
 *                 returns 10 paths, one to each of the 10 stations within
 *                 two hops, 7 of them direct.
 */
MATCH (hub:Geo {name: $cityName})
MATCH p = (hub)-[:ROAD*1..2]-(cs:ChargingStation)
RETURN p
LIMIT $limit;
```

## Feasible routes under battery and time constraints

```cypher
/*
 * @name           Feasible routes under battery and time constraints
 * @description    The flagship query. Expands paths of ROAD and CHARGE hops
 *                 inside the corridor carrying {soc, time_in_min} for one
 *                 vehicle, prunes any partial route that breaches the
 *                 state-of-charge window or the shift length, and draws the
 *                 survivors. A ROAD hop spends distance_km ×
 *                 efficiency_kwh_per_km; a CHARGE hop adds the lower of
 *                 power_kw and max_charge_power_kw over time_in_minutes.
 * @params         carId - Car.id of the vehicle. Ask the user, or offer one
 *                     from Available anchors.
 *                 sourceName - Name of the start location.
 *                 targetName - Name of the destination location.
 *                 detourRatio - Corridor width as a multiple of the direct
 *                     distance; use the value Corridor preview confirmed.
 *                 minSoc - Lowest state of charge allowed at any step, in
 *                     percent. Start at 10, a common operational reserve.
 *                 maxSoc - State-of-charge ceiling and post-charge clamp, in
 *                     percent. Start at 100; 80 avoids the charge taper.
 *                 maxMins - Shift length in minutes for the run.
 *                 departureHour - Departure hour, 0–23; hours 7–9 and 16–18
 *                     use peak_speed_kph.
 *                 limit - Maximum number of routes returned. Start at 50
 *                     for a readable graph.
 * @prerequisites  Cypher 25 on Neo4j 2025.08+. Run Corridor preview first
 *                 to confirm a corridor exists.
 * @returns        Up to $limit paths p from source to target, each a
 *                 sequence of ROAD and CHARGE hops; which feasible routes
 *                 are returned is not ordered.
 * @usage          The {1,14} bound is a literal counting charge stops as
 *                 hops — raise it for short-range vehicles. Clamping soc at
 *                 $maxSoc matters: without it a high-power station
 *                 overshoots and allReduce prunes a valid path. Capping
 *                 power at max_charge_power_kw matters too, or routes
 *                 assume charging the fleet cannot do. REPEATABLE ELEMENTS
 *                 lets a route revisit a node or road — out to a spur
 *                 charger and back, or several charges at one site.
 * @tags           visualisation, route-planning, stateful, battery, cypher-25
 * @sample         Bundled sample data only: $carId = 'EV-013', $sourceName =
 *                 'Paris', $targetName = 'Marseille', $detourRatio = 1.35,
 *                 $minSoc = 10.0, $maxSoc = 100.0, $maxMins = 900.0,
 *                 $departureHour = 6, $limit = 50 returns 50 paths — more
 *                 than 50 feasible routes exist, so which ones is not fixed.
 */
CYPHER 25
MATCH (c:Car {id: $carId})
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
WITH c, a, b,
     point({latitude: a.lat, longitude: a.lon}) AS pa,
     point({latitude: b.lat, longitude: b.lon}) AS pb
WITH c, a, b, pa, pb, point.distance(pa, pb) AS direct_m
MATCH REPEATABLE ELEMENTS p = (a)
  ((:Geo|ChargingStation) -[rels:ROAD|CHARGE]- (x:Geo|ChargingStation
      WHERE point.distance(pa, point({latitude: x.lat, longitude: x.lon}))
          + point.distance(point({latitude: x.lat, longitude: x.lon}), pb)
          < $detourRatio * direct_m
  )){1,14}
  (b)
WHERE allReduce(
  state = {soc: c.current_soc_percent, time_in_min: 0.0},
  r IN rels |
    CASE
      WHEN r:ROAD THEN {
        soc: state.soc
             - (r.distance_km * c.efficiency_kwh_per_km * 100.0) / c.battery_capacity_kwh,
        time_in_min: state.time_in_min
             + 60.0 * r.distance_km /
               CASE
                 WHEN ($departureHour + toInteger(state.time_in_min / 60.0)) % 24
                      IN [7, 8, 9, 16, 17, 18]
                 THEN toFloat(r.peak_speed_kph)
                 ELSE toFloat(r.free_flow_speed_kph)
               END
      }
      ELSE {
        soc: CASE
               WHEN state.soc
                    + (CASE WHEN r.power_kw < c.max_charge_power_kw
                            THEN r.power_kw ELSE c.max_charge_power_kw END)
                      * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
                    > $maxSoc
               THEN $maxSoc
               ELSE state.soc
                    + (CASE WHEN r.power_kw < c.max_charge_power_kw
                            THEN r.power_kw ELSE c.max_charge_power_kw END)
                      * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
             END,
        time_in_min: state.time_in_min + r.time_in_minutes
      }
    END,
  state.soc >= $minSoc
  AND state.soc <= $maxSoc
  AND state.time_in_min <= $maxMins
)
RETURN p
LIMIT $limit;
```

## Best route, scored — one recommendation with the numbers behind it

```cypher
/*
 * @name           Best route, scored — one recommendation with the numbers behind it
 * @description    Ranks every feasible route for one vehicle — the same
 *                 corridor-pruned, stateful expansion as Feasible routes
 *                 under battery and time constraints — by arrival time,
 *                 then energy drawn, then hop count, and returns the best
 *                 path with the figures a dispatcher needs. Replays each
 *                 route with the same energy and timing rules, also
 *                 accumulating energy drawn and kilometres driven.
 * @params         carId - Car.id of the vehicle. Ask the user, or offer one
 *                     from Available anchors.
 *                 sourceName - Name of the start location.
 *                 targetName - Name of the destination location.
 *                 detourRatio - Corridor width as a multiple of the direct
 *                     distance; use the value Corridor preview confirmed.
 *                 minSoc - Lowest state of charge allowed at any step, in
 *                     percent. Start at 10, a common operational reserve.
 *                 maxSoc - State-of-charge ceiling and post-charge clamp, in
 *                     percent. Start at 100; 80 avoids the charge taper.
 *                 maxMins - Shift length in minutes for the run.
 *                 departureHour - Departure hour, 0–23; hours 7–9 and 16–18
 *                     use peak_speed_kph.
 * @prerequisites  Cypher 25 on Neo4j 2025.08+. Run Corridor preview first
 *                 to confirm a corridor exists.
 * @returns        One row: p, car_id, model, hops, charge_stops,
 *                 driving_km (1 dp), elapsed_hours (2 dp), energy_drawn_kwh
 *                 (1 dp) and arrival_soc_percent (rounded). No row when no
 *                 route is feasible.
 * @usage          Enumerates every feasible route before ranking, so it
 *                 costs more than the feasible-routes query: keep
 *                 $detourRatio as tight as Corridor preview allows. The
 *                 {1,14} bound is a literal counting charge stops as hops.
 *                 Departure hour changes the answer through peak speeds.
 *                 Swap the first two ORDER BY terms to optimise for energy
 *                 instead of time. A planning input only: no charger
 *                 queueing, live traffic or driver-hours rules.
 * @tags           route-planning, scoring, recommendation, cypher-25
 * @sample         Bundled sample data only: $carId = 'EV-013', $sourceName =
 *                 'Paris', $targetName = 'Marseille', $detourRatio = 1.35,
 *                 $minSoc = 10.0, $maxSoc = 100.0, $maxMins = 900.0,
 *                 $departureHour = 6 returns 1 row — 9 hops, 3 charge stops,
 *                 800.0 km, 7.47 h, 136.0 kWh, arrival 32% SoC, via Paris -
 *                 CS-A6-01 - CS-A6-01 - Lyon - CS-LYON-02 - CS-LYON-02 -
 *                 Lyon - CS-A7-01 - CS-A7-01 - Marseille.
 */
CYPHER 25
MATCH (c:Car {id: $carId})
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
WITH c, a, b,
     point({latitude: a.lat, longitude: a.lon}) AS pa,
     point({latitude: b.lat, longitude: b.lon}) AS pb
WITH c, a, b, pa, pb, point.distance(pa, pb) AS direct_m
MATCH REPEATABLE ELEMENTS p = (a)
  ((:Geo|ChargingStation) -[rels:ROAD|CHARGE]- (x:Geo|ChargingStation
      WHERE point.distance(pa, point({latitude: x.lat, longitude: x.lon}))
          + point.distance(point({latitude: x.lat, longitude: x.lon}), pb)
          < $detourRatio * direct_m
  )){1,14}
  (b)
WHERE allReduce(
  state = {soc: c.current_soc_percent, time_in_min: 0.0},
  r IN rels |
    CASE
      WHEN r:ROAD THEN {
        soc: state.soc
             - (r.distance_km * c.efficiency_kwh_per_km * 100.0) / c.battery_capacity_kwh,
        time_in_min: state.time_in_min
             + 60.0 * r.distance_km /
               CASE
                 WHEN ($departureHour + toInteger(state.time_in_min / 60.0)) % 24
                      IN [7, 8, 9, 16, 17, 18]
                 THEN toFloat(r.peak_speed_kph)
                 ELSE toFloat(r.free_flow_speed_kph)
               END
      }
      ELSE {
        soc: CASE
               WHEN state.soc
                    + (CASE WHEN r.power_kw < c.max_charge_power_kw
                            THEN r.power_kw ELSE c.max_charge_power_kw END)
                      * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
                    > $maxSoc
               THEN $maxSoc
               ELSE state.soc
                    + (CASE WHEN r.power_kw < c.max_charge_power_kw
                            THEN r.power_kw ELSE c.max_charge_power_kw END)
                      * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
             END,
        time_in_min: state.time_in_min + r.time_in_minutes
      }
    END,
  state.soc >= $minSoc
  AND state.soc <= $maxSoc
  AND state.time_in_min <= $maxMins
)
WITH c, p,
     reduce(state = {soc: c.current_soc_percent, time_in_min: 0.0, energy_kwh: 0.0, km: 0.0},
       r IN relationships(p) |
         CASE
           WHEN r:ROAD THEN {
             soc: state.soc
                  - (r.distance_km * c.efficiency_kwh_per_km * 100.0) / c.battery_capacity_kwh,
             time_in_min: state.time_in_min
                  + 60.0 * r.distance_km /
                    CASE
                      WHEN ($departureHour + toInteger(state.time_in_min / 60.0)) % 24
                           IN [7, 8, 9, 16, 17, 18]
                      THEN toFloat(r.peak_speed_kph)
                      ELSE toFloat(r.free_flow_speed_kph)
                    END,
             energy_kwh: state.energy_kwh + r.distance_km * c.efficiency_kwh_per_km,
             km: state.km + r.distance_km
           }
           ELSE {
             soc: CASE
                    WHEN state.soc
                         + (CASE WHEN r.power_kw < c.max_charge_power_kw
                                 THEN r.power_kw ELSE c.max_charge_power_kw END)
                           * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
                         > $maxSoc
                    THEN $maxSoc
                    ELSE state.soc
                         + (CASE WHEN r.power_kw < c.max_charge_power_kw
                                 THEN r.power_kw ELSE c.max_charge_power_kw END)
                           * (r.time_in_minutes / 60.0) * 100.0 / c.battery_capacity_kwh
                  END,
             time_in_min: state.time_in_min + r.time_in_minutes,
             energy_kwh: state.energy_kwh,
             km: state.km
           }
         END) AS final
ORDER BY final.time_in_min ASC,
         final.energy_kwh  ASC,
         length(p)         ASC
LIMIT 1
RETURN p,
       c.id                                        AS car_id,
       c.model                                     AS model,
       length(p)                                   AS hops,
       size([r IN relationships(p) WHERE r:CHARGE]) AS charge_stops,
       round(final.km, 1)                          AS driving_km,
       round(final.time_in_min / 60.0, 2)          AS elapsed_hours,
       round(final.energy_kwh, 1)                  AS energy_drawn_kwh,
       round(final.soc)                            AS arrival_soc_percent;
```

## Node-key constraints

Import creates these node-key constraints from the key definitions in `ONTOLOGY.json`. They are listed as a reference for checking the live database (`SHOW CONSTRAINTS`), not as statements to run: recreating them, or adding `UNIQUE` variants, conflicts with the existing `KEY` constraints.

```cypher
CREATE CONSTRAINT name_Geo_key IF NOT EXISTS
  FOR (g:Geo) REQUIRE g.name IS NODE KEY;
CREATE CONSTRAINT name_ChargingStation_key IF NOT EXISTS
  FOR (cs:ChargingStation) REQUIRE cs.name IS NODE KEY;
CREATE CONSTRAINT id_Car_key IF NOT EXISTS
  FOR (c:Car) REQUIRE c.id IS NODE KEY;
```
