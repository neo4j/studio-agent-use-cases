# Post-import setup

Two statements, **both recommended, neither required**. The Import flow
creates everything the queries need to be correct; these two only make the
date-filtered queries faster on a full handbook.

Rules for the agent running them:

- Explain what a statement creates, and why, before running it.
- Confirm the target database and connection first — these write to the
  schema.
- If the user declines a statement, say which queries are affected and
  caveat their performance for the rest of the conversation. Results stay
  correct either way; neither query fails without its index.
- Do not add indexes or constraints beyond these two. The node-key
  constraints are created by Import from `GRAPH_MODEL.json` and must not be
  recreated here.

## Range index on Section.lastUpdated

**Recommended, not required.**

```cypher
/*
 * @name           Range index on Section.lastUpdated
 * @description    Creates a range index over the in-force date of section
 *                 text, so that filtering sections by change date seeks the
 *                 index rather than scanning every Section node.
 * @usage          Supports 'Sections changed since a date and the obligations
 *                 they drive'. Skipping it leaves that query correct but
 *                 scanning all sections — unnoticeable on a single handbook,
 *                 material once several full rulebooks are loaded. Safe to
 *                 run more than once thanks to IF NOT EXISTS.
 */
CREATE INDEX section_last_updated IF NOT EXISTS
FOR (n:Section) ON (n.lastUpdated)
```

## Range index on Control.lastTestedDate

**Recommended, not required.**

```cypher
/*
 * @name           Range index on Control.lastTestedDate
 * @description    Creates a range index over the date each control was last
 *                 tested, so that the overdue-testing query seeks the index
 *                 rather than scanning every Control node.
 * @usage          Supports 'Controls overdue for testing, weighted by
 *                 obligation risk'. Skipping it leaves that query correct but
 *                 scanning the whole control inventory. Safe to run more than
 *                 once thanks to IF NOT EXISTS.
 */
CREATE INDEX control_last_tested IF NOT EXISTS
FOR (n:Control) ON (n.lastTestedDate)
```
