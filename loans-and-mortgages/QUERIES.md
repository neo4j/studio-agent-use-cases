# Loans and Mortgages — Query Guidance

Cypher for the `loans-and-mortgages` use case. Every query references only labels, relationship types, and properties defined in the reference ontology (`ONTOLOGY.json`). No query writes to the database.

## Prerequisites

- Neo4j 5.x and Cypher 5, at a release that supports `COUNT {}` and `COLLECT {}` subqueries (5.6 or later). No APOC or Graph Data Science required.
- The graph is loaded through the Import flow from `ONTOLOGY.json` — the bundled `sample-data/` CSVs, or the user's own data mapped onto the reference ontology.
- Types matter to the queries: amounts, rates and ratios are FLOAT; `creditScore`, `termMonths`, `dwellingUnits` and `daysLate` are INTEGER; and every date is a ZONED DATETIME at midnight UTC, because Import does not accept DATE for local CSV files. Only the calendar date carries meaning. Comparisons and `duration` arithmetic work directly; compare against `datetime(...)`, never `date(...)` (a datetime compared with a date is null), and wrap a value in `date()` to display it.
- Amounts are US dollars and assume a single-currency portfolio. Percentages (`interestRate`, `ltvAtOrigination`, `dtiRatio`) are held as percentages, so 80 means 80%.
- A missed installment is a `Payment` with `amountPaid` below `amountDue`; `Loan.status` is the servicer's own snapshot as of `balanceAsOfDate`. The queries use each for what it is: payment-level questions read `Payment`, status questions read `Loan.status`.
- No `SETUP.md` statements are needed, and no query creates a label, relationship type, or property.
- Queries run from simple lookups, through portfolio and delinquency views, to the collateral, connected-party and origination-quality patterns.

## Adapting these queries

These queries assume the reference ontology in `ONTOLOGY.json`. When the user's database differs — their own ontology, a modified one, or a database that predates this package — the queries are patterns to rebuild, not Cypher to run.

1. Read the live schema (`CALL db.schema.visualization()`, `SHOW CONSTRAINTS`) rather than assuming the reference ontology applies.
2. Map their labels onto the role map in `SKILL.md`. A role with no counterpart means the pattern below it has no analogue — say so rather than forcing a fit.
3. Rewrite from the pattern, and update the annotation block to describe what the rewritten query actually does.

## Loan overview

```cypher
/*
 * @name           Loan overview
 * @description    Gathers everything the reference ontology holds about one
 *                 loan into a single row: terms and servicer snapshot, the
 *                 product and officer from its application, lender and
 *                 servicer, the securing property, every borrower with
 *                 their role, guarantors, and a payment-history summary.
 * @params         loanId - Loan.loanId of the loan to describe.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row: loan terms and status, product, lender, servicer,
 *                 loanOfficer, property (null when unsecured), borrowers as
 *                 "name (borrowerRole)", guarantors, paymentsRecorded and
 *                 paymentsMissed (installments with amountPaid below
 *                 amountDue). No row when the loanId does not exist.
 * @usage          The starting point for any question about a single loan,
 *                 and a quick check that an import connected every part of
 *                 it. ltvAtOrigination is this loan alone; use Stacked liens
 *                 with high combined LTV for the property-level view.
 * @tags           loan, lookup, overview
 * @sample         Bundled sample data only: $loanId = 'L-00712' returns 1
 *                 row — a Fixed-rate home equity loan in subordinate lien
 *                 position, status in default, lent by Lakeshore Mortgage
 *                 Company, serviced by Meridian Servicing Group, officer
 *                 Carolyn Jensen, borrower Brandon Wagner (primary
 *                 borrower), no guarantors, 10 payments recorded, 9 missed.
 */
MATCH (l:Loan {loanId: $loanId})
MATCH (app:LoanApplication)-[:RESULTED_IN]->(l)
MATCH (app)-[:FOR_PRODUCT]->(prod:LoanProduct)
MATCH (l)-[:LENT_BY]->(lender:FinancialInstitution)
MATCH (l)-[:SERVICED_BY]->(servicer:FinancialInstitution)
OPTIONAL MATCH (app)-[:HANDLED_BY]->(officer:LoanOfficer)
OPTIONAL MATCH (l)-[:SECURED_BY]->(prop:Property)
RETURN l.loanId AS loanId, prod.name AS product, l.status AS status,
       l.principalAmount AS principalAmount, l.currentBalance AS currentBalance,
       date(l.balanceAsOfDate) AS balanceAsOfDate, l.interestRate AS interestRate,
       date(l.originationDate) AS originationDate, date(l.maturityDate) AS maturityDate,
       l.lienPosition AS lienPosition, l.ltvAtOrigination AS ltvAtOrigination,
       lender.name AS lender, servicer.name AS servicer, officer.name AS loanOfficer,
       prop.address + ', ' + prop.city + ', ' + prop.state AS property,
       COLLECT { MATCH (b:Person)-[r:BORROWER_ON]->(l) RETURN b.name + ' (' + r.borrowerRole + ')' } AS borrowers,
       COLLECT { MATCH (g:Person)-[:GUARANTEES]->(l) RETURN g.name } AS guarantors,
       COUNT { (l)-[:HAS_PAYMENT]->(:Payment) } AS paymentsRecorded,
       COUNT { (l)-[:HAS_PAYMENT]->(p:Payment) WHERE p.amountPaid < p.amountDue } AS paymentsMissed
```

