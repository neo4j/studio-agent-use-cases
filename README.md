# Studio Agent Use Cases

This public repository hosts the versioned skill packages used by Neo4j Studio Agent use cases.

## Repository layout

```text
.
├── catalog.json
├── <skill-id>/
│   ├── SKILL.md
│   ├── GRAPH_MODEL.json
│   └── ...supporting files and sample-data/
```

`catalog.json` contains directory of file. It declares `schemaVersion: 1`; each entry contains a `skillId` and the complete, sorted list of files relative to that skill's repository-root directory.

Every skill must have:

- a safe, unique kebab-case directory name matching the `name` in `SKILL.md` frontmatter;
- a non-empty `SKILL.md` body and the required Neo4j card metadata;
- a parseable `GRAPH_MODEL.json`; and
- every sample CSV referenced by the graph model, with the fields that model uses.

## Raw files

The catalog and skill files are available through GitHub's raw-content endpoint:

```text
https://raw.githubusercontent.com/neo4j/studio-agent-use-cases/<ref>/catalog.json
https://raw.githubusercontent.com/neo4j/studio-agent-use-cases/<ref>/<skill-id>/<relative-file>
```

`<ref>` can be `main`, `stage`, or `prod` for development and manual testing. Resolve files listed in a catalog relative to the repository-root `<skillId>/` directory.

## Environment branches and promotion

| Branch  | Environment | Purpose                                     |
| ------- | ----------- | ------------------------------------------- |
| `main`  | Development | Source of truth for new and updated skills. |
| `staging` | Staging     | Skills being validated before release.      |
| `production`  | Production  | Approved skills available to production.    |

Changes move in one direction:

```text
main -> staging -> production
```

1. Develop on a short-lived branch and open a pull request into `main`.
2. Use [Promote main to staging](https://github.com/neo4j/studio-agent-use-cases/compare/staging...main?expand=1).
3. Validate the skills in staging.
4. Use [Promote staging to production](https://github.com/neo4j/studio-agent-use-cases/compare/production...staging?expand=1).
5. Complete required checks and approvals, then create a merge commit.

Do not commit directly to `staging` or `production`. Apply fixes to `main` and promote them through the same sequence. Promotion pull requests must use merge commits: squash or rebase merges break ancestry between the long-lived branches and can make later promotions include previously released changes.

## Catalog format

`catalog.json` is the machine-readable index of published skills. Schema version `1` looks like this:

```json
{
  "schemaVersion": 1,
  "skills": [
    {
      "skillId": "example-skill",
      "files": {
        "graph": "GRAPH_MODEL.json",
        "markdown": "SKILL.md",
        "skill": [
          "INTRODUCTION.md",
          "QUERIES.md",
          "sample-data/example.csv"
        ]
      }
    }
  ]
}
```

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schemaVersion` | number | Catalog schema version. Currently `1`. |
| `skills` | array | One entry per skill package in the repository. |
| `skills[].skillId` | string | Directory name of the skill at the repository root (kebab-case). |
| `skills[].files.graph` | string | Path to the graph model file, relative to the skill directory. Always `GRAPH_MODEL.json`. |
| `skills[].files.markdown` | string | Path to the skill card markdown, relative to the skill directory. Always `SKILL.md`. |
| `skills[].files.skill` | string[] | Remaining supporting files relative to the skill directory, sorted lexicographically. Includes docs, Cypher, and sample CSVs. |

Resolve any path in `files` as `<skillId>/<path>` from the repository root. When adding or updating a skill, keep `catalog.json` in sync with the files that skill actually ships.
