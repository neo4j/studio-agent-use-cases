Use two core node labels:

- `Account`
- `Transaction`

Use two core relationship types:

- `(:Account)-[:PERFORMS]->(:Transaction)`
- `(:Transaction)-[:BENEFITS_TO]->(:Account)`

Minimum useful properties:

```text
Account.accountNumber
Transaction.transactionId
Transaction.amount
Transaction.date
```

Use these source-page meanings for required fields:

- `Account.accountNumber`: account identifier (replace with institution key if needed).
- `Transaction.transactionId`: unique transaction identifier.
- `Transaction.amount`: amount moved.
- `Transaction.date`: transaction timestamp.

The baseline model does not require relationship properties on `PERFORMS` or `BENEFITS_TO`.
