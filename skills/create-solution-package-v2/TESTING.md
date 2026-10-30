# Test mode

Test mode imports a package's sample data into a throwaway Cypherlite database and checks the data landed as the reference ontology says. It then runs every query and judges each result against TESTS.md.

It runs in two situations:
- on its own, as `/create-solution-package-v2 test [package]`;
- inside create mode, on the draft (SKILL.md steps 2 and 4).

Test mode **reports problems; it does not fix them**:
- It never edits a package, never edits v1 (`skills/solution-package-builder/`), and never rewrites a query to make it pass.
- Proposed fixes go in the report.
- A workaround you try goes in a scratch copy, and never counts as a PASS.

Every Cypherlite behaviour this procedure relies on is recorded in [CYPHERLITE.md](CYPHERLITE.md). Do not assume anything about Cypherlite that file does not record. If you need a behaviour it does not cover, probe it with `scripts/probe_cypherlite.py` first.

## Before you start

- **Version:** check `cypherlite --version --json` against the pin in CYPHERLITE.md.
  - If Cypherlite is missing, install it as CYPHERLITE.md describes.
  - If it is a different version, say so and re-run the probe before trusting any result:
    ```bash
    python3 scripts/probe_cypherlite.py <repo-root>
    ```
- **Telemetry:** the scripts set `CYPHERLITE_TELEMETRY=0` themselves. Telemetry defaults to on, so set it in any shell where you call `cypherlite` by hand.
- **No live databases:** do not connect to Aura or any other Neo4j instance unless the user says so. Test mode needs neither.
- **Where results go:** under `output/cypherlite-tests/<timestamp>/` at the repo root. `output` is git-ignored. Never write them into a package or a skill folder.

## Running it

```bash
S=<skill-path>/scripts
python3 $S/run_queries.py run                     # every package in catalog.json, plus uncatalogued folders with an ONTOLOGY.json
python3 $S/run_queries.py run patient-journey     # one package, by folder name under the repo root
python3 $S/run_queries.py run ../drafts/my-pkg    # a draft package, by path
```

Options:

- `--keep` keeps the Cypherlite store and prints its path. Use it when you need to reproduce something by hand; the user can also ask for it in words.
- `--timeout 60s` sets the per-statement timeout. Raise it if a query is legitimately slow on Cypherlite, and say that you did.
- `--run-dir` and `--root` override where the results go and where packages are found.

The script runs steps 1 to 7 below for each package, in catalogue order, and decides everything mechanical. The rest is yours: step 6's judgement and the triage of anything that failed. When the script finishes, it prints the summary and the lines that need attention.

## The steps, per package

### 1. Static preflight

The script runs `check_annotations.py`. If it reports any `BLOCKER`, the package is **BLOCKED**:
- the blocker lines are quoted in the report;
- nothing else runs.

If `ontology_to_cypher.py` refuses the ONTOLOGY.json, the package is BLOCKED the same way. That happens on a mapping shape, binding or property type outside what Import loads locally, or on an unmapped entity, all of which make Import refuse too.

### 2. Fresh store

A directory store from `mktemp -d`, never `:memory:`. Each one-shot CLI call against `:memory:` starts with an empty graph.

### 3. Import

`import_check.py` generates `import.cypher` with `ontology_to_cypher.py`, saves it in the run folder, and runs it one statement per call with `--load-csv-dir <package>/sample-data`.

The script mirrors what Aura's Import does with the same ONTOLOGY.json. CYPHERLITE.md's "Import fidelity" section has the detail:
- **Constraints:** it creates the ones Import creates, one per `key`, `unique` and `must_exist` flag. A composite constraint comes only from a `constraints` entry.
- **Nodes:** MERGE on the mapping key, then SET every other mapped property.
- **Relationships:** MATCH both endpoints and MERGE the relationship on its mapping key.
- **Values:** converted by Import's rules: `''` becomes null, BOOLEAN is `toLower(trim(v)) IN ['1','true','yes']`, and numbers and datetimes are trimmed first.

