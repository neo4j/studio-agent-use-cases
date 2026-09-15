# Post-import setup

One statement, recommended rather than required.

Rules for the agent running it:

- Explain what the statement does before running it, and confirm the target
  database first.
- Nothing here is required for correctness. If the user declines it, say which
  queries are affected and that the effect is on speed rather than on results,
  and do not raise it again in the same conversation.
- Do not add indexes or constraints beyond this file. Node-key constraints are
  created by the Import flow from `GRAPH_MODEL.json`; creating them again
  conflicts with the constraints already in place.

## Recommended

### Relationship property index on RESOLVED_LINK.idVariant

```cypher
/*
 * @name           Index resolved links by variant
 * @description    Creates a relationship property index on
 *                 RESOLVED_LINK.idVariant, the property every resolution query
 *                 filters on. The Import flow does not create it, because
 *                 RESOLVED_LINK is written by the queries rather than imported.
 * @usage          Recommended before working with resolved variants. Affects
 *                 "Resolve a variant against constraints", "Show a resolved
 *                 bill of materials", "Prune undecided decisions by scoring",
 *                 "Remove resolved links detached from the product", "Roll up
 *                 weight and cost of a resolved variant", "Find configuration
 *                 decisions the constraints could not satisfy" and "Clear a
 *                 resolved variant" — which is every query that names a
 *                 variant. Skipping it changes no result: those queries still
 *                 return exactly the same rows, but each scans all resolved
 *                 links instead of seeking the variant's own. The cost of
 *                 skipping grows with the number of variants held in the
 *                 database at once, and is negligible when there is only one.
 *                 Safe to run more than once.
 */
CREATE INDEX resolved_link_variant IF NOT EXISTS
FOR ()-[r:RESOLVED_LINK]-() ON (r.idVariant);
```
