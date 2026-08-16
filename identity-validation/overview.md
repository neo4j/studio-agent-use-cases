# Overview

Identity resolution is the problem of recognising that two or more records — captured at different times, through different channels, or in different systems — describe the same real-world person, account, or device. "Robert J. Smith" in an EHR system, "Bob Smith" at a lab, and "R.J. Smith" at a pharmacy may all be the same patient; without resolving them, that person's history stays fragmented across systems that don't know about each other.

There are three broad approaches:

- **Deterministic matching** — exact-match rules (same SSN, same email). Simple, but brittle against real-world variation.
- **Probabilistic matching** — statistical scoring of how likely two records are the same, weighting rarer values more heavily.
- **Graph-based matching** — following relationship paths between records to find indirect connections, considering multiple shared attributes and their combined strength at once. This is what this package implements.

Graph-based matching is what lets a two-person fraud ring surface even when no single attribute matches exactly: Account A and Account B share a phone number, Account B and Account C share an IP address, and none of the three share a name.

Core objective:

```text
Identity -> shared attribute (Phone / Email / SSN / Address / DOB / IP) <- other Identity
```

A legitimate match usually shares several attributes at once — name, address, and DOB alongside a changed phone or email. A synthetic-identity fraud signal looks different: a reused contact identifier (phone, device) paired with a slightly altered identifier (SSN off by one digit) while everything else differs.

Treat all outputs as match candidates ranked by confidence, not confirmed identity. Shared attributes have legitimate explanations; the graph ranks where to look first.

## Identifiers vs descriptors

Not every property is equally useful for finding matches.

An **identifier** (phone, email, SSN) is specific enough that sharing one is meaningful evidence two records are the same entity.

A **descriptor** (name, gender, city) is too common on its own. A property that would connect a very large number of unrelated records is a descriptor, not an identifier, and should only corroborate a match already found via real identifiers — never find candidates by itself.

That distinction drives the shape of nearly every query in this package. `PersonName` is excluded from the fan-out query and reappears only as a secondary signal, and geographic proximity is treated the same way. See `query-patterns.md`.

This package's queries are a deliberately lightweight starter subset of a fuller process: data standardisation and placeholder flagging, candidate scoring, weighted composite matching, and recording results back into the graph. See `implementation-guidance.md` for what a production deployment adds on top.
