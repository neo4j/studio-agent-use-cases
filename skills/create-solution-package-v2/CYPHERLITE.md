# Cypherlite for test mode

Test mode runs a package's import and queries on Cypherlite, an embedded openCypher engine shipped as a single binary. This file records:

- the version the skill is pinned to;
- what that version does and does not do, as measured by `scripts/probe_cypherlite.py`;
- the workaround for each gap.

Nothing in test mode relies on a Cypherlite behaviour this file does not record. Re-run the probe whenever the pin changes, and update this file from its output.

A pass on Cypherlite is evidence, not proof. Cypherlite is not Aura's Cypher engine, and the generated `LOAD CSV` script is a second implementation of Aura's Import. Rows marked **verify** state Neo4j's behaviour from its documentation or implementation, not from a live run. They belong on the Aura parity list. Rows marked **confirmed on Aura** were checked in the patient-journey parity run of 30 October 2026 (see "Parity with Aura" below).

## Pinned version

```json
{"arch":"aarch64","name":"cypherlite","os":"macos","version":"0.13.0"}
```

- **Source:** `neo4j-labs/cypherlite` release `v0.13.0` (24 October 2026). Installed by the repo's `distribution/install.sh` to `~/.local/bin/cypherlite`.
- **Verification:** the install script checks `SHA256SUMS.sig` against the pinned `cypherlite-release` ED25519 key, then checks the binary's SHA-256 against `SHA256SUMS`. Both passed.
- **Install:**

  ```bash
  GITHUB_TOKEN=$(gh auth token) sh <cypherlite-checkout>/distribution/install.sh
  ```

  The script installs the latest release. To pin, compare `cypherlite --version --json` with the block above, and re-run the probe if it differs.
- **Telemetry** is on by default. Every script sets `CYPHERLITE_TELEMETRY=0` (`scripts/cypherlite_cli.py`).

### Other surfaces (not used yet)

| Surface | State at v0.13.0 |
| ------- | ---------------- |
| Python | `neo4j_cypherlite-0.13.0` abi3 wheels for macOS, Linux and Windows are release assets (`pip install <wheel>`). PyPI publication is pending. The source builds with maturin from `surfaces/cypherlite-python`. |
| Rust | Cargo workspace (`cypherlite/*`, `surfaces/*`). Not on crates.io yet; usable as a git dependency. |
| Node | `@neo4j-labs/cypherlite` in `clients/javascript`, a C ABI client over the `cypherlite-ffi` tarballs attached to each release. There is also a WASM build (`surfaces/cypherlite-wasm`). |

The skill uses the CLI only. The Python wheel is the natural next step if one-process-per-statement start-up ever matters. At present it does not: a full patient-journey import is about 4 s.

## How test mode calls the CLI

These rules are what `scripts/cypherlite_cli.py` does. Each one rests on a probe case.

- **Store:** a directory from `mktemp -d`, never `:memory:`. Each one-shot call on `:memory:` starts empty (`cli.store_types`). A directory store persists between calls.
- **Output:** `--mode envelope`, one JSON object per statement, with these keys:
  - `columns`, `columnTypes`, `rows` and `truncated`;
  - `notifications`, always present.

  Keys inside a row are sorted, so read `columns` for the order. A failure prints `{"error": {...}}` on stdout. Its `code`, `kind`, `message` and `exit_code` are what test mode records (`cli.envelope`).
- **Row cap:** always pass `--max-rows 0`. Under an agent harness the CLI otherwise stops at 100 rows, sets `truncated`, and warns on stderr (`cli.row_cap`).
- **Parameters:** pass each value as JSON with `--param name=<json>`. A bare `123` binds an INTEGER, so a string must be quoted. Lists and maps work (`cli.params`).
- **Comments and semicolons:** a `;` inside a `/* … */` annotation block, a `//` comment or a string literal does not split the statement. A trailing `;` is fine. So a QUERIES.md block can be run whole, annotation included (`cli.*_semicolon`).
- **Timeouts:** `--timeout 60s` per statement. Exit code 7 means a timeout (`cli.exit_timeout`).
- **Exit codes:**
  - **0** success;
  - **6** statement rejected: syntax, semantic and type errors, unknown functions and procedures, a missing parameter, constraint violations;
  - **7** timeout;
  - **1** other runtime failure.

  A runtime arithmetic error such as `/ by zero` also exits **6**, with kind `type` (`cli.exit_runtime`). So exit 6 alone does not mean "the engine cannot run this". Test mode uses the error message to tell an engine gap from a package fault.
