# Relate for test mode

Test mode runs a package's import and queries on Relate, an embedded openCypher engine shipped as a single binary. This file records:

- the version the skill is pinned to;
- what that version does and does not do, as measured by `scripts/probe_relate.py`;
- the workaround for each gap.

Nothing in test mode relies on a Relate behaviour this file does not record. Re-run the probe whenever the pin changes, and update this file from its output.

A pass on Relate is evidence, not proof. Relate is not Aura's Cypher engine, and the generated `LOAD CSV` script is a second implementation of Aura's Import. Rows marked **verify** state Neo4j's behaviour from its documentation or implementation, not from a live run. They belong on the Aura parity list. Rows marked **confirmed on Aura** were checked in the patient-journey parity run of 30 October 2026 (see "Parity with Aura" below).

## Pinned version

Relate is Cypherlite renamed. The project moved from `neo4j-labs/cypherlite` to [`relatedb/relate`](https://github.com/relatedb/relate), and its version numbering restarted at 0.1.0 (9 November 2026). The skill is pinned to:

```json
{"arch":"aarch64","license":"Apache 2.0 (binary)","name":"relate","os":"macos","version":"0.1.3"}
```

The probe was re-run on this version on 11 November 2026, and every row below is from that run. The previous pin was Cypherlite 0.13.0 (`{"arch":"aarch64","name":"cypherlite","os":"macos","version":"0.13.0"}`). "Changes since Cypherlite 0.13.0" below lists what moved.

- **Source:** `relatedb/relate` release `v0.1.3` (11 November 2026). Installed by the repo's `distribution/install.sh` (also served at `https://relatedb.ai/install.sh`) to `~/.local/bin/relate`.
- **Verification:** the install script authenticates `SHA256SUMS` against its SSHSIG signature (`SHA256SUMS.sig`) with `ssh-keygen` and the `relate-release` ED25519 key pinned in the script. It then checks the binary's SHA-256 against `SHA256SUMS`, and fails closed if either check fails.
- **Check first:** `python3 scripts/check_relate.py` reports whether Relate is installed, at which version, and whether it runs. When it is missing, it checks what the installer needs. It installs nothing. SKILL.md's "Before you start: Relate" says what the agent does with each result.
- **Prerequisites:** macOS or Linux; the GitHub CLI logged in (`gh auth login`) to an account with access to `relatedb/relate`, which is internal to the Neo4j GitHub organisation; `ssh-keygen`; Python 3.9 or later for the scripts.
- **Install:**

  ```bash
  gh api repos/relatedb/relate/contents/distribution/install.sh -H "Accept: application/vnd.github.raw" | GITHUB_TOKEN=$(gh auth token) sh
  ```

  This fetches the repository's current installer and runs it with your GitHub token. The token is needed because the repository is internal; without it the installer stops with a 404. The copy served at `https://relatedb.ai/install.sh` lagged the repository's on 11 November 2026, so prefer this one. The command was checked from a clean `HOME` on 12 November 2026.
- **Version:** the installer has no version option; it always installs the latest release. On 12 November 2026 that was already `v1.0.1`, ahead of the pin. A newer version is usable, but re-run the probe and compare it with this file before trusting test-mode results; `check_relate.py` reports this as `INSTALLED, DIFFERENT VERSION`. `relate upgrade --check` reports the latest release without changing anything.
- **Where the scripts look:** `$RELATE_BIN`, then `relate` on `PATH`, then `~/.local/bin/relate`. So a binary the installer put outside `PATH` is still found. On Windows, the installer does not run: download `relate-windows-amd64.exe` from the release page and set `RELATE_BIN` to its path.
- A leftover `~/.local/bin/cypherlite` is not used by any script and can be removed.
- **Telemetry** is on by default. Every script sets `RELATE_TELEMETRY=0` (`scripts/relate_cli.py`). `DO_NOT_TRACK=1` and `relate telemetry off` also disable it. The old `CYPHERLITE_*` variables are ignored, and Relate warns when one is set.

### Other surfaces (not used yet)

| Surface | State at v0.1.3 |
| ------- | --------------- |
| Python | `relate_db-0.1.3` abi3 wheels for macOS, Linux and Windows are release assets (`pip install <wheel>`). It is `relate-db` on PyPI once published, and is imported as `import relate`. The source builds with maturin from `surfaces/relate-python`. |
| Rust | Cargo workspace (`relate/*`, `surfaces/*`). The crate is `relate`; until crates.io publication it is used as a git dependency (`cargo add --git https://github.com/relatedb/relate relate`). |
| Node | `@relate/relate` in `clients/javascript`, a C ABI client over the `relate-ffi` tarballs attached to each release (Node 18+). The browser WASM build is `@relate/relate-wasm` (`surfaces/relate-wasm`). |

The skill uses the CLI only. The Python wheel is the natural next step if one-process-per-statement start-up ever matters. At present it does not: a full patient-journey import is about 9 s.

## How test mode calls the CLI

These rules are what `scripts/relate_cli.py` does. Each one rests on a probe case.

- **Store:** a directory from `mktemp -d`, never `:memory:`. Each one-shot call on `:memory:` starts empty (`cli.store_types`). A directory store persists between calls.
- **Output:** `--mode envelope`, one JSON object per statement, with these keys:
  - `columns`, `columnTypes`, `rows` and `truncated`;
  - `notifications`, always present.

  Relate also adds `planCache` and `timings` (per-phase milliseconds), which test mode does not read. Keys inside a row are sorted, so read `columns` for the order. A failure prints `{"error": {...}}` on stdout. Its `code`, `kind`, `message` and `exit_code` are what test mode records (`cli.envelope`).
- **Row cap:** always pass `--max-rows 0`. Under an agent harness the CLI otherwise stops at 100 rows, sets `truncated`, and warns on stderr (`cli.row_cap`).
- **Parameters:** pass each value as JSON with `--param name=<json>`. A bare `123` binds an INTEGER, so a string must be quoted. Lists and maps work (`cli.params`).
- **Comments and semicolons:** a `;` inside a `/* … */` annotation block, a `//` comment or a string literal does not split the statement. A trailing `;` is fine. So a QUERIES.md block can be run whole, annotation included (`cli.*_semicolon`).
- **Timeouts:** `--timeout 60s` per statement. Exit code 7 means a timeout (`cli.exit_timeout`). A statement that would build one huge value, such as `range(1, 1000000000)`, is refused first: exit 1, kind `capacity`, "a safety limit protecting against memory exhaustion".
- **Exit codes:**
  - **0** success;
  - **6** statement rejected: syntax, semantic and type errors, unknown functions and procedures, a missing parameter, constraint violations;
  - **7** timeout;
  - **1** other runtime failure, including the capacity limit above;
  - **5** a write-write conflict or a store locked by another opener (from Relate's CLI spec; test mode never opens a store twice at once).

  A runtime arithmetic error such as `/ by zero` also exits **6**, with kind `type` (`cli.exit_runtime`). So exit 6 alone does not mean "the engine cannot run this". Test mode uses the error message to tell an engine gap from a package fault.
- **EXPLAIN** plans without parameter values (`cli.explain_without_params`). Its envelope carries Neo4j's notification codes:

  | Code | GQLSTATUS |
  | ---- | --------- |
  | `Neo.ClientNotification.Statement.UnknownLabelWarning` | 01N50 |
  | `Neo.ClientNotification.Statement.UnknownRelationshipTypeWarning` | 01N51 |
  | `Neo.ClientNotification.Statement.UnknownPropertyKeyWarning` | 01N52 |
  | `Neo.ClientNotification.Statement.UnboundedVariableLengthPattern` | 03N91 |

  There is also a Relate-only `Relate.Notification.Statement.MissingIndex` (03C91), which test mode ignores.
- **Scripts:** a script on stdin (`relate query`) stops at the first failed statement and reports how many committed (`cli.script_stops`). Test mode therefore runs `import.cypher` one statement per call, so that one failure does not hide the rest. Aura's Import likewise carries on with other entities when one fails.
- **Other CLI checks:** `relate clone SRC DEST` copies a store without touching the source (`cli.clone`). `--read-only` rejects writes (`cli.read_only`).

## Capability matrix

The probe ran 252 cases:

| Status | Cases |
| ------ | ----- |
| SUPPORTED | 229 |
| DIFFERENT | 6 |
| UNSUPPORTED | 17 |

Phase 3 added one case, `cypher.limit_short_circuit`, after patient-journey's test run turned it up. Phase 4 added `cypher.allreduce_pruning`, after ev-route-planning's three route queries timed out. The Aura parity run then settled five verify rows; one of them, `toInteger(' 5')`, moved from DIFFERENT to SUPPORTED.

Its full output, with every observation, is under `output/relate-tests/probe-<timestamp>/`. That folder is not committed; this table is the record.

### Changes since Cypherlite 0.13.0

On Cypherlite 0.13.0 the probe gave 221 SUPPORTED, 15 DIFFERENT and 16 UNSUPPORTED. On Relate 0.1.3:

| Case | Cypherlite 0.13.0 | Relate 0.1.3 |
| ---- | ----------------- | ------------ |
| `cypher.allreduce_pruning` | DIFFERENT: bound 6 took 0.44 s against 0.04 s at bound 4 | SUPPORTED: 0.06 s at both bounds; but see ev-route-planning under Cypher |
| `cypher.limit_short_circuit` | DIFFERENT: `LIMIT 1` 2.9 s, `count(*)` 2.4 s | SUPPORTED: `LIMIT 1` 0.06 s, `count(*)` 0.68 s |
| `toString(datetime)` at a whole minute (`cypher.datetime_param`, `cypher.duration_months`, `import.datetime.date_only`, `.midnight`, `.package1`) | DIFFERENT: `…T00:00Z` | SUPPORTED: `…T00:00:00Z`, as Aura prints it |
| `cypher.round_half` | DIFFERENT: `round(-2.5)` = `-3.0` | SUPPORTED: `-2.0` |
| `proc.fulltext_query` | DIFFERENT: the package's query returned nothing | Still DIFFERENT: Lucene syntax now parses, but the analyser is still ignored (see Procedures) |
| `ontology.set_apply` | DIFFERENT: rejected on field names | UNSUPPORTED: rejects the 1.0.0 spec URI outright |
| `import.datetime.space` | DIFFERENT, serialised as `…Z[Z]` | Still DIFFERENT (accepted), now serialised as `…Z` |
| `schema.node_key.seek` | SUPPORTED; plan showed `NodeByLabelScan` | SUPPORTED; plan names `NodeIndexSeek RANGE INDEX` |

Two cases changed only because the probe's own checks were out of date, and both checks were fixed. `cli.envelope` now allows the extra `planCache` and `timings` keys. `cli.exit_timeout` now uses a statement that runs past the timeout without hitting the capacity limit. Error messages were reworded (`UnknownFunction: unknown function foo.bar()`, not `` `foo.bar` ``), but every exit code and `kind` is unchanged.

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
| `MATCH REPEATABLE ELEMENTS` + `allReduce` (Cypher 25) | 3 | SUPPORTED for results; two of ev-route-planning's three route queries still do not finish (see Cypher) |
| `NEXT` chaining, including inside `CALL (x) {}` and feeding a `MERGE` | 2 | SUPPORTED |
| `CYPHER 25` prefix | 5 | SUPPORTED |
| `UNION`, `OPTIONAL MATCH`, pattern predicates, `MERGE`, `SET n:Label`, `DELETE` | various | SUPPORTED |
| `point()`, `point.distance` | 18 / 13 | SUPPORTED |
| `date()`, `duration()`, `duration.*` | 8 / 2 / 0 | SUPPORTED |
| `datetime()` | 3 | SUPPORTED |
| `elementId()`, `reduce()`, list and pattern comprehensions, dynamic property access, chained comparison, regex `=~` | various | SUPPORTED |
| `round()` | 48 | SUPPORTED, including negative half-way values |
| `toString()` on numbers | 10 | SUPPORTED |
| `toInteger` / `toFloat` | 4 / 10 | SUPPORTED (`' 5'` confirmed on Aura) |
| `db.index.fulltext.queryNodes` | 2 | DIFFERENT (analyser ignored) |
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
| `datetime()` on the only package format, `YYYY-MM-DDTHH:MM:SSZ` | SUPPORTED | Same instant; `toString` gives `2024-02-09T00:00:00Z` | Same (confirmed on Aura) |
| `datetime()` with millis, with an offset, with no zone | SUPPORTED (verify) | ISO form kept; no zone means UTC | Same on Aura (default zone UTC) |
| `datetime('2024-01-02')` | SUPPORTED (verify) | Midnight UTC, `2024-01-02T00:00:00Z` | Midnight UTC |
| `datetime('2024-01-02 03:04:05')` (space separator) | DIFFERENT (verify) | Accepted; serialises as `2024-01-02T03:04:05Z` | Rejected (the ISO parser needs `T`) |
| Throughput: full patient-journey import | SUPPORTED | 36 statements, 27,401 CSV lines, 9 s; 13,023 nodes and 31,394 relationships | Aura Import takes tens of seconds |

### Schema

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| Single-property `NODE KEY`, in Import's exact statement form | SUPPORTED | Duplicate and missing key both rejected | Same (Enterprise/Aura) |
| Composite `NODE KEY` (tuple syntax) | SUPPORTED | Pair uniqueness and existence enforced | Same |
| Node key used for lookups | SUPPORTED | 20,000 nodes: 0.06 ms with the key, 4.7 ms without. The plan names `NodeIndexSeek RANGE INDEX n:K(id)` | Same; Neo4j's operator is `NodeUniqueIndexSeek` |
| `IS UNIQUE` (node and relationship) | SUPPORTED | Duplicates rejected; missing allowed | Same |
| `IS NOT NULL` (node and relationship), Import's `must_exist` | SUPPORTED | Missing property rejected | Same (Enterprise/Aura) |
| `IS RELATIONSHIP KEY` | SUPPORTED | Enforced | Same |
| `IS :: STRING` property type | SUPPORTED | Enforced | Same (Import never emits it) |
| `SHOW CONSTRAINTS` | SUPPORTED | Neo4j's columns plus `enforcedLabel`; type `NODE_KEY`; constraint name kept | Same as 2025.x |
| `SHOW INDEXES` | SUPPORTED | Neo4j's twelve columns. A new store lists Neo4j's two default `LOOKUP` indexes (node labels and relationship types) before any created ones. Every index reports `id: 0` | Same, with distinct ids |
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
| `allReduce` prunes `REPEATABLE ELEMENTS` expansion | SUPPORTED on the probe; **DIFFERENT (performance, verify)** on ev-route-planning | On the probe's 8-node complete graph, with `allReduce` failing after the first hop, bounds 4 and 6 both take 0.06 s (Cypherlite: 0.04 s and 0.44 s). But ev-route-planning's three Cypher 25 route queries (`{1,14}`) are still slow. "Feasible routes" (`LIMIT $limit`) now returns its 50 rows in about 60 s, because `LIMIT` stops early. "Lane feasibility" (aggregates over every route) and "Best route, scored" (`ORDER BY … LIMIT 1`, which needs every route) still run past 10 minutes. Whether Neo4j prunes these enough to finish is unconfirmed. | `allReduce` is evaluated during expansion, so a prefix that fails it is never extended |
| `LIMIT` stops the pattern match early | SUPPORTED | Over 1,124,250 matches, `LIMIT 1` takes 0.06 s against 0.68 s for `count(*)` (Cypherlite: 2.9 s against 2.4 s). A `LIMIT` after `ORDER BY` still needs every match. | Streams: `LIMIT 1` returns after the first match |

### Procedures

| Case | Status | Observed | Neo4j |
| ---- | ------ | -------- | ----- |
| `db.index.fulltext.queryNodes` | **DIFFERENT** | identity-validation's index is created with the `keyword` analyser, and `SHOW FULLTEXT INDEXES` reports it, but values are still split on `-`. Its query `'123\-45\-6789~1'` returns the exact SSN and its one-edit neighbour, and also `123-45-0000`, four edits away but sharing the `123` and `45` groups. A bare `123` matches every SSN starting `123-`. On identity-validation's sample, the near-duplicate SSN queries return 7 rows instead of 3: every masked SSN shares the `XXX` group. Escapes, `~1` and multi-term queries now parse; `helo~1` still misses `hello`. | Keyword analyser: each SSN is one token, so only the exact SSN and its one-edit neighbour match, and `123` matches nothing |
| `apoc.*` functions | UNSUPPORTED | Exit 6, `UnknownFunction` | Needs the APOC plugin |
| `gds.*` procedures and `gds.util.asNode` | UNSUPPORTED | Exit 6, `ProcedureNotFound` / `UnknownFunction` | Needs the GDS plugin |
| `SHOW PROCEDURES` | SUPPORTED | 31 procedures (`db.*`, `dbms.*`, `tx.*`; the `cdc.*` ones are gone, and `dbms.listCapabilities` is new). `db.index.fulltext.listAvailableAnalyzers` is still listed but `ProcedureNotFound` when called | n/a |

### Ontology namespace

| Case | Status | Observed |
| ---- | ------ | -------- |
| `RELATE_PREVIEW=ontology`, `CALL db.ontology.set(<package ONTOLOGY.json>)` | **UNSUPPORTED** | Rejected on the spec URI itself, with or without the field renames: "Unsupported ontology spec version: '…/ontology-graph-spec/1.0.0/schema.json'. This version of Relate supports up to Ontology Graph Spec 1.1.0". The packages declare 1.0.0, the bundled pin (ONTOLOGY_SPEC_FORMAT.md). On Cypherlite 0.13.0 the document was rejected on `data_source_tables` instead, and accepted once renamed to `tables` / `mappings`; `db.ontology.apply()` then created a different constraint set from Import's. |
| `system_ontologies` namespace | SUPPORTED | Listed by `SHOW DATABASES` as read-only. Any statement routed to it fails: "not queryable; use the db.ontology.* procedures on 'neo4j'". It is where the store keeps its one ontology document (ADR-0116, ADR-0229). It holds no graph and does not load data. |

## Workarounds

| Gap | Workaround | Where |
| --- | ---------- | ----- |
| BOM kept in the first header key | The generator detects a BOM and addresses that column by its raw key (`` row.`﻿id` ``). This works today. | `ontology_to_cypher.py` `BOM_STAYS_IN_FIRST_KEY` |
| Empty cells arrive as `''`, where Neo4j's `,,` is null | Every conversion reads `null` and `''` alike as empty, which is also Import's rule (Import nulls `''` before sending rows). No change is needed whichever way Neo4j behaves. | `ontology_to_cypher.py` `conv` |
| `LOAD CSV … CALL IN TRANSACTIONS` rejected | Not needed. The generator emits plain `LOAD CSV … MERGE`, one statement per mapping; the largest package imports in seconds. | — |
| ev-route-planning's full-enumeration route queries do not finish | "Lane feasibility" and "Best route, scored" time out even at `--timeout 600s`. Record them as ENGINE-GAP, with the `allReduce` row above as the evidence; they need manual testing on Aura. "Feasible routes" finishes close to the default 60 s, so run ev-route-planning with `--timeout 120s` and say so. | TESTING.md, "Engine or package?" |
| Fulltext ignores the analyser | Classify any query calling `db.index.fulltext.*` as SKIPPED (manual testing on Aura). Still run the `CREATE FULLTEXT INDEX` statement in SETUP.md: it succeeds, and it checks the statement's syntax. | `run_queries.py` classification |
| APOC and GDS absent | SKIPPED, judged from the heading label, `@prerequisites` and the Cypher. A query that reads what a skipped query writes is SKIPPED too. | `run_queries.py` classification |
| Exit 6 covers runtime type errors | Classify by message: `UnknownFunction` / `ProcedureNotFound` on `apoc.` or `gds.` means SKIPPED; a construct named UNSUPPORTED above means ENGINE-GAP; anything else is a package fault (FAIL) once reduced to a minimal reproduction. | `run_queries.py` |
| `db.ontology.set` rejects the 1.0.0 spec | Not used. Test mode generates `LOAD CSV` instead. | — |

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

The first parity check is patient-journey, on 30 October 2026, against Cypherlite 0.13.0 (Relate before the rename). Ian ran the 13 queries manually on Aura after a sample import through the Import flow, using the parameters test mode used, and exported each result as JSON. `scripts/compare_aura.py` compared them with the Cypherlite run. It reduces nodes to their reference-ontology key, paths to node and relationship sequences, and temporal values to ISO strings. It ignores row order unless the query has an `ORDER BY`, and then also allows ties in any order.

| Result | Queries |
| ------ | ------- |
| Same rows | 1, 2, 3, 5, 6, 7 (same order up to ties), 9 |
| Same rows once collected lists are compared as sets. The query `collect()`s with no `ORDER BY` in front, so the order inside the list is the engine's choice: Aura and Cypherlite list Gerardo's four conditions in different orders | 4 |
| Same rows once the known `toString(datetime)` difference is normalised | 8 |
| Same pairs and counts. The representative path is an arbitrary choice the query leaves to the engine (`head(collect(e))`, `elementId` ordering). Every representative Aura chose is valid against the CSVs | 11, 13 |
| Arbitrary 50-row subsets under `LIMIT` with no `ORDER BY`. Aura's rows meet every TESTS.md invariant, as Cypherlite's did | 10, 12 |
| Import: Aura's Import created the same 20 constraints, with the same names (8 node keys, 12 existence), and the same relationship counts per type | — |

- **Query 5 confirms the test-mode FAIL.** Aura returns Cypherlite's 447, 341, 189, 154, 147, 134, 119 and 67, in the same order, not TESTS.md's figures.
- **All 13 queries and both import checks agree.** No row differed for an engine reason beyond the two rendering differences this file then listed (`toString(datetime)` seconds and `round()` half-way negatives), both fixed in Relate 0.1.3. Every normalisation the comparison needed is one Cypher itself leaves undefined: `collect()` order, `head(collect())` choice, `elementId` ordering, and which rows a `LIMIT` with no `ORDER BY` returns.

## Draft asks for the Relate team

Re-checked against Relate 0.1.3. The numbering is new; resolved asks are listed after the open ones.

1. **Strip a UTF-8 BOM from the LOAD CSV header.** Neo4j and Aura's Import both do. Today the first key is `'﻿id'` and every `row.id` is null, silently.
2. **Reject `datetime('2024-01-02 03:04:05')`**, as Neo4j does. (The `…Z[Z]` serialisation Cypherlite gave it is fixed.)
3. **Accept `LOAD CSV … CALL (row) { … } IN TRANSACTIONS OF n ROWS`.** Neo4j does, and Import's own Cypher exporter emits exactly this.
4. **Fulltext:**
   - honour `fulltext.analyzer`, at least `keyword`. Today it is stored and reported but values are still split on `-`, so identity-validation's near-duplicate SSN queries match on shared digit groups. This is the only gap that turns plain-Cypher-plus-built-in-procedure queries into manual-only ones;
   - match fuzzy terms one insertion away (`helo~1` should find `hello`);
   - make `db.index.fulltext.listAvailableAnalyzers` callable, or drop it from `SHOW PROCEDURES`.
5. **Give runtime errors their own exit code or `kind`.** `/ by zero` still exits 6 as `validation_error`, the same as a rejected statement. Test mode wants to tell "the engine cannot run this" apart from "this failed while running".
6. **Accept the 1.0.0 ontology graph spec in `db.ontology.set`.** It now rejects the spec URI every package declares, saying it "supports up to 1.1.0". A store that supports 1.1.0 should still read 1.0.0 documents.
7. **Consider a native import:** `relate import --ontology ONTOLOGY.json --csv-dir …` that implements Import's rules in the table above. This is only worth having if it shares one specification with Import, since otherwise it is a third implementation. `FINDINGS.md` discusses it.
8. **Confirm Neo4j parity on the remaining verify rows:**
   - bare-path LOAD CSV;
   - `,,` as null;
   - `shortestPath` from a node to itself.

   These need an Aura run; the team may already know.
9. **Report write counters.** The envelope of a write statement carries no counts (nodes or relationships created, deleted, set), so a test has to diff the graph to see what a write did. Neo4j returns them with every result.
10. **Give each index its own `id` in `SHOW INDEXES`.** Every index, the two default `LOOKUP` indexes included, reports `id: 0`.
11. **Telemetry defaults to on.** For CI and agent use, consider defaulting it off under a detected harness or `CI=true`.
12. **Make `allReduce`-bounded route search finish when every route is needed.** ev-route-planning's "Lane feasibility" and "Best route, scored" (`MATCH REPEATABLE ELEMENTS … {1,14}` with `allReduce` on battery and time, then an aggregate or `ORDER BY … LIMIT 1`) run past 10 minutes on the package's sample. The probe's small case prunes, so the gap is in how far pruning reaches on a real road network.

Resolved in Relate 0.1.3 (asked of Cypherlite 0.13.0):

- `toString()` on temporal values prints seconds, as Aura does.
- Fulltext parses Lucene syntax: escapes, fuzzy `~1` and multi-term queries (the analyser is still ignored; see ask 4).
- The plan names index use (`NodeIndexSeek RANGE INDEX`).
- `allReduce` prunes `REPEATABLE ELEMENTS` expansion on small graphs (ev-route-planning's full-enumeration route queries still do not finish; see Cypher).
- `LIMIT` stops the match early.
- `round()` matches Neo4j on negative half-way values.
