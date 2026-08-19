# EV Route Planning — Query Guidance

Cypher for the `ev-route-planning` use case. Every query references only labels, relationship types, and properties defined in `GRAPH_MODEL.json`. The `//` comments before each query state its purpose, inputs, prerequisites, and the expected result against the bundled `sample-data/` so they act as a lightweight test oracle.

Prerequisites in one place:

- Sections A0–A11 and B G1–G4 need Neo4j 5.x, Cypher 5. No APOC or GDS required.
- Sections A12–A13 and G5–G6 need Cypher 25 on Neo4j 2025.08+ for `allReduce` and `REPEATABLE ELEMENTS` quantified path patterns. Confirm the version before offering them.
- The graph is loaded via the bundled sample-data Import (`GRAPH_MODEL.json`). No post-import Cypher is required — the queries use only the three labels the import creates. See the appendix at the end of this file before adding any label yourself.
- KEY constraints from `GRAPH_MODEL.json` make `Geo.name`, `ChargingStation.name` and `Car.id` unique, so every anchored lookup below is an index seek rather than a label scan.

Sample-data profile: a synthetic French network — 150 `Geo` (cities), 100 `ChargingStation`, 30 `Car`, 440 `ROAD` segments, 200 `CHARGE` self-loops. Aggregate results below are for this data; per-entity results for the documented anchors are stable.

**Label rule — the single most important thing in this file.** `Geo` (cities) and `ChargingStation` share NO label. Graph spec 4.0.0 declares one primary label per node, so there is no supertype to traverse on. Any traversal meaning "any location on the network" MUST use the union `(:Geo|ChargingStation)`. A bare `(x:Geo)` is valid Cypher that returns rows while silently excluding all 100 charging stations. On this data the fleet-feasibility query A13 answers 26 of 30 vehicles with the union and 0 of 30 without it, and neither version errors.

`ROAD` is stored once per segment and traversed undirected — always `-[:ROAD]-`, never `-[:ROAD]->`. `CHARGE` is a self-loop on `ChargingStation`; a station name repeated on consecutive hops of a route is a charge stop, not a bug.

Anchors are **parameters**, never hardcoded IDs. Before running an anchored query, either ask the user which entity they want or offer them a real anchor from query 0 (Available anchors). Do not invent IDs. To test in Neo4j Browser or cypher-shell, set the sample parameters first — these are real values verified against the bundled CSVs:

```text
:param carId           => 'EV-013'     // Aurex Estate 77, Fleet Car, 95% SoC
:param stationName     => 'CS-A7-01'   // 300 kW ElectraRoute site, mid-corridor on the A7
:param cityName        => 'Lyon'       // 14 road links, 7 of them to charging stations
:param sourceName      => 'Paris'      // lane source for the route-planning queries
:param targetName      => 'Marseille'  // lane target, 660 km direct
:param detourRatio     => 1.35         // ellipse width for spatial pruning
:param minSoc          => 10.0         // operational reserve, percent
:param maxSoc          => 100.0        // also the clamp ceiling inside the accumulator
:param maxMins         => 900.0        // shift length in minutes
:param departureHour   => 6            // integer 0-23, drives the peak-speed CASE
:param reserveSoc      => 10.0         // reserve used by the plain range arithmetic
:param requiredRangeKm => 400          // "mission-ready" threshold for the fleet rollup
:param limit           => 50           // cap for graph/visualisation results
```

Quantifier bounds like `{1,14}` are **literals**. Cypher rejects a parameter inside `{1,n}`. Raise the bound for short-range vehicles: EV-013 needs 14, the low-SoC van EV-005 needs 24.

Sections: A — point and tabular queries (0–13); B — graph/visualisation queries (G1–G6), which return nodes, relationships and paths to render; Appendix — optional shared-label workaround (read before running).

## A. Point & tabular queries

### 0. Available anchors

```cypher
// Purpose: enumerate valid anchor values so the agent never has to guess or hardcode one.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 280 rows — 150 cities, 100 charging stations, 30 vehicles.
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

### 1. Model sanity check — node and relationship counts

```cypher
// Purpose: confirm the import completed and every ROAD table loaded.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: cities 150, charging_stations 100, cars 30,
//   road_segments 440, charge_options 200.
//   If road_segments comes back at 270, only roads-city-city.csv loaded — the 170 station
//   roads are missing and every route will look like it never charges.
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