## Person's lending network

```cypher
/*
 * @name           Person's lending network
 * @description    Draws one person's position across the portfolio: their
 *                 applications, the loans they borrow on or guarantee, the
 *                 property and servicer behind each of those loans, and the
 *                 other people on the same loans.
 * @params         personId - Person.personId of the person to draw.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Paths for Browser or Bloom to draw, one per row: Person →
 *                 LoanApplication or Loan; Person → Loan → Property or
 *                 FinancialInstitution; and Person → Loan ← Person for each
 *                 other borrower or guarantor. UNION removes duplicates.
 * @usage          Visual, not tabular. The third part is what turns a single
 *                 customer view into a connected-party view: a co-borrower
 *                 or guarantor reached here is exposed to the same loan. A
 *                 person on many loans draws a busy picture; read Total
 *                 exposure per person first to see how many open loans they
 *                 touch.
 * @tags           visualisation, person, borrower, guarantor, network
 * @sample         Bundled sample data only: $personId = 'P-0739' (Michael
 *                 Lee) returns 11 paths — 2 applications, 3 loans (primary
 *                 borrower on L-00736, co-borrower on L-00737, guarantor of
 *                 L-00738), 4 property or servicer paths, and 2 other
 *                 people: Michael Cox and Nathan Jensen.
 */
MATCH path = (:Person {personId: $personId})-[:APPLIED_FOR|BORROWER_ON|GUARANTEES]->()
RETURN path
UNION
MATCH path = (:Person {personId: $personId})-[:BORROWER_ON|GUARANTEES]->(:Loan)-[:SECURED_BY|SERVICED_BY]->()
RETURN path
UNION
MATCH path = (p:Person {personId: $personId})-[:BORROWER_ON|GUARANTEES]->(:Loan)<-[:BORROWER_ON|GUARANTEES]-(other:Person)
WHERE other <> p
RETURN path
```

## Portfolio by product