- **EXPLAIN** plans without parameter values (`cli.explain_without_params`). Its envelope carries Neo4j's notification codes:

  | Code | GQLSTATUS |
  | ---- | --------- |
  | `Neo.ClientNotification.Statement.UnknownLabelWarning` | 01N50 |
  | `Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning` | 01N51 |
  | `Neo.ClientNotification.Statement.UnknownPropertyKeyWarning` | 01N52 |
  | `Neo.ClientNotification.Statement.UnboundedVariableLengthPattern` | 03N91 |

  There is also a Cypherlite-only `CypherLite.Notification.Statement.MissingIndex` (03C91), which test mode ignores.
- **Scripts:** a script on stdin (`cypherlite query`) stops at the first failed statement and reports how many committed (`cli.script_stops`). Test mode therefore runs `import.cypher` one statement per call, so that one failure does not hide the rest. Aura's Import likewise carries on with other entities when one fails.
- **Other CLI checks:** `cypherlite clone SRC DEST` copies a store without touching the source (`cli.clone`). `--read-only` rejects writes (`cli.read_only`).

## Capability matrix

The probe ran 251 cases:

| Status | Cases |
| ------ | ----- |
| SUPPORTED | 221 |
| DIFFERENT | 14 |
| UNSUPPORTED | 16 |

Phase 3 added one case, `cypher.limit_short_circuit`, after patient-journey's test run turned it up. The Aura parity run then settled five verify rows; one of them, `toInteger(' 5')`, moved from DIFFERENT to SUPPORTED.

Its full output, with every observation, is under `output/cypherlite-tests/probe-<timestamp>/`. That folder is not committed; this table is the record.

### Every package statement, planned

The probe EXPLAINs all 119 annotated statements in the ten packages' QUERIES.md and SETUP.md.

- **107 plan.**
- **12 do not**, all APOC or GDS:
  - identity-validation: 2 using `apoc.text.jaroWinklerDistance`;
  - retail-banking: 2 using `apoc.coll.toSet`;
  - insurance-claims-fraud: 4 GDS;
  - regulatory-dependency-mapping: 4 GDS.
- **2 more plan but cannot give Neo4j's answer:** identity-validation's two fulltext queries (see Procedures).

That makes 14 non-portable statements, which matches the earlier analysis.

### Construct inventory

The probe greps every package's Cypher, with comments and strings removed, and maps each construct to the cases that cover it. No construct the packages use is uncovered.

| Construct | Uses | Status |
| --------- | ---- | ------ |
| `IS NODE KEY` (QUERIES.md reference sections) | 53 | SUPPORTED |
| `COLLECT {}` / `COUNT {}` / `EXISTS {}` | 11 / 6 / 11 | SUPPORTED |
| `CALL {}` (importing `WITH`, unit) / `CALL (x) {}` | 2 / 1 | SUPPORTED |
| Legacy `shortestPath` / `allShortestPaths` | 5 / 1 | SUPPORTED |
| Variable length `*a..b` | 35 | SUPPORTED |
| Quantified path patterns: `{m,n}`, `+`, `*`, inner `WHERE`, inline node `WHERE`, group variables, cycles | 13 | SUPPORTED |
| Type negation `[r:!T]`, node label disjunction `(x:A\|B)`, type predicate `r:T` | 4 / 22 / 18 | SUPPORTED |
| `MATCH REPEATABLE ELEMENTS` + `allReduce` (Cypher 25) | 3 | SUPPORTED |
| `NEXT` chaining, including inside `CALL (x) {}` and feeding a `MERGE` | 2 | SUPPORTED |
| `CYPHER 25` prefix | 5 | SUPPORTED |
| `UNION`, `OPTIONAL MATCH`, pattern predicates, `MERGE`, `SET n:Label`, `DELETE` | various | SUPPORTED |
| `point()`, `point.distance` | 18 / 13 | SUPPORTED |
| `date()`, `duration()`, `duration.*` | 8 / 2 / 0 | SUPPORTED (values); `toString` differs, see below |
| `datetime()` | 3 | DIFFERENT (`toString` only) |
| `elementId()`, `reduce()`, list and pattern comprehensions, dynamic property access, chained comparison, regex `=~` | various | SUPPORTED |
| `round()` | 48 | DIFFERENT on negative half-way values only (confirmed on Aura) |
| `toString()` on numbers | 10 | SUPPORTED |
| `toInteger` / `toFloat` | 4 / 10 | SUPPORTED (`' 5'` confirmed on Aura) |
| `db.index.fulltext.queryNodes` | 2 | DIFFERENT (no results) |
| `apoc.*` / `gds.*` | 4 / 12 | UNSUPPORTED (as expected) |
| `CREATE INDEX` / `CREATE FULLTEXT INDEX` / `CREATE POINT INDEX` | 2 / 1 / 1 | SUPPORTED |