### 2. Road network by class — the four-tier hierarchy

```cypher
// Purpose: show how distance and speed are distributed across the road hierarchy.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 4 rows — Motorway 162 (avg 67.9 km), Trunk 162 (avg 71.4),
//   Local 63 (avg 43.4), Express 53 (avg 158.5). Express is the long hub-to-hub tier:
//   fewest segments, highest average distance, and the only class at 130 kph free-flow.
//   Express is a modelling device — one hop standing in for a long motorway run whose
//   intermediate junctions are not decision points — not a real road category.
MATCH ()-[r:ROAD]->()
RETURN r.road_class                 AS road_class,
       count(*)                     AS segments,
       round(avg(r.distance_km), 1) AS avg_km,
       round(sum(r.distance_km))    AS total_km,
       max(r.free_flow_speed_kph)   AS top_free_flow_kph
ORDER BY segments DESC;
```

### 3. Vehicle range — one vehicle's usable range from telemetry

```cypher
// Purpose: turn state of charge into a distance the vehicle can actually cover.
// Inputs: $carId — ask the user, or offer a vehicle from query 0 (sample: EV-013).
//         $reserveSoc — the do-not-drop-below floor, percent.
// Prerequisites: graph loaded; $carId and $reserveSoc set.
// Expected against sample data ($carId = 'EV-013'): 1 row — Aurex Estate 77, Fleet Car,
//   77.0 kWh, 95% SoC, max charge 150 kW, usable 65.5 kWh, range_km 385.
//   Negative case: $carId = 'EV-005' (Meridian LV-85, Light Van, 26% SoC) gives range_km 52,
//   not enough to leave the Paris conurbation.
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

### 4. Charging station detail — one station, its charge tiers and the roads that reach it

```cypher
// Purpose: inspect a single site before routing through it.
// Inputs: $stationName — ask the user, or offer a station from query 0 (sample: CS-A7-01).
// Prerequisites: graph loaded; $stationName set.
// Expected against sample data ($stationName = 'CS-A7-01'): 1 row — 300 kW, ElectraRoute,
//   Auvergne-Rhone-Alpes, tiers ['full (40 min)','top-up (15 min)'], roads to Lyon via A7
//   (159.8 km) and Marseille via A7 (155.2 km). A mid-corridor site with exactly two roads.
//   Contrast 'CS-LYON-02': an urban spur, 50 kW, one 10.0 km Local road to Lyon.
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

### 5. Charging options near a city — stations within two road hops, by depth

```cypher
// Purpose: find where a vehicle leaving this city can actually charge.
// Inputs: $cityName — ask the user, or offer a city from query 0 (sample: Lyon).
//         The 1..2 hop bound is a literal.
// Prerequisites: graph loaded; $cityName set.
// Expected against sample data ($cityName = 'Lyon'): 10 rows. Seven stations are 1 hop —
//   CS-LYON-02 (50 kW), CS-A6-01 (150), CS-A7-01 (300), CS-A31-02, CS-A36-01, CS-A89-01,
//   CS-A89-02 — and three more at 2 hops. Tightening the bound to 1 returns exactly 7.
MATCH (hub:Geo {name: $cityName})
MATCH p = (hub)-[:ROAD*1..2]-(cs:ChargingStation)
WITH cs, min(length(p)) AS hops
RETURN cs.name     AS station,
       hops,
       cs.power_kw AS power_kw,
       cs.operator AS operator
ORDER BY hops, power_kw DESC;
```

### 6. Charging capacity by region

```cypher
// Purpose: compare installed capacity across regions to spot thin coverage.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 12 rows, every region represented. Nouvelle-Aquitaine leads
//   with 16 sites / 4050 kW. Ile-de-France is last with 4 sites / 725 kW — notable because
//   Paris is the highest-degree node in the network (28 road links), so capacity does not
//   track connectivity.
MATCH (cs:ChargingStation)
RETURN cs.region                   AS region,
       count(*)                    AS sites,
       round(sum(cs.power_kw))     AS total_kw,
       round(avg(cs.power_kw), 1)  AS avg_kw,
       max(cs.power_kw)            AS best_kw
ORDER BY total_kw DESC;
```