The script also applies CYPHERLITE.md's workarounds, such as addressing a BOM-prefixed first column by its raw key.

### 4. Landing checks

`import_check.py` compares the graph with expectations it computes independently, in Python, from the CSVs:

| Check | What must hold |
| ----- | -------------- |
| Counts | Nodes per label and relationships per (from label, type, to label) equal the CSV-derived counts. A relationship row whose endpoint never became a node is dropped silently by `LOAD CSV`, as it is by Import. This check is what catches it, and the detail names an example row. |
| Properties | Every declared property is present wherever its CSV cell is non-empty, and has its declared type. |
| Keys | Mapping-key values are never null and never repeated. |
| Multiplicity | Every relationship end's `count`, `min_count` and `max_count` holds in the graph. |
| Vocabulary | No label or type outside the reference ontology. |
| Constraints | Every constraint the script created appears in `SHOW CONSTRAINTS`. |
| TESTS.md profile | Counts the sample-data profile states equal the CSVs and the graph. |

- **IMPORT-FAIL:** if any check fails, other than the profile, or any import statement fails, the import is IMPORT-FAIL. The queries still run, but every result is flagged untrusted. Report what failed and the likely cause: a dangling reference in the CSVs, a wrong type, a missing column.
- **Profile mismatch:** a mismatch with TESTS.md's profile is a stale-TESTS.md finding, whichever side is wrong. It does not by itself fail the import.

### 5. SETUP.md

If the package has a SETUP.md, the script runs its statements in order, annotation block included, and records each result.
- A statement that needs APOC, GDS or a fulltext procedure is SKIPPED.
- `CREATE FULLTEXT INDEX` itself runs: it succeeds, which checks its syntax.

### 6. Queries

The script parses QUERIES.md with `annotations.py`, which is the one parser for the `@` blocks; `check_annotations.py` parses no Markdown. It processes the queries in file order on the single store, because some later queries read what earlier ones write. For each query it does the following.

1. **Classifies it.** A query is **SKIPPED** if:
   - its Cypher calls `apoc.*`, `gds.*` or `db.index.fulltext.*`;
   - its heading or `@prerequisites` says it needs APOC, GDS or a fulltext index; or
   - it reads a label, type or property that only a skipped query writes.

   Fulltext is skipped because Cypherlite's fulltext index ignores the analyser and Lucene query syntax (CYPHERLITE.md).
2. **Static check.** It runs `EXPLAIN` in envelope mode and records the notifications.
   - An unknown label, relationship type or property key is a **FAIL for drift**, unless the name is either:
     - declared in ONTOLOGY.json and merely absent from the sample at that point; or
     - written by a query or SETUP.md statement and documented in SKILL.md.
   - An unbounded variable-length pattern is recorded as a finding. It is not a status.
3. **Parameters.** In this order, the script takes values from:
   1. the TESTS.md section's Parameters field. If the field names a parameter without giving its value ("`$constraints` as listed above"), it looks in the rest of that section;
   2. `@sample`;
   3. a starting value stated in `@params` ("Start at 4").

   If a parameter has no value from any of these, the query is **NEEDS-PARAMS**. A later query that reads a label or relationship type only a NEEDS-PARAMS query writes is NEEDS-PARAMS too, with the reason. It is not run, so it does not show up as a misleading empty-result FAIL. When TESTS.md gives several scenarios, the first scenario's values are used and the report says so.
4. **Run.** With `--mode envelope --max-rows 0 --timeout 60s`, annotation block included. It records the columns, rows, time taken and exit code. The full rows go to `rows/<NN>.json`.
5. **Mechanical checks.** In order:
   - the exit code is 0;
   - the result is non-empty, unless TESTS.md's Invariant or Expected field expects an empty one, or the statement has no `RETURN`;
   - the row count equals `@sample`'s, where `@sample` says "returns N rows" or "returns N paths".

   A query that passes all three is left as **JUDGE**: the script has nothing more to say and the judgement is yours. A query that fails one is **FAIL**, with the reason; triage it as described under "Engine or package?".

