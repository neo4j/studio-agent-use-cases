// ============================================================================
// Identity Graph — schema setup
//
// THIS FILE WRITES TO THE DATABASE. It creates constraints and indexes only; it
// creates no nodes, relationships or properties, except for the clearly marked
// optional section at the end. Confirm the target database and connection before
// running it.
//
// The sample-data Import flow creates the KEY constraints itself from
// GRAPH_MODEL.json, so on a freshly imported database the constraint statements
// below are no-ops (each is IF NOT EXISTS). Run them when you are loading data
// some other way, or to verify the expected schema is in place.
//
// The two index statements in section 2 are NOT created by Import and are
// required by specific query templates.
// ============================================================================

// ---------------------------------------------------------------------------
// 1. Node key constraints
//
// Every node is keyed on exactly one property, which is what the Import flow
// requires. Address and Location have naturally composite identities, so each
// carries a derived single-property key (addressId, locationId) instead.
//
// Purpose: guarantee attribute nodes deduplicate correctly and give every MERGE
//   an index to look up rather than a label scan. Without a backing index, a
//   MERGE on an attribute value scans every existing node of that label; fine at
//   a handful of rows, genuinely slow at hundreds of thousands.
// Prerequisites: none. Create these BEFORE loading data, not after.
// Expected: 9 constraints exist afterwards. Verify with SHOW CONSTRAINTS.
// ---------------------------------------------------------------------------

CREATE CONSTRAINT identity_id_unique IF NOT EXISTS
FOR (i:Identity) REQUIRE i.identityId IS UNIQUE;

CREATE CONSTRAINT person_name_unique IF NOT EXISTS
FOR (n:PersonName) REQUIRE n.fullName IS UNIQUE;

CREATE CONSTRAINT phone_number_unique IF NOT EXISTS
FOR (p:Phone) REQUIRE p.phoneNumber IS UNIQUE;

CREATE CONSTRAINT email_unique IF NOT EXISTS
FOR (e:Email) REQUIRE e.email IS UNIQUE;

CREATE CONSTRAINT ssn_unique IF NOT EXISTS
FOR (s:SSN) REQUIRE s.ssn IS UNIQUE;

CREATE CONSTRAINT address_id_unique IF NOT EXISTS
FOR (a:Address) REQUIRE a.addressId IS UNIQUE;

CREATE CONSTRAINT dob_hash_unique IF NOT EXISTS
FOR (d:DOB) REQUIRE d.dateHash IS UNIQUE;

CREATE CONSTRAINT ip_unique IF NOT EXISTS
FOR (ip:IPAddress) REQUIRE ip.ip IS UNIQUE;

CREATE CONSTRAINT location_id_unique IF NOT EXISTS
FOR (l:Location) REQUIRE l.locationId IS UNIQUE;

// ---------------------------------------------------------------------------
// 2. Fulltext index required by the "Near-Duplicate SSN" query template
//
// Purpose: let Lucene's fuzzy operator (~1) measure edit distance across the
//   whole masked SSN value.
// Prerequisites: none. Required — that query template fails without this index.
// Expected: SHOW INDEXES lists ssnFuzzyIndex as a FULLTEXT index on SSN(ssn).
//
// The 'keyword' analyzer is not optional. The default analyzer tokenizes on the
// hyphens and fuzzes each token independently, so fuzzy matching silently
// degrades instead of failing loudly.
// ---------------------------------------------------------------------------

CREATE FULLTEXT INDEX ssnFuzzyIndex IF NOT EXISTS
FOR (s:SSN) ON EACH [s.ssn]
OPTIONS { indexConfig: { `fulltext.analyzer`: 'keyword' } };

// ---------------------------------------------------------------------------
// 3. OPTIONAL: materialise a point property for spatial indexing
//
// Purpose: the "Nearby Address" template constructs points inline from latitude
//   and longitude, so it works on imported data with no extra step. If you plan
//   to run radius or bounding-box queries at scale, materialise a real point
//   property and index it, then substitute l.coordinates in that query.
// Prerequisites: Location nodes already loaded. THIS SECTION WRITES A PROPERTY
//   to every Location node — run it only if you want that.
// Expected: 405 Location nodes updated against the bundled sample data, then a
//   POINT index named locationCoordinatesIndex.
//
// Note that `coordinates` is deliberately absent from GRAPH_MODEL.json: it is
// derived after load, not imported from a CSV, in the same way the :Placeholder
// label is applied by a query rather than provided by a source system.
// ---------------------------------------------------------------------------

// MATCH (l:Location)
// WHERE l.coordinates IS NULL
// SET l.coordinates = point({latitude: l.latitude, longitude: l.longitude})
// RETURN count(l) AS locationsUpdated;

// CREATE POINT INDEX locationCoordinatesIndex IF NOT EXISTS
// FOR (l:Location) ON (l.coordinates);
