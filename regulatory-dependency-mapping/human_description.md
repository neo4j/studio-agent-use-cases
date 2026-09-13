# Regulatory Dependency Mapping

Trace a regulatory change through cross-referenced handbook sections to every other rule it reaches.

## Overview

### Regulatory change in investment banking

Banks operate under handbooks published by supervisory authorities — long, numbered documents divided into sourcebooks, chapters, sections and subsections. Compliance and regulatory-change teams are responsible for knowing which parts of those handbooks apply to the business, and for working out what has to change each time the regulator amends the text.

The difficulty is not the volume. It is that a handbook is not a list of independent rules. Sections cite one another constantly: a reporting obligation in one chapter defines its scope by reference to a client-categorisation rule in another, which in turn leans on a definition in a third. Citations cross chapters, and they cross sourcebooks.

So when a regulator amends a single section, the question that matters — what else does this touch? — is several hops deep. Answered in a PDF reader or tracked in a spreadsheet, it is worked by hand, one cross-reference at a time, under a deadline. Text gets missed. What gets missed is usually what sits three references away.

### What it helps with

Treating the handbook as connected text rather than as a document turns each of those questions into a traversal.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| An amendment lands and nobody knows its full reach | Follow citations backwards from the changed section to everything that relies on it, directly or through a chain, and state the blast radius as a set rather than a judgement call |
| Some text is far more expensive to change than it looks | Rank sections by how heavily they are cited, so the structurally load-bearing text is known before anyone proposes amending it |
| A change backlog has no defensible order | Combine how recently text took effect with how heavily it is cited, putting the amendments most depended upon at the top |
| Dependencies between sourcebooks are invisible | Surface the citations that cross from one standard into another, where responsibility for the impact often sits with a different team |
| Periodic reviews are manual | Filter on the date a section's current wording took effect to see everything that has moved since the last sweep |

Everything the ontology surfaces is a lead for a compliance professional to verify. A blast radius is bounded by how completely the cross-references were captured in the first place, so treat it as a floor on the impact of a change, never a ceiling, and never as a compliance determination in its own right.

## Ontology

The reference ontology is deliberately small: two kinds of thing, two kinds of connection. A standard is a published handbook. A section is one addressable unit of text within it. Sections nest beneath their standard and beneath each other to form the hierarchy, and cite each other freely across it.

The two connections are read in opposite spirits. Containment runs from a child upwards to its parent, and chaining it reconstructs the full depth of a handbook. Citation runs from the citing section to the cited one, and following it backwards is what answers the impact question. Merging the two into a single connection, or recording citations without a direction, breaks every pattern that rests on them.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Standard` | A named handbook or sourcebook published by a supervisory authority — the top of the regulatory hierarchy, with sections hanging beneath it |
| `Section` | A single addressable unit of regulatory text: a chapter, section or subsection. Sections form the hierarchy, cross-reference one another, and are the level at which regulatory change is tracked |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Standard` | `id` | String | Short identifier for the standard as the regulator publishes it, typically the sourcebook code. Section identifiers within that standard are built from this prefix |
| `Section` | `id` | String | Section identifier exactly as the regulator cites it, including the standard prefix — a sourcebook code followed by chapter and section numbers. Unique across every standard, not merely within one |
| `Section` | `title` | String | Long heading of the section as published, conventionally repeating the section identifier before the heading text |
| `Section` | `lastUpdated` | Date | Calendar date on which the section's current text took effect — the in-force date of its most recent amendment, not the date that amendment was announced or published. This is what regulatory-change analysis filters on |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `DEPENDS_ON` | `Section` → `Standard` | Places a top-level section directly beneath the standard that publishes it. Only sections at the top of a handbook's hierarchy carry this |
| `DEPENDS_ON` | `Section` → `Section` | Places a section beneath its immediate parent, read child to parent. Deeper sections reach their standard by chaining through their parents rather than connecting to it directly |
| `RELATED` | `Section` → `Section` | Records a cross-reference made by the citing section to the cited one, so that a change to the cited text is known to reach the citing text. The direction is the direction of the citation, not of influence; two sections that cite each other carry one of these each way |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `RELATED` | `subsection` | String | The specific rule within the cited section that the citing section relies on, in the regulator's own rule notation. Where a section is cited as a whole, this is the cited section's own identifier |