### Import

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| `file:///x.csv` with `--load-csv-dir` | SUPPORTED | Resolves against the directory | Same |
| `file:///sub/x.csv` | SUPPORTED | Resolves | Same |
| Bare `x.csv` | DIFFERENT (verify) | Accepted | Rejected as an invalid URL |
| `file:///../x.csv` | SUPPORTED | Refused (exit 1, "file unavailable") | Never reads outside the import directory |
| Empty cell `,,` and quoted `""` | DIFFERENT (verify) | Both arrive as `''`, key present | `,,` is null, `""` is `''` |
| CRLF line endings | SUPPORTED | No trailing `\r` | Same |
| Quoting: commas, doubled quotes, embedded newlines | SUPPORTED | RFC 4180 | Same |
| UTF-8 BOM on the header | **DIFFERENT** | BOM kept in the first key (`'﻿id'`), so `row.id` is null | Stripped; Import's papaparse strips it too |
| Leading and trailing whitespace | SUPPORTED (verify) | Preserved | Preserved |
| `LOAD CSV … CALL (row) {…} IN TRANSACTIONS` | **UNSUPPORTED** | `WriteBeforeCallInTransactions` | Supported; Import's own LOAD CSV exporter emits this shape |
| `toInteger` on `'1.0'`, `'TRUE'`, `''`, `' 5'` | SUPPORTED (`' 5'` confirmed on Aura; the rest verify) | `1, null, null, 5` | Same: Aura gives 5 for `' 5'`, where I had expected null |
| `toFloat` on the same | SUPPORTED (`' 5'` confirmed on Aura; the rest verify) | `1.0, null, null, 5.0` | Same |
| `toBoolean` on `'1.0'`, `'TRUE'`, `''`, `' 5'` | SUPPORTED (verify) | `null, true, null, null` | Same |
| Import's BOOLEAN rule `toLower(trim(v)) IN ['1','true','yes']` | SUPPORTED | As expected | Same |
| `datetime()` on the only package format, `YYYY-MM-DDTHH:MM:SSZ` | SUPPORTED (value) / DIFFERENT (`toString`, confirmed on Aura) | Same instant; `toString` drops zero seconds: `2024-02-09T00:00Z` | `2024-02-09T00:00:00Z` |
| `datetime()` with millis, with an offset, with no zone | SUPPORTED (verify) | ISO form kept; no zone means UTC | Same on Aura (default zone UTC) |
| `datetime('2024-01-02')` | DIFFERENT (verify) | Midnight UTC; `toString` drops seconds | Midnight UTC |
| `datetime('2024-01-02 03:04:05')` (space separator) | DIFFERENT (verify) | Accepted; serialises as `2024-01-02T03:04:05Z[Z]` | Rejected (the ISO parser needs `T`) |
| Throughput: full patient-journey import | SUPPORTED | 36 statements, 27,401 CSV lines, 4–7 s; 13,023 nodes and 31,394 relationships | Aura Import takes tens of seconds |

