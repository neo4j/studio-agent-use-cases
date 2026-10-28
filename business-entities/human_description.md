# Business Entities: Ownership and Control

Trace ownership and control through layers of companies, trusts and boards to find who really owns and runs a business — the answer a register of direct shareholders rarely gives.

## Overview

### Knowing who you are dealing with

Banks, insurers, asset managers and their regulators must know who ultimately owns and controls every company they deal with. Know-your-customer (KYC) onboarding, anti-money-laundering (AML) monitoring, sanctions screening and counterparty-risk teams all ask the same question: which natural persons stand behind this legal entity?

The difficulty is that ownership is rarely direct. A company may be owned by a holding company, which is owned by another in a different country, which is held in trust for a family. Control can sit with a board, a general partner or a nominee rather than with whoever owns the shares. And corporate groups change constantly, so the parent a company reported last year may no longer be its parent.

The vocabulary in this package follows the **Financial Industry Business Ontology (FIBO)**, the shared description of financial concepts developed by the EDM Council (Enterprise Data Management Council) with industry experts, and specifically its Business Entities domain. FIBO is open source, rigorously governed and used by financial institutions worldwide, so practitioners who already work with it — or with Legal Entity Identifier (LEI) data — will recognise the terms. It is also deliberately formal: this package keeps FIBO's concepts and definitions but simplifies its structure so the result is easy to explore. It is an adaptation, not FIBO itself, and is not endorsed by the EDM Council.

