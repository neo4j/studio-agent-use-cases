# Securities Reference Data — Tests

Expected results of every query in `QUERIES.md` on the bundled sample data. This file is for the manual tester and the curating engineer; the runtime never loads it.

## How to run

1. Use a disposable Neo4j 5.23+ database (Aura or local). No APOC or GDS is needed.
2. Import the sample data through the Import flow from `ONTOLOGY.json`: all fourteen CSVs in `sample-data/`. Every node and relationship is mapped; nothing needs adding by hand.
3. No `SETUP.md` statements exist; run the queries straight after the import.
4. Run each query in `QUERIES.md` with the parameters below and compare against the section of the same name. Check the invariant first: it is the contract. The expected values are a convenience that holds for the CSVs as committed.
5. `SHOW CONSTRAINTS` should list the seven node keys at the end of `QUERIES.md`. The reference ontology also flags as required `LegalEntity.name`, `Security.name`, `Security.securityType`, `Identifier.scheme`, `Identifier.value`, `Fund.name`, `REPRESENTS.multiplier`, `CONVERTIBLE_INTO.conversionRatio`, `HOLDS.weightPct` and `UNDERWRITTEN_BY.role`; note whether Import creates existence constraints for them.

## Sample-data profile

### Counts

| Label | Nodes |
| ----- | ----- |
| `LegalEntity` | 500 (499 with an LEI; 5 sovereign issuers with sector `Government`) |
| `Security` | 598 |
| `Identifier` | 1,676 |
| `Exchange` | 12 |
| `Listing` | 397 (330 active, 67 delisted; 360 primary; 186 with no ticker, all bond listings) |
| `Fund` | 25 |
| `Offering` | 381 |

| Relationship | Count | Source |
| ------------ | ----- | ------ |
| `ISSUED_BY` | 598 | `securities.csv` |
| `DIRECTLY_CONSOLIDATED_BY` | 334 | `entity_parents.csv` |
| `IDENTIFIED_BY` | 1,678 | `identifiers.csv` |
| `LISTS` | 397 | `listings.csv` |
| `LISTED_ON` | 397 | `listings.csv` |
| `REPRESENTS` | 11 | `depositary_receipts.csv` |
| `CONVERTIBLE_INTO` | 9 | `conversions.csv` |
| `UNIT_OF` | 32 | `fund_units.csv` |
| `HOLDS` | 1,359 | `holdings.csv` |
| `MANAGED_BY` | 25 | `funds.csv` |
| `OFFERS` | 381 | `offering_securities.csv` |
| `UNDERWRITTEN_BY` | 775 | `offering_underwriters.csv` |

No relationship CSV repeats an endpoint pair, so every row becomes one relationship. `IDENTIFIED_BY` has two more rows than there are `Identifier` nodes because two identifiers are deliberately shared (S2).

Security types: 346 corporate bonds, 148 common shares, 32 fund units, 31 government bonds, 21 preferred shares, 11 depositary receipts, 9 convertible bonds. Identifier schemes: 598 ISIN, 598 FIGI, 271 CUSIP, 109 Common Code, 74 SEDOL, 22 Valoren, 6 CINS. Restrictions: 542 none, 36 Regulation S, 20 Rule 144A. Fund types: 15 mutual funds, 5 ETFs, 2 funds of funds, 1 closed-end, 1 hedge fund, 1 pension fund. Offerings: 323 public, 58 exempt, all firm commitment; 381 bookrunner and 394 co-manager roles. Group depth reaches three levels of `DIRECTLY_CONSOLIDATED_BY`. The holdings snapshot date (`Fund.reportingDate`) is 2026-10-30 for every fund.

### How the data was generated

A seeded, deterministic script (`securities-reference-data-gen.py`, kept outside the package at the repository root; seed `20261113`) builds a background and then adds each seeded pattern explicitly. All names are fictional except the twelve exchanges (real MICs) and the five sovereign issuers. Identifiers are synthetic but well formed: ISINs, CUSIPs, CINS, SEDOLs and FIGIs carry valid check digits, LEIs valid ISO 7064 check digits, and every ISIN embeds its national number (or Common Code) as ISO 6166 prescribes — except the two seeded mismatches.

**Background**