### Schema

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| Single-property `NODE KEY`, in Import's exact statement form | SUPPORTED | Duplicate and missing key both rejected | Same (Enterprise/Aura) |
| Composite `NODE KEY` (tuple syntax) | SUPPORTED | Pair uniqueness and existence enforced | Same |
| Node key used for lookups | SUPPORTED | 20,000 nodes: 0.05 ms with the key, 5.5 ms without | Same, but the plan names the operator `NodeByLabelScan` (start `index-0`) rather than `NodeUniqueIndexSeek` |
| `IS UNIQUE` (node and relationship) | SUPPORTED | Duplicates rejected; missing allowed | Same |
| `IS NOT NULL` (node and relationship), Import's `must_exist` | SUPPORTED | Missing property rejected | Same (Enterprise/Aura) |
| `IS RELATIONSHIP KEY` | SUPPORTED | Enforced | Same |
| `IS :: STRING` property type | SUPPORTED | Enforced | Same (Import never emits it) |
| `SHOW CONSTRAINTS` | SUPPORTED | Neo4j's columns plus `enforcedLabel`; type `NODE_KEY`; constraint name kept | Same as 2025.x |
| `SHOW INDEXES` | SUPPORTED | Neo4j's twelve columns | Same |
| Every `CREATE INDEX` / `FULLTEXT` / `POINT` statement in the packages' SETUP.md, run verbatim | SUPPORTED | Created; `IF NOT EXISTS` reruns as a no-op; right type in `SHOW INDEXES` | Same |
| `CALL db.schema.visualization()` | SUPPORTED | One row of `nodes` and `relationships` | Same |

### Cypher

All SUPPORTED with Neo4j's results unless listed below:

- **Subqueries:** `COLLECT {}` (with `ORDER BY`), `COUNT {}` and `count{}` in `WHERE`, `EXISTS {}` (pattern and `MATCH … WHERE`), `CALL {}` with an importing `WITH`, unit `CALL {}`, `CALL (x) {}`, and `CALL (x) { … NEXT … }`.
- **Shortest paths:** legacy `shortestPath` (`*1..5`, `*0..8`, and a node to itself, which gives a zero-length path (verify)) and `allShortestPaths` (undirected, type disjunction, `*..8`).
- **Patterns:** bounded and upper-only variable length; quantified path patterns in every shape the packages use; `[r:!T]`; `(x:A|B)`; `WHERE r:T`; `MATCH REPEATABLE ELEMENTS` with `allReduce`.
- **Functions:**
  - `startNode`, `endNode`, `elementId` (a STRING, comparable), and `reduce` (including map accumulators and over `relationships(p)`);
  - `point.distance`: WGS-84 matches Aura to 15 significant figures (London–Paris 343,941.0847125 m on both; confirmed on Aura), and Cartesian is exact;
  - `date()`, `duration.between`, `duration.inDays`, and datetime arithmetic, which clamps to month end.
- **Comparisons:** a datetime compared with a date is null, as the packages' prose relies on.
- **Numbers and lists:** `round(x, n)`; `toString` on floats and integers in Java form (`1.0`, `150.0`, `0.30000000000000004`); integer division and modulo; list and pattern comprehensions; dynamic property access; chained comparison; regex with `(?i)` and `\b`.
- **Clauses:** `UNION`, `NEXT` (including `NEXT` into `MERGE`), `CYPHER 25`, `OPTIONAL MATCH`, `SET n:Label`, `DELETE`.
- **Types:** `valueType()` and `IS :: <type>`.

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| `toString(datetime)` at a whole minute | DIFFERENT (confirmed on Aura) | `2024-01-02T00:00Z` | `2024-01-02T00:00:00Z`: Aura printed the seconds both in the verify statement and in patient-journey's pathway query |
| `toString(datetime + duration({months: 1}))` | DIFFERENT | Same seconds rendering; the value itself is right | Same |
| `round(-2.5)` | DIFFERENT (confirmed on Aura) | `-3.0` (half away from zero) | `-2.0`. `round(2.675, 2)` is `2.68` on both |
| `LIMIT` stops the pattern match early | **DIFFERENT** (performance) | No. Over 1,124,250 matches, `LIMIT 1` takes about as long as `count(*)` (2–3 s each). patient-journey's "Shared-condition patient cluster" (`… RETURN path LIMIT 50` over 2,865,853 matches) takes about 29.5 s, the same as counting them all. | Streams: `LIMIT 1` returns after the first match |