```cypher
/*
 * @name           Portfolio by product
 * @description    Summarises open loans by the product they were written
 *                 under, reached through the application each loan resulted
 *                 from: count, outstanding balance, average note rate, and
 *                 the share that is delinquent or in default.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per product with at least one open loan: product,
 *                 marketCategory, openLoans, outstandingBalance (sum of
 *                 currentBalance, US dollars), avgInterestRate (unweighted
 *                 mean of interestRate, percent), troubledLoans (status
 *                 delinquent or in default) and troubledPct, ordered by
 *                 outstandingBalance descending.
 * @usage          Open means any status other than paid in full. The
 *                 average rate is a simple mean, not balance-weighted; weight
 *                 by currentBalance for a portfolio yield. Products with few
 *                 open loans give volatile percentages.
 * @tags           portfolio, product, balance, delinquency
 * @sample         Bundled sample data only: returns 7 rows, led by
 *                 30-year fixed-rate mortgage (250 open loans, 12 troubled);
 *                 Fixed-rate home equity loan has the highest troubledPct
 *                 (25.0).
 */
MATCH (prod:LoanProduct)<-[:FOR_PRODUCT]-(:LoanApplication)-[:RESULTED_IN]->(l:Loan)
WHERE l.status <> 'paid in full'
WITH prod, count(l) AS openLoans, sum(l.currentBalance) AS outstandingBalance,
     avg(l.interestRate) AS avgRate,
     sum(CASE WHEN l.status IN ['delinquent', 'in default'] THEN 1 ELSE 0 END) AS troubledLoans
RETURN prod.name AS product, prod.marketCategory AS marketCategory, openLoans,
       round(outstandingBalance, 2) AS outstandingBalance, round(avgRate, 2) AS avgInterestRate,
       troubledLoans, round(100.0 * troubledLoans / openLoans, 1) AS troubledPct
ORDER BY outstandingBalance DESC
```

## Application outcomes by product

```cypher
/*
 * @name           Application outcomes by product
 * @description    Counts applications by product and HMDA disposition:
 *                 how many became loans, were denied, were withdrawn, or
 *                 ended another way, and the pull-through rate.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per product: product, applications, originated
 *                 (disposition loan originated), denied (application denied
 *                 or preapproval request denied), withdrawn, otherOutcomes
 *                 (approved but not accepted, file closed for
 *                 incompleteness, and the rest) and pullThroughPct
 *                 (originated as a percentage of applications), ordered by
 *                 applications descending.
 * @usage          Covers every application ever recorded; add a filter on
 *                 applicationDate to compare periods. Pull-through is
 *                 operational, not a credit-quality measure: withdrawals
 *                 and incomplete files lower it as much as denials do.
 * @tags           application, disposition, pipeline, product
 * @sample         Bundled sample data only: returns 7 rows, led by
 *                 30-year fixed-rate mortgage (421 applications, 330
 *                 originated, 54 denied, 78.4% pull-through).
 */
MATCH (a:LoanApplication)-[:FOR_PRODUCT]->(prod:LoanProduct)
WITH prod, count(a) AS applications,
     sum(CASE WHEN a.disposition = 'loan originated' THEN 1 ELSE 0 END) AS originated,
     sum(CASE WHEN a.disposition IN ['application denied', 'preapproval request denied'] THEN 1 ELSE 0 END) AS denied,
     sum(CASE WHEN a.disposition = 'application withdrawn' THEN 1 ELSE 0 END) AS withdrawn
RETURN prod.name AS product, applications, originated, denied, withdrawn,
       applications - originated - denied - withdrawn AS otherOutcomes,
       round(100.0 * originated / applications, 1) AS pullThroughPct
ORDER BY applications DESC
```

## Denial reasons and applicant profile

```cypher
/*
 * @name           Denial reasons and applicant profile
 * @description    Ranks the primary denial reasons on denied applications
 *                 and profiles the applicants behind each: average credit
 *                 score at application, average debt-to-income ratio, and
 *                 the products involved.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per denialReason ('not recorded' where a denial
 *                 has none): denials, avgCreditScore, avgDtiRatio (percent)
 *                 and products, ordered by denials descending.
 * @usage          Denied means disposition application denied or
 *                 preapproval request denied. Only the primary reason is
 *                 held, so a denial with several reasons counts once, under
 *                 the first. Read the averages as a check that each reason
 *                 is applied consistently (a debt-to-income denial should
 *                 carry a high dtiRatio). This is an operational view only:
 *                 fair-lending analysis needs demographic data and controls
 *                 this reference ontology does not hold.
 * @tags           application, denial, underwriting
 * @sample         Bundled sample data only: returns 9 rows, led by
 *                 debt-to-income ratio (66 denials, average dtiRatio 51.1)
 *                 and insufficient credit history (41).
 */
MATCH (a:LoanApplication)-[:FOR_PRODUCT]->(prod:LoanProduct)
WHERE a.disposition IN ['application denied', 'preapproval request denied']
WITH coalesce(a.denialReason, 'not recorded') AS denialReason, a, prod
RETURN denialReason, count(a) AS denials,
       round(avg(a.creditScore)) AS avgCreditScore, round(avg(a.dtiRatio), 1) AS avgDtiRatio,
       collect(DISTINCT prod.name) AS products
ORDER BY denials DESC
```

