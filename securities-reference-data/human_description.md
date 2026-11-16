# Securities: Reference Data and Look-through Exposure

Know exactly which instrument an identifier or ticker means, see every security an issuer group stands behind, and measure how much of a fund really sits with one issuer once other funds, depositary receipts and subsidiaries are followed. The reference ontology is adapted from the Securities domain of the EDM Council's Financial Industry Business Ontology (FIBO).

## Overview

### The industry

Every bank, asset manager, custodian and exchange keeps a **security master**: the reference record of each instrument it trades, holds or prices — who issued it, what kind of instrument it is, what it pays, when it matures, where it is listed and under which identifiers. Every trade, position, price and regulatory report is keyed to it.

The work is hard because the same instrument travels under many names. An ISIN, a national number (CUSIP, SEDOL, Valoren), a FIGI and a ticker on each exchange all point at one security, vendors disagree, and tickers are recycled after delistings. Issuers are not single companies but groups, borrowing through financing subsidiaries. And a fund's exposure is rarely just its own holdings list:

- **Funds of funds and pension schemes** hold units of other funds, so the real exposure sits one or two layers down.
- **Depositary receipts** carry a foreign company's share risk but are issued by a bank.
- **Convertible and exchangeable bonds** turn into another company's shares, sometimes a company that did not issue them.

Compliance teams must also watch how securities came to market: a fund buying deals its own group's bank underwrote is a conflict of interest many regimes restrict.

### What it helps with

The reference ontology connects instruments, issuers, identifiers, listings, offerings and funds, so these questions become a walk through the connections rather than a reconciliation project.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| "Which security is this ISIN, CUSIP or ticker?" | Each identifier is its own entry linked to the security, with its issuer, the issuer's group and its listings one step away |
| A ticker in an old trade file now means a different company | Listings carry start and end dates per exchange, so a ticker resolves to the right security on any date |
| Two securities carry the same identifier, or an ISIN disagrees with the CUSIP beside it | Shared identifiers meet at a single entry, and the national number embedded in each ISIN can be checked against the one on record |
| A matured bond is still shown as listed | Maturity dates and listing end dates sit side by side, so stale listings stand out |
| "What has this group issued, and in what order would it be repaid?" | Subsidiaries link to their parents, so every security issued anywhere in the group can be gathered and ranked by seniority |
| "Where is our exposure to this issuer, under any name?" | Depositary receipts link to the shares they represent, and convertibles to the securities they convert into, wherever they were issued |
| "How much of this fund really sits with one issuer?" | A fund's holdings of other funds' units are followed down, weights multiplied, receipts mapped to their underlying issuer, and everything summed to the ultimate parent |
| A fund holds deals underwritten by its manager's own bank | Offerings link securities to their underwriters, and both underwriter and manager link to their corporate groups |

## Ontology