### Judging (the agent's part of step 6)

For every query left as JUDGE, read its section in `report.md` and, where the head of the rows is not enough, `rows/<NN>.json`. Judge in this order.

1. **Invariant first.** It is the contract. Check every clause of it against the rows: membership, exclusions, ordering, bounds. Example: "never the anchor", "ordered by PatientCount descending", "no more than `$limit`".
2. **Expected second, where stated.** Compare counts and named values. Ignore row order unless the query has an `ORDER BY`. Where TESTS.md says something is not fixed ("which pairs are returned is not fixed", a tie at fifth place), do not hold the result to it.
3. **Allow for the engine differences CYPHERLITE.md lists.** Most often:
   - `toString()` of a datetime on a whole minute renders as `…T00:00Z` where Neo4j gives `…T00:00:00Z`. Normalise before comparing, and say so in the evidence.
   - `round()` differs only on negative half-way values.
4. **Record the verdict**, quoting evidence from the rows: the counts you checked, the named entities you found or did not find.

   ```bash
   python3 $S/run_queries.py judge <run-dir>/<package> <query number or heading> \
       --status PASS --evidence "8 rows; Diabetes 692, Hypertension 541, … all match; anchor absent; ordered desc"
   ```

   The verdicts:
   - **PASS:** the invariant holds and every stated expectation matches.
   - **FAIL:** the rows contradict the invariant or a stated expectation. Add `--fix` with the proposed change to the package, and say which side you think is wrong: the query, the data, or TESTS.md.
   - **UNSURE:** TESTS.md does not let you decide with confidence. Examples: the invariant cannot be checked from the result, or the expectation is ambiguous. Say what would settle it, and propose machine-checkable wording for TESTS.md in the finding.

`judge` re-renders `report.md` and `summary.md` each time. It refuses to change a status the script decided mechanically (FAIL, ENGINE-GAP, SKIPPED, NEEDS-PARAMS) unless you pass `--override`. The override and the original reason both appear in the report.

### Engine or package?

Before you call any failure a package fault:

- **Rejected on a known gap:** if the statement was rejected (exit 6) on a construct CYPHERLITE.md lists as UNSUPPORTED, or on a difference it lists, the status is **ENGINE-GAP**, not FAIL. Record it with `judge … --status ENGINE-GAP --override` and name the CYPHERLITE.md entry.
- **Cause unclear:** reduce the query to a minimal reproduction before blaming either side.
  - Re-run with `--keep` and work against the kept store with `cypherlite --database <store> --mode envelope --max-rows 0 -c '…'`.
  - Cut the query down until one construct explains the failure.
  - A construct the probe never covered goes into CYPHERLITE.md as a new probe case. Never let it become an assumption.
- **Workaround rewrite:** you may try a rewrite in a scratch copy of the query, never in the package, and report with `--workaround` whether it passed. It never counts as PASS.
- **Exit codes are not enough on their own:**
  - exit 6 also covers runtime type errors such as `/ by zero`, so read the message;
  - exit 7 is a timeout. A slow query on Cypherlite is not a package fault unless it would be slow on Neo4j too. Say which you believe and why.

### 7. Teardown

The script deletes the store unless `--keep` was given. It always keeps `import.cypher`, `import.json`, `results.json`, `report.md` and the `rows/` files.

## Statuses

| Status | Meaning |
| ------ | ------- |
| PASS | Ran, and the result satisfies the TESTS.md invariant and expectations |
| FAIL | Package fault: rejected statement, empty or wrong result, or drift caught by `EXPLAIN` |
| ENGINE-GAP | Cypherlite does not support a construct that is valid on Neo4j |
| SKIPPED | Needs APOC, GDS or a fulltext procedure; requires manual testing on Aura |
| NEEDS-PARAMS | No parameter values found in TESTS.md, `@sample` or `@params` |
| UNSURE | Ran, but the result cannot be judged against TESTS.md with confidence |
| BLOCKED / IMPORT-FAIL | Preflight or import failed; see the package report |

