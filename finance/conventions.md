# Finance Conventions

Updated: 2026-05-15

## Directory Structure

- [profile.md](profile.md) stores durable personal inputs used for calculations and planning assumptions.
- [planning/](planning) stores cross-account strategy, cash flow, and milestone notes.
- [accounts/](accounts) stores one folder per real account or vehicle.
- Each account folder should use this shape when possible:

  - `overview.md`
  - `exports/`

## Account Folder Rules

- Use a stable kebab-case account slug for the folder name.
- Put human-readable summaries, balances, contribution rules, payoff strategy, and assumptions in `overview.md`.
- Put raw site exports in `exports/`.
- Do not edit CSV contents unless a cleanup task explicitly requires it.

## CSV Naming Scheme

Pattern:

`<date-or-range>__<account-slug>__[source]__<export-kind>.csv`

## Naming Parts

| Part | Rule | Example |
| --- | --- | --- |
| `date-or-range` | Use `YYYY-MM-DD` for a point-in-time snapshot or `YYYY-MM-DD_to_YYYY-MM-DD` for an activity range. | `2026-05-15`, `2026-01-01_to_2026-05-15` |
| `account-slug` | Match the account folder name in lowercase kebab-case. | `amazon-prime-visa` |
| `source` | Optional institution or site-specific label in lowercase kebab-case when it adds clarity. | `chase`, `capital-one`, `360-checking` |
| `export-kind` | Short noun describing the file type. | `activity`, `snapshot`, `statement` |

## Additional Rules

- Use lowercase ASCII and kebab-case for all generated filename parts.
- If the website provides a coverage range, use that range in the first field.
- If the website does not provide a date in the filename, use the download date or the file's last-write date and explain that assumption in the relevant `overview.md`.
- Preserve the raw export itself even if the filename is changed.
- Prefer a stable account slug over a bank-specific slug so the folder can stay valid if the same account changes institutions later.