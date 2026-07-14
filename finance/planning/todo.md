# Finance Repository TODO

Updated: 2026-07-14

This file tracks repository additions that would make the finance notebook more exact, easier to maintain, and easier to review over time.

## Completed

- [x] Add a main-checking spending summary generated from processed transactions and description-mapping categories.

## Next Additions

- [ ] Add support for the Costco Citi Visa credit card across the finance repository and reports.
- [x] Add an account-selection dropdown at the top of the HTML report so each account can show its own overview.
- [x] Add line charts for balance-over-time history for each credit card and savings account in the HTML report.
- [ ] Add a total-debt view in the HTML report with a numeric debt breakdown, a pie chart of each debt item as a share of total debt, and a line chart of total debt over time.
- [ ] In the unknown-purchase questionnaire, add a default-off `Remember merchant category?` checkbox that reveals JSON-safe `Description`, `Merchant Name`, and `Category` fields, defaults `Description` to the first 10 transaction-description characters, uses the category buttons to fill `Category` without advancing while enabled, and appends completed entries to `config/description_mappings.json` as `pattern`, `replace`, and `category`.
- [ ] On the main-checking report tab, move the transaction list into its own scroll panel and add a page-size toggle with 10, 20, 50, and 100 item options, defaulting to 20.
- [ ] On the main-checking report tab, add monthly total-spending line charts that can be switched by category with a radio-button selector in the pie-chart pane.
- [ ] Create a recurring monthly close snapshot with current balances, debts, and liquid cash.
- [ ] Add a single net-worth rollup that totals cash, retirement assets, HSA, credit cards, and loans.
- [ ] Convert processed transaction history into a durable spending baseline by category.
- [ ] Document joint household planning inputs for Brennan and Bailey, including who funds which obligations and what is modeled jointly.
- [ ] Add a house-purchase criteria document with target price range, down payment target, closing-cost assumption, payment ceiling, and timing target.
- [ ] Record fuller debt metadata for each active loan: servicer, minimum payment, due date, payoff rules, and term/end date.
- [ ] Replace the estimated post-401(k)-restart paycheck math with confirmed observed payroll numbers and paystub facts.
- [ ] Track annual and irregular expenses as sinking-fund categories instead of leaving them outside the monthly baseline.
- [ ] Record insurance, deductible, and other risk-buffer context so emergency-fund targets are grounded in actual exposure.