JUDGE is not a final status. It means the mechanical checks passed and the judgement has not been recorded yet. A run is finished only when no JUDGE remains.

## Reports

- **Per package:** `output/cypherlite-tests/<timestamp>/<package>/` holds:
  - `report.md`;
  - `results.json`, the full record, including each judgement;
  - `import.cypher` and `import.json`;
  - `rows/`.
- **Per run:** `output/cypherlite-tests/<timestamp>/summary.md` has one row per package, with:
  - the import status;
  - the count of each query status;
  - the time taken;
  - one line for every FAIL, ENGINE-GAP, UNSURE, IMPORT-FAIL and BLOCKED.

  To rebuild it, run `python3 $S/run_queries.py report <run-dir>`.
- **In chat:** show the summary table, then one line for every FAIL, ENGINE-GAP, UNSURE and IMPORT-FAIL. Then list the SKIPPED queries that need manual testing on Aura. Say that a pass on Cypherlite is evidence, not proof.

## Parity with Aura

A Cypherlite pass becomes proof only once parity with Aura has been checked. Do not connect to Aura yourself unless the user authorises it. The usual route is a manual run.

1. **Kit:** `python3 $S/compare_aura.py <run-dir>/<package> --kit` writes `AURA_PARITY_KIT.md`. It holds every query test mode ran, in run order, with its `:param` lines, plus two import checks (`SHOW CONSTRAINTS` and relationship counts by type).
2. **Manual run:** the user runs them on a disposable Aura database after a sample import through the Import flow. Each result is exported as JSON to `<run-dir>/<package>/aura/NN.json`.
3. **Compare:** `python3 $S/compare_aura.py <run-dir>/<package>` writes `parity.md` and `parity.json`.
   - **Normalisation:** nodes become their reference-ontology key, paths become node and relationship sequences, and temporal values become ISO strings.
   - **Row order:** ignored unless the query has an `ORDER BY`, and then ties may come in any order.
   - **Known differences:** a mismatch is retried at three further levels, each labelled, so nothing is waved through silently:
     - after CYPHERLITE.md's known rendering difference is normalised;
     - with collected lists compared as sets, where the query `collect()`s with no `ORDER BY` in front;
     - with each path reduced to its end nodes, where the query leaves the path's interior to the engine (`head(collect(...))`, `elementId` ordering).
   - **Subsets:** a query with `LIMIT` and no `ORDER BY` returns an arbitrary subset on each engine. Judge Aura's rows against the TESTS.md invariant instead.
4. **Check what the labels leave open:** verify Aura's own arbitrary choices against the CSVs, such as each representative path being valid. Write those checks in `<run-dir>/<package>/parity-notes.md`; the script appends it to `parity.md` on every run. Then record what parity confirmed or overturned in CYPHERLITE.md, including any "verify" row it settles.

If an export's columns do not match the query's, the file probably holds another query's result. The script reports it as NOT-COMPARABLE rather than guessing.

## In create mode

Run test mode on the draft folder by path as soon as QUERIES.md and TESTS.md exist, and after every change to the data, the queries or TESTS.md. SKILL.md step 4 has the rules. In short:

- **FAIL, IMPORT-FAIL and BLOCKED are blockers.** Each sends the build back to fix the data or the queries.
- **NEEDS-PARAMS** means TESTS.md's Parameters field needs a value.
- **Never write a result into TESTS.md** that was neither observed in a run nor derived from the CSVs.
- **SKIPPED queries** still need manual testing on Aura, and the handoff says so.

The draft is a normal package folder, so the same scripts apply unchanged. Nothing test mode writes goes into the draft.
