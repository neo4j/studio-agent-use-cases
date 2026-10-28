# Loans and Mortgages

Connect borrowers, loans, collateral and originators to see combined exposure, stacked liens and early-default patterns that loan-by-loan reporting misses.

## Overview

### Consumer lending and mortgages

Banks, credit unions and mortgage companies lend to households against two kinds of security: the borrower's promise to repay, and — for mortgages and home equity lending — a lien on their home. A loan starts as an application, is underwritten and originated by a loan officer, and is then often serviced by a different institution that collects payments and manages arrears for years afterwards.

The vocabulary in this package follows the **Financial Industry Business Ontology (FIBO)**, the industry-standard description of financial concepts maintained by the EDM Council, and specifically its Loans domain. FIBO is deliberately formal; this package keeps its terms and code lists but simplifies its structure so the result is easy to explore.

Most lending systems are organised around one loan at a time, which leaves the hard risk questions spread across several of them:

- **Who is really exposed** — a person can borrow on one loan, co-sign another and guarantee a third, and each sits in a different file.
- **What the collateral really supports** — a first mortgage and a home equity line on the same house are often held by different lenders, so neither sees the combined debt.
- **Whether the valuation is real** — a property re-appraised much higher a few months after purchase, just before new borrowing, is a classic warning sign.
- **Where bad loans come from** — early payment default (a loan failing within its first months) clustered behind one originator points at origination quality or fraud, not bad luck.

### What it helps with

Each of these questions becomes a short walk across connected records rather than a reconciliation between systems.

| Problem | How the reference ontology helps |
| ------- | -------------------------------- |
| A person's total liability is split across loans they borrow on, co-borrow and guarantee | Borrowers and guarantors are links from one person to many loans, so their whole position can be summed in one place |
| One default can spread to other loans through shared borrowers and guarantors | Follow a defaulted borrower to every other loan they are on, and see which performing loans are now at risk |
| Liens from different lenders stack up on the same home | Loans are linked to the property that secures them, so combined loan-to-value is measured across every open lien |
| Inflated valuations support new borrowing | Appraisals are dated and linked to the property, so a sharp rise in value just before a new loan stands out |
| Early defaults cluster behind particular loan officers | Each loan traces back through its application to the officer who originated it, so early payment default rates can be compared by originator |
| Delinquency differs by servicer, product and lender | Loans link to their product, lender and servicer, so arrears can be broken down along any of them |
| The application pipeline and denial reasons are hard to see alongside the loan book | Applications and their outcomes sit in the same graph as the loans they became, with standard US mortgage-reporting (HMDA) dispositions and denial reasons |

Everything surfaced this way is a lead for a credit or fraud analyst, not a decision. Each pattern has innocent explanations — a renovation behind a higher valuation, an officer serving first-time borrowers — and none of it is a fair-lending analysis, which needs data this reference ontology does not hold.

## Ontology

The reference ontology follows a loan from application to repayment. A **person** applies for a **loan product** through an **application** handled by a **loan officer**; an approved application becomes a **loan**, made by one **financial institution** and serviced by another or the same one. Mortgages and home equity loans are secured on a **property**, which is valued by **appraisals** over time. Each loan's repayment record is a series of **payments**. Roles such as borrower, guarantor, lender and servicer are connections, not separate kinds of thing, so one person or institution carries all of its roles at once.

Conventions throughout: amounts are in US dollars, and rates and ratios are percentages, so 80 means 80%.

### Entities

| Entity | What it represents |
| ------ | ------------------ |
| `Person` | An individual who applies for, borrows on, or guarantees loans; one node holds all of a person's roles |
| `LoanApplication` | A request to borrow, with the information used to decide it and the outcome |
| `LoanProduct` | A loan product a lender offers, with the terms every loan under it shares |
| `Loan` | A funded loan: its terms at origination plus the servicer's current balance and status |
| `Property` | A home or small residential building pledged as collateral for one or more loans |
| `Appraisal` | A valuation of a property on a given date |
| `Payment` | One scheduled monthly installment on a loan and what was actually paid against it |
| `FinancialInstitution` | A lender or loan servicer, or an institution that is both |
| `LoanOfficer` | An individual loan originator who handles applications for the institution employing them |

### Properties