### 7. Operator footprint

```cypher
// Purpose: show how each charging operator is spread across the network.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 5 rows — ElectraRoute, NordVolt, AmperGrid, ChargeLine,
//   VoltWay. Each covers at least 9 of the 12 regions, so no single operator can be dropped
//   without losing national coverage. Operator names are synthetic, not real companies.
MATCH (cs:ChargingStation)
RETURN cs.operator                AS operator,
       count(*)                   AS sites,
       round(sum(cs.power_kw))    AS total_kw,
       count(DISTINCT cs.region)  AS regions_covered,
       count(CASE WHEN cs.power_kw >= 300 THEN 1 END) AS high_power_sites
ORDER BY sites DESC, total_kw DESC;
```

### 8. Charge tiers — what each dwell time delivers

```cypher
// Purpose: quantify the core routing trade-off, dwell time against energy.
// Inputs: none.
// Prerequisites: graph loaded.
// Expected against sample data: 2 rows — 'top-up' 100 options, 15 min, avg 57.9 kWh
//   delivered, best 87.5; 'full' 100 options, 40 min, avg 154.5, best 233.3. 2.7x the dwell
//   buys 2.7x the energy, so the choice is whether 25 extra minutes beats an extra stop.
//   Delivered energy is capped in practice by Car.max_charge_power_kw. Charging is modelled
//   as linear; real charge curves taper sharply above roughly 80% SoC, so a long dwell here
//   delivers more than it would in reality.
MATCH (cs:ChargingStation)-[ch:CHARGE]->(cs)
RETURN ch.tier            AS tier,
       count(*)           AS options,
       ch.time_in_minutes AS dwell_minutes,
       round(avg(ch.power_kw * ch.time_in_minutes / 60.0), 1) AS avg_kwh_delivered,
       round(max(ch.power_kw * ch.time_in_minutes / 60.0), 1) AS best_kwh_delivered
ORDER BY dwell_minutes;
```

### 9. Charging coverage gaps — cities with no station within two road hops

```cypher
// Purpose: find the planning blind spots in the network.
// Inputs: none. The 1..2 hop bound is a literal inside the EXISTS subquery.
// Prerequisites: graph loaded. Requires Neo4j 5.x EXISTS subquery syntax.
// Expected against sample data: 12 rows — Albertville, Annecy, Annemasse, Belfort, Besancon,
//   Cambrai, Digne-les-Bains, La Rochelle, Montelimar, Mulhouse, Saint-Louis, Vesoul.
//   They cluster in the Alps and the Franche-Comte / Alsace corridor.
//   Raising the bound to 3 returns 0 rows: the network is fully covered within 3 hops, so
//   this is a depth-sensitive result, not a hole in the data. Always state the hop count
//   alongside the number.
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

### 10. Fleet composition and reach

```cypher
// Purpose: show how little of the fleet is mission-ready without charging — the case for
//   the route-planning queries.
// Inputs: $reserveSoc and $requiredRangeKm define "mission-ready".
// Prerequisites: graph loaded; both parameters set.
// Expected against sample data ($reserveSoc = 10.0, $requiredRangeKm = 400): 3 rows —
//   Light Van 12 vehicles, avg 74 kWh, avg 58% SoC, avg range 151 km, 0 ready.
//   Fleet Car 10, avg 89 kWh, avg 61% SoC, avg range 280 km, 1 ready.
//   Rigid Truck 8, avg 260 kWh, avg 66% SoC, avg range 205 km, 0 ready.
//   Exactly 1 of 30 vehicles can cover 400 km on its current charge.
//   Efficiency is constant here — it ignores payload, gradient and temperature. Cold-weather
//   consumption on a van can run 30% above nominal, which turns a feasible route infeasible.
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

### 11. Inline corridor stations — sites with no bypass

