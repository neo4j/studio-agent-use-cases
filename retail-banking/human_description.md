# Retail Banking Fraud

Follow money, people and devices together to expose transaction rings, money mules, account takeovers and synthetic identities — fraud that only shows up when payments, identities and logins are read as one network.

## Overview

### Fraud and financial crime in retail banking

Retail banks move enormous numbers of small payments for millions of customers, and almost all of them are exactly what they appear to be. Fraud and financial-crime teams look for the small fraction that is not: money laundered through chains of accounts, accounts opened under invented identities, customers whose online banking has been taken over, and "money mules" — accounts recruited, or opened, to receive stolen money and pass it on before it can be recalled.

What these schemes share is that no single record gives them away. Each payment in a laundering ring is a plausible amount between plausible accounts. A synthetic identity passes onboarding because each of its details is real, even though the combination is not. A takeover looks like a customer logging in and paying someone. A mule account looks like a new customer receiving money from friends. The evidence is in the connections: who shares what with whom, where money goes next, and what happened just before.

Those connections cross systems that rarely meet. Payments sit in a core banking ledger, identity details in onboarding and know-your-customer (KYC) records, logins in the digital channel's logs, and country risk in a compliance policy. Joining them record by record is slow, and the useful questions — does this money come back to where it started, which customers share a phone, did this payment follow a login from a new device — are questions about paths, not about single records.

### What it helps with

The reference ontology puts payments, identities and digital access in one connected structure, so each scheme becomes a pattern that can be followed rather than a join across systems.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| Layering moves money through a chain of accounts and back, and no single payment looks wrong | Payments are entities between accounts, so a ring is a path that returns to its start, and the order and amount of each step can be checked along it |
| Synthetic identities are built from shared contact details and reused documents | Each email, phone, address, passport and driving licence is a single shared point, so customers who share several of them are directly connected, along with the accounts they hold |
| One device or one fraudster operates many customers' accounts | Logins record the device and network used, so a device used by many customers, and the accounts behind them, is one step away |
| A takeover is a login followed by a payment to someone new | A login from a device or country new to that customer can be lined up with the customer's payments and their payment history |
| Mule accounts are new, receive from many unrelated people and pass money on quickly | Accounts carry their opening date, and payments in and out carry timestamps, so age, fan-in and time-to-forward are measurable together |
| Money leaving for high-risk jurisdictions is layered first | Each account is tied to the country it is held in, with the institution's risk classification, so a payment abroad can be traced back through the accounts that fed it |
| Separate signals are weak; together they are strong | A payment ring whose members also share a device or an identifier connects the money layer to the people layer in one view |

Everything surfaced this way is an investigative lead, never proof. Households share addresses and landlines, families share tablets, refunds and loan repayments close loops, and people pay new friends from new phones. The value is in how many independent connections agree, and every result needs an analyst's review.

## Ontology

The reference ontology joins three layers around the customer. The money layer holds accounts and the payments between them; the identity layer holds the contact details and documents customers give; the digital layer holds the sessions customers log in with, and the devices and network addresses those sessions use. Countries tie the layers to geography and to risk.

Two design choices matter. A payment is an entity, not a link: it sits between the account it leaves and the account it reaches, so it can carry its own amount and time and be compared with its neighbours along a path. And every shared value — an email, a phone number, an address, a document, a device — is a single entity that all its users point to, so a shared detail is a direct connection between customers rather than a coincidence of matching text.

