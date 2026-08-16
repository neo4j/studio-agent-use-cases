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
| `stage` | Staging     | Skills being validated before release.      |
| `prod`  | Production  | Approved skills available to production.    |

Changes move in one direction:

```text
main -> stage -> prod
```

1. Develop on a short-lived branch and open a pull request into `main`.
2. Use [Promote main to stage](https://github.com/neo4j/studio-agent-use-cases/compare/stage...main?expand=1).
3. Validate the skills in staging.
4. Use [Promote stage to prod](https://github.com/neo4j/studio-agent-use-cases/compare/prod...stage?expand=1).
5. Complete required checks and approvals, then create a merge commit.

Do not commit directly to `stage` or `prod`. Apply fixes to `main` and promote them through the same sequence. Promotion pull requests must use merge commits: squash or rebase merges break ancestry between the long-lived branches and can make later promotions include previously released changes.