```cypher
// Purpose: separate mid-corridor stations, where an outage forces a full reroute, from urban
//   spurs, where it only costs a short detour.
// Inputs: $limit caps the output for readability.
// Prerequisites: graph loaded; $limit set.
// Expected against sample data: 70 stations match; $limit rows shown. The other 30 are urban
//   spurs with a single road link and do not match. Ordered by power ascending the first rows
//   are 150 kW sites — CS-A10-02, CS-A26-01, CS-A29-01, CS-A6-01. A worked example is
//   CS-A10-01: 250 kW, inline between Bordeaux and Paris on the A10, the longest single
//   Express leg in the data at 336.5 km from Bordeaux.
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

### 12. Corridor preview — how hard the spatial prune bites, before paying for traversal

```cypher
// Purpose: the cheapest possible check on a lane. Always run this before A13 or G5. An empty
//   or charger-free corridor means no route exists and there is no point expanding paths.
// Inputs: $sourceName, $targetName, $detourRatio.
// Prerequisites: graph loaded; parameters set. Neo4j 5.x is sufficient.
// Expected against sample data (Paris -> Marseille, $detourRatio = 1.35): 1 row —
//   corridor_nodes 162, corridor_stations 62, direct_km 660.
//   At 1.10 that drops to 82 nodes / 33 stations; at 1.02 to 36 / 14. The best route survives
//   even at 1.02, so the tight corridor is the one worth running — the wide one costs 4.5x
//   the search space for the same answer.
//
// The prune is an ellipse: a node is in the corridor when the detour through it stays within
// $detourRatio of the direct source-target line. That is much tighter than testing each
// endpoint radius separately. Points are built inline from lat/lon; there is no geo property.
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

### 13. Lane feasibility across the fleet — which vehicles can serve this lane today

```cypher
// Purpose: the question that usually matters operationally. Not "what is the best route for
//   one vehicle" but "how many of the fleet can do this run, and is that enough".
// Inputs: $sourceName, $targetName, $detourRatio, $minSoc, $maxSoc, $maxMins, $departureHour.
//   Does not use $carId. The {1,14} bound is a literal.
// Prerequisites: CYPHER 25 on Neo4j 2025.08+. Run query 12 first to confirm a corridor exists.
//   EXISTS short-circuits on the first feasible route, so this is far cheaper than
//   enumerating every path per vehicle.
// Expected against sample data (Paris -> Marseille, ratio 1.35, bound 14): 3 rows —
//   Fleet Car 10 of 10 feasible, Rigid Truck 8 of 8, Light Van 8 of 12; 26 of 30 overall.
//   The 4 that fail are hop-bound, not range-bound: raise the quantifier to {1,24} and all 30
//   return a route. That distinction is the point of the query — the answer depends on how far
//   you let it look. When a lane returns nothing, suspect the hop bound before the battery.
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

## B. Graph / visualisation queries

These return nodes, relationships and paths so Neo4j Browser or Bloom draws a graph rather than a table. Keep viz result sets bounded with `$limit`.

### G1. Location ego network — everything one hop from a city

```cypher
// Purpose: visualise a hub and its road neighbourhood, cities and charging stations together.
//   This is the query that makes the label rule visible: drop the union and half the
//   neighbourhood disappears without any error.
// Inputs: $cityName — ask the user, or offer a city from query 0 (sample: Lyon).
// Prerequisites: graph loaded; $cityName set.
// Expected against sample data ($cityName = 'Lyon'): a subgraph of Lyon plus 14 neighbours,
//   7 of them ChargingStation. Nearest is Villeurbanne at 5.3 km on the N383; the urban
//   station CS-LYON-02 is 10.0 km on a Local road; the farthest are Express corridor stations
//   CS-A7-01 (159.8 km), CS-A6-01 (258.5), CS-A36-01 (268.8), CS-A89-01 (318.5).
//   With (n:Geo) instead of the union this returns 7 neighbours and 0 stations.
MATCH (hub:Geo {name: $cityName})-[r:ROAD]-(n:Geo|ChargingStation)
RETURN hub, r, n;
```

### G2. Fewest-hop route between two locations

```cypher
// Purpose: return a path object across the network, the fewest-hop answer.
// Inputs: $sourceName, $targetName — offer values from query 0. The 1..12 bound is a literal.
// Prerequisites: graph loaded; parameters set.
// Expected against sample data (Paris -> Nice): 1 path — 6 hops, 980.0 km, roads
//   [A6,A6,A7,A7,A8,A8] via Paris - CS-A6-01 - Lyon - CS-A7-01 - Marseille - CS-A8-01 - Nice.
//   Every intermediate node is a ChargingStation, because the Express tier routes through
//   mid-corridor service sites. This is NOT the shortest drive — see G3, which is 81 km less.
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
MATCH p = shortestPath((a)-[:ROAD*1..12]-(b))
RETURN p;
```

### G3. Least-distance routes — ranked by driving distance, not hop count

```cypher
// Purpose: show that fewest hops and least distance give different answers, and let the user
//   see both drawn.
// Inputs: $sourceName, $targetName, $limit. The 1..8 bound is a literal — do not raise it far
//   above 8 on this data; path enumeration grows quickly at average degree 3.5.
// Prerequisites: graph loaded; parameters set.
// Expected against sample data (Paris -> Nice, $limit = 5): 5 paths. Best is 899.1 km over
//   8 hops via Paris - CS-A6-01 - Lyon - Grenoble - Gap - Digne-les-Bains - Draguignan -
//   Cannes - Nice, the Route Napoleon. Second is the 6-hop Express route at 980.0 km from G2.
//   Two more hops, 81 km less driving — the classic hops-versus-distance trade-off.
MATCH (a:Geo|ChargingStation {name: $sourceName}),
      (b:Geo|ChargingStation {name: $targetName})
