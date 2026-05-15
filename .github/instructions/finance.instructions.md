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
- Use the CSV header as the schema of record: `Transaction Description`, `Transaction Date`, `Transaction Type`, `Transaction Amount`, `Balance`.
- Separate income, fixed bills, subscriptions, debt payments, transfers, and discretionary spending.
- Keep calculations reproducible and state assumptions when categorization is ambiguous.

When updating documentation in `finance/`:
- Prefer adding concise summaries, budgets, or action plans in markdown.
- If `goals.md` or a `context.md` file is empty, propose or create structured starter content instead of leaving analysis only in chat.
- Use dated notes when capturing point-in-time reviews so historical decisions remain traceable.

Provide practical financial planning guidance, but avoid presenting tax, legal, or regulated financial advice as certain without a cited source or a clear assumption note.