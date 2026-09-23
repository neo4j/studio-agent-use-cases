# Post-import setup

One optional statement. Nothing here is required: every query in `QUERIES.md`
returns identical results without it, and only the speed of the crown-jewel
lookups changes.

Rules for the agent running these:

- Explain the statement before running it, and confirm the target database
  first. It writes schema, not data.
- If the user declines it, say plainly that no query result changes and that
  only the anchor lookup in the crown-jewel queries is slower, then do not raise
  it again in the conversation.
- Do not improvise further indexes or constraints. The node-key constraints are
  created by Import from `GRAPH_MODEL.json`; recreating them conflicts with what
  is already there.

## Recommended: index the application criticality tier

```cypher
/*
 * @name           Index the application criticality tier
 * @description    Creates a range index on Application.tier so that queries
 *                 anchoring on a criticality band seek to the matching
 *                 applications instead of scanning every application in the
 *                 portfolio.
 * @usage          Recommended, never required. Two queries in QUERIES.md open
 *                 with a tier predicate on Application and benefit directly:
 *                 "Attack paths from an exposed foothold to a crown-jewel
 *                 application" and "Crown-jewel exposure summary"; "Choke
 *                 points on crown-jewel attack paths" benefits through the same
 *                 anchor. If skipped, all three return exactly the same rows
 *                 and simply scan the Application label first — unnoticeable on
 *                 a small portfolio, and worth having on a large one. Run once;
 *                 the IF NOT EXISTS clause makes a repeat run a no-op.
 */
CREATE INDEX application_tier IF NOT EXISTS
FOR (a:Application) ON (a.tier)
```

Deliberately not indexed: `CVE.knownExploited` and `CVE.cvssScore`, because
every query reaches `CVE` by traversing `HAS_VULNERABILITY` from an instance
rather than by scanning the label, so those predicates are applied as filters an
index would not serve. The same reasoning applies to
`CloudService.dataClassification`, which is reached by traversal from a policy.