## Loans with missed payments

```cypher
/*
 * @name           Loans with missed payments
 * @description    Lists loans with at least a given number of missed
 *                 installments in their payment history — a Payment whose
 *                 amountPaid is below amountDue — with the oldest missed due
 *                 date, the servicer, and the primary borrower.
 * @params         minMissed - Minimum missed installments for a loan to be
 *                     listed. Integer. Start at 2: two unpaid monthly
 *                     installments is the conventional 30-plus-days
 *                     delinquency mark, where a single one is often a
 *                     timing slip.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per qualifying loan: loanId, status (the
 *                 servicer's Loan.status), missedPayments, oldestMissedDue,
 *                 currentBalance, primaryBorrower and servicer, ordered by
 *                 missedPayments descending then oldestMissedDue.
 * @usage          Counts missed installments in the recorded history, so a
 *                 loan whose history starts recently can only show recent
 *                 misses. Partial payments count as missed. Compare
 *                 missedPayments with status: a loan with misses but status
 *                 current, or the reverse, points at a timing difference or
 *                 a servicing data problem.
 * @tags           delinquency, payment, servicing
 * @sample         Bundled sample data only: $minMissed = 2 returns 44 rows
 *                 — 31 loans in default and 13 delinquent; $minMissed = 1
 *                 adds 3 current loans with a single missed installment.
 */
MATCH (l:Loan)-[:HAS_PAYMENT]->(p:Payment)
WHERE p.amountPaid < p.amountDue
WITH l, count(p) AS missedPayments, date(min(p.dueDate)) AS oldestMissedDue
WHERE missedPayments >= $minMissed
MATCH (l)-[:SERVICED_BY]->(servicer:FinancialInstitution)
OPTIONAL MATCH (b:Person)-[:BORROWER_ON {borrowerRole: 'primary borrower'}]->(l)
RETURN l.loanId AS loanId, l.status AS status, missedPayments, oldestMissedDue,
       l.currentBalance AS currentBalance, b.name AS primaryBorrower, servicer.name AS servicer
ORDER BY missedPayments DESC, oldestMissedDue
```

## Delinquency by servicer

```cypher
/*
 * @name           Delinquency by servicer
 * @description    Compares servicers by the share of the open loans they
 *                 service that are delinquent or in default.
 * @params         None
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per servicing institution with open loans:
 *                 servicer, openLoans, delinquent, inDefault and troubledPct
 *                 ((delinquent + inDefault) as a percentage of openLoans),
 *                 ordered by troubledPct descending.
 * @usage          A servicer inherits the credit quality of the lenders whose
 *                 loans it services, so a high rate is a lead to follow back
 *                 through SERVICED_BY and LENT_BY to who originated those
 *                 loans, not a verdict on the servicer.
 * @tags           servicing, delinquency, portfolio
 * @sample         Bundled sample data only: returns 4 rows, led by
 *                 Meridian Servicing Group (169 open loans, 4 delinquent, 16
 *                 in default, 11.8%).
 */
MATCH (l:Loan)-[:SERVICED_BY]->(s:FinancialInstitution)
WHERE l.status <> 'paid in full'
WITH s, count(l) AS openLoans,
     sum(CASE WHEN l.status = 'delinquent' THEN 1 ELSE 0 END) AS delinquent,
     sum(CASE WHEN l.status = 'in default' THEN 1 ELSE 0 END) AS inDefault
RETURN s.name AS servicer, openLoans, delinquent, inDefault,
       round(100.0 * (delinquent + inDefault) / openLoans, 1) AS troubledPct
ORDER BY troubledPct DESC
```