*Source and license: adapted from the Business Entities (BE) domain of FIBO, Copyright (c) 2013-2026 EDM Council, Inc. (also EDM Association dba EDM Council, Inc.) and Copyright (c) 2013-2025 Object Management Group, Inc., used under the [MIT License](https://opensource.org/licenses/MIT). FIBO is available at [github.com/edmcouncil/fibo](https://github.com/edmcouncil/fibo).*

The hard questions are all questions about chains:

- **Who is the ultimate beneficial owner** — the person whose share, multiplied down every chain of companies and added across all of them, crosses the reporting threshold (commonly 25%).
- **Who controls without owning** — directors and officers of a parent, or the partners behind a fund's general partner, who run a business while holding almost none of it.
- **Where structures hide** — layers of offshore companies, trusts, stakes split across a household, or companies that own each other in a circle.

### What it helps with

Each of these becomes a walk along connected records rather than a manual reconstruction from registry extracts.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| The real owner sits several companies away | Ownership links carry percentages, so effective ownership is multiplied along each chain and summed across every chain to the same person |
| A stake is split across two routes so each looks small | All routes from a person to a company are found together, so a 15% direct holding and a 12% indirect one add up to 27% |
| A family divides a stake so no one crosses the threshold | People are linked to their home address, so household members' holdings in the same company can be added together |
| A trust sits in the ownership chain | Trusts link to their trustor, trustees and beneficiaries, so the people behind a trust are one step away |
| Control without ownership | Board seats, offices and general partner interests are separate from shareholdings, so control can be traced up a chain of parents independently of ownership |
| Ownership passes through several offshore jurisdictions | Each company links to where it is incorporated, and jurisdictions can be flagged by policy, so layered offshore chains stand out |
| Shell companies cluster at a formation agent's address | Companies at the same registered address meet at one point, along with the few nominee directors who sit on all their boards |
| Companies own each other in a loop | Circular chains of ownership are found directly, however many companies they pass through |
| Reported parents go stale after a deal | Reported direct and ultimate parents sit beside the actual ownership chain, so disagreements show up at once |
| A supplier is secretly linked to a buyer's executive | The shortest connection between any two companies, through owners, directors, officers, trusts or addresses, is found in one step |

Everything surfaced this way is a lead for a compliance analyst, not a legal determination. Families divide shares for inheritance, offshore funds have lawful purposes, and professional directors sit on many boards; each pattern needs review before it means anything.

## Ontology

The reference ontology connects three kinds of party — **people**, **legal entities** and **trusts** — through ownership and through roles. People, entities and trusts own shares in legal entities, each holding carrying a percentage and the kind of interest held. People sit on boards and hold offices. People establish, manage and benefit from trusts, and trust companies act as trustees. Every legal entity is incorporated in a **jurisdiction** and registered at an **address**; people have a home address; and entities with an LEI report their direct and ultimate parent.

Roles such as shareholder, director, trustee and beneficiary are connections, not separate kinds of thing, so one person carries all of their holdings and positions at once. Dates are held as datetimes at midnight UTC, where only the calendar date matters.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Person` | An individual who owns, directs, manages, establishes or benefits from companies and trusts; one node holds all of a person's roles |
| `LegalEntity` | A business with legal personality — a company, limited liability company, partnership, joint venture or not-for-profit corporation |
| `Trust` | An arrangement in which a trustee holds and manages assets for beneficiaries, established by a trustor |
| `Jurisdiction` | A country, or a state or territory with its own company law, under which entities are incorporated and trusts governed |
| `Address` | A postal address used as a registered office or a home; one per distinct address |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Person` | `personId` | String | Unique identifier of the person |
| `Person` | `name` | String | Full name as recorded; not unique |
| `Person` | `nationality` | String | Country of citizenship, as a two-letter ISO 3166-1 country code |
| `Person` | `isPoliticallyExposed` | Boolean | Whether the person holds, or is close to someone who holds, a prominent public function, as determined by the institution's own screening |
| `LegalEntity` | `entityId` | String | Unique identifier of the entity |
| `LegalEntity` | `name` | String | Registered legal name, including its legal-form suffix |
| `LegalEntity` | `legalForm` | String | Legal form, using FIBO's labels: publicly held company, privately held company, private limited company, limited liability company, joint stock company, general partnership, limited partnership, limited liability partnership, joint venture, not-for-profit corporation or cooperative society |
| `LegalEntity` | `lei` | String | ISO 17442 Legal Entity Identifier, 20 characters; empty when the entity has none |
| `LegalEntity` | `registrationNumber` | String | Number allocated by the registry of the jurisdiction of incorporation, in that registry's format |
| `LegalEntity` | `status` | String | Active (registered and operating) or inactive (dissolved, struck off or otherwise ceased) |
| `LegalEntity` | `incorporationDate` | Zoned datetime | Date of incorporation or registration |
| `Trust` | `trustId` | String | Unique identifier of the trust |
| `Trust` | `name` | String | Name of the trust as stated in its trust agreement |
| `Trust` | `trustType` | String | Revocable trust, irrevocable trust or testamentary trust (created under a will) |
| `Trust` | `establishedDate` | Zoned datetime | Date the trust was established |
| `Jurisdiction` | `jurisdictionId` | String | ISO 3166-1 country code, or ISO 3166-2 subdivision code (such as US-DE for Delaware) where company law is set below national level |
| `Jurisdiction` | `name` | String | Name of the jurisdiction in English |
| `Jurisdiction` | `isOffshoreCentre` | Boolean | Whether the institution's policy treats the jurisdiction as an offshore financial centre; a policy choice, not a legal classification |
| `Address` | `addressId` | String | Unique identifier of a distinct, standardised address |
| `Address` | `street` | String | Street line, including any building or suite name |
| `Address` | `city` | String | City or town |
| `Address` | `postalCode` | String | Postal code in the local format; empty where the country uses none |
| `Address` | `countryCode` | String | Country, as a two-letter ISO 3166-1 code |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `OWNS` | `Person` → `LegalEntity` | The person directly holds an ownership interest in the entity; a person may own many entities and an entity have many owners |
| `OWNS` | `LegalEntity` → `LegalEntity` | One entity directly owns part or all of another — parent and subsidiary, holding and operating company, fund and portfolio company; chains of these form corporate groups |
| `OWNS` | `Trust` → `LegalEntity` | The trust, through its trustees, holds an ownership interest in the entity; the people behind it are found through its roles, not through ownership |
| `DIRECTOR_OF` | `Person` → `LegalEntity` | The person sits on the entity's board; a person may hold many directorships and an entity have many directors |
| `OFFICER_OF` | `Person` → `LegalEntity` | The person holds an executive office in the entity; each office held is a separate connection |
| `TRUSTOR_OF` | `Person` → `Trust` | The person established the trust; every trust has at least one trustor |
| `BENEFICIARY_OF` | `Person` → `Trust` | The person is a beneficiary of the trust; a trust may have many |
| `TRUSTEE_OF` | `Person` → `Trust` | The person acts as an individual trustee of the trust |
| `TRUSTEE_OF` | `LegalEntity` → `Trust` | The entity — typically a trust company — acts as corporate trustee; one trust company may serve many trusts |
| `INCORPORATED_IN` | `LegalEntity` → `Jurisdiction` | The entity is incorporated or registered under that jurisdiction's law; exactly one per entity |
| `ESTABLISHED_IN` | `Trust` → `Jurisdiction` | The trust is governed by that jurisdiction's law; exactly one per trust |
| `REGISTERED_AT` | `LegalEntity` → `Address` | The entity's officially recorded registered address; exactly one per entity, and many entities may share one |
| `RESIDES_AT` | `Person` → `Address` | The person's home address; at most one per person, and a household shares one |
| `DIRECTLY_CONSOLIDATED_BY` | `LegalEntity` → `LegalEntity` | The parent the entity reports as its closest consolidating parent, as in LEI records; at most one per entity |
| `ULTIMATELY_CONSOLIDATED_BY` | `LegalEntity` → `LegalEntity` | The parent the entity reports as its ultimate consolidating parent, as in LEI records; at most one per entity, and it can go stale after a deal |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `OWNS` | `percentage` | Float | Share of the owned entity's equity held directly, in percent (0–100); economic ownership, not voting rights |
| `OWNS` | `interestType` | String | Kind of interest: shares, membership interest (in an LLC), general partner interest (which controls a partnership whatever its size) or limited partner interest |
| `DIRECTOR_OF` | `role` | String | Executive director (also employed by the entity) or non-executive director |
| `DIRECTOR_OF` | `appointedDate` | Zoned datetime | Date the director was appointed |
| `OFFICER_OF` | `title` | String | Chief executive officer, chief financial officer, company secretary, or managing member (who runs an LLC day to day) |
