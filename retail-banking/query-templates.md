## Directed Ring (Basic)

```cypher
MATCH path =
  (start:Account)
  (()-[:PERFORMS]->()-[:BENEFITS_TO]->()){3,6}
  (start)
RETURN path;
```

## Directed Ring with Distinct Accounts

```cypher
MATCH path =
  (start:Account)
  ((source)-[:PERFORMS]->(tx)-[:BENEFITS_TO]->(target)){3,6}
  (start)
WHERE size(apoc.coll.toSet(source)) = size(source)
RETURN path;
```

## Chronological + Amount Decay Pattern

```cypher
MATCH path =
  (start:Account)-[:PERFORMS]->(firstTx)
  (
    (previousTx)-[:BENEFITS_TO]->(middleAccount)-[:PERFORMS]->(nextTx)
    WHERE previousTx.date < nextTx.date
      AND 0.80 <= nextTx.amount / previousTx.amount <= 1.00
  )*
  (lastTx)-[:BENEFITS_TO]->(start)
WHERE size(apoc.coll.toSet([start] + middleAccount)) = size([start] + middleAccount)
RETURN path;
```