- **About 140 corporate groups** across US, CA, GB, IE, DE, FR, NL, CH, JP and HK: a parent plus up to four subsidiaries, some of them financing vehicles (`… Finance B.V.`, `… Capital LLC`, `… Finance S.A.`) that issue the group's bonds. Each group has a common share listed on a home exchange (a quarter also have a secondary listing), about a fifth a preferred share, and zero to five bonds. Domestic bonds of GB, IE, CH, DE, FR and NL issuers and every eurobond (XS ISIN, Common Code) are listed — eurobonds on XLUX; US bonds are not. A bond that has matured is delisted on its maturity date (65 such listings).
- **Eight bank groups**, some with underwriting subsidiaries, two with depositary banks (Harrowgate Depositary Trust Company, Calloway Trust Bank, N.A.) and three with asset managers (Brookline, Harrowgate, Meridian, Shinonome — four in all). Banks also issue shares and bonds. Four independent managers (Aldermoor, Northgate, Westmark, Tidewater).
- **Five sovereign issuers** (US, UK, Germany, France, Japan) with five to eight government bonds each.
- **Nine background ADRs** on non-US ordinary shares, and seven background convertibles into their issuer's own common share.
- **Offerings** for every corporate bond and convertible (one to three underwriters drawn from all bank groups) and for about 30% of common shares (an IPO). Government bonds have no offering.
- **25 funds** with 4 to 110 holdings each, invested 91–99.8%. Direct-holding funds pick from a universe that excludes the seeded groups (Kairo Denki, Calder Brennan, Halvorsen, Sakuragi), cap a single security at 2–7% depending on the fund, and cap any one non-government issuer group at **7.5%** per fund; the cap is applied after mapping depositary receipts to the underlying share. A fund whose manager belongs to a bank group never holds a security from an offering that group underwrote, outside S10. Two funds of funds and the pension fund hold other funds' units, so look-through runs up to three layers deep (Tidewater Staff Pension Fund → Aldermoor Global Allocation Fund of Funds → Aldermoor Japan Equity ETF).

**Seeded signals**