## Stacked liens with high combined LTV

```cypher
/*
 * @name           Stacked liens with high combined LTV
 * @description    Finds properties securing two or more open loans and
 *                 computes combined loan-to-value: the summed currentBalance
 *                 of every open loan secured on the property, as a
 *                 percentage of its most recent appraisedValue. Returns the
 *                 properties above a ceiling.
 * @params         maxCltv - Combined LTV, in percent, above which a property
 *                     is returned. Float. Start at 90: lenders commonly cap
 *                     combined LTV for home-equity lending between 80 and
 *                     90%, so a property above 90 is outside typical policy.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per property: propertyId, property address,
 *                 openLiens (each loanId with its lienPosition),
 *                 combinedBalance (US dollars), latestAppraisedValue,
 *                 latestAppraisalDate and combinedLtv (percent), ordered by
 *                 combinedLtv descending.
 * @usage          The liens are often held by different lenders, which is
 *                 why no single lender's view shows the combined figure.
 *                 The most recent appraisal is used whatever its purpose,
 *                 so a lower valuation taken for a declined application
 *                 still counts; read the appraisal date. A high figure
 *                 against a recent, sharply higher appraisal is a different
 *                 problem — see Rapid appraisal increases on the same
 *                 property. Lower maxCltv towards 80 for a wider watch
 *                 list.
 * @tags           collateral, combined-ltv, lien, property
 * @sample         Bundled sample data only: $maxCltv = 90 returns 8 rows,
 *                 led by PR-0402 (combinedLtv 105.33) and PR-0403 (102.48);
 *                 $maxCltv = 85 returns 14.
 */
MATCH (prop:Property)<-[:SECURED_BY]-(l:Loan)
WHERE l.status <> 'paid in full'
WITH prop, count(l) AS lienCount, sum(l.currentBalance) AS combinedBalance,
     collect(l.loanId + ' (' + coalesce(l.lienPosition, 'lien position not recorded') + ')') AS openLiens
WHERE lienCount >= 2
MATCH (prop)<-[:VALUES]-(a:Appraisal)
WITH prop, openLiens, combinedBalance, a
ORDER BY a.appraisalDate DESC
WITH prop, openLiens, combinedBalance, head(collect(a)) AS latest
WITH prop, openLiens, combinedBalance, latest,
     round(100.0 * combinedBalance / latest.appraisedValue, 2) AS combinedLtv
WHERE combinedLtv > $maxCltv
RETURN prop.propertyId AS propertyId,
       prop.address + ', ' + prop.city + ', ' + prop.state AS property,
       openLiens, round(combinedBalance, 2) AS combinedBalance,
       latest.appraisedValue AS latestAppraisedValue,
       date(latest.appraisalDate) AS latestAppraisalDate, combinedLtv
ORDER BY combinedLtv DESC
```

## Rapid appraisal increases on the same property