Accounts held at other institutions appear too, seen only through the payments that reach them or come from them, with their identifier and their country.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Customer` | A person who holds one or more of the institution's accounts, as primary or secondary holder. Identifiers and logins attach to the customer, so it is where identity, device use and money meet |
| `Account` | A bank account that sends or receives payments: held at this institution, or elsewhere and known only as the other side of a payment |
| `Transaction` | A single payment from one account to another, held as an entity so it can carry its own amount and time and be compared with the payments around it |
| `Country` | A country, by its two-letter ISO code: where an account is held, where an address is, or where a network address is located. Carries the institution's high-risk-jurisdiction classification |
| `Email` | An email address given by one or more customers |
| `Phone` | A telephone number given by one or more customers: a personal mobile, or a landline a household shares |
| `Address` | A postal address where customers live or have lived |
| `Passport` | A passport presented as proof of identity |
| `DrivingLicense` | A driving licence presented as proof of identity |
| `Session` | One login, or login attempt, on the bank's digital channel |
| `Device` | A phone, computer or tablet a customer banks from, identified by the fingerprint the digital channel assigns |
| `IP` | A network (IP) address sessions connect from, which places a session in a country |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Customer` | `customerId` | String | Identifier for the customer record, unique and stable |
| `Customer` | `firstName` | String | Given name, as recorded at onboarding |
| `Customer` | `lastName` | String | Family name, as recorded at onboarding |
| `Customer` | `dateOfBirth` | Zoned datetime | Date of birth; only the date carries meaning |
| `Account` | `accountNumber` | String | Account identifier: sort code and account number for UK accounts, IBAN for accounts abroad. Unique across all accounts |
| `Account` | `accountScope` | String | `INTERNAL` if held at this institution, `EXTERNAL` if held at another |
| `Account` | `accountType` | String | Product type of an internal account, such as current, savings or business; empty for external accounts |
| `Account` | `openedDate` | Zoned datetime | When the account was opened; empty for external accounts |
| `Transaction` | `transactionId` | String | Identifier for the payment, unique across the institution |
| `Transaction` | `amount` | Float | Value moved, in the currency's major units, always positive: direction is carried by the connections |
| `Transaction` | `currency` | String | ISO 4217 currency code of the amount; no conversion is performed |
| `Transaction` | `date` | Zoned datetime | When the payment executed — a true execution time, not a posting date |
| `Transaction` | `type` | String | Payment method or scheme, such as Faster Payments, BACS, SWIFT, card or direct debit |
| `Country` | `code` | String | Two-letter ISO 3166-1 country code |
| `Country` | `name` | String | Country name in English |
| `Country` | `isHighRiskJurisdiction` | Boolean | Whether the institution's risk policy classes the country as high-risk for money laundering — a policy setting, not a fact about the country |
| `Email` | `address` | String | The full email address, in lower case |
| `Email` | `domain` | String | The part after the `@` |
| `Phone` | `phoneNumber` | String | The number in international (E.164) form, starting with `+` and the country code |
| `Phone` | `countryCode` | String | International calling code, such as `+44` |
| `Address` | `addressId` | String | Single identifier built from the first line, post town and postcode, so the same address is always one entity |
| `Address` | `addressLine1` | String | House or building number and street |
| `Address` | `addressLine2` | String | Optional flat, building or estate |
| `Address` | `postTown` | String | Post town for delivery |
| `Address` | `postCode` | String | Postcode in standard form |
| `Passport` | `passportId` | String | Single identifier built from issuing country and passport number |
| `Passport` | `passportNumber` | String | Number as printed, unique only within the issuing country |
| `Passport` | `issuingCountry` | String | Two-letter code of the issuing government |
| `Passport` | `issueDate` | Zoned datetime | Date of issue |
| `Passport` | `expiryDate` | Zoned datetime | Date of expiry |
| `DrivingLicense` | `licenseId` | String | Single identifier built from issuing country and licence number |
| `DrivingLicense` | `licenseNumber` | String | Number as printed, unique only within the issuing country |
| `DrivingLicense` | `issuingCountry` | String | Two-letter code of the issuing authority |
| `DrivingLicense` | `issueDate` | Zoned datetime | Date of issue |
| `DrivingLicense` | `expiryDate` | Zoned datetime | Date of expiry |
| `Session` | `sessionId` | String | Identifier for the session |
| `Session` | `status` | String | Outcome: `success`, `failed`, `suspicious` (blocked or challenged by the bank's controls) or `timeout`. Only a successful session gives access |
| `Session` | `createdAt` | Zoned datetime | When the session started |
| `Device` | `deviceId` | String | Fingerprint the digital channel assigns to the device |
| `Device` | `deviceType` | String | `mobile`, `desktop`, `tablet` or `unknown` |
| `Device` | `userAgent` | String | Browser or app identification the device reported; descriptive only, as it is easily faked |
| `IP` | `ipAddress` | String | The address in standard form, IPv4 or IPv6 |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `HAS_ACCOUNT` | `Customer` → `Account` | The customer holds the account. Every internal account has exactly one primary holder and may have secondary holders; external accounts have none |
| `PERFORMS` | `Account` → `Transaction` | The account the money leaves. Exactly one per payment |
| `BENEFITS_TO` | `Transaction` → `Account` | The account the money reaches. Exactly one per payment |
| `IS_HOSTED` | `Account` → `Country` | The country the account is held in. Exactly one per account |
| `HAS_EMAIL` | `Customer` → `Email` | An email address the customer has given; an address may be shared by several customers |
| `HAS_PHONE` | `Customer` → `Phone` | A phone number the customer has given; a number may be shared |
| `HAS_ADDRESS` | `Customer` → `Address` | An address the customer lives or has lived at; an address may be shared |
| `HAS_PASSPORT` | `Customer` → `Passport` | A passport the customer presented; one passport on several customers is a strong warning sign |
| `HAS_DRIVING_LICENSE` | `Customer` → `DrivingLicense` | A driving licence the customer presented; likewise |
| `LOCATED_IN` | `Address` → `Country` | The country the address is in. Exactly one per address |
| `LOCATED_IN` | `IP` → `Country` | The country the network address is located in, when it can be placed. At most one per address |
| `HAS_SESSION` | `Customer` → `Session` | The session was a login, or attempted login, to the customer's digital banking. Exactly one customer per session |
| `SESSION_USES_DEVICE` | `Session` → `Device` | The device the session ran on. Exactly one per session; a device may serve many customers |
| `USES_IP` | `Session` → `IP` | The network address the session came from. Exactly one per session |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `HAS_ACCOUNT` | `role` | String | `PRIMARY` for the primary owner, `SECONDARY` for a co-owner such as the second name on a joint account |
| `HAS_ACCOUNT` | `since` | Zoned datetime | When the customer became a holder |
| `HAS_EMAIL` | `since` | Zoned datetime | When the address was first recorded for the customer |
| `HAS_PHONE` | `since` | Zoned datetime | When the number was first recorded for the customer |
| `HAS_ADDRESS` | `addedAt` | Zoned datetime | When the address was first linked to the customer |
| `HAS_ADDRESS` | `lastChangedAt` | Zoned datetime | When the address details were last updated |
| `HAS_ADDRESS` | `isCurrent` | Boolean | Whether it is the customer's current address |
| `HAS_PASSPORT` | `verificationDate` | Zoned datetime | When the bank verified the passport |
| `HAS_PASSPORT` | `verificationMethod` | String | How it was verified, such as in branch, by digital scan or by video |
| `HAS_PASSPORT` | `verificationStatus` | String | `VERIFIED`, `PENDING`, `REJECTED` or `EXPIRED` |
| `HAS_DRIVING_LICENSE` | `verificationDate` | Zoned datetime | When the bank verified the licence |
| `HAS_DRIVING_LICENSE` | `verificationMethod` | String | How it was verified |
| `HAS_DRIVING_LICENSE` | `verificationStatus` | String | `VERIFIED`, `PENDING`, `REJECTED` or `EXPIRED` |
