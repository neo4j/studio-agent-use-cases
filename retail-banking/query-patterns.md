Use `resources/query-templates.md` for runnable Cypher.

Template usage:

- `Directed Ring (Basic)`: first pass to prove directed cycles exist.
- `Directed Ring with Distinct Accounts`: remove loops with repeated intermediate accounts.
- `Chronological + Amount Decay Pattern`: enforce time ordering plus amount-ratio constraints.

Guidance:

- Validate amount-ratio direction against a known example.
- Add explicit path bounds in production to control query cost.
- If APOC is unavailable, avoid templates that require `apoc.coll.toSet`.