```cypher
/*
 * @name           Rapid appraisal increases on the same property
 * @description    Finds pairs of appraisals of the same property where the
 *                 later value exceeds the earlier by at least a given
 *                 percentage within a given number of months, and lists the
 *                 loans secured on the property since the later appraisal,
 *                 with their status and originating officer.
 * @params         minIncreasePct - Minimum rise in appraisedValue, in
 *                     percent of the earlier value. Float. Start at 20:
 *                     residential prices rarely rise 20% in a year outside
 *                     exceptional local markets.
 *                 maxMonths - Longest gap, in months, between the two
 *                     appraisal dates. Integer. Start at 12, so ordinary
 *                     appreciation over several years is not mistaken for a
 *                     jump.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per qualifying pair: propertyId, property,
 *                 earlierDate, earlierValue, laterDate, laterValue,
 *                 increasePct and loansAfterIncrease (each as "loanId
 *                 (status, officer name)"), ordered by increasePct
 *                 descending.
 * @usage          A sharp rise just before new borrowing against the
 *                 property is a classic sign of an inflated valuation
 *                 supporting a second lien. Renovation, a stale earlier
 *                 appraisal or a hot local market are innocent
 *                 explanations, so compare against the local house-price
 *                 index before treating a hit as more than a lead. Widen
 *                 maxMonths to 36 or lower minIncreasePct to 15 to see the
 *                 slower rises around the cut-off.
 * @tags           appraisal, collateral, valuation, fraud-signal
 * @sample         Bundled sample data only: $minIncreasePct = 20,
 *                 $maxMonths = 12 returns 6 rows, PR-0404 (54.4%) to
 *                 PR-0408 (32.9%); each lists one loan in default
 *                 originated by Carolyn Jensen or Adam Schmidt.
 */
MATCH (prop:Property)<-[:VALUES]-(earlier:Appraisal), (prop)<-[:VALUES]-(later:Appraisal)
WHERE earlier.appraisalDate < later.appraisalDate
  AND later.appraisalDate <= earlier.appraisalDate + duration({months: $maxMonths})
  AND later.appraisedValue >= earlier.appraisedValue * (1 + $minIncreasePct / 100.0)
RETURN prop.propertyId AS propertyId,
       prop.address + ', ' + prop.city + ', ' + prop.state AS property,
       date(earlier.appraisalDate) AS earlierDate, earlier.appraisedValue AS earlierValue,
       date(later.appraisalDate) AS laterDate, later.appraisedValue AS laterValue,
       round(100.0 * (later.appraisedValue / earlier.appraisedValue - 1), 1) AS increasePct,
       COLLECT {
         MATCH (prop)<-[:SECURED_BY]-(l:Loan)
         WHERE l.originationDate >= later.appraisalDate
         OPTIONAL MATCH (l)<-[:RESULTED_IN]-(:LoanApplication)-[:HANDLED_BY]->(o:LoanOfficer)
         RETURN l.loanId + ' (' + l.status + ', ' + coalesce(o.name, 'no officer') + ')'
       } AS loansAfterIncrease
ORDER BY increasePct DESC
```

## Total exposure per person

```cypher
/*
 * @name           Total exposure per person
 * @description    Ranks people by everything they are liable for across the
 *                 portfolio: the currentBalance of every open loan they
 *                 borrow on (as primary borrower or co-borrower) plus every
 *                 open loan they guarantee.
 * @params         limit - Number of people to return. Integer. Start at 20,
 *                     a list a reviewer can read in one pass.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        Up to limit rows: personId, name, openLoans,
 *                 borrowedBalance, guaranteedBalance and totalExposure (US
 *                 dollars), ordered by totalExposure descending.
 * @usage          Co-borrowers are jointly and severally liable, so each is
 *                 charged the full balance, and a guarantee is taken to
 *                 cover the full balance; summing totalExposure across
 *                 people therefore double counts shared loans by design.
 *                 Single-loan borrowers of a large mortgage rank high too:
 *                 read openLoans and guaranteedBalance to find the people
 *                 whose exposure only appears once loans are connected.
 * @tags           exposure, connected-party, borrower, guarantor
 * @sample         Bundled sample data only: $limit = 10 returns 10 rows,
 *                 led by Jeremy Howard (P-0754): 6 open loans, borrowed
 *                 1360920.79, guaranteed 80853.44, total 1441774.23.
 */
MATCH (p:Person)-[r:BORROWER_ON|GUARANTEES]->(l:Loan)
WHERE l.status <> 'paid in full'
WITH p, count(DISTINCT l) AS openLoans,
     sum(CASE WHEN type(r) = 'BORROWER_ON' THEN l.currentBalance ELSE 0 END) AS borrowedBalance,
     sum(CASE WHEN type(r) = 'GUARANTEES' THEN l.currentBalance ELSE 0 END) AS guaranteedBalance
RETURN p.personId AS personId, p.name AS name, openLoans,
       round(borrowedBalance, 2) AS borrowedBalance, round(guaranteedBalance, 2) AS guaranteedBalance,
       round(borrowedBalance + guaranteedBalance, 2) AS totalExposure
ORDER BY totalExposure DESC
LIMIT $limit
```

