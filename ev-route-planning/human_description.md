# EV Route Planning

Work out which electric vehicles can actually make a delivery run, and what the route looks like once charging stops are part of the plan.

## Overview

### Electrifying a logistics fleet

Planning a run for a diesel van is mostly a question of distance and driver hours. Refuelling is quick, filling stations are dense, and the vehicle's range is rarely the binding constraint. Replace the van with an electric one and the problem changes shape.

Range is now finite and varies by vehicle. Recharging takes a meaningful slice of the working day rather than a few minutes. Charging sites are sparse, unevenly distributed, and not all equally fast. And the rate at which a vehicle actually charges is the *lower* of what the site can deliver and what the vehicle can accept — so a fast charger does nothing for a vehicle that cannot draw the power.

The result is that four things interact, and no one of them can be settled first:

- **Battery capacity and efficiency**, which set how far a vehicle goes on a charge.
- **Charger power and dwell time**, which set how much range a stop buys back.
- **Traffic**, which changes journey time and therefore whether a run fits a shift at all.
- **Network shape**, which decides whether a charger is anywhere near the route.

Planning each leg independently does not work, because a decision early in a route — taking a shorter leg, or stopping at a slower charger — changes what is reachable later. The state of charge has to be carried along the route as it is built, and the route has to be built knowing the state of charge. That circularity is what makes the problem hard in a spreadsheet, and it is why teams often fall back on a conservative rule of thumb that leaves usable capacity on the table.

### What it helps with

Treating roads, charging sites and vehicles as one connected network means a route can be traversed while the battery and the clock are tracked along it.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Whether a vehicle can serve a lane depends on the whole route, not on any leg | Carry state of charge and elapsed time along the route as it is built, so feasibility is decided by the route as a whole |
| A route and its charging stops have to be chosen together | Let a traversal pass through charging sites as ordinary places on the network, so stops are part of the route rather than added afterwards |
| A fast charger is wasted on a vehicle that cannot draw the power | Hold the site's maximum power and the vehicle's own charging limit separately, so the rate delivered is the lower of the two |
| Fleets are mixed, and a lane one vehicle can serve another cannot | Evaluate the same lane against every vehicle's battery and efficiency, so the answer is which vehicles can serve it today |
| Charging deserts are invisible until a route fails | Search outward from each place for a charging site within a set number of road hops, so the places with none are listed rather than discovered in service |
| Journey time depends on when you travel | Hold a free-flowing and a peak speed on every road segment, so the same route can be timed for either condition |
| Capacity and operator coverage are hard to summarise | Aggregate charging sites by region, operator and power to show where capacity actually sits |

Routes produced this way are planning inputs that need operational validation, not dispatch instructions. The energy model is deliberately simple: consumption is treated as a constant per kilometre, with no allowance for load, gradient, weather or driving style, and charging is modelled as a flat rate over a fixed dwell rather than the tapering curve real batteries follow. Both approximations flatter the vehicle slightly, so treat computed feasibility as optimistic.

## Ontology

The reference ontology has three kinds of thing and two kinds of connection, and two of its design decisions are unusual enough to explain up front.

**Places and charging sites are kept deliberately separate.** A city and a charging site are both points on the road network, but they are distinct kinds of thing here, with nothing in common to traverse generically. This is a consequence of each entity carrying a single primary classification, and it has a practical edge: a traversal that means "any location" has to name both kinds explicitly. One that names only places is perfectly valid and returns perfectly plausible routes — routes that never charge.

**Charging is modelled as a connection from a site back to itself.** That sounds odd until you see what it buys: a route can pass *through* a charging stop without leaving the site, so a stop is a step in the path like any other rather than a special case handled outside the traversal. Each site carries one such loop per charging option it offers, distinguished by tier, so choosing a quick top-up over a full charge is choosing between parallel connections.

Roads are stored once per segment and are meant to be read in both directions — the stored orientation records how the segment was written down, not a one-way restriction. Because places and sites are distinct kinds of thing, the same road connection appears in three forms, one for each pairing of endpoints.