MATCH p = (a)-[:ROAD*1..8]-(b)
WITH p, reduce(d = 0.0, r IN relationships(p) | d + r.distance_km) AS total_km
ORDER BY total_km ASC
LIMIT $limit
RETURN p, round(total_km, 1) AS total_km;
```

### G4. Charging catchment of a city — the paths out to reachable stations

```cypher
// Purpose: visualise how a city reaches its charging options, including which roads are shared
//   by several stations. Useful for spotting a single road that all charging depends on.
// Inputs: $cityName, $limit. The 1..2 hop bound is a literal.
// Prerequisites: graph loaded; parameters set.
// Expected against sample data ($cityName = 'Lyon'): paths from Lyon out to the 10 stations
//   within 2 hops, capped at $limit. Seven are direct. For a city with no catchment try one
//   of the 12 from query 9, such as 'Annecy' or 'Mulhouse' — those return no paths at all,
//   which is the result worth showing.
MATCH (hub:Geo {name: $cityName})
MATCH p = (hub)-[:ROAD*1..2]-(cs:ChargingStation)
RETURN p
LIMIT $limit;
```

### G5. Feasible routes under battery and time constraints

```cypher
// Purpose: the flagship query. Expand paths while carrying {soc, time_in_min} and prune any
//   partial route that breaches the reserve or the shift length, then draw the survivors.
// Inputs: $carId, $sourceName, $targetName, $detourRatio, $minSoc, $maxSoc, $maxMins,
//   $departureHour, $limit. The {1,14} bound is a literal — raise it to 24 for EV-005.
// Prerequisites: CYPHER 25 on Neo4j 2025.08+. Run query 12 first to confirm a corridor exists.
// Expected against sample data ($carId = 'EV-013', Paris -> Marseille, bound 14): several
//   feasible paths, capped at $limit. G6 scores them and picks one.
//   Negative case: set $minSoc to 35.0 with $carId 'EV-005' and this returns no paths.
//
// Clamping soc at $maxSoc inside the accumulator matters. Without it a high-power station
// overshoots and allReduce prunes an otherwise valid path. Capping delivered power at the
// vehicle's max_charge_power_kw matters too: a 90 kW van at a 350 kW site still draws 90 kW,
// and ignoring that produces routes the fleet cannot drive.
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

### G6. Best route, scored — one recommendation with the numbers behind it

Chain this onto G5 with `NEXT` — it consumes `c` and `p` from that query.

