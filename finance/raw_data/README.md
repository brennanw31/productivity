Raw data exports
================

This folder contains raw CSV exports from financial institutions.

These files may include sensitive personal information (account numbers, full transaction descriptions, dates, balances, and other identifiable data). For privacy and security:

- Do NOT commit raw CSV files from this folder to version control.
- Keep raw exports local and secure on your machine.
- Use the `scripts/` tools to parse and sanitize exports, then place cleaned outputs in `data/processed/`.

The folder itself is tracked in the repository so helpful metadata (like this README) can be shared, but the CSV contents are ignored by the local `.gitignore` to prevent accidental commits.

If you need to share data, redact or sanitize sensitive fields before exporting.
