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