```cypher
// Purpose: rank the survivors of G5 by arrival time, then energy drawn, then hop count, and
//   return a single path plus the figures a dispatcher needs.
// Inputs: same as G5.
// Prerequisites: CYPHER 25 on Neo4j 2025.08+.
// Expected against sample data ($carId = 'EV-013', Paris -> Marseille, bound 14): 1 path —
//   9 hops, 3 charge stops, 800 km, 7.47 h elapsed, 136 kWh drawn, arrives at 32% SoC, via
//   Paris - CS-A6-01 - CS-A6-01 - Lyon - CS-LYON-02 - CS-LYON-02 - Lyon - CS-A7-01 -
//   CS-A7-01 - Marseille. Repeated station names are CHARGE self-loops: the vehicle stays put
//   and takes both tiers.
//   Departure hour changes the answer. On Paris -> Lyon the same vehicle takes 3.83 h leaving
//   at 04:00 and 4.68 h leaving at 07:00, purely from peak-speed penalties.
//   Ordering time before energy is a choice — swap the first two ORDER BY terms to optimise
//   for consumption instead, which usually trades about an hour for a few kWh on long lanes.
//   Treat the result as a planning input. The model has no charger availability or queueing,
//   no live traffic and no driver-hours rules, any of which can invalidate it.
NEXT
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

## Appendix — optional shared-label workaround. NOT REQUIRED. Read before running.

Everything above works off a bare sample-data import. This appendix exists for one narrow case: you want to reuse query text from the published Neo4j demo page, which traverses a plain `(x:Geo)` rather than the `(:Geo|ChargingStation)` union used here.

Graph spec 4.0.0 declares one primary label per node, so a label shared by cities and stations cannot be imported. These statements add it afterwards. **They WRITE to the database** — offer them only after explicit confirmation that writes are wanted.

The statement everyone reaches for is step 2 alone — and alone it breaks things. Before it runs, `:Geo` means "city". After it runs, `:Geo` means "any location" and nothing is left meaning "city". Queries 1 and 9 above depend on that distinction: the census would report 250 cities instead of 150, and the coverage-gap query would flag 150 instead of 12. Run both statements. The WHERE guard makes the order safe either way; without it, running step 2 first labels all 250 nodes `:City`, stations included, and nothing complains.

```cypher
// 1. give cities their own label, while :Geo still means "city"
MATCH (n:Geo) WHERE NOT n:ChargingStation SET n:City;

// 2. stations join the shared traversal label
MATCH (s:ChargingStation) SET s:Geo;

// 3. verify — expect geo_total 250, cities 150, stations 100, missing_geo 0
MATCH (n:Geo) WITH count(n) AS geo_total
MATCH (c:City) WITH geo_total, count(c) AS cities
MATCH (s:ChargingStation) WITH geo_total, cities, count(s) AS stations
MATCH (s2:ChargingStation) WHERE NOT s2:Geo
RETURN geo_total, cities, stations, count(s2) AS missing_geo;
```

Afterwards every query in this file needs revisiting: 18 union traversals can collapse to `(:Geo)`, and queries 1 and 9 must switch from `(c:Geo)` to `(c:City)` or they silently break.

To undo:

```cypher
MATCH (s:ChargingStation) REMOVE s:Geo;
MATCH (c:City) REMOVE c:City;
```

Unrelated and also optional: materialise a point property and index it if spatial distance shows up in profiling, then swap `point({latitude: x.lat, longitude: x.lon})` for `x.geo` above.

```cypher
MATCH (n:Geo|ChargingStation) SET n.geo = point({longitude: n.lon, latitude: n.lat});
CREATE POINT INDEX point_index_geo IF NOT EXISTS FOR (n:Geo) ON (n.geo);
```

## Constraints

The node-key constraints below are created automatically when the sample data is loaded via the Import app from `GRAPH_MODEL.json`. If you seed the graph another way, create them first:

```cypher
// Node-key constraints matching GRAPH_MODEL.json.
CREATE CONSTRAINT name_Geo_key IF NOT EXISTS
  FOR (g:Geo) REQUIRE g.name IS NODE KEY;
CREATE CONSTRAINT name_ChargingStation_key IF NOT EXISTS
  FOR (cs:ChargingStation) REQUIRE cs.name IS NODE KEY;
CREATE CONSTRAINT id_Car_key IF NOT EXISTS
  FOR (c:Car) REQUIRE c.id IS NODE KEY;
```