- **S1 — Reassigned tickers.** XNYS `KVR`: Kestrel Vale Resources Common Stock (SEC-00543) listed 2008-04-14, delisted 2019-06-28; reassigned to Korvara Robotics Common Stock (SEC-00544) from 2021-03-15. XNAS `SOLN`: Solanum Networks (SEC-00546) 2011-09-20 to 2018-11-30, then Solenne Therapeutics (SEC-00547) from 2022-05-04. Near miss: XLON `KVR` is Kingsvale Retail Ordinary Shares (SEC-00545), an unrelated listing on another exchange. These are the only tickers used twice on one exchange.
- **S2 — Shared identifiers.** CUSIP `240345520` belongs to Ostrander Energy 1.625% Sr Notes 2030 (SEC-00548) and is also attached to Ostrander Energy 3.750% Sr Notes 2030 (SEC-00549), which keeps its own CUSIP too. SEDOL `HBX4BB7` of Wexcombe Breweries Ordinary Shares (SEC-00055) is also attached to its ADR (SEC-00528). Near miss: value `0616225` is the SEDOL of Tessaly Water 3.875% Sr Sec Notes 2031 (SEC-00550) and the Valoren of Mirelle Cosmetics 3.000% Sr Notes 2027 (SEC-00551) — two schemes, two `Identifier` nodes.
- **S3 — ISIN inconsistent with national number.** Varnell Aerospace 1.625% Sr Notes 2031 (SEC-00552): CUSIP `143405E95`, but its ISIN `US14340E5969` embeds `14340E596` (two characters transposed). Hollis & Crane Ordinary Shares (SEC-00054): SEDOL `J9QC5D2`, but its ISIN `GB00B12PL289` embeds SEDOL `B12PL28`. Near misses: six Regulation S eurobonds (SEC-00553 to SEC-00558) carry a CINS beside an XS ISIN that correctly embeds their Common Code; every other GB, IE, CH and XS ISIN embeds its national number correctly.
- **S4 — Listings left active after maturity.** Tessaly Water plc 1.500% Sr Notes 2024 (SEC-00559, matured 2024-07-15, XLON listing LST-00384) and Rostova Shipping Finance 3.500% Sr Notes 2025 (SEC-00560, matured 2025-03-03, XLUX listing LST-00385) have no delisting date. Near misses: Wexcombe Breweries 0.875% Sr Notes 2025 (SEC-00561) matured 2025-05-20 and was delisted that day, as were the 64 other matured background listings.
- **S5 — Layered capital structure.** Halvorsen Industrie AG (LE-0477, DE) with Halvorsen Finance B.V. (LE-0478), Halvorsen North America Inc. (LE-0479), its subsidiary Halvorsen Capital LLC (LE-0480) and Halvorsen Antriebstechnik GmbH (LE-0481, no LEI, issues nothing). Seven securities: ordinary shares (SEC-00511), preferred shares (SEC-00512), three Halvorsen Finance eurobonds — senior 2029 (SEC-00513), senior 2028 (SEC-00514), subordinated 2050 (SEC-00515) — a Halvorsen Capital 144A senior secured note 2030 (SEC-00516) and a Halvorsen Industrie junior subordinated note 2029 (SEC-00517).
- **S6 — Routes to one issuer.** Kairo Denki Holdings K.K. (LE-0482, JP) with Kairo Denki Finance B.V. (LE-0483) and Kairo Denki Devices K.K. (LE-0484). Group securities: ordinary shares (SEC-00518), Kairo Denki Finance 2.750% Sr Notes 2029 (SEC-00519) and a zero-coupon convertible 2029 into the ordinary shares (SEC-00520). Outside the group: an ADR (SEC-00521, multiplier 0.5) issued by Harrowgate Depositary Trust Company, and Sakuragi Capital 0.250% Exchangeable Bonds 2028 (SEC-00523), issued by Sakuragi Capital K.K. (a separate group) and exchangeable into Kairo ordinary shares.
- **S7 — Look-through breach through fund units.** Aldermoor Global Allocation Fund of Funds (FND-002) holds 60% Aldermoor Japan Equity ETF units, 25% Northgate Asia Income Fund units, 8% Aldermoor Global Corporate Bond Fund units and 3.5% Kairo ordinary shares directly. The ETF (FND-001) holds Kairo ordinary 6.0% and the Kairo convertible 3.5%; Northgate Asia Income (FND-005) holds the Kairo ADR 2.0% and the Kairo Finance note 4.0%. Kairo look-through in FND-002: 3.5 + 0.60 × 9.5 + 0.25 × 6.0 = **10.7%**, of which 3.5% direct.
- **S8 — Look-through breach through receipts and subsidiaries.** Northgate Global Leaders Fund (FND-006) holds Calder Brennan Ordinary Shares 4.0% (SEC-00524), the Calder Brennan ADR 3.5% (SEC-00526, issued by Calloway Trust Bank, N.A.) and Calder Brennan Finance 0.875% Sr Notes 2029 3.0% (SEC-00525): **10.5%** of Calder Brennan plc, though no single security exceeds 4.0% and the ADR's issuer is a bank.
- **S9 — Near misses on concentration.** Aldermoor Japan Equity ETF (FND-001) at **9.5%** in Kairo Denki (6.0 + 3.5); Westmark Dividend Fund (FND-009) at **9.4%** in Halvorsen (ordinary 4.2, preferred 2.7, Halvorsen Finance 2029 note 2.5).
- **S10 — Affiliated underwriting.** Brookline Financial Group plc (LE-0001) owns Brookline Capital Markets Limited (LE-0002), Brookline Securities LLC (LE-0003) and, through Brookline Investment Holdings Limited (LE-0004), Brookline Asset Management Limited (LE-0005), which manages three funds. Brookline Sterling Corporate Bond Fund (FND-013) holds Larchmont Insurance 6.500% Sub Notes 2033 (SEC-00562, 2.8%, offering OFF-00376) and Tessaly Water 3.500% Sr Sec Notes 2036 (SEC-00563, 2.2%, OFF-00377), both bookrun by Brookline Capital Markets. Brookline Global Equity Fund (FND-014) holds Pellucid Health Common Stock (SEC-00007, 1.4%), whose IPO (OFF-00380) Brookline Securities LLC co-managed. Near misses: FND-013 also holds Larchmont Insurance 3.125% Sr Notes 2030 (SEC-00564, from an offering without Brookline) and Wexcombe Breweries 5.875% Sr Notes 2030 (SEC-00565, underwritten by the similarly named but unrelated Brookhaven Partners LLC); Hollis & Crane 3.375% Sr Notes 2029 (SEC-00566), bookrun by Brookline Capital Markets, is held only by the unaffiliated Aldermoor Global Corporate Bond Fund.