The reference ontology centres on the **security**. Each security is issued by a **legal entity**, and entities link to their parents to form issuer groups. Securities carry **identifiers** and **listings** on **exchanges**; depositary receipts and convertibles link to the securities whose risk they carry. **Funds** hold securities, including other funds' units, and are managed by a legal entity. **Offerings** connect newly issued securities to the entities that underwrote them.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `LegalEntity` | An organisation playing a role in the securities lifecycle: an issuer (company, financing subsidiary, fund vehicle or government), an underwriter, a depositary bank or a fund manager |
| `Security` | A tradable instrument issued by one legal entity: a share, preferred share, depositary receipt, bond, convertible or fund unit |
| `Identifier` | A market identifier under one scheme — ISIN, CUSIP, CINS, SEDOL, Valoren, Common Code or FIGI — one entry per distinct scheme and value |
| `Exchange` | A regulated market or trading venue, identified by its Market Identifier Code |
| `Listing` | One exchange's entry for a security, with its ticker and listing period |
| `Fund` | A pooled investment vehicle with a portfolio of holdings: mutual fund, exchange-traded fund, closed-end fund, hedge fund, fund of funds or pension fund |
| `Offering` | The sale of newly issued securities to investors, distributed by one or more underwriters |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `LegalEntity` | `entityId` | STRING | Identifier of the entity, unique and stable |
| `LegalEntity` | `name` | STRING | Registered legal name, with its legal-form suffix |
| `LegalEntity` | `lei` | STRING | ISO 17442 Legal Entity Identifier (20 characters); empty when the entity has none |
| `LegalEntity` | `countryCode` | STRING | Country of incorporation, as an ISO 3166-1 two-letter code |
| `LegalEntity` | `sector` | STRING | Principal business activity under the user's industry classification; Government for sovereign and agency issuers |
| `Security` | `securityId` | STRING | Internal identifier of the security; market identifiers are held separately |
| `Security` | `name` | STRING | Issuer short name plus instrument description |
| `Security` | `securityType` | STRING | Kind of security: common or preferred share, depositary receipt, corporate, government or municipal bond, convertible bond, asset-backed or mortgage-backed security, money market instrument, or fund unit |
| `Security` | `cfiCode` | STRING | Six-letter ISO 10962 Classification of Financial Instruments code |
| `Security` | `currency` | STRING | Currency of denomination, as an ISO 4217 code |
| `Security` | `issueDate` | ZONED DATETIME | Date first issued; only the calendar date carries meaning |
| `Security` | `maturityDate` | ZONED DATETIME | Date the principal falls due; empty for shares, fund units and perpetual instruments |
| `Security` | `couponRate` | FLOAT | Interest rate as an annual percentage of face value; debt only |
| `Security` | `seniority` | STRING | Rank of a debt claim in liquidation: senior secured, senior unsecured, subordinated or junior subordinated |
| `Security` | `faceAmountOutstanding` | FLOAT | Principal outstanding, in whole units of the security's currency; debt only |
| `Security` | `securityForm` | STRING | How ownership is evidenced: registered, bearer, book entry, bearer and registered, or miscellaneous form |
| `Security` | `restriction` | STRING | US resale restriction: Rule 144A, Regulation S, Regulation D, or none |
| `Identifier` | `identifierId` | STRING | Scheme and value joined by a colon |
| `Identifier` | `scheme` | STRING | Identification scheme, such as ISIN, CUSIP, SEDOL, Valoren, Common Code or FIGI |
| `Identifier` | `value` | STRING | The identifier exactly as issued, upper case, without separators |
| `Exchange` | `mic` | STRING | ISO 10383 Market Identifier Code (four characters) |
| `Exchange` | `name` | STRING | Name of the exchange |
| `Exchange` | `countryCode` | STRING | Country where the exchange operates, as an ISO 3166-1 two-letter code |
| `Listing` | `listingId` | STRING | Identifier of the listing, unique and stable |
| `Listing` | `ticker` | STRING | Ticker symbol on the exchange — unique there at any one time, but reassignable after a delisting |
| `Listing` | `listingDate` | ZONED DATETIME | Date the security was admitted to trading on the exchange |
| `Listing` | `delistingDate` | ZONED DATETIME | Date it was delisted; empty while still listed |
| `Listing` | `isPrimary` | BOOLEAN | Whether this exchange is the security's home (primary) market |
| `Fund` | `fundId` | STRING | Identifier of the fund, unique and stable |
| `Fund` | `name` | STRING | Name of the fund |
| `Fund` | `fundType` | STRING | Mutual fund, exchange-traded fund, closed-end investment, hedge fund, fund of funds or pension fund |
| `Fund` | `domicile` | STRING | Country whose law the fund is constituted under |
| `Fund` | `baseCurrency` | STRING | Currency the fund reports in, as an ISO 4217 code |
| `Fund` | `totalNetAssets` | FLOAT | Total net assets at the reporting date, in whole units of the base currency |
| `Fund` | `reportingDate` | ZONED DATETIME | Date of the holdings snapshot the fund's holdings describe |
| `Offering` | `offeringId` | STRING | Identifier of the offering, unique and stable |
| `Offering` | `offeringType` | STRING | Public, private or exempt offering |
| `Offering` | `underwritingType` | STRING | Firm commitment (underwriters buy the whole issue) or best efforts |
| `Offering` | `closingDate` | ZONED DATETIME | Date the offering closed and securities were delivered |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `ISSUED_BY` | `Security` → `LegalEntity` | The entity that issued the security — for a depositary receipt the depositary bank, for a fund unit the fund vehicle. Exactly one per security |
| `DIRECTLY_CONSOLIDATED_BY` | `LegalEntity` → `LegalEntity` | The entity's direct parent; following these upward reaches the group's ultimate parent. At most one per entity |
| `IDENTIFIED_BY` | `Security` → `Identifier` | A market identifier of the security. At least one per security; an identifier on two securities is a data-quality defect |
| `LISTS` | `Listing` → `Security` | The security an exchange listing makes available. Exactly one per listing |
| `LISTED_ON` | `Listing` → `Exchange` | The exchange that manages the listing. Exactly one per listing |
| `REPRESENTS` | `Security` → `Security` | A depositary receipt's underlying share, whose issuer carries the real risk. At most one per receipt |
| `CONVERTIBLE_INTO` | `Security` → `Security` | The security a convertible or exchangeable converts into, possibly another issuer's share. At most one per convertible |
| `UNIT_OF` | `Security` → `Fund` | The fund a fund-unit security is a share of. At most one per security |
| `HOLDS` | `Fund` → `Security` | A position held by the fund at its reporting date; a holding of another fund's units is a look-through link |
| `MANAGED_BY` | `Fund` → `LegalEntity` | The fund's manager, which makes its investment decisions. Exactly one per fund |
| `OFFERS` | `Offering` → `Security` | A newly issued security sold in the offering. At least one per offering |
| `UNDERWRITTEN_BY` | `Offering` → `LegalEntity` | An underwriter of the offering. At least one per offering |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `REPRESENTS` | `multiplier` | FLOAT | Number of underlying shares one receipt represents; fractional when one receipt is part of a share |
| `CONVERTIBLE_INTO` | `conversionRatio` | FLOAT | Number of target shares received for one bond of 1,000 face amount, or one preferred share |
| `HOLDS` | `weightPct` | FLOAT | Market value of the position as a percentage (0–100) of the fund's total net assets |
| `HOLDS` | `marketValue` | FLOAT | Market value of the position, in whole units of the fund's base currency |
| `UNDERWRITTEN_BY` | `role` | STRING | The underwriter's role: bookrunner, lead manager, co-manager or selling group member |
