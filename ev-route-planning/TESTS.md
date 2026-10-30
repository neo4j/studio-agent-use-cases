# EV Route Planning — Tests

What each query in `QUERIES.cypher` should return on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it. Everything below was derived from the CSVs in `sample-data/`, not from a database run.

## How to run

1. Use a disposable Neo4j database — 2025.08 or later, so the three Cypher 25 queries (**Lane feasibility across the fleet**, **Feasible routes under battery and time constraints**, **Best route, scored**) can run alongside the Cypher 5 ones.
2. Import the CSVs in `sample-data/` through the Import flow, using `ONTOLOGY.json` as the import definition. This also creates the node-key constraints.
3. No `SETUP.md` statements are needed.
4. Run **Reference ontology sanity check — node and relationship counts** first. `charge_options` must be 200: the `CHARGE` mapping identifies each relationship by `tier`, so the two options at a station stay separate. A count of 100 means the tiers merged on import, and the route queries will then see only one tier per station.
5. Run each query in `QUERIES.cypher` with the parameters given in its section below, and compare the result with the Invariant first and the Expected values second. The parameter values are the ones the legacy `:param` block used, and the ones each query's `@sample` gives.

## Sample-data profile

A synthetic French logistics network. City names and coordinates are real French communes; every road, charging station, operator and vehicle model is generated and represents nothing real. No geographic point property is stored — the queries build points from `lat`/`lon`.

**Nodes**