Vehicles sit outside the network entirely. A vehicle is not positioned anywhere; it supplies the battery and efficiency figures a route is evaluated against.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Geo` | A place on the network that is not a charging site — a city, depot or delivery point. Shares no classification with a charging site, so a traversal meaning "any location" must name both or it will plan routes that never charge |
| `ChargingStation` | A site where vehicles can charge, sitting on the road network as a place in its own right |
| `Car` | A vehicle in the fleet, described by the battery and efficiency figures a route plan needs. Carries no connection to the network — it supplies the energy model rather than occupying a position |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Geo` | `name` | String | Name of the place and its identifier on the network, unique across the whole network rather than within a region |
| `Geo` | `lat` | Float | Latitude in decimal degrees, positive northwards. Used for straight-line filters that narrow candidates before a traversal — not the distance a vehicle drives |
| `Geo` | `lon` | Float | Longitude in decimal degrees, positive eastwards |
| `Geo` | `region` | String | Administrative region the place sits in, used to group and summarise coverage rather than to route |
| `ChargingStation` | `name` | String | Name of the charging site and its identifier on the network |
| `ChargingStation` | `lat` | Float | Latitude in decimal degrees, positive northwards |
| `ChargingStation` | `lon` | Float | Longitude in decimal degrees, positive eastwards |
| `ChargingStation` | `region` | String | Administrative region the site sits in, used to summarise charging capacity and coverage by area |
| `ChargingStation` | `operator` | String | Network operator running the site. Matters for access and tariffs rather than for routing |
| `ChargingStation` | `power_kw` | Float | Maximum power the site can deliver to one vehicle, in kilowatts. A ceiling rather than a delivered rate — what a given vehicle receives is the lower of this and its own limit |
| `Car` | `id` | String | Identifier for the vehicle in the fleet |
| `Car` | `model` | String | Manufacturer's model name. Descriptive only; the energy model reads the numeric properties |
| `Car` | `vehicle_class` | String | Category of vehicle, used to group the fleet when comparing what different classes can serve |
| `Car` | `battery_capacity_kwh` | Float | Usable battery capacity in kilowatt-hours — the usable figure rather than the nominal pack size, since range is computed directly from it |
| `Car` | `efficiency_kwh_per_km` | Float | Energy consumed per kilometre, in kilowatt-hours per kilometre. A consumption rate, so a higher number is a less efficient vehicle. Treated as constant, with no allowance for load, gradient, weather or speed |
| `Car` | `max_charge_power_kw` | Float | Highest charging power the vehicle can accept, in kilowatts. Caps what it draws however powerful the site; ignoring this cap produces charging stops shorter than the fleet can achieve |
| `Car` | `current_soc_percent` | Float | Current battery state of charge as a percentage of capacity, from 0 to 100. A snapshot of the vehicle now and the starting state a route is evaluated from, not a static attribute |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `ROAD` | `Geo` → `Geo` | A road segment between two places, neither a charging site. Stored once per segment and read in both directions — the stored orientation is not a one-way restriction. A place may be joined to several others, or none |
| `ROAD` | `Geo` → `ChargingStation` | A road segment joining a place to a charging site — the approach that makes the site reachable. Stored once and read in both directions. A place may reach several sites, or none |
| `ROAD` | `ChargingStation` → `Geo` | A road segment joining a charging site back to a place — the continuation after a stop. Not every site carries one, and its absence means only that no onward segment was recorded, never that a site is a dead end |
| `CHARGE` | `ChargingStation` → `ChargingStation` | A charging option at a site, looping from the site to itself so a route can pass through a stop without leaving. One per tier the site offers, so several run in parallel and are told apart by tier |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `ROAD` | `road_ref` | String | Designation of the road the segment belongs to, as signed. Several segments may share one designation |
| `ROAD` | `road_class` | String | Class of road, from a four-tier vocabulary — motorway, express, trunk and local — in descending order of speed |
| `ROAD` | `distance_km` | Float | Driving distance along the segment in kilometres. This, not the straight-line distance between coordinates, is what energy consumption is computed from |
| `ROAD` | `free_flow_speed_kph` | Integer | Speed in kilometres per hour expected on the segment when traffic is light |
| `ROAD` | `peak_speed_kph` | Integer | Speed in kilometres per hour expected at peak traffic, at or below the free-flowing speed. Choosing between the two is how a plan accounts for time of day |
| `CHARGE` | `tier` | String | Name of the charging option, distinguishing the parallel options at one site — a short top-up against a longer full charge |
| `CHARGE` | `time_in_minutes` | Integer | Dwell time the option represents, in minutes. Combined with delivered power it gives the energy gained, and it is what a route's elapsed time accumulates |
| `CHARGE` | `power_kw` | Float | Power offered by this option in kilowatts. The vehicle receives the lower of this and its own charging limit, so energy gained is that lower figure over the dwell time, never this alone |
