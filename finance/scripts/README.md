# Finance Scripts

Scripts that process raw transaction exports and generate planning models.
All scripts require **Python 3.10+** (system default `python` is 2.7 — use
`C:\Users\williamsbrenn\AppData\Local\Programs\Python\Python312\python.exe`
or another Python 3 install).

---

## Transaction Pipeline

### `finance_app.py`

Opens a basic Tkinter application with buttons for the finance scripts.

```bash
python finance/scripts/finance_app.py
```

Buttons currently run:

- `parse_transactions.py`
- `aggregate_transactions.py`
- `generate_main_checking_spending_chart.py`
- `generate_house_model.py`

Two-step flow: parse raw exports into staging CSVs, then merge into
year-to-date consolidated files.

### `parse_transactions.py`

Canonicalizes raw CSV exports and writes one staging CSV per export to
`finance/data/tmp`.

- Maps account suffixes to slugs via `finance/config/account_mappings.json`.
- Fills the `purchase_category` column when a transaction matches
   `finance/config/description_mappings.json`.
- Preserves original row order with a `row_index` column.
- Does **not** merge or de-duplicate — that is the aggregator's job.

```bash
python finance/scripts/parse_transactions.py          # writes to data/tmp
python finance/scripts/parse_transactions.py --dry-run # preview only
```

### `aggregate_transactions.py`

Reads staging CSVs from `data/tmp`, groups by account slug and year,
de-duplicates on `(date, amount, description, category)`, infers signed
amounts from adjacent balances, propagates balances from anchors, and
writes newest-first year-to-date files to `finance/data/processed/`.

- Appends balance warnings to `finance/scripts/logs/balance_inconsistencies.log`.
- Preserves existing non-empty `purchase_category` values when rebuilding processed files.
- Deletes the staging directory on successful completion.

```bash
python finance/scripts/aggregate_transactions.py          # merge + cleanup
python finance/scripts/aggregate_transactions.py --dry-run # preview only
```

---

## Planning Models

### `generate_main_checking_spending_chart.py`

Generates `finance/accounts/checking/main-checking/spending_summary.html` as a
self-contained multi-account HTML report from the processed account ledgers plus
`finance/config/description_mappings.json`.

- Discovers processed account files in `finance/data/processed/` and shows them in
   an account-selection dropdown.
- Uses the processed CSV `purchase_category` column to group spending rows.
- For checking and savings accounts, spending rows are `Debit` transactions. For
   credit cards, spending rows are `Charge` transactions.
- Before generating HTML, prompts for missing debit purchase categories in the
   default main-checking input and writes the answers back to that processed CSV.
   Use `--no-questionnaire` to skip prompts.
- Produces a self-contained HTML report with account and month filters, checking
   account spending pie charts, savings/credit-card balance line charts, category
   summaries, and transaction tables.
- Leaves unmatched merchants in an `Uncategorized` bucket so mapping gaps stay visible.

```bash
python finance/scripts/generate_main_checking_spending_chart.py
```

Optional arguments:

```bash
python finance/scripts/generate_main_checking_spending_chart.py \
   --input finance/data/processed/main-checking_2026.csv \
   --processed-dir finance/data/processed \
   --account-mappings finance/config/account_mappings.json \
   --mappings finance/config/description_mappings.json \
   --output finance/accounts/checking/main-checking/spending_summary.html
```

### `generate_house_model.py`

Generates `finance/planning/house_project.xlsx` — a scenario-driven
workbook that projects when Brennan + Bailey will be ready to buy a house
under the current debt-elimination and savings plan.

**Requires:** `openpyxl` (`pip install openpyxl`)

```bash
python finance/scripts/generate_house_model.py
```

#### How it works

The script reads planning assumptions from the `ASSUMPTIONS` block at the
top of the file (sourced from `goals.md`, `cash-flow.md`, and `profile.md`)
and runs three scenario forecasts — Conservative, Base, and Optimistic.
Each scenario varies raise rates, promotion uplift, mortgage rate, HYSA
APY, and Bailey's monthly saving contribution.

The forecast engine steps month by month through these phases:

1. **401(k) loan payoff** — payroll deductions + lump-sum fund.
2. **Ring financing + emergency fund** — ring payments at 0% APR overlap
   with HYSA growth toward the $15,000 e-fund gate.
3. **Car loan extra payments** — saving power accelerates the car payoff
   beyond its regular amortization.
4. **Student loan extra payments** — same approach after the car is clear.
5. **House fund** — HYSA grows from $15k toward the combined $75k target
   ($15k e-fund + $60k for down payment and closing costs, sharing one
   Capital One HYSA account).

The HYSA earns interest every month (compounded monthly at the
scenario-specific APY) on the full balance, including during the debt-payoff
phases when the balance sits at the $15k floor.

Three-paycheck months are modeled explicitly — they add an extra
main-checking deposit rather than being smoothed into a monthly average.

#### Workbook sheets

| Sheet | Contents |
|-------|----------|
| **Assumptions** | All editable inputs with blue-highlighted cells. Scenario preset table. Source traceability notes. |
| **Forecast — _Scenario_** | One sheet per scenario. Month-by-month projections with 3-paycheck months highlighted yellow and milestone cells highlighted green. |
| **Mortgage Affordability** | PITI + PMI + maintenance breakdown, rent comparison, post-debt cash-flow check. |
| **Summary** | Milestone dates across scenarios, housing cost comparison, readiness gates, cash-flow release waterfall. |

#### Changing assumptions

Edit the `ASSUMPTIONS` section at the top of `generate_house_model.py`
(or the `SCENARIOS` dict for per-preset overrides), then re-run the script.
The workbook is fully regenerated each time — values in the xlsx are
computed outputs, not live Excel formulas.

#### Source data

| Input | Source file |
|-------|-------------|
| Debt balances and payoff sequence | `finance/planning/goals.md` |
| Paycheck structure and saving power | `finance/planning/cash-flow.md` |
| Pay cadence and profile | `finance/profile.md` |
| HYSA starting balance | `finance/accounts/savings/capital-one-savings/overview.md` |
