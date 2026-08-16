# Graph Model

The authoritative definition is `GRAPH_MODEL.json` (graph-spec `4.0.0`). This file explains the reasoning behind it.

## Labels

One hub node label:

- `Identity` — a single raw profile record as captured by one source system, not yet resolved to a real-world person.

Seven attribute node labels, each holding one identifier type:

| Label        | Key           | Other properties                      |
| ------------ | ------------- | ------------------------------------- |
| `PersonName` | `fullName`    | `firstName`, `lastName`               |
| `Phone`      | `phoneNumber` | —                                     |
| `Email`      | `email`       | —                                     |
| `SSN`        | `ssn`         | —                                     |
| `Address`    | `addressId`   | `address`, `city`, `state`, `zipcode` |
| `DOB`        | `dateHash`    | `dob` (masked, year-only)             |
| `IPAddress`  | `ip`          | —                                     |

Plus one derived attribute node, one hop past `Address`:

- `Location` — keyed on `locationId`, carrying `latitude` and `longitude` as `FLOAT`.

Every node is keyed on exactly **one** property. That is a hard requirement of the Import flow, which needs a single property that uniquely identifies each node and cannot infer one from a composite. `Address` and `Location` are the two nodes with naturally composite identities, so each carries a derived single-property key — see below.

## Relationships

```text
(:Identity)-[:HAS_NAME]->(:PersonName)
(:Identity)-[:HAS_PHONE]->(:Phone)
(:Identity)-[:HAS_EMAIL]->(:Email)
(:Identity)-[:HAS_SSN]->(:SSN)
(:Identity)-[:HAS_ADDRESS]->(:Address)
(:Identity)-[:HAS_DOB]->(:DOB)
(:Identity)-[:HAS_IP]->(:IPAddress)
(:Address)-[:GEOCODED_TO]->(:Location)
```

## Why convergence is the match signal

Attribute nodes deduplicate by their own key. Two `Identity` records sharing a phone number automatically converge on the same `Phone` node, and that convergence _is_ the match signal — no extra modelling required.

Because convergence relies on exact key equality, `Phone.phoneNumber` and `SSN.ssn` in the sample data are each stored in one fixed format (`555-XXX-XXXX`, `XXX-XX-####`). Real source systems rarely agree: `(555) 201-8823`, `555.201.8823`, and `5552018823` are the same phone number but three different `Phone` nodes unless normalised before import. Plan on that as an upstream data-cleaning step; this model does not do it for you. See step 4 of `implementation-guidance.md`.

Not every `Identity` needs every attribute. Missing attributes — a mobile signup with no SSN, a call-centre record with no email — are normal, and are modelled by omitting the relationship, not with a null property. In the bundled sample data, 500 identities carry 439 phones, 390 emails, 367 SSNs, 416 addresses, 416 DOBs, and 487 IPs.

## Address and Location

`Address` is identified by everything that makes it distinct — the raw street string plus city, state, and zipcode — rather than a geocoder-standardised form, specifically so a suite or apartment number captured by one source system isn't lost. Geocoders often normalise that detail away.

Because Import needs a single identifying property, that composite identity is carried by `addressId`, a canonical concatenation of the four values:

```text
addressId = "1210 Foxglove Dr, Austin, TX 78701"
```

`address`, `city`, `state`, and `zipcode` remain as separate properties for querying and display; `addressId` exists purely to identify the node. Because it is derived from exactly the values it replaces, dedup behaviour is identical to a composite key: two identities at the same address still converge on one `Address` node, and two addresses differing in any of the four fields stay distinct. Across the sample data, 416 address rows produce 410 distinct `Address` nodes.

`Location` works the same way. Its natural identity is the coordinate pair, so `locationId` is the canonical form of it:

```text
locationId = "30.2686,-97.7411"
```

`latitude` and `longitude` remain as `FLOAT` properties, which is what the spatial query actually reads.

If you swap in a real geocoding provider, keep the same shape but derive `locationId` from whatever the provider returns — its own place ID is the natural choice, and better than a coordinate string, since two lookups of the same place can return coordinates that differ in the last decimal and would then fail to converge.

`Location` is where standardisation value shows up. Two different `Address` strings that a geocoder treats as the same place ("215 Congress Ave" vs "215 Congress Avenue") converge on one `Location` node, exactly the way two identities sharing a `Phone` converge into a match. In the sample data, 407 geocoded addresses converge onto 405 `Location` nodes — the two seeded location-match pairs are the difference.

Not every `Address` has a `Location`. An address that fails to geocode simply gets no `GEOCODED_TO` relationship, mirroring how missing attributes are modelled elsewhere. That absence is the signal `Implausible Address Detection` looks for, rather than trying to enumerate every way an address can be malformed.

This is why geocoding lives in its own table. `addresses.csv` carries `identityId`, `addressId`, and the four address fields, with no coordinates. `locations.csv` carries `addressId`, `locationId`, `latitude`, and `longitude` — one row per _successfully geocoded_ address — and supplies both the `Location` nodes and the `GEOCODED_TO` relationships. Keeping coordinates out of `addresses.csv` means every relationship endpoint in the sample data resolves to a real node: the three deliberately unresolvable addresses are simply absent from `locations.csv` rather than present with empty cells.

`Location.coordinates` is **not** in the graph model. `point.distance()` needs a point value, but that point is derived after load rather than imported, so the `Nearby Address` template constructs it inline from `latitude` and `longitude`. `SETUP.md` has a clearly optional section that materialises a real `coordinates` property and indexes it if you want spatial index support.

## DOB and the entropy problem

`DOB` is the one attribute node keyed on a value that is never displayed. `dateHash` is an HMAC-SHA256 of the full unmasked birthdate, computed once at load time, so identical birthdates converge on one node the same way identical phone numbers do. The masked, year-only `dob` rides along as a display-only property on that same node, not as the key.

This matters at scale in a way it doesn't at demo scale. Keying `DOB` on the masked year means every person born in the same year converges onto one node, which is a coincidence, not a match. Across the 500 sample profiles there are only 56 distinct year values, producing 1,566 coincidental same-node pairs. Keying on the full date instead gives 408 distinct values across the 416 identities that have a birthdate, and cuts same-node pairs to 10 — 8 from deliberately-seeded shared identities, and 2 coincidental strangers, in line with what the birthday paradox predicts at this population size.

The fix costs nothing in what a demo displays: only what's used to decide whether two `DOB` nodes are the same node. See `caveats.md` for the secret-key requirement this depends on.

## PersonName

`PersonName` is a descriptor, not an identifier. It's modelled as a node like the others, but deliberately excluded from the core matching queries and used only as corroborating evidence.

`firstName` and `lastName` are loaded but not scored by any query template here. That's deliberate, not an oversight: masked surnames carry too little entropy for a standalone family-link or name-change signal. See "Beyond this starter pattern (name decomposition)" in `implementation-guidance.md`.

Because `fullName` is the node key, two people whose masked names collide would share one `PersonName` node — and, worse, that node's `firstName` and `lastName` would depend on which row loaded last. The sample data had five such collisions (Bowen/Burton both masking to `B***n`, and four others); each is resolved by revealing one extra surname character on the noise-side record, so every `fullName` key now maps to exactly one real name. Watch for this whenever you extend masked sample data: a masked key is a weaker key than the value it stands in for.

## Derived labels

A `:Placeholder` label is applied to attribute nodes by the placeholder-detection query. It is not part of the raw import model and is absent from `GRAPH_MODEL.json`, since it's a derived flag added after data is loaded, not a field any source system provides.