## Resolve a security by identifier

- **Parameters:** `$scheme = 'ISIN'`, `$value = 'CH0713286208'`
- **Invariant:** returns exactly the one security whose identifiers include ISIN CH0713286208, with its issuer, the issuer's ultimate parent, all of its identifiers and only its listings with no delisting date.
- **Expected:** 1 row — SEC-00426 Ingleby Communications Ordinary Shares, common share, CHF, issuer and ultimate parent Ingleby Communications AG; identifiers `FIGI BBG39YJKNR40`, `ISIN CH0713286208`, `Valoren 71328620`; active listings `XLON:IC`, `XSWX:IC`.
- **Sensitivity:** `$scheme = 'CUSIP'`, `$value = '240345520'` returns 2 rows (the S2 collision), showing how a shared identifier surfaces in a lookup.

## Ticker at a date

- **Parameters:** `$mic = 'XNYS'`, `$ticker = 'KVR'`, `$asOf = '2017-05-01'`
- **Invariant:** returns Kestrel Vale Resources Common Stock, the holder of XNYS:KVR on that date, and lists Korvara Robotics Common Stock (the later holder) in otherHolders; never Kingsvale Retail, which uses KVR on XLON.
- **Expected:** 1 row — SEC-00543, issuer Kestrel Vale Resources Inc., listed 2008-04-14, delisted 2019-06-28, otherHolders `["Korvara Robotics Common Stock (2021-03-15 to present)"]`.
- **Sensitivity:** `$asOf = '2023-01-01'` returns SEC-00544 Korvara Robotics with Kestrel Vale (2008-04-14 to 2019-06-28) as the other holder. `$asOf = '2020-06-01'` (between the two listings) returns nothing. `$asOf = '2019-06-28'` returns nothing, because the delisting date is exclusive. `$mic = 'XNAS'`, `$ticker = 'SOLN'` behaves the same way for Solanum Networks / Solenne Therapeutics.

## Listings of a security

- **Parameters:** `$securityId = 'SEC-00105'`
- **Invariant:** returns every listing of Tsukimi Foods Ordinary Shares and no other security's, primary listing first.
- **Expected:** 2 rows — XTKS, ticker `5592`, primary, listed 1994-08-18, active; XLON, ticker `TF`, secondary, listed 2012-10-05, active.

## Identifiers shared by several securities

- **Parameters:** none
- **Invariant:** returns the two seeded shared identifiers — the Ostrander Energy CUSIP on two notes and the Wexcombe Breweries SEDOL on the ordinary share and its depositary receipt — and nothing else; never the near-miss value 0616225, which is a SEDOL on one security and a Valoren on another.
- **Expected:** 2 rows — `CUSIP 240345520` with SEC-00548 and SEC-00549; `SEDOL HBX4BB7` with SEC-00055 and SEC-00528.

## ISIN inconsistent with national number

- **Parameters:** none
- **Invariant:** returns the two seeded mismatches (Hollis & Crane ordinary shares, Varnell Aerospace notes) and the Ostrander note carrying the shared CUSIP; never a Regulation S eurobond with a CINS, and no GB, IE, CH or XS ISIN whose embedded number matches.
- **Expected:** 3 rows, by securityId — SEC-00054 (ISIN `GB00B12PL289`, embedded `00B12PL28`, SEDOL `J9QC5D2`); SEC-00549 (ISIN `US384465A917`, embedded `384465A91`, CUSIP `240345520` — the S2 CUSIP, not its own, which matches); SEC-00552 (ISIN `US14340E5969`, embedded `14340E596`, CUSIP `143405E95`).
- **Sensitivity:** the third row is a consequence of S2 rather than a separate seed, and is correct: the security carries a national number its ISIN does not embed. Removing the `WHEN 'XS'` branch leaves the result unchanged (no XS ISIN is inconsistent); mapping XS to CINS instead would wrongly report the six S3 near misses.

## Active listings of matured securities

