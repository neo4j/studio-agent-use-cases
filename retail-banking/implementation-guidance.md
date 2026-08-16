When helping users operationalize this pattern:

1. Confirm source schema and map to `Account`, `Transaction`, `PERFORMS`, `BENEFITS_TO`.
2. Verify date and amount data types before applying chronology/ratio constraints.
3. Start with basic ring detection and add constraints incrementally.
4. Recommend constraints/indexes for `Account.accountNumber` and `Transaction.transactionId`.
5. Return Cypher plus short investigative interpretation.

Recommended constraints:

```cypher
CREATE CONSTRAINT account_number_unique IF NOT EXISTS
FOR (a:Account)
REQUIRE a.accountNumber IS UNIQUE;

CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS
FOR (t:Transaction)
REQUIRE t.transactionId IS UNIQUE;
```
