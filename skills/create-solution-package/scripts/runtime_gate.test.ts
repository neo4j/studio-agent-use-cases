// Runtime gate for solution packages (VALIDATION.md section 3) — a temporary vitest file, never committed.
//
// Copy into the destination's use-case loader folder and run it there; delete it afterwards:
//   cp <skill-path>/scripts/runtime_gate.test.ts <upx>/commons/chat-assistant/src/skill-loader/tmp-runtime-gate.test.ts
//   cd <upx>/commons/chat-assistant
//   USE_CASES_REPO=<studio-agent-use-cases checkout> [USE_CASES_ONLY=<skillId>,...] \
//     ../../node_modules/.bin/vitest run src/skill-loader/tmp-runtime-gate.test.ts
//   rm src/skill-loader/tmp-runtime-gate.test.ts
//
// It mirrors buildRegisteredSkillPackage in use-case-source.ts: parse and register the package, then convert the
// reference ontology to an Import model. The registry does both while loading the catalogue, and a throw at either
// step drops the package with only a log line, so both must print OK. If the destination's registration path has
// changed, update the two calls below to match it before trusting the result. Packages are taken from catalog.json;
// a skillId named in USE_CASES_ONLY with no catalog entry yet is read from its folder instead.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { ontologySpecJsonToDataModelAndVisualisation } from '@nx/import-shared/sample-models';
import { describe, expect, it } from 'vitest';

import { buildUseCasePackageFromSource, getGraphModelFormat } from './parse-use-case';

const REPO = process.env.USE_CASES_REPO ?? '';
const ONLY = (process.env.USE_CASES_ONLY ?? '').split(',').filter(Boolean);

type CatalogFiles = { graph: string; skill: string[]; markdown: string };
const catalog = existsSync(join(REPO, 'catalog.json'))
  ? (JSON.parse(readFileSync(join(REPO, 'catalog.json'), 'utf8')) as { skills: { skillId: string; files: CatalogFiles }[] })
  : { skills: [] };

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    if (name.startsWith('.')) return [];
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });

const filesFromFolder = (skillId: string): CatalogFiles => {
  const files = walk(join(REPO, skillId)).map((path) => relative(join(REPO, skillId), path));
  return { graph: 'ONTOLOGY.json', markdown: 'SKILL.md', skill: files.filter((f) => f !== 'ONTOLOGY.json' && f !== 'SKILL.md') };
};

const packages: [string, CatalogFiles][] =
  ONLY.length > 0
    ? ONLY.map((id) => [id, catalog.skills.find((s) => s.skillId === id)?.files ?? filesFromFolder(id)])
    : catalog.skills.map((s) => [s.skillId, s.files]);

// Decoding without throwing is not enough: check that every encoded table field keeps a name and every node
// mapping points at a field that exists, which is how a lossy encode has slipped through before.
const encodeProblems = (dataModel: any): string[] => {
  const schema = dataModel.dataSourceSchema ?? dataModel.graphMappingRepresentation?.dataSourceSchema;
  const declared = new Set<string>();
  const problems: string[] = [];
  for (const table of schema?.tableSchemas ?? []) {
    for (const [index, field] of (table.fields ?? []).entries()) {
      if (typeof field.name !== 'string' || field.name === '') problems.push(`table "${table.name}" field #${index} has no name`);
      else declared.add(field.name);
    }
  }
  for (const mapping of dataModel.graphMappingRepresentation?.nodeMappings ?? []) {
    for (const pm of mapping.propertyMappings ?? []) {
      if (pm.fieldName !== undefined && !declared.has(pm.fieldName)) problems.push(`mapping references undeclared field "${pm.fieldName}"`);
    }
  }
  return problems;
};

describe('runtime gate', () => {
  for (const [skillId, files] of packages) {
    it(skillId, () => {
      const dir = join(REPO, skillId);
      const filePaths = [files.graph, ...files.skill, files.markdown];
      const lines: string[] = [];
      const missing = filePaths.filter((f) => !existsSync(join(dir, f)));
      lines.push(missing.length === 0 ? 'FILES OK' : `FILES MISSING: ${missing.join(', ')}`);

      const skillSource = readFileSync(join(dir, files.markdown), 'utf8');
      const graphModelSource = readFileSync(join(dir, files.graph), 'utf8');
      const graphModelFormat = getGraphModelFormat(files.graph);
      try {
        const pkg = buildUseCasePackageFromSource({ skillId, skillSource, graphModelSource, graphModelFormat, filePaths });
        lines.push(`REGISTER OK (format=${graphModelFormat}, hasSampleData=${pkg.manifest.hasSampleData}, csv=${pkg.sampleCsvFiles.length})`);
      } catch (error) {
        lines.push(`REGISTER FAILED: ${error instanceof Error ? error.message : String(error)}`);
      }
      try {
        const { dataModel } = ontologySpecJsonToDataModelAndVisualisation(graphModelSource, { tool: 'importer' });
        const problems = encodeProblems(dataModel);
        lines.push(problems.length === 0 ? 'IMPORT CONVERT OK' : `IMPORT CONVERT LOSSY: ${problems.join('; ')}`);
      } catch (error) {
        lines.push(`IMPORT CONVERT FAILED: ${error instanceof Error ? error.message : String(error)}`);
      }

      console.log(`GATE ${skillId}\n  ${lines.join('\n  ')}`);
      expect(lines.filter((line) => !line.includes(' OK')), lines.join(' | ')).toEqual([]);
    });
  }
});
