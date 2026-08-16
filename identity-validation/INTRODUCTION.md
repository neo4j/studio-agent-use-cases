# Identity Validation

Same person, different records: identity validation resolves a person's identity across systems, channels, and near-duplicate identifiers by following the connections between them, not just matching strings.

# Example

One customer arrives as three records: a CRM row, a mobile signup, a call-centre note. There is no single field that matches cleanly across all three. Graph-connected data turns that from a string-comparison problem into a traversal: each shared phone number, email, or address becomes a node that two records both point at, so the match is something you can see and follow rather than something you have to score in the dark. Weak, coincidental links look visibly different from a genuine cluster.

The bundled sample data is 500 masked profiles, deliberately seeded so every query returns a meaningful result: six legitimate multi-channel clusters, three synthetic-identity fraud pairs, two address pairs that only match once geocoded, and a few hundred realistic non-matching records for contrast.

## What I can help with

- Explain the graph model and why each attribute is keyed the way it is
- Walk through the query patterns, from shared-identifier fan-out to weighted scoring
- Import the bundled sample data and run the queries against it
- Help you map your own source systems onto the model
- Show how synthetic identity fraud looks different from a genuine match
- Explain what to add for production scale, including the Graph Data Science path

Would like to know more or get started with importing data (I can help with sample data or your own data)?
