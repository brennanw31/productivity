---
applyTo: "finance/**"
description: "Use when working with personal finance files under finance/, including budgeting, bill tracking, transaction CSV analysis, and cash-flow planning."
---

# Finance Workspace Guidance

Operate only within `finance/` unless the user explicitly asks to reference or change something elsewhere in the repository.

Treat this area as personal finance records and planning material, not application code:
- There are no build, test, or lint commands to run.
- Prefer markdown summaries and planning notes for analysis.
- Preserve raw bank exports as source data; do not rewrite transaction rows in CSV files unless the user explicitly asks for cleanup.

Ground recommendations in the finance files that already exist:
- [Financial goals](../../finance/goals.md)
- [Checking account context](../../finance/bills-checking-account/context.md)
- Dated transaction snapshots in `finance/**/YYYY-MM-DD_*.csv`

When analyzing transaction exports:
 - Prefer using the repository's processing tools rather than manual edits of raw CSVs.
	 - Use `finance/scripts/parse_transactions.py` to canonicalize and sanitize raw exports.
		 The parser writes a per-export staging CSV (default staging directory: `finance/data/tmp`) with columns:
		 `date, amount, balance, description, category, purchase_category, source, row_index`.
		 - `source` is the mapped account `slug` (from `finance/config/account_mappings.json`).
		 - `purchase_category` is filled from `finance/config/description_mappings.json` when a transaction description is recognized.
		 - `row_index` preserves the original export row order and must be retained to avoid same-day ordering bugs.
		 - The parser intentionally does NOT merge or de-duplicate — it emits one staged file per export.
	 - Use `finance/scripts/aggregate_transactions.py` to merge staging files into year-to-date outputs.
		 The aggregator groups by account `slug` and year, de-duplicates by `(date, amount, description, category)`,
		 infers signed amounts (derives from adjacent explicit balances when available, with a category-based fallback),
		 propagates balances from anchors (backward and forward), preserves existing non-empty `purchase_category` values,
		 writes newest-first CSVs to `finance/data/processed/`,
		 appends any balance inconsistency messages to `finance/scripts/logs/balance_inconsistencies.log`, and removes
		 the entire staging directory on successful completion. Both scripts support `--dry-run` for safe previews.

 - When inspecting or classifying transactions manually, the CSV header remains a useful guide, but prefer parsing
	 via the tooling to ensure consistent sanitization, `source` tagging, and stable ordering for balance math.
 - Separate income, fixed bills, subscriptions, debt payments, transfers, and discretionary spending.
 - Keep calculations reproducible and state assumptions when categorization is ambiguous.

When updating documentation in `finance/`:
- Prefer adding concise summaries, budgets, or action plans in markdown.
- If `goals.md` or a `context.md` file is empty, propose or create structured starter content instead of leaving analysis only in chat.
- Use dated notes when capturing point-in-time reviews so historical decisions remain traceable.

If you change processing behavior or add new scripts that alter how exports are parsed or merged, update this instruction file
so automation (Copilot, CI, or help scripts) and sibling READMEs can remain accurate. In particular, avoid reintroducing
merging/deduplication into the parser; keep that responsibility in the aggregator and expose any options as flags there.

Provide practical financial planning guidance, but avoid presenting tax, legal, or regulated financial advice as certain without a cited source or a clear assumption note.