### Procedures

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| `db.index.fulltext.queryNodes` | **DIFFERENT** | identity-validation's index (keyword analyser) is created, but its query `'123\-45\-6789~1'` returns nothing. Hyphenated terms, escapes, fuzzy `~n` and multi-term queries all return nothing; only a bare single word matches. The `fulltext.analyzer` option is accepted and ignored. | Lucene query syntax: returns the exact SSN and its one-edit neighbour |
| `apoc.*` functions | UNSUPPORTED | Exit 6, `UnknownFunction` | Needs the APOC plugin |
| `gds.*` procedures and `gds.util.asNode` | UNSUPPORTED | Exit 6, `ProcedureNotFound` / `UnknownFunction` | Needs the GDS plugin |
| `SHOW PROCEDURES` | SUPPORTED | 29 procedures (`db.*`, `cdc.*`, `dbms.*`). `db.index.fulltext.listAvailableAnalyzers` is listed but `ProcedureNotFound` when called | n/a |

### Ontology namespace

| Case | Status | Observed |
| ---- | ------ | -------- |
| `CYPHERLITE_PREVIEW=ontology`, `CALL db.ontology.set(<package ONTOLOGY.json>)` | **DIFFERENT** | Rejected: `unknown field 'data_source_tables'`. Cypherlite's vendored 1.0.0 schema uses the pre-release names `tables` / `mappings`. With those renamed it is accepted, and `db.ontology.apply()` creates 8 `NODE_KEY`, 21 `NODE_PROPERTY_TYPE` and 8 + 8 `RELATIONSHIP_SOURCE_LABEL` / `TARGET_LABEL` constraints for patient-journey. That is a different set from Import's: Import creates 8 node keys and 12 existence constraints, and no property-type or endpoint-label constraints. |
| `system_ontologies` namespace | SUPPORTED | Listed by `SHOW DATABASES` as read-only. Any statement routed to it fails: "not queryable; use the db.ontology.* procedures on 'neo4j'". It is where the store keeps its one ontology document (ADR-0116, ADR-0229). It holds no graph and does not load data. |

## Workarounds

| Gap | Workaround | Where |
| --- | ---------- | ----- |
| BOM kept in the first header key | The generator detects a BOM and addresses that column by its raw key (`` row.`﻿id` ``). This works today. | `ontology_to_cypher.py` `BOM_STAYS_IN_FIRST_KEY` |
| Empty cells arrive as `''`, where Neo4j's `,,` is null | Every conversion reads `null` and `''` alike as empty, which is also Import's rule (Import nulls `''` before sending rows). No change is needed whichever way Neo4j behaves. | `ontology_to_cypher.py` `conv` |
| `LOAD CSV … CALL IN TRANSACTIONS` rejected | Not needed. The generator emits plain `LOAD CSV … MERGE`, one statement per mapping; the largest package imports in seconds. | — |
| `toString(datetime)` drops zero seconds | When judging, compare datetimes as values. Where a query returns a datetime rendered into a string, normalise `THH:MMZ` to `THH:MM:00Z` before comparing with TESTS.md, and say so in the evidence. This affects patient-journey's pathway query (`toString(enc.date)`). | `run_queries.py` judging |
| `round()` half-way negatives | None in general. Of the packages' 48 `round` calls, two could see a negative value: loans-and-mortgages' appraisal `increasePct` and ev-route-planning's `arrival_soc_percent`. Even then the results differ only when the value lands exactly half-way at the rounding precision. If a mismatch ever turns on that, record ENGINE-GAP, not FAIL. | `run_queries.py` judging |
| Fulltext queries return nothing | Classify any query calling `db.index.fulltext.*` as SKIPPED (manual testing on Aura). Still run the `CREATE FULLTEXT INDEX` statement in SETUP.md: it succeeds, and it checks the statement's syntax. | `run_queries.py` classification |
| APOC and GDS absent | SKIPPED, judged from the heading label, `@prerequisites` and the Cypher. A query that reads what a skipped query writes is SKIPPED too. | `run_queries.py` classification |
| Exit 6 covers runtime type errors | Classify by message: `UnknownFunction` / `ProcedureNotFound` on `apoc.` or `gds.` means SKIPPED; a construct named UNSUPPORTED above means ENGINE-GAP; anything else is a package fault (FAIL) once reduced to a minimal reproduction. | `run_queries.py` |
| Plans do not name index seeks | Do not judge index use from EXPLAIN operator names. | — |
| `LIMIT` does not stop enumeration | A `LIMIT` query over a large match space can take as long as counting every match, and can hit the timeout. If it times out, raise `--timeout`, say so, and judge the result. It is not a package fault unless the query would be slow on Neo4j too. | TESTING.md, "Engine or package?" |
| `db.ontology.*` cannot read a package's ONTOLOGY.json | Not used. Test mode generates `LOAD CSV` instead. | — |