| Label | Count | Notes |
| ----- | ----- | ----- |
| `Geo` | 150 | Cities in all 12 regions (Nouvelle-Aquitaine 20, Auvergne-Rhone-Alpes 18, Occitanie 18, Grand Est 16, Hauts-de-France 15, Provence-Alpes-Cote d'Azur 14, Bourgogne-Franche-Comte 11, Centre-Val de Loire 8, Ile-de-France 8, Normandie 8, Pays de la Loire 8, Bretagne 6). Every city has at least 3 road links; Paris has 28, then Lyon 14, Bordeaux 13 |
| `ChargingStation` | 100 | 70 inline corridor sites named after their road (`CS-A7-01`, `CS-N79-01`), each with exactly two roads; 30 urban spurs named after their city (`CS-LYON-02`, `CS-PARIS-01`), each with one Local road. Power 50–350 kW: 350 kW ×22, 300 ×10, 250 ×16, 200 ×15, 175 ×17, 150 ×13, 100 ×3, 75 ×2, 50 ×2. Five synthetic operators, each in 10 or 11 regions |
| `Car` | 30 | Light Van 12, Fleet Car 10, Rigid Truck 8; 15 distinct models. Battery 60–320 kWh, max charge 90–350 kW, current SoC 26–95% |

**Relationships**

| Type | Count | Notes |
| ---- | ----- | ----- |
| `ROAD` (`Geo`→`Geo`) | 270 | Trunk 118, Motorway 116, Local 33, Express 3 |
| `ROAD` (`Geo`→`ChargingStation`) | 100 | One per station: Local 30 (the spurs), Express 25, Motorway 23, Trunk 22 |
| `ROAD` (`ChargingStation`→`Geo`) | 70 | One per inline station: Express 25, Motorway 23, Trunk 22 |
| `CHARGE` | 200 | Two per station: `top-up` (15 min) and `full` (40 min), both at the station's `power_kw` |

Every unordered pair of locations has at most one road; no reverse segments exist. Road speeds by class (free-flow / peak kph): Motorway 130/95, Express 130/105, Trunk 110/80, Local 80/60. Distances run 2.4–336.5 km; the longest segment is the Express leg Bordeaux–`CS-A10-01`. Average degree across all locations is 3.5.

**Seeded signals.**

- *Label rule.* Cities and stations share no label, so a traversal on `(x:Geo)` alone never reaches a charger. On the Paris → Marseille lane, **Lane feasibility across the fleet** finds 28 of 30 vehicles able to serve it with the `(:Geo|ChargingStation)` union and 0 of 30 with `(:Geo)` alone (the shortest city-only road route is 888.3 km, beyond every vehicle's range).
- *Fleet reach.* Only EV-016 (Selene GT 110, 88% SoC, 477 km) covers 400 km on its current charge with a 10% reserve; EV-013 (Aurex Estate 77, 95% SoC) reaches 385 km. Low-SoC vans: EV-005 (26%, 52 km), EV-010 (31%), EV-001 (38%).
- *Coverage gaps.* 12 cities have no station within two road hops, clustered in the Alps and the Franche-Comté / Alsace corridor; within three hops every city is covered.
- *Hops versus distance.* Paris → Nice: the fewest-hop route (6 hops, 980.0 km, all on the Express corridor through stations) is not the shortest drive (8 hops, 899.1 km, the Route Napoléon through Grenoble, Gap and Digne-les-Bains).
- *Stateful routing.* Paris → Marseille for EV-013 needs charging: its best route takes three 15-minute top-ups, one of them a detour into the Lyon urban spur `CS-LYON-02`.
- *Capacity versus connectivity.* Ile-de-France has the least installed power (4 sites, 725 kW) although Paris is the best-connected city (28 road links).

**Background noise.** Most of the network is ordinary: 66 of the 150 cities have a station one road away and all but 12 have one within two; operators overlap so that any one of them can be dropped without losing a region; and station power is spread across nine levels. No single query is a clean detector of anything on its own.

**Reference anchors.** Used throughout:

- Vehicle `EV-013` — Aurex Estate 77, Fleet Car, 77.0 kWh, 0.17 kWh/km, 150 kW max charge, 95% SoC.
- Station `CS-A7-01` — 300 kW ElectraRoute, inline on the A7 between Lyon (159.8 km) and Marseille (155.2 km). Contrast `CS-LYON-02`: a 50 kW VoltWay urban spur, 10.0 km from Lyon on the D701.
- `Lyon` (a `Geo` node) — 14 road links, 7 of them to charging stations.
- Lanes: Paris → Marseille (route planning; great-circle distance 661 km) and Paris → Nice (hops versus distance).

**Minimum route length per vehicle.** The fewest hops (roads plus charge stops) any feasible Paris → Marseille route needs at `$detourRatio = 1.35`, `$minSoc = 10.0`: EV-001 and EV-007 18; EV-025, EV-027, EV-029 13; EV-003, EV-005, EV-006, EV-010, EV-012 12; EV-023, EV-024, EV-026, EV-030 10; EV-002, EV-004, EV-008, EV-009, EV-011, EV-015, EV-022, EV-028 9; EV-013, EV-018, EV-019 8; EV-014, EV-016, EV-017, EV-020, EV-021 6. These assume `REPEATABLE ELEMENTS` semantics: a route may drive out to a spur charger and back on the same road, and may take the same charge option twice.

**Editing notes.**

- The legacy `// Expected against sample data` comments and the `:param` block moved here and into each query's `@sample`. Every value was recomputed from the CSVs. Most agreed; these did not:
  - **Lane feasibility across the fleet** — the legacy comment gave 26 of 30 (Light Van 8 of 12) at bound 14, said the four blocked vans need `{1,24}`, and the preamble said EV-005 needs 24. Under `REPEATABLE ELEMENTS` the answer is 28 of 30: only EV-001 and EV-007 are blocked, and each needs 18 hops; EV-005 needs 12. The legacy figure reproduces only if no road may be traversed twice — under that rule EV-001, EV-005, EV-007 and EV-010 are blocked at 14 — which is not what `REPEATABLE ELEMENTS` means.
  - The legacy preamble said EV-013 needs bound 14. It needs 8 to find any route, and its best route uses 9.
  - **Corridor preview** — legacy `direct_km` 660; Neo4j's haversine uses an Earth radius of 6,378,140 m, which gives 661.2 km, so 661. The corridor counts are ratios and do not depend on the radius.
  - **Operator footprint** — the legacy comment said no single operator can be dropped without losing national coverage. The opposite holds: each operator is missing one or two regions, and the other four always cover them.
  - **Fewest-hop route between two locations** — the legacy comment said every intermediate node is a charging station; Lyon and Marseille are intermediate cities on that route.
  - **Road network by class** — the legacy comment called Express "the only class at 130 kph free-flow"; Motorway is also 130 (Express differs at peak, 105 against 95).
  - **Best route, scored** — the legacy query was a `NEXT` segment to append after the feasible-routes query, which returns only `p` and caps routes at `$limit`, so the chain could not bind `c` and would have ranked an arbitrary subset. It is now self-contained: the same expansion, then the existing scoring over every feasible route. The legacy comment also said the repeated station names mean the vehicle "takes both tiers"; the best route takes one top-up at each of three stations.
  - **Best route, scored** — the legacy comment said that ordering by energy first "usually trades about an hour for a few kWh on long lanes". On Paris → Marseille it trades 2.4 minutes for 1.3 kWh (see that section's Sensitivity).
- `$detourRatio = 1.35`, `$minSoc = 10.0`, `$maxSoc = 100.0`, `$maxMins = 900.0`, `$departureHour = 6`, `$reserveSoc = 10.0`, `$requiredRangeKm = 400` and `$limit = 50` are the legacy sample parameters. `1.35` is the upper end of typical road circuity and was not tuned to this data; the best Paris → Marseille route survives at 1.02. `$maxMins = 900` is generous — no feasible route here comes near it.
- The legacy appendix — statements that added a shared `Geo` label to charging stations after import, a verification and undo pair, and an optional point property with its index — was dropped in the migration. No query depended on it, running it silently broke two bundled queries, and the source page's `(x:Geo)` queries are better adapted to the `(:Geo|ChargingStation)` union.
- The `CHARGE` mapping identifies relationships by `tier` (`"key": ["tier"]`), added in the migration so the two options per station are not merged on import. In the spec library's conversion (`GraphSpecDataModelV3Migration.convertMappingKeyProperties`) a relationship mapping key becomes Import's `relationshipKeyProperties` — the merge identity — not a `KEY` constraint.
- `ONTOLOGY.json` sets `must_exist` on the five `ROAD` properties for the `geoRoadGeo` entry only; the other two `ROAD` entries say "Expected on every ROAD relationship" instead. An existence constraint is scoped to the relationship type, not to a node pair, so the same flag on all three entries produced three constraints named `road_ref_ROAD_propertyExistence` (and so on), and the destination dropped the package while registering it (`graph-spec contains duplicate constraint name`). The one remaining flag already constrains every `ROAD` relationship in the database.

## Available anchors

- **Parameters:** none.
- **Invariant:** one row per `Geo`, `ChargingStation` and `Car` node, and nothing else; `kind` takes only `city`, `station`, `vehicle`.
- **Expected:** 280 rows — 150 `city`, 100 `station`, 30 `vehicle`. `EV-013` has label `Aurex Estate 77 (Fleet Car, 95.0%)`.

## Reference ontology sanity check — node and relationship counts

- **Parameters:** none.
- **Invariant:** each count equals the rows in its CSV — `cities.csv`, `charging-stations.csv`, `cars.csv`, the three road CSVs together, and `charges.csv`.
- **Expected:** 1 row — cities 150, charging_stations 100, cars 30, road_segments 440, charge_options 200.
- **Sensitivity:** road_segments 270 means only `roads-city-city.csv` loaded; charge_options 100 means the two tiers per station merged.

## Road network by class — the four-tier hierarchy

- **Parameters:** none.
- **Invariant:** one row per distinct `road_class` across all three road tables; segments sum to the road row count.
- **Expected:** 4 rows — Motorway 162 segments, avg 67.9 km, total 11008, top 130; Trunk 162, 71.4, 11559, 110; Local 63, 43.4, 2735, 80; Express 53, 158.5, 8400, 130. Motorway and Trunk tie on segments, so their order is not fixed.

## Vehicle range — one vehicle's usable range from telemetry

- **Parameters:** `$carId = 'EV-013'`, `$reserveSoc = 10.0`.
- **Invariant:** usable_kwh = battery_capacity_kwh × (current_soc_percent − 10) / 100, and range_km = usable_kwh / efficiency_kwh_per_km, for the one vehicle.
- **Expected:** 1 row — Aurex Estate 77, Fleet Car, battery 77.0, SoC 95.0, max charge 150.0, usable 65.5 kWh, range_km 385.
- **Sensitivity:** `$carId = 'EV-005'` (Meridian LV-85, Light Van, 26% SoC) gives usable 13.6 kWh and range_km 52 — not enough to leave the Paris area without charging.

## Charging station detail — one station, its charge tiers and the roads that reach it

- **Parameters:** `$stationName = 'CS-A7-01'`.
- **Invariant:** one row; charge_tiers lists every `charges.csv` option for the station in tier order; connected_roads lists every road row touching it, in either direction.
- **Expected:** 1 row — 300.0 kW, ElectraRoute, Auvergne-Rhone-Alpes, `['full (40 min)', 'top-up (15 min)']`, roads `Lyon via A7 (159.8 km)` and `Marseille via A7 (155.2 km)` in either order.
- **Sensitivity:** `'CS-LYON-02'` — 50.0 kW, VoltWay, one road `Lyon via D701 (10.0 km)`.

## Charging options near a city — stations within two road hops, by depth

- **Parameters:** `$cityName = 'Lyon'`.
- **Invariant:** every station reachable from Lyon in one or two road segments, each once, at its fewest hops; nothing farther.
- **Expected:** 10 rows. 1 hop: CS-A89-01 350, CS-A7-01 300, CS-A89-02 300, CS-A36-01 250, CS-A31-02 175, CS-A6-01 150, CS-LYON-02 50. 2 hops: CS-A72-01 350, CS-GRENOBLE-15 350, CS-N79-01 200. Ties on power (CS-A7-01/CS-A89-02; CS-A72-01/CS-GRENOBLE-15) appear in either order.
- **Sensitivity:** a 1..1 bound returns exactly the 7 one-hop stations.

## Charging capacity by region

- **Parameters:** none.
- **Invariant:** one row per region with a station; sites and total_kw sum to 100 and 23,175 kW.
- **Expected:** 12 rows — Nouvelle-Aquitaine 16 / 4050, Normandie 12 / 2650, Auvergne-Rhone-Alpes 11 / 2600, Occitanie 9 / 2475, Bretagne 8 / 2150, Bourgogne-Franche-Comte 9 / 1750, Grand Est 8 / 1700, Provence-Alpes-Cote d'Azur 7 / 1550, Centre-Val de Loire 6 / 1275, Hauts-de-France 4 / 1150, Pays de la Loire 6 / 1100, Ile-de-France 4 / 725.

## Operator footprint

- **Parameters:** none.
- **Invariant:** one row per operator; sites sum to 100.
- **Expected:** 5 rows — ElectraRoute 22 sites, 5750 kW, 10 regions, 10 high-power; NordVolt 22, 5000, 11, 4; ChargeLine 19, 4550, 11, 8; AmperGrid 19, 4300, 10, 5; VoltWay 18, 3575, 10, 5. No operator is in all 12 regions, yet any one of them can be dropped and the other four still cover all 12.

## Charge tiers — what each dwell time delivers

- **Parameters:** none.
- **Invariant:** one row per tier; each station contributes one option to each.
- **Expected:** 2 rows — top-up: 100 options, 15 min, avg 57.9 kWh, best 87.5; full: 100 options, 40 min, avg 154.5 kWh, best 233.3. The full tier is 2.7× the dwell for 2.7× the energy, because both tiers run at the station's power.

## Charging coverage gaps — cities with no station within two road hops

- **Parameters:** none.
- **Invariant:** exactly the cities from which no road path of one or two segments reaches a station.
- **Expected:** 12 rows, in this order — Belfort (5 links), Besancon (4), Mulhouse (4), then at 3 links Albertville, Annecy, Annemasse, Cambrai, Digne-les-Bains, La Rochelle, Montelimar, Saint-Louis, Vesoul. Regions: Auvergne-Rhone-Alpes 4, Bourgogne-Franche-Comte 3, Grand Est 2, one each in Hauts-de-France, Nouvelle-Aquitaine and Provence-Alpes-Cote d'Azur.
- **Sensitivity:** a 1..3 bound returns 0 rows.

## Fleet composition and reach

- **Parameters:** `$reserveSoc = 10.0`, `$requiredRangeKm = 400`.
- **Invariant:** one row per vehicle class; ready_without_charging counts the class's vehicles whose range at the reserve reaches the required range.
- **Expected:** 3 rows — Light Van 12 vehicles, avg battery 74, avg SoC 58, avg range 151, 0 ready; Fleet Car 10, 89, 61, 280, 1 ready (EV-016, 477 km); Rigid Truck 8, 260, 66, 205, 0 ready.
- **Sensitivity:** the next-longest ranges are EV-013 385 km and EV-020 377 km, so `$requiredRangeKm = 375` makes 3 vehicles ready.

## Inline corridor stations — sites with no bypass

- **Parameters:** `$limit = 50`.
- **Invariant:** only stations with exactly two road segments; never a spur.
- **Expected:** 70 stations qualify — every corridor-named station — so `$limit = 50` returns 50 rows. The first six are the 150 kW sites CS-A10-02 (Orleans, Paris), CS-A26-01 (Lille, Reims), CS-A29-01 (Le Havre, Lille), CS-A6-01 (Lyon, Paris), CS-A6-02 (Auxerre, Chalon-sur-Saone), CS-A71-01 (Clermont-Ferrand, Paris).
- **Sensitivity:** `$limit = 100` returns all 70. A worked example outside the first rows: CS-A10-01, 250 kW, between Bordeaux (336.5 km, the longest segment in the data) and Paris (248.5 km).

## Corridor preview — how hard the spatial prune bites, before paying for traversal

- **Parameters:** `$sourceName = 'Paris'`, `$targetName = 'Marseille'`, `$detourRatio = 1.35`.
- **Invariant:** corridor_nodes counts every location whose summed great-circle distance to Paris and Marseille is below 1.35 × the direct distance; Paris and Marseille themselves are always inside.
- **Expected:** 1 row — corridor_nodes 162, corridor_stations 62, direct_km 661.
- **Sensitivity:** 1.10 gives 82 nodes / 33 stations; 1.02 gives 36 / 14. The best EV-013 route survives at 1.02, so the tight corridor finds the same answer as the wide one at a fraction of the search space.

## Lane feasibility across the fleet — which vehicles can serve this lane today

- **Parameters:** `$sourceName = 'Paris'`, `$targetName = 'Marseille'`, `$detourRatio = 1.35`, `$minSoc = 10.0`, `$maxSoc = 100.0`, `$maxMins = 900.0`, `$departureHour = 6`.
- **Invariant:** a vehicle counts as able to serve the lane exactly when some route of at most 14 ROAD and CHARGE hops through the corridor keeps its state of charge at or above 10% after every hop. Time never binds here: every vehicle that can serve the lane has a route under 12 hours.
- **Expected:** 3 rows — Light Van 12 vehicles, 10 can serve, 2 blocked (EV-001, EV-007); Fleet Car 10, 10, 0; Rigid Truck 8, 8, 0. 28 of 30 overall.
- **Sensitivity:** both blocked vans are hop-bound, not range-bound: each needs 18 hops, so `{1,18}` (or the legacy `{1,24}`) lets all 30 through. Replacing every `(:Geo|ChargingStation)` with `(:Geo)` gives 0 of 30. See the profile's minimum-route-length list for every vehicle's threshold.

## Location ego network — everything one hop from a city

- **Parameters:** `$cityName = 'Lyon'`.
- **Invariant:** the drawn neighbours are exactly the locations sharing a road row with Lyon, cities and stations both.
- **Expected:** Lyon plus 14 neighbours, 7 of them ChargingStation. Nearest Villeurbanne 5.3 km (N383); CS-LYON-02 10.0 km (D701, Local); farthest the Express corridor stations CS-A7-01 159.8, CS-A6-01 258.5, CS-A36-01 268.8, CS-A89-01 318.5 km.
- **Sensitivity:** with `(n:Geo)` instead of the union, 7 neighbours and no stations.

## Fewest-hop route between two locations

- **Parameters:** `$sourceName = 'Paris'`, `$targetName = 'Nice'`.
- **Invariant:** the returned path has the fewest road segments of any Paris–Nice road path.
- **Expected:** 1 path — 6 hops, 980.0 km, roads A6, A6, A7, A7, A8, A8, via Paris - CS-A6-01 - Lyon - CS-A7-01 - Marseille - CS-A8-01 - Nice. It is the only 6-hop path, so the result is fixed. Every intermediate node except Lyon and Marseille is a charging station, because the Express tier runs through mid-corridor sites.

## Least-distance routes — ranked by driving distance, not hop count

- **Parameters:** `$sourceName = 'Paris'`, `$targetName = 'Nice'`, `$limit = 5`.
- **Invariant:** paths in ascending order of summed distance_km, none longer than 8 segments, none reusing a road.
- **Expected:** 5 paths — 899.1 km (8 hops, Paris - CS-A6-01 - Lyon - Grenoble - Gap - Digne-les-Bains - Draguignan - Cannes - Nice); 980.0 (6 hops, the fewest-hop route); 991.8 (via Marseille, Toulon, Frejus, Cannes); 994.1 (via Marseille, Toulon, Frejus, Antibes); 998.9 (via Marseille, Toulon, Draguignan, Cannes). Only 11 road paths of at most 8 segments join Paris and Nice.

## Charging catchment of a city — the paths out to reachable stations

- **Parameters:** `$cityName = 'Lyon'`, `$limit = 50`.
- **Invariant:** every path ends at a station and has one or two segments.
- **Expected:** 10 paths, one to each station listed under **Charging options near a city**; 7 are a single segment.
- **Sensitivity:** `'Annecy'` or `'Mulhouse'` (both coverage gaps) return no paths.

## Feasible routes under battery and time constraints

- **Parameters:** `$carId = 'EV-013'`, `$sourceName = 'Paris'`, `$targetName = 'Marseille'`, `$detourRatio = 1.35`, `$minSoc = 10.0`, `$maxSoc = 100.0`, `$maxMins = 900.0`, `$departureHour = 6`, `$limit = 50`.
- **Invariant:** every returned path starts at Paris, ends at Marseille, stays in the corridor, has at most 14 hops, and replayed hop by hop keeps EV-013's state of charge between 10% and 100% and its elapsed time within 900 minutes.
- **Expected:** 50 paths. Well over 50 feasible routes exist, so which 50 are returned is not fixed. The shortest feasible route has 8 hops.
- **Sensitivity:** `$carId = 'EV-005'` with `$minSoc = 35.0` returns no paths — the van starts at 26%.

## Best route, scored — one recommendation with the numbers behind it

- **Parameters:** `$carId = 'EV-013'`, `$sourceName = 'Paris'`, `$targetName = 'Marseille'`, `$detourRatio = 1.35`, `$minSoc = 10.0`, `$maxSoc = 100.0`, `$maxMins = 900.0`, `$departureHour = 6`.
- **Invariant:** the row is, among every feasible route the feasible-routes query could return (no `$limit`), the one with the earliest arrival; among equal arrivals the least energy; then the fewest hops.
- **Expected:** 1 row — EV-013, Aurex Estate 77, 9 hops, 3 charge stops (one `top-up` each at CS-A6-01, CS-LYON-02 and CS-A7-01), driving_km 800.0, elapsed_hours 7.47, energy_drawn_kwh 136.0, arrival_soc_percent 32, via Paris - CS-A6-01 - CS-A6-01 - Lyon - CS-LYON-02 - CS-LYON-02 - Lyon - CS-A7-01 - CS-A7-01 - Marseille. The best route is the same at `$detourRatio` 1.10 and 1.02.
- **Sensitivity:** departure hour changes the answer through the peak-speed penalty — Paris → Lyon for EV-013 (route Paris - CS-A6-01 - CS-A6-01 - Lyon, one top-up, 465.0 km) takes 3.83 h leaving at 04:00, 4.30 h at 06:00 and 4.68 h at 07:00. Ordering energy first instead of time picks an 11-hop route via Fontainebleau, Auxerre, two top-ups at CS-A6-02, Chalon-sur-Saone, Macon, Lyon and a top-up at CS-A7-01: 792.6 km, 134.7 kWh, 7.51 h, arrival 29% — 1.3 kWh saved for 2.4 extra minutes. `$carId = 'EV-005'` with `$minSoc = 35.0` returns no row.