## Default contagion through borrowers and guarantors

```cypher
/*
 * @name           Default contagion through borrowers and guarantors
 * @description    Finds people who borrow on a troubled loan and are also
 *                 a borrower, co-borrower or guarantor on another loan that
 *                 is still performing — the loans a default is most likely
 *                 to spread to.
 * @params         statuses - List of Loan.status values that mark a loan as
 *                     troubled. Start at ['in default']; widen to
 *                     ['delinquent', 'in default'] for an earlier warning.
 * @prerequisites  None beyond the imported reference ontology.
 * @returns        One row per person and exposed loan: personId, name,
 *                 troubledLoans (their loans in the given statuses),
 *                 exposedLoan, role (primary borrower, co-borrower or
 *                 guarantor), exposedStatus and exposedBalance, ordered by
 *                 personId then exposedLoan.
 * @usage          An exposed loan is any loan in neither the given statuses
 *                 nor paid in full. Includes a borrower's other loans as
 *                 well as loans reached through guarantees: a borrower in
 *                 default on a second lien is a risk to their first
 *                 mortgage too. Exposure is not loss — the exposed
 *                 borrower may be paying perfectly well — so treat each row
 *                 as a loan to review, not a loss estimate.
 * @tags           contagion, connected-party, guarantor, default
 * @sample         Bundled sample data only: $statuses = ['in default']
 *                 returns 13 rows for 11 people, including Michael Lee
 *                 (P-0739) on L-00737 (co-borrower) and L-00738
 *                 (guarantor); ['delinquent', 'in default'] returns 15.
 */
MATCH (p:Person)-[:BORROWER_ON]->(troubled:Loan)
WHERE troubled.status IN $statuses
WITH p, collect(troubled.loanId) AS troubledLoans
MATCH (p)-[r:BORROWER_ON|GUARANTEES]->(other:Loan)
WHERE NOT other.status IN $statuses AND other.status <> 'paid in full'
RETURN p.personId AS personId, p.name AS name, troubledLoans,
       other.loanId AS exposedLoan,
       CASE type(r) WHEN 'GUARANTEES' THEN 'guarantor' ELSE r.borrowerRole END AS role,
       other.status AS exposedStatus, other.currentBalance AS exposedBalance
ORDER BY personId, exposedLoan
```

## Early payment defaults by loan officer

