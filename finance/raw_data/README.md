Raw data exports
================

This folder contains raw CSV exports from financial institutions.

These files may include sensitive personal information (account numbers, full transaction descriptions, dates, balances, and other identifiable data). For privacy and security:

- Do NOT commit raw CSV files from this folder to version control.
- Keep raw exports local and secure on your machine.
- Use the `scripts/` tools to parse and sanitize exports, then place cleaned outputs in `data/processed/`.

The folder itself is tracked in the repository so helpful metadata (like this README) can be shared, but the CSV contents are ignored by the local `.gitignore` to prevent accidental commits.

If you need to share data, redact or sanitize sensitive fields before exporting.

Staging and processing notes
----------------------------

- Sanitized per-export staging CSVs are produced by `finance/scripts/parse_transactions.py`.
- By default the parser writes staging files to `finance/data/tmp` using the
	filename pattern `<slug>__<year>__<timestamp>.csv` and the columns
	`date, amount, balance, description, category, source, row_index`.
- `source` is the mapped account `slug` from `finance/config/account_mappings.json`.
- The aggregator (`finance/scripts/aggregate_transactions.py`) reads staging
	files from `finance/data/tmp`, merges and de-duplicates them, writes
	year-to-date outputs into `finance/data/processed/`, and removes the
	entire staging directory once finished. Use `--dry-run` on either script to
	preview actions without writing or deleting files.