- **Parameters:** `$asOf = '2026-10-30'`
- **Invariant:** returns exactly the two seeded stale listings (Tessaly Water, Rostova Shipping); never a matured bond whose listing carries a delisting date, and never a bond maturing after `$asOf`.
- **Expected:** 2 rows — SEC-00559 Tessaly Water plc 1.500% Sr Notes 2024, matured 2024-07-15, XLON, LST-00384; SEC-00560 Rostova Shipping Finance 3.500% Sr Notes 2025, matured 2025-03-03, XLUX, LST-00385.
- **Sensitivity:** `$asOf = '2025-01-01'` returns only the Tessaly Water listing; `$asOf = '2024-01-01'` returns nothing.

## Issuer group capital structure

- **Parameters:** `$entityId = 'LE-0480'`, `$asOf = '2026-10-30'`
- **Invariant:** every row's ultimateParent is Halvorsen Industrie AG; returns every outstanding Halvorsen security issued by any group entity, ordered senior secured, senior unsecured, subordinated, junior subordinated, preferred, common.
- **Expected:** 7 rows in this order — SEC-00516 (Halvorsen Capital LLC, senior secured, USD 500,000,000, 2030-07-17); SEC-00514 (Halvorsen Finance B.V., senior unsecured, EUR 1,250,000,000, 2028-10-07); SEC-00513 (Halvorsen Finance B.V., senior unsecured, EUR 750,000,000, 2029-06-15); SEC-00515 (Halvorsen Finance B.V., subordinated, EUR 500,000,000, 2050-01-09); SEC-00517 (Halvorsen Industrie AG, junior subordinated, EUR 750,000,000, 2029-11-22); SEC-00512 preferred shares; SEC-00511 ordinary shares. Three issuing entities; Halvorsen North America Inc. and Halvorsen Antriebstechnik GmbH issue nothing.
- **Sensitivity:** `$entityId = 'LE-0477'`, `'LE-0478'`, `'LE-0479'` or `'LE-0481'` returns the same 7 rows. `$asOf = '2028-12-31'` drops SEC-00514.

## Routes to an issuer group

- **Parameters:** `$entityId = 'LE-0482'`
- **Invariant:** returns Kairo Denki's own securities as 'issued by group', the Kairo ADR as 'depositary receipt', and the Sakuragi exchangeable as 'convertible from outside the group'; Kairo's own convertible appears only as 'issued by group'.
- **Expected:** 5 rows — `convertible from outside the group`: SEC-00523 (issuer Sakuragi Capital K.K., via Kairo Denki Holdings Ordinary Shares); `depositary receipt`: SEC-00521 (issuer Harrowgate Depositary Trust Company, via Kairo Denki Holdings Ordinary Shares); `issued by group`: SEC-00518, SEC-00519, SEC-00520.

## Fund look-through holdings

- **Parameters:** `$fundId = 'FND-002'`, `$limit = 25`
- **Invariant:** no row is a fund unit; Kairo Denki ordinary shares rank first; lookThroughPct of every row is at least its directPct; at most `$limit` rows.
- **Expected:** 25 rows. First: SEC-00518 Kairo Denki Holdings Ordinary Shares, lookThroughPct 7.1 (3.5 direct + 0.60 × 6.0 via the ETF), directPct 3.5, minFundLayers 0. Every other row has directPct 0.0 and minFundLayers 1. The Kairo convertible (SEC-00520) appears at 2.1 (0.60 × 3.5). Uncapped, the fund reaches 153 distinct underlying securities.
- **Sensitivity:** `$fundId = 'FND-025'` (Tidewater Staff Pension Fund) reaches Kairo through two layers of units (FND-025 → FND-002 → FND-001), exercising the deepest chain in the sample.

## Look-through exposure by issuer group

- **Parameters:** `$fundId = 'FND-002'`, `$limit = 10`
- **Invariant:** Kairo Denki Holdings K.K. ranks first, with lookThroughPct above 10 and directPct at 3.5; the Kairo depositary receipt counts toward Kairo, not toward Harrowgate.
- **Expected:** 10 rows. First: LE-0482 Kairo Denki Holdings K.K., Information Technology, lookThroughPct 10.7, directPct 3.5, securities 4 (ordinary shares, convertible, ADR, Kairo Finance note). Every other group is reached only through fund units (directPct 0.0) and stays below 7.5 (second is Hoshida Motors Holdings K.K. at 6.0011). Uncapped, the fund reaches 82 issuer groups.