```cypher
/*
 * @name           Early payment defaults by loan officer
 * @description    Measures early payment default (EPD) — an installment
 *                 missed, or paid 30 or more days late, within the first
 *                 months after origination — per originating loan officer,
 *                 and returns officers whose EPD rate is a multiple of the
 *                 rate across all officers' loans in the same cohort.
 * @params         fromDate - Earliest originationDate in the cohort, as an
 *                     ISO date string, read as midnight UTC. Set it one month before the
 *                     earliest Payment.dueDate in the database, so every
 *                     loan counted has its first payments recorded.
 *                 months - Length of the early window after origination.
 *                     Integer. Start at 6; early payment default is
 *                     conventionally measured over the first three to
 *                     twelve months.
 *                 minLoans - Minimum loans an officer must have in the
 *                     cohort to be rated. Integer. Start at 5, so a single
 *                     bad loan cannot make a rate; no strong prior.
 *                 minRatio - How many times the cohort-wide EPD rate an
 *                     officer's rate must reach. Float. Start at 2.0; no
 *                     strong prior, so read the full list with 1.0 first.
 * @prerequisites  None beyond the imported reference ontology. Loans whose
 *                 application has no HANDLED_BY officer are left out of the
 *                 cohort.
 * @returns        One row per flagged officer: officerId, loanOfficer,
 *                 institution, loans, earlyDefaults, epdRatePct and
 *                 portfolioRatePct, ordered by EPD rate then loans.
 * @usage          A concentration of early defaults on one originator is a
 *                 standard origination-quality and broker-fraud signal, but
 *                 also follows from the borrowers an officer serves; read
 *                 the loans before concluding anything. Loans originated
 *                 near the end of the history have had less time to
 *                 default, which understates every rate equally.
 * @tags           origination, early-payment-default, loan-officer, quality
 * @sample         Bundled sample data only: $fromDate = '2025-09-01',
 *                 $months = 6, $minLoans = 5, $minRatio = 2.0 returns 2
 *                 rows — Carolyn Jensen (LO-020) and Adam Schmidt (LO-021)
 *                 of Lakeshore Mortgage Company, 7 early defaults in 18
 *                 loans each (38.9% against 15.8%).
 */
MATCH (o:LoanOfficer)<-[:HANDLED_BY]-(:LoanApplication)-[:RESULTED_IN]->(l:Loan)
WHERE l.originationDate >= datetime($fromDate)
WITH o, l, COUNT {
  (l)-[:HAS_PAYMENT]->(p:Payment)
  WHERE p.dueDate < l.originationDate + duration({months: $months})
    AND (p.amountPaid < p.amountDue OR p.daysLate >= 30)
} > 0 AS earlyDefault
WITH collect({officer: o, earlyDefault: earlyDefault}) AS cohort
WITH cohort, toFloat(size([c IN cohort WHERE c.earlyDefault])) / size(cohort) AS portfolioRate
UNWIND cohort AS c
WITH c.officer AS o, portfolioRate, count(*) AS loans,
     sum(CASE WHEN c.earlyDefault THEN 1 ELSE 0 END) AS earlyDefaults
WITH o, portfolioRate, loans, earlyDefaults, toFloat(earlyDefaults) / loans AS epdRate
WHERE loans >= $minLoans AND epdRate >= $minRatio * portfolioRate
MATCH (o)-[:EMPLOYED_BY]->(fi:FinancialInstitution)
RETURN o.officerId AS officerId, o.name AS loanOfficer, fi.name AS institution,
       loans, earlyDefaults, round(100.0 * epdRate, 1) AS epdRatePct,
       round(100.0 * portfolioRate, 1) AS portfolioRatePct
ORDER BY epdRate DESC, loans DESC
```

## Node-key constraints

Import creates these from the `key: true` properties in `ONTOLOGY.json`. They are listed as a reference for checking the live database with `SHOW CONSTRAINTS`, not to be run after Import.

```cypher
CREATE CONSTRAINT person_personId_key IF NOT EXISTS FOR (n:Person) REQUIRE n.personId IS NODE KEY;
CREATE CONSTRAINT loanApplication_applicationId_key IF NOT EXISTS FOR (n:LoanApplication) REQUIRE n.applicationId IS NODE KEY;
CREATE CONSTRAINT loanProduct_productId_key IF NOT EXISTS FOR (n:LoanProduct) REQUIRE n.productId IS NODE KEY;
CREATE CONSTRAINT loan_loanId_key IF NOT EXISTS FOR (n:Loan) REQUIRE n.loanId IS NODE KEY;
CREATE CONSTRAINT property_propertyId_key IF NOT EXISTS FOR (n:Property) REQUIRE n.propertyId IS NODE KEY;
CREATE CONSTRAINT appraisal_appraisalId_key IF NOT EXISTS FOR (n:Appraisal) REQUIRE n.appraisalId IS NODE KEY;
CREATE CONSTRAINT payment_paymentId_key IF NOT EXISTS FOR (n:Payment) REQUIRE n.paymentId IS NODE KEY;
CREATE CONSTRAINT financialInstitution_institutionId_key IF NOT EXISTS FOR (n:FinancialInstitution) REQUIRE n.institutionId IS NODE KEY;
CREATE CONSTRAINT loanOfficer_officerId_key IF NOT EXISTS FOR (n:LoanOfficer) REQUIRE n.officerId IS NODE KEY;
```