| Entity | Property | Type | What it holds |
| ------ | -------- | ---- | ------------- |
| `Person` | `personId` | String | Unique identifier for the person, after duplicate identities have been resolved |
| `Person` | `name` | String | Full name as recorded on applications |
| `LoanApplication` | `applicationId` | String | Unique identifier for the application |
| `LoanApplication` | `applicationDate` | Date | Date the application was signed and submitted |
| `LoanApplication` | `requestedAmount` | Float | Amount the applicants asked to borrow |
| `LoanApplication` | `loanPurpose` | String | What the funds are for: real property purchase, loan refinancing, home improvement, dwelling construction, business or commercial, mortgage modification, or personal expenditure |
| `LoanApplication` | `occupancy` | String | How the property will be used — primary residence, second home or investment; blank when no property is involved |
| `LoanApplication` | `creditScore` | Integer | Primary applicant's credit score at application, on the 300–850 scale |
| `LoanApplication` | `monthlyIncome` | Float | Gross monthly qualifying income of all applicants combined |
| `LoanApplication` | `dtiRatio` | Float | Debt-to-income ratio: all monthly debt payments, including the new loan, as a percentage of gross monthly income |
| `LoanApplication` | `disposition` | String | Outcome in US mortgage-reporting (HMDA) terms: loan originated, approved but not accepted, denied, withdrawn, file closed for incompleteness, loan purchased, or a preapproval outcome |
| `LoanApplication` | `dispositionDate` | Date | Date of the outcome; for an originated loan, the closing date |
| `LoanApplication` | `denialReason` | String | Main reason for a denial, such as debt-to-income ratio, insufficient credit history or insufficient collateral value; blank unless denied |
| `LoanProduct` | `productId` | String | Unique identifier for the product |
| `LoanProduct` | `name` | String | Product name as marketed |
| `LoanProduct` | `marketCategory` | String | Lending market: auto, commercial, construction, education, mortgage, personal or small business loan |
| `LoanProduct` | `creditType` | String | Closed-end (fixed amount once it closes) or open-end (drawn and repaid up to a limit, like a home equity line) |
| `LoanProduct` | `amortizationType` | String | How rate and repayments behave over the term, such as fixed rate or adjustable rate |
| `LoanProduct` | `termMonths` | Integer | Contractual term in months |
| `LoanProduct` | `isSecured` | Boolean | Whether loans under the product are secured on property |
| `Loan` | `loanId` | String | Unique identifier for the loan |
| `Loan` | `principalAmount` | Float | Amount advanced at origination |
| `Loan` | `interestRate` | Float | Annual note rate at origination, as a percentage; the initial rate for adjustable loans |
| `Loan` | `originationDate` | Date | Date the loan closed and funds were advanced |
| `Loan` | `maturityDate` | Date | Date the final scheduled payment is due |
| `Loan` | `lienPosition` | String | Whether the lender has first claim on the property (primary) or stands behind another lien (subordinate); blank when unsecured |
| `Loan` | `ltvAtOrigination` | Float | Loan-to-value at origination: this loan's principal as a percentage of the property's appraised value, ignoring other liens |
| `Loan` | `currentBalance` | Float | Outstanding principal at the snapshot date; zero once paid in full |
| `Loan` | `balanceAsOfDate` | Date | Date the balance and status were reported |
| `Loan` | `status` | String | Current (under 30 days past due), delinquent (30–89 days), in default (90 days or more), or paid in full |
| `Property` | `propertyId` | String | Unique identifier for the property |
| `Property` | `address` | String | Street address |
| `Property` | `city` | String | City |
| `Property` | `state` | String | Two-letter US state code |
| `Property` | `postalCode` | String | Five-digit US ZIP code |
| `Property` | `constructionType` | String | How the dwelling was built: site built, manufactured, modular, on-frame modular or mobile home |
| `Property` | `dwellingUnits` | Integer | Number of separate homes in the building; 1 for a single-family house |
| `Appraisal` | `appraisalId` | String | Unique identifier for the appraisal |
| `Appraisal` | `appraisalDate` | Date | Date the value was established |
| `Appraisal` | `appraisedValue` | Float | Market value of the whole property on that date |
| `Payment` | `paymentId` | String | Unique identifier for the installment |
| `Payment` | `dueDate` | Date | Date the installment was due |
| `Payment` | `amountDue` | Float | Scheduled principal and interest |
| `Payment` | `amountPaid` | Float | Amount actually paid; zero for a missed installment |
| `Payment` | `paidDate` | Date | Date payment was received; blank when nothing was paid |
| `Payment` | `daysLate` | Integer | Days between due date and payment; zero when on time, blank when unpaid |
| `FinancialInstitution` | `institutionId` | String | Unique identifier for the institution |
| `FinancialInstitution` | `name` | String | Legal or trading name |
| `FinancialInstitution` | `lei` | String | Legal Entity Identifier, the global 20-character code for legal entities |
| `LoanOfficer` | `officerId` | String | Unique identifier for the loan officer |
| `LoanOfficer` | `name` | String | Full name |
| `LoanOfficer` | `nmlsId` | String | The officer's identifier in the US Nationwide Mortgage Licensing System and Registry |

### Relationships

| Relationship | Direction | What it means |
| ------------ | --------- | ------------- |
| `APPLIED_FOR` | `Person` → `LoanApplication` | The person is a party to the application; every application has at least one applicant |
| `FOR_PRODUCT` | `LoanApplication` → `LoanProduct` | The product applied for; exactly one per application |
| `HANDLED_BY` | `LoanApplication` → `LoanOfficer` | The officer who took the application and originated any resulting loan; at most one |
| `RESULTED_IN` | `LoanApplication` → `Loan` | The loan an approved application became; every loan comes from exactly one application |
| `BORROWER_ON` | `Person` → `Loan` | The person is liable for repaying the loan; every loan has at least one borrower |
| `GUARANTEES` | `Person` → `Loan` | The person guarantees the full outstanding balance if the borrowers do not pay |
| `LENT_BY` | `Loan` → `FinancialInstitution` | The institution that made the loan; exactly one |
| `SERVICED_BY` | `Loan` → `FinancialInstitution` | The institution that collects payments and manages arrears; exactly one, possibly the lender |
| `EMPLOYED_BY` | `LoanOfficer` → `FinancialInstitution` | The institution the officer currently originates for |
| `SECURED_BY` | `Loan` → `Property` | The loan is secured by a lien on the property; at most one property per loan, while a property may secure several loans |
| `VALUES` | `Appraisal` → `Property` | The appraisal valued the property; a property may be valued many times |
| `HAS_PAYMENT` | `Loan` → `Payment` | One scheduled installment in the loan's payment history |

### Relationship properties

| Relationship | Property | Type | What it holds |
| ------------ | -------- | ---- | ------------- |
| `APPLIED_FOR` | `applicantRole` | String | Applicant or co-applicant |
| `BORROWER_ON` | `borrowerRole` | String | Primary borrower or co-borrower; co-borrowers are each liable for the full balance |
