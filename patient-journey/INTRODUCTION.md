# Patient Journey

Turn fragmented clinical records into a single, connected view of each patient's path through the healthcare system.

A patient's history is scattered across encounters, lab results, prescriptions, diagnoses, and the providers and facilities that delivered care. Those connections are exactly what a graph represents naturally: instead of stitching records together with complex joins, you traverse the relationships directly — from a patient, along their sequence of encounters, out to the conditions diagnosed, drugs prescribed, and measurements taken at each one.

<p align="center">
    <img src="TODO(review): confirmed patient-journey model image URL" alt="Graph model showing a Patient linked to a chronological chain of Encounters, each connected to its Observations, Conditions, Drugs, and attending Provider, with Providers linked to their Speciality and Organisation" width="400" />
</p>

The bundled sample is synthetic data (Synthea, Massachusetts) covering a few patients with overlapping conditions such as hypertension and type 2 diabetes — enough to demonstrate single-patient pathways and cross-patient comorbidity patterns.

## Try the live demo

TODO(review): confirm whether a demo-showcase guide exists for this use case; if so, link it as `/projects/{{project_id}}/guides/demo-showcase`, otherwise remove this section.

## What I can help with

- Explain the graph model and the schema choices behind it
- Walk through the primary query patterns, from a single patient to population-level comorbidity analysis
- Help you import the bundled sample data
- Help adapt the model to your own EHR, FHIR, or OMOP data
- Run Cypher against a connected database when you're ready

Would like to know more or get started with importing data (I can help with sample data or your own data)?
