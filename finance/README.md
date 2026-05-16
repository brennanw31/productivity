# Finance Workspace

Updated: 2026-05-15

This directory is intentionally a version-controlled finance notebook. Markdown works well here because it is searchable, diffable, easy to update over time, and easy for Copilot to analyze alongside the raw CSV exports.

## Layout

- [profile.md](profile.md): durable personal inputs and assumptions used across planning notes.
- [planning/](planning): cross-account plans, cash-flow summaries, and dated decisions.
- [accounts/](accounts): one folder per real account or vehicle, each with an `overview.md` and an `exports/` folder when raw files exist.
- [conventions.md](conventions.md): directory and filename rules for future additions.

## Quick Links

- [profile.md](profile.md)
- [planning/goals.md](planning/goals.md)
- [planning/cash-flow.md](planning/cash-flow.md)
- [planning/actions-taken.md](planning/actions-taken.md)
- [accounts/checking/bills-checking/overview.md](accounts/checking/bills-checking/overview.md)
- [accounts/checking/main-checking/overview.md](accounts/checking/main-checking/overview.md)
- [accounts/credit-cards/amazon-prime-visa/overview.md](accounts/credit-cards/amazon-prime-visa/overview.md)
- [accounts/credit-cards/capital-one-venture/overview.md](accounts/credit-cards/capital-one-venture/overview.md)
- [accounts/investments/traditional-401k/overview.md](accounts/investments/traditional-401k/overview.md)
- [accounts/investments/roth-ira/overview.md](accounts/investments/roth-ira/overview.md)
- [accounts/investments/hsa/overview.md](accounts/investments/hsa/overview.md)

## Working Rules

- Keep cross-account analysis in `planning/`.
- Keep durable personal facts in [profile.md](profile.md), not scattered through planning notes.
- Keep one real account per folder in `accounts/`.
- Keep raw CSV contents unchanged after export; only rename files to match the documented convention.
- Add new raw files to an account's `exports/` folder and update that account's `overview.md` with any assumptions or context needed to interpret the export.

## CSV Naming Summary

Use this pattern for raw exports:

`<date-or-range>__<account-slug>__[source]__<export-kind>.csv`

Examples in this repo:

- `2026-05-15__bills-checking__360-checking__snapshot.csv`
- `2026-05-15__main-checking__snapshot.csv`
- `2026-01-01_to_2026-05-15__amazon-prime-visa__chase__activity.csv`
- `2026-05-15__capital-one-venture__capital-one__activity.csv`

The detailed rules live in [conventions.md](conventions.md).

## Processing pipeline (updates: 2026-05-16)

This repository now contains a two-step transaction processing pipeline used to
sanitize exports, stage per-export canonical CSVs, then merge year-to-date
consolidated files.

- **Parser:** `finance/scripts/parse_transactions.py` — canonicalizes raw CSV
	exports and writes a per-export staging CSV (no merging). Staging files are
	written by default to `finance/data/tmp`.
- **Aggregator:** `finance/scripts/aggregate_transactions.py` — reads staging CSVs
	from `finance/data/tmp`, groups by account slug and year, de-duplicates,
	infers signed amounts (derives from adjacent balances when available), fills
	missing balances by propagating from anchors, writes newest-first year-to-date
	files into `finance/data/processed/`, appends balance warnings to
	`finance/scripts/logs/balance_inconsistencies.log`, and deletes the entire
	staging directory on successful completion.

Key details:

- **Staging directory:** `finance/data/tmp` (parser default; aggregator reads and removes it)
- **Staging CSV columns:** `date, amount, balance, description, category, source, row_index`
	- `source` is the account `slug` (from `finance/config/account_mappings.json`)
	- `row_index` preserves the original per-export row order to avoid same-day ordering bugs
- **De-duplication key:** `(date, amount, description, category)`
- **Output filenames:** `<slug>_<year>.csv` written to `finance/data/processed/`
- **Logs:** balance inconsistency messages appended to `finance/scripts/logs/balance_inconsistencies.log`
- **Dry-run:** both scripts accept `--dry-run` to preview changes without writing or deleting

Run the flow locally:

```bash
python finance/scripts/parse_transactions.py
python finance/scripts/aggregate_transactions.py
# add --dry-run to either command to preview without writing/deleting
```

If you see persistent balance inconsistencies, re-run the pipeline with
`--dry-run` and inspect the staging CSVs in `finance/data/tmp` (check `source`
and `row_index` are present), and review `finance/config/account_mappings.json`
for correct `slug`, `kind`, and optional `initial_balance` entries.

See `finance/copilot-instructions.md` for a fuller session-oriented summary
that documents the recent code and behavior changes intended for tooling and
automation helpers like Copilot.