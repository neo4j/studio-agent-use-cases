Start broad, then progressively constrain:

1. Find directed transaction rings.
2. Remove repeated intermediate accounts.
3. Require chronological transaction ordering.
4. Add amount-ratio constraints for fee-skimming/decay patterns.
5. Rank by additional risk context (velocity, shared identifiers, account age).

This progression improves explainability and helps isolate which constraint suppresses true positives when data quality is uneven.
