# Insurance Claims Fraud

Spot suspicious insurance claims by exploring how claimants, medical professionals, vehicles, and claims connect.

Fraudulent claims — staged accidents, exaggerated injuries, inflated repair costs — often hide in the relationships between parties rather than in any single record. Modelling claims as a graph makes those shared connections visible: the same vehicle turning up across several claims, one medical professional tied to an unusual number of high-value claims, or a claimant filing repeatedly.

<p align="center">
    <img src="https://neo4j.com/developer/industry-use-cases/_images/insurance/insurance-claims-fraud-schema.svg" alt="Graph schema showing Claimant, MedicalProfessional, Claim, and Vehicle nodes connected by HAS_CLAIM, TREATED_BY, OWNS, INVOLVED_IN, and TREATS relationships." width="400" />
</p>

The bundled sample dataset seeds each of these patterns so you can run the example queries and see them return straight away.

## What I can help with

- Explain the graph model and the schema choices behind it
- Walk through the primary query patterns: repeat claimants, unusual medical-professional activity, and vehicles reused across claims
- Help adapt the model to your own claims data
- Run Cypher against a connected database when you are ready
- Point to Graph Data Science approaches (community detection, centrality) for deeper network analysis

Would like to know more or get started with importing data (I can help with sample data or your own data)?