There is no fallback for `IS NODE KEY`, because it is supported. If a future version drops it, the fallback is `IS UNIQUE` plus `IS NOT NULL` on each key property. Import itself does this on Community Edition, though there it uses `IS UNIQUE` only.

## Import fidelity

`ontology_to_cypher.py` mirrors what Aura's Import does with a package, as read from `neo4j/upx`:
- the load runs in `apps/import/src/cypher-runner/`;
- the model is decoded by `@neo4j/ontology-graph-spec` 0.9.1, called from `platform/import-shared`.

| Area | Import's behaviour (mirrored) |
| ---- | ----------------------------- |
| Constraints | Built from the ontology, never from the mapping `key`. Each `key`, `unique` and `must_exist` property flag is its own single-property constraint, so two `key: true` properties give two NODE KEYs, not one composite. A composite comes only from a `constraints` entry listing several properties. Statements: `CREATE CONSTRAINT <props>_<Label>_<key\|uniq\|propertyExistence> IF NOT EXISTS FOR … REQUIRE (…) IS NODE KEY \| IS UNIQUE`, or `REQUIRE n.p IS NOT NULL`. Relationships use `IS RELATIONSHIP KEY`. `PROPERTY_TYPE` becomes `IS UNIQUE`, an Import bug the generator reproduces and flags. For the ten packages: 53 node keys, 71 node and 17 relationship existence constraints. |
| Nodes | `MERGE` on the mapping key, then `SET` every other mapped property. Only the first label is written. A row whose converted key is null is dropped. |
| Relationships | Both endpoints are MATCHed on their key, never created. A missing endpoint drops the row silently. `MERGE (s)-[r:T]->(t)` when the mapping key is empty, so parallel rows collapse into one; `MERGE (s)-[r:T {key…}]->(t)` otherwise. Every mapped property, key included, is then SET. |
| Values | `''` becomes null. STRING is not trimmed. INTEGER, FLOAT and ZONED DATETIME are converted after `trim`. BOOLEAN is `toLower(trim(v)) IN ['1','true','yes']`, so any other non-empty value, including `no`, is `false`. A value that does not convert becomes null, silently. Cypher's `datetime()` would fail the whole statement instead, so the generator passes only ISO-shaped values to it and nulls the rest. `import_check.py` then reports every non-empty cell that did not convert, so nothing is hidden. If the property has an existence constraint, the null fails that entity's load, as it fails Import's one-transaction chunk on Aura. |
| CSV | papaparse: header names trimmed, BOM stripped, quotes `"` with `""` escaping, line endings auto-detected, blank lines skipped. |

Not mirrored; `ontology_to_cypher.py` reports these:

- **Datetimes:** Import converts each value with JavaScript `Date(...).toISOString()`, so a value with no zone is read in the browser's time zone and an offset is converted to `Z`. The generator notes any ZONED DATETIME value that is not already a UTC ISO instant. Every package value is.
- **Deduplication:** Import removes exact duplicate rows within each roughly 1 MB chunk. This does not change the counts.
- **Mappings:** Import loads only the last of several mappings for one entity. The generator refuses such a document; no package has one.

## Parity with Aura

The first parity check is patient-journey, on 30 October 2026. Ian ran the 13 queries manually on Aura after a sample import through the Import flow, using the parameters test mode used, and exported each result as JSON. `scripts/compare_aura.py` compared them with the Cypherlite run. It reduces nodes to their reference-ontology key, paths to node and relationship sequences, and temporal values to ISO strings. It ignores row order unless the query has an `ORDER BY`, and then also allows ties in any order.

