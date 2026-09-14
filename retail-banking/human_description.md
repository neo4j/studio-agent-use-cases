# Retail Banking

Spot money moved through a chain of accounts and back to where it started, by treating payments as a network rather than a ledger.

## Overview

### Transaction fraud in retail banking

Retail banks move enormous numbers of small payments, and the great majority are exactly what they appear to be. Financial crime teams sit downstream of that flow, looking for the fraction that is moving stolen or illicit money — and the methods that matter most to them are the ones built specifically to survive a look at any single payment.

The pattern this reference ontology is built around is the **transaction ring**: money that leaves an account, passes through a chain of intermediary accounts, and arrives back at its origin. Rings appear in a few recognisable forms:

- **Layering** — moving funds through several hands to break the audit trail between where money came from and who ultimately benefited.
- **Authorised push payment fraud** — a victim is persuaded to send money onward, and it is then shuffled through mule accounts fast enough to outrun a recall.
- **Circular trading** — payments arranged to manufacture apparent activity on accounts that have no real business between them.

Every payment in a ring is individually unremarkable: a plausible amount, a plausible counterparty, nothing to trip a per-transaction rule. The shape only exists at the level of the chain, and it only becomes visible when you follow the payments and find they return to their starting point.

That is genuinely awkward in a conventional ledger. Asking "does money leaving this account come back to it?" means joining the payments table to itself once for every hop, and the number of joins depends on how long the ring is — which is exactly what you do not know in advance. Most teams cap the search at three or four hops because the query stops being practical, and rings longer than the cap simply go unseen.

### What it helps with

Modelling payments as a network turns a variable-length self-join into a traversal, and three checks that are hard to write in a ledger become natural.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| A ring's length is unknown, so the search depth cannot be fixed in advance | Walk the payment chain outward from an account until it returns, letting the path length vary rather than fixing it in the query's shape |
| No single payment in a ring looks wrong | Evaluate the closed chain as a whole, so the evidence is the shape of the cycle rather than any property of one payment |
| Cycles alone are far too noisy to act on | Require the payments around the ring to run in chronological order, which discards the cycles that are merely an artefact of two accounts trading normally |
| Layering skims a cut at each hop, and simple cycle checks miss it | Test whether the amount decays consistently as it moves around the ring — the signature of each intermediary taking a share |
| Investigators need to see the chain, not read it | Return the ring and the accounts on it as a picture, so a reviewer can judge it at a glance |
| The same accounts recur across separate rings | Traverse outward from a known ring to the payments and accounts around it, surfacing the wider network a single cycle sits inside |

Everything surfaced this way is an investigative lead, never proof. Closed loops have entirely legitimate explanations — refunds, treasury sweeps, transfers between a customer's own accounts — and a chronological, decaying ring is a stronger signal than a bare cycle rather than a conclusion. Real behaviour also branches instead of forming tidy circles, so this catches a recognisable shape, not all coordinated movement.

## Ontology

The reference ontology is as small as it can usefully be: two kinds of thing and two kinds of connection.

The design decision worth understanding is that a payment is **a thing, not a link**. The obvious model joins two accounts directly and hangs the amount and date on that link. This one places the payment between them as an entity in its own right, with the originating account pointing into it and the payment pointing on to the beneficiary.

That indirection is what makes the useful checks expressible. Because a payment is an entity, it can be reached from either end, compared with its neighbours around a ring, and ordered against them — which is what the chronology and amount-decay tests depend on. It also means an account carries no customer, product or balance detail: it is a point money passes through, and everything interesting is in how those points connect.

Direction matters throughout. Each payment has exactly one originating account and exactly one beneficiary, and that orientation is what distinguishes a genuine cycle from accounts that merely happen to be connected.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Account` | A retail bank account that can send and receive payments. Carries only its identifier — no customer, product or balance detail — so it is a point money passes through rather than a party profile |
| `Transaction` | A single payment moving money from one account to another. Held as an entity rather than as a connection so it can carry its own amount and timestamp and be reached from either end, which is what makes the chronology and decay checks possible |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Account` | `accountNumber` | Integer | Identifier for the account, unique across the institution. An internal account key rather than a printed sort code and number, and stable for the life of the account |
| `Transaction` | `transactionId` | String | Identifier for the payment, unique across the institution — the source system's own transaction reference |
| `Transaction` | `amount` | Float | Value of money moved, in the major units of the currency rather than in minor units. Always positive: direction is carried by the connections, not by the sign |
| `Transaction` | `currency` | String | ISO 4217 alphabetic currency code of the amount, recorded in whatever case the source system supplies. Amounts around a ring are only comparable when every payment shares one currency; no conversion is performed |
| `Transaction` | `date` | Zoned datetime | Instant the payment was executed. Ordering on this is what separates a ring moving money forward in time from an arbitrary cycle, so it is the true execution timestamp rather than a posting or value date |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `PERFORMS` | `Account` → `Transaction` | Attributes the payment to the account the money leaves. Exactly one originating account per payment; an account may perform many payments, or none |
| `BENEFITS_TO` | `Transaction` → `Account` | Credits the payment to the account receiving the money. Exactly one beneficiary per payment; an account may benefit from many payments, or none. Following this and then out again through the beneficiary's own payments is how a ring is walked |
