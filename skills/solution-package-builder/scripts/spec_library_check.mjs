// Spec-library check for ONTOLOGY.json files (VALIDATION.md section 3).
//
// Usage, from a scratch directory (never inside a package or the repo):
//   npm init -y && npm install @neo4j/ontology-graph-spec@<release>   # the release pinned in ONTOLOGY_SPEC_FORMAT.md
//   cp <skill-path>/scripts/spec_library_check.mjs . && node spec_library_check.mjs <path/to/ONTOLOGY.json> [...]
//
// Decodes each file with the spec library and runs every built-in validation set (Validations.all), so the
// semantic rules the JSON Schema cannot express are checked by the same code the format is defined in.
// One rule is filtered: missing_property_name (in the consistentSchema set) mirrors an Import-UI requirement
// that every property carry a `name`, and packages deliberately leave property names unset because each
// property's key is its database name (ONTOLOGY_SPEC_FORMAT.md). Every other issue is reported as a BLOCKER.
// The library does not check constraint-name uniqueness across entries that share a type; check_annotations.py
// and the runtime gate do. Prints "SPEC LIBRARY OK" per clean file; exits 1 on any blocker.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const FILTERED = new Set(['missing_property_name']);

const require = createRequire(pathToFileURL(`${process.cwd()}/`));
const entry = require.resolve('@neo4j/ontology-graph-spec');
const { GraphSpec, GraphModel, Validations } = await import(pathToFileURL(entry).href);
const version = JSON.parse(readFileSync(require.resolve('@neo4j/ontology-graph-spec/package.json'), 'utf8')).version;
console.log(`@neo4j/ontology-graph-spec ${version}`);

const toArray = (list) => (list.asJsReadonlyArrayView ? [...list.asJsReadonlyArrayView()] : [...list.toArray()]);

let failed = false;
for (const path of process.argv.slice(2)) {
  let model;
  try {
    model = GraphSpec.Json.decodeFromString(readFileSync(path, 'utf8'));
  } catch (error) {
    console.log(`${path} BLOCKER decode failed: ${error?.message ?? error}`);
    failed = true;
    continue;
  }
  const issues = toArray(GraphModel.validate(model, Validations.all)).filter((issue) => !FILTERED.has(issue.code));
  if (issues.length === 0) {
    console.log(`${path} SPEC LIBRARY OK`);
    continue;
  }
  failed = true;
  for (const issue of issues) console.log(`${path} BLOCKER ${issue.code} at ${issue.path}: ${issue.message}`);
}
process.exit(failed ? 1 : 0);