| Result | Queries |
| ------ | ------- |
| Same rows | 1, 2, 3, 5, 6, 7 (same order up to ties), 9 |
| Same rows once collected lists are compared as sets. The query `collect()`s with no `ORDER BY` in front, so the order inside the list is the engine's choice: Aura and Cypherlite list Gerardo's four conditions in different orders | 4 |
| Same rows once the known `toString(datetime)` difference is normalised | 8 |
| Same pairs and counts. The representative path is an arbitrary choice the query leaves to the engine (`head(collect(e))`, `elementId` ordering). Every representative Aura chose is valid against the CSVs | 11, 13 |
| Arbitrary 50-row subsets under `LIMIT` with no `ORDER BY`. Aura's rows meet every TESTS.md invariant, as Cypherlite's did | 10, 12 |
| Import: Aura's Import created the same 20 constraints, with the same names (8 node keys, 12 existence), and the same relationship counts per type | — |

- **Query 5 confirms the test-mode FAIL.** Aura returns Cypherlite's 447, 341, 189, 154, 147, 134, 119 and 67, in the same order, not TESTS.md's figures.
- **All 13 queries and both import checks agree.** No row differed for an engine reason beyond the two rendering differences this file already listed. Every normalisation the comparison needed is one Cypher itself leaves undefined: `collect()` order, `head(collect())` choice, `elementId` ordering, and which rows a `LIMIT` with no `ORDER BY` returns.

## Draft asks for the Cypherlite team

1. **Strip a UTF-8 BOM from the LOAD CSV header.** Neo4j and Aura's Import both do. Today the first key is `'﻿id'` and every `row.id` is null, silently.
2. **`toString()` on temporal values should always print seconds** (`2024-01-02T00:00:00Z`), as Aura does (confirmed in the parity run). The envelope's JSON form already prints them; only `toString` drops them.
3. **Reject `datetime('2024-01-02 03:04:05')`**, as Neo4j does. Also, a datetime parsed without a zone carries a region-like `Z` that serialises as `…Z[Z]`.
4. **Accept `LOAD CSV … CALL (row) { … } IN TRANSACTIONS OF n ROWS`.** Neo4j does, and Import's own Cypher exporter emits exactly this.
5. **Fulltext:**
   - honour `fulltext.analyzer` (at least `keyword`);
   - support Lucene query syntax: escapes, fuzzy `~n`, and multi-term OR;
   - make `db.index.fulltext.listAvailableAnalyzers` callable, or drop it from `SHOW PROCEDURES`.

   This is the only gap that turns plain-Cypher-plus-built-in-procedure queries into manual-only ones.
6. **Give runtime errors their own exit code or `kind`.** `/ by zero` exits 6 as `validation_error`, the same as a rejected statement. Test mode wants to tell "the engine cannot run this" apart from "this failed while running".
7. **Name index use in the plan.** A key lookup served by a NODE KEY and an unindexed scan both show `NodeByLabelScan` with start `index-0`, and only timing separates them. A `NodeUniqueIndexSeek`-style operator, or the index name in `StartReason`, would let an agent confirm index use statically.
8. **Align `db.ontology.set` with the published 1.0.0 schema.** Every package's ONTOLOGY.json is rejected: the packages and upx's library use `data_source_tables` / `data_source_mappings`, and Cypherlite's vendored copy uses `tables` / `mappings`.
9. **Make `LIMIT` stop the match early.** Today `MATCH … RETURN … LIMIT 1` enumerates every match first. On patient-journey's sample, one visualisation query takes 29.5 s for 50 rows, where Neo4j streams.
10. **Consider a native import:** `cypherlite import --ontology ONTOLOGY.json --csv-dir …` that implements Import's rules in the table above. This is only worth having if it shares one specification with Import, since otherwise it is a third implementation. `FINDINGS.md` discusses it.
11. **Match Neo4j's `round()` on negative half-way values.** Aura gives `round(-2.5)` = `-2.0`; Cypherlite gives `-3.0`.
12. **Confirm Neo4j parity on the remaining verify rows:**
    - bare-path LOAD CSV;
    - `,,` as null;
    - `shortestPath` from a node to itself.

    These need an Aura run; the team may already know.
13. **Telemetry defaults to on.** For CI and agent use, consider defaulting it off under a detected harness or `CI=true`.