## Look-through concentration breaches

- **Parameters:** `$limitPct = 10`
- **Invariant:** returns the two seeded breaches (Aldermoor Global Allocation Fund of Funds / Kairo Denki; Northgate Global Leaders Fund / Calder Brennan) and nothing else; never a government issuer.
- **Expected:** 2 rows — FND-002, fund of funds, Kairo Denki Holdings K.K., lookThroughPct 10.7, directPct 3.5, largestSecurityPct 7.1, securities 4; FND-006, mutual fund, Calder Brennan plc, lookThroughPct 10.5, directPct 10.5, largestSecurityPct 4.0, securities 3.
- **Sensitivity:** `$limitPct = 9` adds the two S9 near misses (FND-001 / Kairo 9.5; FND-009 / Halvorsen 9.4) for 4 rows, and any limit from 7.6 up to 9.3 returns those same 4. At 7.5 and below, background groups appear in bulk (14 rows at 7.49, 18 at 7.0), because the generator caps every background group at 7.5% per fund and many funds reach the cap; at exactly 7.5, floating-point products make the count unstable (5 in a CSV-derived calculation). The shipped starting value of 10 comes from the single-issuer ceiling of diversified-fund rules such as UCITS, not from the seed; the seed was then built so that the breaches sit just above it and the near misses just below. Government issuers are excluded: without that filter, Harrowgate Treasury Bond ETF (99.5% US Treasury), Tidewater Staff Pension Fund (26.52% UK gilts) and Brookline Sterling Corporate Bond Fund (18.0% UK gilts) would appear.

## Affiliated underwriting

- **Parameters:** none
- **Invariant:** returns the three seeded Brookline holdings and nothing else; never the Larchmont note from the offering Brookline did not underwrite, the Wexcombe note underwritten by Brookhaven Partners, or the Brookline-underwritten Hollis & Crane note held only by an unaffiliated fund.
- **Expected:** 3 rows, all with manager Brookline Asset Management Limited and group Brookline Financial Group plc — Brookline Global Equity Fund / Brookline Securities LLC, co-manager, OFF-00380, closed 1997-02-13, SEC-00007 Pellucid Health Common Stock, 1.4; Brookline Sterling Corporate Bond Fund / Brookline Capital Markets Limited, bookrunner, OFF-00376, closed 2023-07-24, SEC-00562, 2.8; Brookline Sterling Corporate Bond Fund / Brookline Capital Markets Limited, bookrunner, OFF-00377, closed 2024-03-26, SEC-00563, 2.2.
- **Sensitivity:** the manager reaches the group's ultimate parent through two levels (Brookline Asset Management Limited → Brookline Investment Holdings Limited → Brookline Financial Group plc), so a bound of `*0..1` on the manager walk would return nothing.

## Review items

Items the curating engineer should confirm with a domain owner. They are recorded here, not in the agent-facing files.

- TODO(review): inferred description — `Security.securityType` `one_of`. The eleven values follow FIBO SEC class labels, but the list is a choice: warrants, structured notes and certificates of deposit are absent, and a user mapping such data would need the list extended.
- TODO(review): inferred description — `UNDERWRITTEN_BY.role` `one_of` (`bookrunner`, `lead manager`, `co-manager`, `selling group member`). Market vocabulary, not FIBO; syndicate titles vary by market.
- TODO(review): inferred description — `Fund.fundType` `one_of` uses six FIBO fund classes; money market funds and UCITS/AIF regulatory categories are not represented.
- TODO(review): inferred description — `CONVERTIBLE_INTO.conversionRatio` is per one bond of 1,000 face amount or per preferred share; markets also quote per 100 or per denomination.
- TODO(review): inferred description — `Identifier.scheme` is an open set with prescribed spellings, deliberately without `one_of`; confirm the spellings (`Common Code`, `Valoren`) against the user's vendor feeds.
- TODO(review): the ISIN-to-national-scheme mapping in "ISIN inconsistent with national number" covers US, CA, GB, IE, CH, LI and XS only.
- TODO(review): the 10% starting value for "Look-through concentration breaches" cites UCITS; confirm the framing with a fund-compliance owner.
