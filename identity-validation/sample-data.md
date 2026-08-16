# Sample Data

500 masked profiles under `sample-data/`, deliberately seeded so every query template returns a meaningful result.

| File               | Rows | Produces               |
| ------------------ | ---- | ---------------------- |
| `identities.csv`   | 500  | 500 `Identity` nodes   |
| `names.csv`        | 500  | 484 `PersonName` nodes |
| `phones.csv`       | 439  | 428 `Phone` nodes      |
| `emails.csv`       | 390  | 386 `Email` nodes      |
| `ssns.csv`         | 367  | 366 `SSN` nodes        |
| `addresses.csv`    | 416  | 410 `Address` nodes    |
| `dobs.csv`         | 416  | 408 `DOB` nodes        |
| `ip_addresses.csv` | 487  | 482 `IPAddress` nodes  |
| `locations.csv`    | 407  | 405 `Location` nodes   |

Every attribute file also carries `identityId`, which supplies the relationship from `Identity`. `locations.csv` is the exception: it carries `addressId` and supplies `GEOCODED_TO` from `Address` rather than from `Identity`.

Every node is keyed on a single property, as the Import flow requires. Seven labels have a natural one — `identityId`, `fullName`, `phoneNumber`, `email`, `ssn`, `dateHash`, `ip`. The two with composite identities carry a derived key instead:

| Column       | In                               | Form                                   |
| ------------ | -------------------------------- | -------------------------------------- |
| `addressId`  | `addresses.csv`, `locations.csv` | `"1210 Foxglove Dr, Austin, TX 78701"` |
| `locationId` | `locations.csv`                  | `"30.2686,-97.7411"`                   |

Both are derived from exactly the values they stand in for, so dedup is unchanged: 416 address rows produce 410 `Address` nodes, and 407 geocoded addresses produce 405 `Location` nodes. Both contain commas and are therefore CSV-quoted throughout.

## Masked, not randomised

The sample data uses realistic-format but masked identifiers — `XXX-XX-4821` for SSN, `555-201-8823` using the reserved fake area code, `203.0.113.x` reserved documentation IPs — rather than opaque random strings or full plaintext PII. This lets an audience visually confirm exact and near-duplicate matches themselves during a demo, without ever showing anything resembling a real, complete identifier.

Preserve this convention if you add or edit sample data. Don't anonymise into random tokens, and don't add full unmasked identifiers.

Two fields are exceptions.

`Location.latitude` / `longitude` — there's no PII-equivalent to mask in a coordinate pair, so the data uses real ZIP-centroid coordinates for the 12 cities in this dataset, jittered a few hundred metres per address. Distances stay directionally realistic and no external geocoding API is needed to load or demo the package. This is not the output of an actual geocoder run against these addresses; don't present it as one.

`DOB.dateHash` — the opposite of masking. `DOB` is keyed on a keyed hash of the full birthdate rather than the masked display value, so matching runs on real date precision without the real date ever being stored or shown. If you regenerate this field, keep using an HMAC with a secret key, not a plain hash: a birthdate has too little entropy for a plain hash to protect it. See `caveats.md`.

A masked value carries less entropy than the value it replaces, and that has consequences the queries have to be designed around. `caveats.md` covers each one.

## What's seeded

- **9 hand-curated identities** from the original design, including the three-channel Robert Anderson cluster (CRM, MobileApp, CallCenter).
- **10 more** across four additional multi-channel match clusters, varying which attributes each shares: phone+address+DOB+IP, phone+email, address+DOB, IP+phone.
- **3 synthetic-identity fraud pairs**, each corroborated by a shared phone, a near-duplicate SSN, and a near-miss name spelling.
- **5 identities** across two placeholder collisions (`none@none.com`, `test@test.com`), plus three sharing the placeholder phone `999-999-9999`.
- **4 identities** across two location-only match pairs: same geocoded coordinates, different address text, no other shared identifier.
- **3 identities** with addresses the geocoder couldn't resolve: two invalid zip formats, one zip/city mismatch.
- **~466 non-colliding noise profiles** with realistic capture gaps, roughly 10–30% missing per attribute.

## Expected results

Running the templates in order against this data produces:

| Query                                   | Result                                                      |
| --------------------------------------- | ----------------------------------------------------------- |
| Placeholder detection (email)           | 2 flagged values, 4 identities                              |
| Placeholder detection (phone)           | 1 flagged value, 3 identities                               |
| Shared Identifier Fan-out               | 39 rows across 17 distinct pairs                            |
| Confidence-Scored Matches               | 17 pairs: 5 at confidence 1, 7 at 2, 1 at 3, 3 at 4, 1 at 5 |
| Match Cluster as a Graph (`ID-1001`)    | 8 paths                                                     |
| Implausible Address Detection           | 3 addresses                                                 |
| Location Match                          | 2 pairs                                                     |
| Descriptor Similarity                   | 3 pairs (0.948, 0.923, 0.861)                               |
| Nearby Address                          | 1 pair, 241m apart                                          |
| Weighted Composite                      | 15 rows, 0.375–0.883                                        |
| Near-Duplicate SSN                      | 3 corroborated pairs                                        |
| Cross-Channel Assembly (`555-201-8823`) | 3 rows / 17 paths                                           |

Six legitimate multi-channel clusters rank at the top of both scored queries (confidence 2–5, scores 0.533–0.883). The three synthetic-identity pairs sit distinctly below them (confidence 1, scores 0.375–0.401), flagged only because three corroboration signals agree — and a fourth for one of the three, since David and Daniel Kim also land 241m apart. Two location-only pairs are invisible to every attribute-based query and are found only by `Location Match`. 476 of the 500 identities have no genuine match at all.

The counts above are a property of this dataset's random seed, not a guarantee. If you regenerate or extend the sample data, re-run every template and update both this file and the expected-result comments in `query-templates.md`.
