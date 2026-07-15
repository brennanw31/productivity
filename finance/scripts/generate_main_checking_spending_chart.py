#!/usr/bin/env python3
"""Generate an interactive multi-account finance HTML report."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tkinter as tk
from datetime import datetime
from decimal import Decimal, InvalidOperation


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINANCE_DIR = os.path.dirname(SCRIPT_DIR)

DEFAULT_INPUT = os.path.join(FINANCE_DIR, "data", "processed", "main-checking_2026.csv")
DEFAULT_PROCESSED_DIR = os.path.join(FINANCE_DIR, "data", "processed")
DEFAULT_ACCOUNT_MAPPINGS = os.path.join(FINANCE_DIR, "config", "account_mappings.json")
DEFAULT_MAPPINGS = os.path.join(FINANCE_DIR, "config", "description_mappings.json")
DEFAULT_OUTPUT = os.path.join(
    FINANCE_DIR,
    "accounts",
  "overview.html",
)

CATEGORY_OPTIONS = [
  "Car",
  "Credit Card Payment",
  "Dining",
  "Gas",
  "Groceries",
  "Income",
  "Interest & Fees",
  "Bills",
  "Pets",
  "Personal Care",
  "Rent",
  "Shopping",
  "Subscriptions",
  "Sinking Fund",
  "Activities/Date Nights",
  "Other",
]

ACCOUNT_ORDER = {
  "main-checking": 0,
  "bills-checking": 1,
  "capital-one-savings": 2,
  "amazon-prime-visa": 3,
  "capital-one-venture": 4,
}

KIND_LABELS = {
  "checking": "Checking",
  "savings": "Savings",
  "credit_card": "Credit Card",
}


def parse_amount(raw_value: str) -> Decimal | None:
    value = (raw_value or "").strip().replace("$", "").replace(",", "")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def load_mappings(path: str) -> list[dict[str, object]]:
    with open(path, "r", encoding="utf-8") as handle:
        items = json.load(handle)

    mappings: list[dict[str, object]] = []
    for index, item in enumerate(items, start=1):
        missing = [key for key in ("pattern", "replace", "category") if not item.get(key)]
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"Mapping #{index} is missing required field(s): {missing_list}")

        mappings.append(
            {
                "pattern": str(item["pattern"]),
                "replace": str(item["replace"]),
                "category": str(item["category"]),
                "regex": re.compile(str(item["pattern"]), flags=re.IGNORECASE),
            }
        )

    return mappings


def load_account_mappings(path: str) -> dict[str, dict[str, str]]:
    with open(path, "r", encoding="utf-8") as handle:
        items = json.load(handle)

    by_slug: dict[str, dict[str, str]] = {}
    for item in items.values():
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        by_slug[slug] = {
            "kind": str(item.get("kind") or "unknown"),
        }
    return by_slug


def classify_description(description: str, mappings: list[dict[str, object]]) -> tuple[str, str, bool]:
    for mapping in mappings:
        replace = str(mapping["replace"])
        if description == replace:
            return str(mapping["category"]), replace, True

    for mapping in mappings:
        regex = mapping["regex"]
        if regex.search(description):
            return str(mapping["category"]), str(mapping["replace"]), True

    return "Uncategorized", description, False


def classify_from_mapping(description: str, mappings: list[dict[str, object]]) -> str:
    category, _normalized_description, matched = classify_description(description, mappings)
    return category if matched else ""


def ask_purchase_category(root: tk.Tk, description: str, details: dict[str, object]) -> str | None:
    result: dict[str, str | None] = {"value": None}

    dialog = tk.Toplevel(root)
    dialog.title("Purchase Category")
    dialog.grab_set()
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)

    container = tk.Frame(dialog, padx=16, pady=14)
    container.pack(fill=tk.BOTH, expand=True)

    tk.Label(container, text="Assign a purchase category", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
    tk.Label(container, text="Description", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(14, 2))
    tk.Label(
        container,
        text=description,
        font=("TkDefaultFont", 12, "bold"),
        justify=tk.LEFT,
        wraplength=620,
    ).pack(anchor="w")

    dates = sorted(str(date_value) for date_value in details["dates"])
    amounts = sorted((Decimal(amount) for amount in details["amounts"]), reverse=True)
    date_text = dates[0] if len(dates) == 1 else f"{dates[0]} through {dates[-1]}"
    amount_text = ", ".join(f"${amount:,.2f}" for amount in amounts[:5])
    if len(amounts) > 5:
        amount_text += ", ..."

    attributes = tk.Frame(container)
    attributes.pack(fill=tk.X, pady=(12, 8))
    attribute_rows = []
    if details.get("account"):
      attribute_rows.append(("Account", str(details["account"])))
    attribute_rows.extend((
        ("Transactions", str(details["count"])),
        ("Date", date_text),
        ("Total amount", f"${Decimal(details['amount']):,.2f}"),
        ("Example amounts", amount_text),
    ))
    for label, value in attribute_rows:
        row = tk.Frame(attributes)
        row.pack(anchor="w", fill=tk.X, pady=1)
        tk.Label(row, text=f"{label}: ", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(row, text=value, font=("TkDefaultFont", 10), justify=tk.LEFT, wraplength=520).pack(side=tk.LEFT)

    button_frame = tk.Frame(container)
    button_frame.pack(fill=tk.X, pady=(12, 0))

    def choose(value: str | None) -> None:
        result["value"] = value
        dialog.destroy()

    for index, category in enumerate(CATEGORY_OPTIONS):
        button = tk.Button(button_frame, text=category, width=20, command=lambda c=category: choose(c))
        button.grid(row=index // 3, column=index % 3, padx=4, pady=4, sticky="ew")

    action_frame = tk.Frame(container)
    action_frame.pack(fill=tk.X, pady=(12, 0))
    tk.Button(action_frame, text="Skip", width=16, command=lambda: choose("__SKIP__")).pack(side=tk.LEFT)
    tk.Button(action_frame, text="Abort", width=16, command=lambda: choose("__ABORT__")).pack(side=tk.RIGHT)

    dialog.protocol("WM_DELETE_WINDOW", lambda: choose("__ABORT__"))
    dialog.update_idletasks()
    x = root.winfo_screenwidth() // 2 - dialog.winfo_width() // 2
    y = root.winfo_screenheight() // 2 - dialog.winfo_height() // 2
    dialog.geometry(f"+{x}+{y}")
    dialog.lift()
    dialog.focus_force()
    dialog.after(500, lambda: dialog.attributes("-topmost", False) if dialog.winfo_exists() else None)
    root.wait_window(dialog)

    if result["value"] in ("__SKIP__", "__ABORT__"):
        return result["value"]
    return result["value"]


def apply_missing_purchase_categories(
    csv_path: str,
    mappings: list[dict[str, object]],
    ask_missing: bool,
    spending_categories: set[str],
    account_label: str,
) -> None:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "purchase_category" not in fieldnames:
        fieldnames.append("purchase_category")

    changed = False
    unknown_descriptions: dict[str, dict[str, object]] = {}
    for row in rows:
        if (row.get("category") or "").strip() not in spending_categories:
            row.setdefault("purchase_category", "")
            continue

        existing_category = (row.get("purchase_category") or "").strip()
        if existing_category:
            continue

        description = (row.get("description") or "").strip()
        mapped_category = classify_from_mapping(description, mappings)
        if mapped_category:
            row["purchase_category"] = mapped_category
            changed = True
            continue

        amount = parse_amount(row.get("amount", "")) or Decimal("0")
        date_value = (row.get("date") or "").strip()
        bucket = unknown_descriptions.setdefault(
            description,
            {"count": 0, "amount": Decimal("0"), "dates": set(), "amounts": [], "account": account_label},
        )
        bucket["count"] = int(bucket["count"]) + 1
        bucket["amount"] = Decimal(bucket["amount"]) + amount
        if date_value:
            bucket["dates"].add(date_value)
        bucket["amounts"].append(amount)

    answered_categories: dict[str, str] = {}
    if ask_missing and unknown_descriptions:
        root = tk.Tk()
        root.withdraw()
        for description, details in sorted(
            unknown_descriptions.items(),
            key=lambda item: Decimal(item[1]["amount"]),
            reverse=True,
        ):
            answer = ask_purchase_category(root, description, details)
            if answer == "__ABORT__":
                break
            if answer == "__SKIP__" or not answer:
                continue
            answered_categories[description] = answer.strip()
        root.destroy()

    if answered_categories:
        for row in rows:
            if (row.get("category") or "").strip() not in spending_categories:
                continue
            if (row.get("purchase_category") or "").strip():
                continue
            description = (row.get("description") or "").strip()
            if description in answered_categories:
                row["purchase_category"] = answered_categories[description]
                changed = True

    if changed:
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def display_account_label(slug: str) -> str:
    return " ".join(part.upper() if part in {"hsa", "ira"} else part.capitalize() for part in slug.split("-"))


def spending_categories_for_kind(kind: str) -> set[str]:
    if kind == "credit_card":
        return {"Charge"}
    return {"Debit"}


def load_transactions(
    csv_path: str,
    mappings: list[dict[str, object]],
    spending_categories: set[str],
) -> list[dict[str, object]]:
    transactions: list[dict[str, object]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            transaction_kind = (row.get("category") or "").strip()
            if transaction_kind not in spending_categories:
                continue

            amount = parse_amount(row.get("amount", ""))
            if amount is None or amount <= 0:
                continue

            description = (row.get("description") or "").strip()
            purchase_category = (row.get("purchase_category") or "").strip()
            if purchase_category:
                spending_category = purchase_category
                normalized_description = description
                matched = True
            else:
                spending_category, normalized_description, matched = classify_description(description, mappings)
            date_value = (row.get("date") or "").strip()

            transactions.append(
                {
                    "date": date_value,
                    "month": date_value[:7],
                    "description": description,
                    "normalizedDescription": normalized_description,
                    "amount": float(amount),
                    "spendingCategory": spending_category,
                    "transactionKind": transaction_kind,
                    "matched": matched,
                }
            )

    transactions.sort(key=lambda item: (item["date"], item["amount"]), reverse=True)
    return transactions


def load_balance_points(csv_path: str) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            date_value = (row.get("date") or "").strip()
            balance = parse_amount(row.get("balance", ""))
            if not date_value or balance is None:
                continue
            points.append(
                {
                    "date": date_value,
                    "balance": float(balance),
                    "rowIndex": index,
                }
            )

    points.sort(key=lambda item: (item["date"], item["rowIndex"]))
    return points


def discover_accounts(
    processed_dir: str,
    account_mappings: dict[str, dict[str, str]],
    mappings: list[dict[str, object]],
) -> list[dict[str, object]]:
    accounts: list[dict[str, object]] = []
    if not os.path.isdir(processed_dir):
        return accounts

    for filename in sorted(os.listdir(processed_dir)):
        if not filename.endswith("_2026.csv"):
            continue
        slug = filename[:-len("_2026.csv")]
        csv_path = os.path.join(processed_dir, filename)
        kind = account_mappings.get(slug, {}).get("kind", "unknown")
        spending_categories = spending_categories_for_kind(kind)
        transactions = load_transactions(csv_path, mappings, spending_categories)
        balance_points = load_balance_points(csv_path)
        accounts.append(
            {
                "slug": slug,
                "label": display_account_label(slug),
                "kind": kind,
                "kindLabel": KIND_LABELS.get(kind, display_account_label(kind)),
                "sourcePath": os.path.relpath(csv_path, FINANCE_DIR).replace("\\", "/"),
                "transactions": transactions,
                "balancePoints": balance_points,
                "spendingKinds": sorted(spending_categories),
            }
        )

    accounts.sort(key=lambda account: (ACCOUNT_ORDER.get(str(account["slug"]), 99), str(account["label"])))
    return accounts


def apply_missing_categories_for_processed_accounts(
    processed_dir: str,
    account_mappings: dict[str, dict[str, str]],
    mappings: list[dict[str, object]],
    ask_missing: bool,
) -> None:
    if not os.path.isdir(processed_dir):
        return

    for filename in sorted(os.listdir(processed_dir)):
        if not filename.endswith("_2026.csv"):
            continue
        slug = filename[:-len("_2026.csv")]
        kind = account_mappings.get(slug, {}).get("kind", "unknown")
        apply_missing_purchase_categories(
            os.path.join(processed_dir, filename),
            mappings,
            ask_missing=ask_missing,
            spending_categories=spending_categories_for_kind(kind),
            account_label=display_account_label(slug),
        )


def build_html(
    accounts: list[dict[str, object]],
    processed_dir: str,
    mappings_path: str,
    output_path: str,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    accounts_json = json.dumps(accounts, indent=2)
    title = "Financial Dashboard"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3efe7;
      --panel: #fffdf8;
      --panel-strong: #f7f1e7;
      --ink: #1f2933;
      --muted: #5f6c7b;
      --line: #ddcfbe;
      --accent: #9c4f2d;
      --accent-soft: #ead0c2;
      --shadow: 0 18px 44px rgba(65, 45, 28, 0.12);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(156, 79, 45, 0.12), transparent 26%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
      color: var(--ink);
    }}

    .page {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}

    .hero {{
      display: grid;
      gap: 10px;
      margin-bottom: 24px;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(2rem, 3.2vw, 3rem);
      line-height: 1.05;
      letter-spacing: -0.04em;
    }}

    .subtitle,
    .meta,
    .empty-note {{
      color: var(--muted);
    }}

    .controls,
    .summary,
    .content {{
      display: grid;
      gap: 16px;
    }}

    .controls {{
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-bottom: 20px;
    }}

    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}

    .control-card,
    .card {{
      padding: 18px 20px;
    }}

    .control-card label,
    .section-label {{
      display: block;
      font-size: 0.8rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }}

    select,
    button {{
      font: inherit;
    }}

    select {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
    }}

    .summary {{
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      margin-bottom: 20px;
    }}

    .metric-value {{
      font-size: 1.9rem;
      font-weight: 700;
      line-height: 1.1;
      margin-bottom: 6px;
    }}

    .metric-note {{
      color: var(--muted);
      font-size: 0.95rem;
    }}

    .content {{
      grid-template-columns: minmax(340px, 440px) minmax(0, 1fr);
      align-items: start;
    }}

    .content.content-wide-chart {{
      grid-template-columns: 1fr;
    }}

    .content.content-wide-chart #chartWrap {{
      min-height: 300px;
    }}

    .content.content-wide-chart .table-card {{
      max-width: none;
    }}

    .table-card.is-hidden {{
      display: none;
    }}

    .chart-card,
    .table-card {{
      padding: 20px;
    }}

    .chart-frame {{
      display: grid;
      gap: 18px;
    }}

    #chartWrap {{
      position: relative;
      min-height: 380px;
      display: grid;
      place-items: center;
      background: linear-gradient(180deg, #fffaf2 0%, #fff 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}

    #chartWrap svg {{
      max-width: 100%;
      height: auto;
      overflow: visible;
    }}

    .chart-center-label {{
      font-size: 0.85rem;
      fill: var(--muted);
      text-anchor: middle;
    }}

    .chart-center-value {{
      font-size: 1.4rem;
      font-weight: 700;
      fill: var(--ink);
      text-anchor: middle;
    }}

    .axis-label {{
      font-size: 0.72rem;
      fill: var(--muted);
    }}

    .line-chart-path {{
      fill: none;
      stroke: var(--accent);
      stroke-width: 1.35;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    .balance-point {{
      fill: var(--accent);
      stroke: #fffdf8;
      stroke-width: 1.25;
      cursor: crosshair;
    }}

    .balance-point-group.is-active .balance-point,
    .balance-point:hover {{
      stroke: var(--ink);
      stroke-width: 2;
    }}

    .balance-hit-area {{
      fill: transparent;
      cursor: crosshair;
    }}

    .chart-tooltip {{
      position: absolute;
      z-index: 4;
      min-width: 150px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 253, 248, 0.96);
      box-shadow: 0 12px 28px rgba(65, 45, 28, 0.18);
      pointer-events: none;
      opacity: 0;
      transform: translate(-50%, calc(-100% - 12px));
      transition: opacity 100ms ease;
    }}

    .chart-tooltip.is-visible {{
      opacity: 1;
    }}

    .tooltip-label {{
      color: var(--muted);
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}

    .tooltip-value {{
      font-size: 1.05rem;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}

    .slice {{
      cursor: pointer;
      transition: opacity 140ms ease, transform 140ms ease;
      transform-origin: 180px 180px;
    }}

    .slice:hover,
    .slice.active {{
      opacity: 0.88;
      transform: scale(1.02);
    }}

    .legend {{
      display: grid;
      gap: 10px;
    }}

    .legend button {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
      color: inherit;
      text-align: left;
      cursor: pointer;
    }}

    .legend button.active {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(156, 79, 45, 0.16);
    }}

    .legend-top,
    .legend-bottom {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    .legend-left {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }}

    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      flex: 0 0 auto;
    }}

    .legend-name {{
      font-weight: 700;
    }}

    .legend-meta {{
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .balance-stats {{
      display: grid;
      gap: 10px;
    }}

    .line-chart-details {{
      display: grid;
      gap: 10px;
    }}

    .line-metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 10px;
    }}

    .line-metric-card {{
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}

    .line-metric-card .metric-value {{
      font-size: 1.35rem;
      margin-bottom: 2px;
    }}

    .chart-footnote {{
      color: var(--muted);
      font-size: 0.82rem;
      text-align: right;
    }}

    .stat-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}

    .stat-row strong {{
      font-variant-numeric: tabular-nums;
    }}

    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }}

    .control-card.is-hidden {{
      display: none;
    }}

    .filter-chip {{
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      color: var(--ink);
    }}

    .clear-button {{
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      cursor: pointer;
    }}

    .page-size-toggle {{
      display: inline-flex;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel-strong);
    }}

    .page-size-toggle button {{
      min-width: 42px;
      padding: 7px 10px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
    }}

    .page-size-toggle button.active {{
      background: #fff;
      color: var(--ink);
      box-shadow: 0 1px 4px rgba(65, 45, 28, 0.12);
    }}

    .pagination-controls {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}

    .pagination-controls button {{
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      cursor: pointer;
    }}

    .pagination-controls button:disabled {{
      opacity: 0.45;
      cursor: default;
    }}

    .page-status {{
      color: var(--muted);
      font-size: 0.92rem;
      white-space: nowrap;
    }}

    .table-scroll {{
      max-height: 560px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fffdf8;
      margin-top: 14px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
    }}

    th,
    td {{
      padding: 10px 8px;
      border-bottom: 1px solid #ece1d3;
      vertical-align: top;
    }}

    th {{
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      text-align: left;
      position: sticky;
      top: 0;
      z-index: 1;
      background: #fffdf8;
    }}

    td.amount {{
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--panel-strong);
      color: var(--muted);
      font-size: 0.82rem;
    }}

    @media (max-width: 920px) {{
      .content {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>{title}</h1>
      <div class="meta">Generated {generated_at} from {processed_dir} using {mappings_path}. Output: {output_path}</div>
    </section>

    <section class="controls">
      <div class="panel control-card">
        <label for="accountFilter">Account</label>
        <select id="accountFilter"></select>
      </div>
      <div id="monthControl" class="panel control-card">
        <label for="monthFilter">Month Filter</label>
        <select id="monthFilter"></select>
      </div>
      <div id="currentFilterControl" class="panel control-card">
        <span class="section-label">Current Filter</span>
        <div id="filterSummary" class="metric-note">All months, all categories.</div>
      </div>
    </section>

    <section id="summaryCards" class="summary"></section>

    <section id="contentSection" class="content">
      <div class="panel chart-card">
        <div class="chart-frame">
          <div id="chartWrap"></div>
          <div id="legend" class="legend"></div>
        </div>
      </div>

      <div id="transactionPanel" class="panel table-card">
        <div class="toolbar">
          <div id="tableHeading" class="filter-chip">All debit transactions</div>
          <button id="clearCategoryButton" class="clear-button" type="button">Clear category filter</button>
          <div id="pageSizeToggle" class="page-size-toggle" aria-label="Transaction page size"></div>
          <div id="paginationControls" class="pagination-controls" aria-label="Transaction pagination"></div>
        </div>
        <div id="tableNote" class="empty-note">Transactions are filtered to spending-style rows for the selected account.</div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Category</th>
                <th>Description</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody id="transactionRows"></tbody>
          </table>
        </div>
      </div>
    </section>
  </div>

  <script>
    const accounts = {accounts_json};
    const palette = [
      '#9c4f2d', '#d96c3f', '#f0a202', '#77966d', '#3d7068', '#467599',
      '#6c5b7b', '#b56576', '#355070', '#588157', '#bc6c25', '#6d597a',
      '#2a9d8f', '#8d99ae', '#7f5539', '#8f2d56'
    ];

    const currency = new Intl.NumberFormat('en-US', {{ style: 'currency', currency: 'USD' }});
    const monthLabel = new Intl.DateTimeFormat('en-US', {{ year: 'numeric', month: 'long', timeZone: 'UTC' }});
    const pageSizes = [10, 20, 50, 100];
    const state = {{ account: accounts[0] ? accounts[0].slug : '', month: 'ALL', category: null, pageSize: 20, pageIndex: 0 }};

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, (char) => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }}[char]));
    }}

    function getCurrentAccount() {{
      return accounts.find((account) => account.slug === state.account) || accounts[0] || null;
    }}

    function shouldShowBalanceChart(account) {{
      return account && (account.kind === 'savings' || account.kind === 'credit_card');
    }}

    function isLineChartAccount(account) {{
      return shouldShowBalanceChart(account);
    }}

    function shouldShowTransactions(account) {{
      return account && account.kind !== 'savings';
    }}

    function accountActionLabel(account) {{
      if (!account) {{
        return 'transactions';
      }}
      if (account.kind === 'credit_card') {{
        return 'charges';
      }}
      return 'debit transactions';
    }}

    function getMonthOptions() {{
      const account = getCurrentAccount();
      if (!account) {{
        return [];
      }}
      return Array.from(new Set(account.transactions.map((item) => item.month))).sort().reverse();
    }}

    function getMonthFilteredTransactions() {{
      const account = getCurrentAccount();
      if (!account) {{
        return [];
      }}
      return account.transactions.filter((item) => state.month === 'ALL' || item.month === state.month);
    }}

    function getVisibleTransactions() {{
      return getMonthFilteredTransactions().filter((item) => !state.category || item.spendingCategory === state.category);
    }}

    function getMappingStats(baseTransactions, categoryRows) {{
      const total = baseTransactions.reduce((sum, item) => sum + item.amount, 0);
      const mappedTotal = baseTransactions
        .filter((item) => item.spendingCategory !== 'Uncategorized')
        .reduce((sum, item) => sum + item.amount, 0);
      const uncategorizedTotal = total - mappedTotal;
      const coverage = total === 0 ? 0 : (mappedTotal / total) * 100;

      return {{ total, mappedTotal, uncategorizedTotal, coverage, categoryCount: categoryRows.length }};
    }}

    function aggregateByCategory(items) {{
      const totals = new Map();
      for (const item of items) {{
        const existing = totals.get(item.spendingCategory) || {{ amount: 0, count: 0 }};
        existing.amount += item.amount;
        existing.count += 1;
        totals.set(item.spendingCategory, existing);
      }}

      return Array.from(totals.entries())
        .map(([category, value]) => ({{ category, amount: value.amount, count: value.count }}))
        .sort((left, right) => right.amount - left.amount);
    }}

    function pickColor(category, index) {{
      if (category === 'Uncategorized') {{
        return '#b0a79c';
      }}
      return palette[index % palette.length];
    }}

    function formatMonth(monthValue) {{
      if (monthValue === 'ALL') {{
        return 'All months';
      }}
      return monthLabel.format(new Date(`${{monthValue}}-01T00:00:00Z`));
    }}

    function polarToCartesian(cx, cy, radius, angleDegrees) {{
      const angleRadians = (angleDegrees - 90) * Math.PI / 180;
      return {{
        x: cx + radius * Math.cos(angleRadians),
        y: cy + radius * Math.sin(angleRadians),
      }};
    }}

    function describeArc(cx, cy, radius, startAngle, endAngle) {{
      const start = polarToCartesian(cx, cy, radius, endAngle);
      const end = polarToCartesian(cx, cy, radius, startAngle);
      const largeArc = endAngle - startAngle <= 180 ? '0' : '1';
      return `M ${{cx}} ${{cy}} L ${{start.x}} ${{start.y}} A ${{radius}} ${{radius}} 0 ${{largeArc}} 0 ${{end.x}} ${{end.y}} Z`;
    }}

    function selectYAxisIncrement(maxBalance) {{
      const presets = [100, 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 20000, 50000];
      let selected = presets[0];

      presets.forEach((increment, index) => {{
        const axisMax = increment * 5;
        const lesserIncrement = presets[Math.max(0, index - 1)];
        const fillsAxis = maxBalance >= axisMax * (2 / 3);
        const exceedsLesserAxis = index > 0 && maxBalance > lesserIncrement * 5;
        if (maxBalance <= axisMax && (fillsAxis || exceedsLesserAxis)) {{
          selected = increment;
        }}
      }});

      return selected;
    }}

    function populateAccountFilter() {{
      const select = document.getElementById('accountFilter');
      select.innerHTML = '';

      for (const account of accounts) {{
        const option = document.createElement('option');
        option.value = account.slug;
        option.textContent = `${{account.label}} (${{account.kindLabel}})`;
        select.appendChild(option);
      }}

      select.value = state.account;
      select.addEventListener('change', (event) => {{
        state.account = event.target.value;
        state.month = 'ALL';
        state.category = null;
        state.pageSize = 20;
        state.pageIndex = 0;
        populateMonthFilter();
        render();
      }});
    }}

    function populateMonthFilter() {{
      const select = document.getElementById('monthFilter');
      select.innerHTML = '';

      const allOption = document.createElement('option');
      allOption.value = 'ALL';
      allOption.textContent = 'All months';
      select.appendChild(allOption);

      for (const monthValue of getMonthOptions()) {{
        const option = document.createElement('option');
        option.value = monthValue;
        option.textContent = formatMonth(monthValue);
        select.appendChild(option);
      }}

      const monthOptions = getMonthOptions();
      if (state.month !== 'ALL' && !monthOptions.includes(state.month)) {{
        state.month = 'ALL';
      }}

      select.value = state.month;
      select.onchange = (event) => {{
        state.month = event.target.value;
        state.category = null;
        state.pageSize = 20;
        state.pageIndex = 0;
        render();
      }};
    }}

    function renderPageSizeToggle(account) {{
      const toggle = document.getElementById('pageSizeToggle');
      if (!shouldShowTransactions(account)) {{
        toggle.innerHTML = '';
        return;
      }}

      toggle.innerHTML = pageSizes.map((size) => `
        <button type="button" class="${{state.pageSize === size ? 'active' : ''}}" data-page-size="${{size}}">${{size}}</button>
      `).join('');

      toggle.querySelectorAll('button').forEach((button) => {{
        button.addEventListener('click', () => {{
          state.pageSize = Number(button.getAttribute('data-page-size'));
          state.pageIndex = 0;
          render();
        }});
      }});
    }}

    function renderPaginationControls(account, itemCount) {{
      const controls = document.getElementById('paginationControls');
      if (!shouldShowTransactions(account)) {{
        controls.innerHTML = '';
        return;
      }}

      const totalPages = Math.max(1, Math.ceil(itemCount / state.pageSize));
      state.pageIndex = Math.min(state.pageIndex, totalPages - 1);
      controls.innerHTML = `
        <button type="button" data-page-action="previous" ${{state.pageIndex === 0 ? 'disabled' : ''}}>Previous</button>
        <span class="page-status">Page ${{state.pageIndex + 1}} of ${{totalPages}}</span>
        <button type="button" data-page-action="next" ${{state.pageIndex >= totalPages - 1 ? 'disabled' : ''}}>Next</button>
      `;

      controls.querySelectorAll('button').forEach((button) => {{
        button.addEventListener('click', () => {{
          if (button.getAttribute('data-page-action') === 'previous') {{
            state.pageIndex = Math.max(0, state.pageIndex - 1);
          }} else {{
            state.pageIndex = Math.min(totalPages - 1, state.pageIndex + 1);
          }}
          render();
        }});
      }});
    }}

    function getBalanceStats(account) {{
      const points = account.balancePoints || [];
      if (!points.length) {{
        return null;
      }}

      const balances = points.map((point) => point.balance);
      const latest = points[points.length - 1];
      return {{
        latest,
        min: Math.min(...balances),
        max: Math.max(...balances),
        count: points.length,
      }};
    }}

    function renderSummary(account, baseTransactions, categoryRows) {{
      const stats = getMappingStats(baseTransactions, categoryRows);
      const balanceStats = getBalanceStats(account);

      const cards = [
        {{ label: account.kind === 'credit_card' ? 'Charge Total' : 'Spending Total', value: currency.format(stats.total), note: `${{baseTransactions.length}} ${{accountActionLabel(account)}}` }},
      ];

      if (!isLineChartAccount(account)) {{
        cards.push(
          {{ label: 'Categories', value: String(stats.categoryCount), note: 'Distinct spending buckets in current view' }},
          {{ label: 'Mapped Coverage', value: `${{stats.coverage.toFixed(1)}}%`, note: 'Share of spend matched to a named category' }},
          balanceStats
            ? {{ label: account.kind === 'credit_card' ? 'Latest Debt' : 'Latest Balance', value: currency.format(balanceStats.latest.balance), note: `${{balanceStats.latest.date}} from ${{account.sourcePath}}` }}
            : {{ label: 'Uncategorized', value: currency.format(stats.uncategorizedTotal), note: 'Transactions that still need new mapping rules' }},
        );
      }}

      const container = document.getElementById('summaryCards');
      container.innerHTML = cards.map((card) => `
        <div class="panel card">
          <div class="section-label">${{card.label}}</div>
          <div class="metric-value">${{card.value}}</div>
          <div class="metric-note">${{card.note}}</div>
        </div>
      `).join('');
    }}

    function renderChart(categoryRows) {{
      const container = document.getElementById('chartWrap');
      const total = categoryRows.reduce((sum, row) => sum + row.amount, 0);

      if (!categoryRows.length || total === 0) {{
        container.innerHTML = '<div class="empty-note">No spending transactions available for the current filter.</div>';
        return;
      }}

      const svgParts = [
        '<svg viewBox="0 0 360 360" role="img" aria-label="Spending category pie chart">',
        '<circle cx="180" cy="180" r="126" fill="#f2e8dc"></circle>'
      ];

      let startAngle = 0;
      categoryRows.forEach((row, index) => {{
        const sweep = (row.amount / total) * 360;
        const endAngle = startAngle + sweep;
        const path = sweep >= 359.999
          ? '<circle cx="180" cy="180" r="126" fill="' + pickColor(row.category, index) + '" class="slice' + (state.category === row.category ? ' active' : '') + '" data-category="' + row.category.replace(/"/g, '&quot;') + '"></circle>'
          : '<path d="' + describeArc(180, 180, 126, startAngle, endAngle) + '" fill="' + pickColor(row.category, index) + '" class="slice' + (state.category === row.category ? ' active' : '') + '" data-category="' + row.category.replace(/"/g, '&quot;') + '"></path>';
        svgParts.push(path);
        startAngle = endAngle;
      }});

      svgParts.push('<circle cx="180" cy="180" r="74" fill="#fffdf8"></circle>');
      svgParts.push('<text x="180" y="168" class="chart-center-label">Current view</text>');
      svgParts.push('<text x="180" y="194" class="chart-center-value">' + currency.format(total) + '</text>');
      svgParts.push('<text x="180" y="216" class="chart-center-label">' + formatMonth(state.month) + '</text>');
      svgParts.push('</svg>');

      container.innerHTML = svgParts.join('');
      container.querySelectorAll('.slice').forEach((slice) => {{
        slice.addEventListener('click', () => {{
          const category = slice.getAttribute('data-category');
          state.category = state.category === category ? null : category;
          state.pageIndex = 0;
          render();
        }});
      }});
    }}

    function renderBalanceChart(account) {{
      const container = document.getElementById('chartWrap');
      const points = account.balancePoints || [];
      if (points.length < 2) {{
        container.innerHTML = '<div class="empty-note">Not enough balance history to draw a line chart.</div>';
        return;
      }}

      const width = 520;
      const height = 280;
      const padding = {{ top: 24, right: 34, bottom: 42, left: 86 }};
      const chartWidth = width - padding.left - padding.right;
      const chartHeight = height - padding.top - padding.bottom;
      const balances = points.map((point) => point.balance);
      const maxBalance = Math.max(...balances);
      const axisIncrement = selectYAxisIncrement(maxBalance);
      const axisMin = 0;
      const axisMax = axisIncrement * 5;
      const range = axisMax - axisMin;
      const xFor = (index) => padding.left + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth);
      const yFor = (balance) => padding.top + ((axisMax - balance) / range) * chartHeight;
      const pathData = points.map((point, index) => `${{index === 0 ? 'M' : 'L'}} ${{xFor(index).toFixed(2)}} ${{yFor(point.balance).toFixed(2)}}`).join(' ');
      const latest = points[points.length - 1];
      const first = points[0];
      const midpoint = Math.floor(points.length / 2);
      const yTicks = [5, 4, 3, 2, 1].map((multiplier) => multiplier * axisIncrement);
      const xTicks = [
        {{ index: 0, label: first.date }},
        {{ index: midpoint, label: points[midpoint].date }},
        {{ index: points.length - 1, label: latest.date }},
      ];

      const pointMarks = points.map((point, index) => `
        <g class="balance-point-group">
          <circle class="balance-point" cx="${{xFor(index).toFixed(2)}}" cy="${{yFor(point.balance).toFixed(2)}}" r="2.25"></circle>
          <circle class="balance-hit-area" cx="${{xFor(index).toFixed(2)}}" cy="${{yFor(point.balance).toFixed(2)}}" r="7" data-date="${{escapeHtml(point.date)}}" data-balance="${{escapeHtml(currency.format(point.balance))}}"></circle>
        </g>
      `).join('');

      const label = account.kind === 'credit_card' ? 'Credit card balance over time' : 'Savings balance over time';
      container.innerHTML = `
        <svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="${{label}}">
          <rect x="${{padding.left}}" y="${{padding.top}}" width="${{chartWidth}}" height="${{chartHeight}}" fill="#fffdf8" stroke="#ddcfbe"></rect>
          ${{yTicks.map((tick) => `
            <line x1="${{padding.left}}" x2="${{padding.left + chartWidth}}" y1="${{yFor(tick).toFixed(2)}}" y2="${{yFor(tick).toFixed(2)}}" stroke="#ece1d3"></line>
            <text x="${{padding.left - 10}}" y="${{(yFor(tick) + 4).toFixed(2)}}" text-anchor="end" class="axis-label">${{currency.format(tick)}}</text>
          `).join('')}}
          ${{xTicks.map((tick) => `
            <text x="${{xFor(tick.index).toFixed(2)}}" y="${{height - 20}}" text-anchor="middle" class="axis-label">${{tick.label}}</text>
          `).join('')}}
          <path class="line-chart-path" d="${{pathData}}"></path>
          ${{pointMarks}}
          <text x="${{padding.left}}" y="18" class="axis-label">${{account.kind === 'credit_card' ? 'Debt balance' : 'Account balance'}}</text>
        </svg>
        <div id="chartTooltip" class="chart-tooltip" aria-hidden="true">
          <div class="tooltip-label"></div>
          <div class="tooltip-value"></div>
        </div>
      `;

      const tooltip = container.querySelector('#chartTooltip');
      const tooltipLabel = tooltip.querySelector('.tooltip-label');
      const tooltipValue = tooltip.querySelector('.tooltip-value');
      container.querySelectorAll('.balance-hit-area').forEach((point) => {{
        point.addEventListener('mouseenter', () => {{
          point.closest('.balance-point-group').classList.add('is-active');
          tooltipLabel.textContent = point.getAttribute('data-date');
          tooltipValue.textContent = point.getAttribute('data-balance');
          tooltip.classList.add('is-visible');
        }});
        point.addEventListener('mousemove', (event) => {{
          const bounds = container.getBoundingClientRect();
          tooltip.style.left = `${{event.clientX - bounds.left}}px`;
          tooltip.style.top = `${{event.clientY - bounds.top}}px`;
        }});
        point.addEventListener('mouseleave', () => {{
          point.closest('.balance-point-group').classList.remove('is-active');
          tooltip.classList.remove('is-visible');
        }});
      }});
    }}

    function renderLegend(categoryRows) {{
      const total = categoryRows.reduce((sum, row) => sum + row.amount, 0);
      const legend = document.getElementById('legend');

      legend.innerHTML = categoryRows.map((row, index) => {{
        const percent = total === 0 ? 0 : (row.amount / total) * 100;
        const active = state.category === row.category ? ' active' : '';
        return `
          <button type="button" class="${{active}}" data-category="${{row.category}}">
            <div class="legend-top">
              <div class="legend-left">
                <span class="swatch" style="background:${{pickColor(row.category, index)}}"></span>
                <span class="legend-name">${{row.category}}</span>
              </div>
              <span>${{currency.format(row.amount)}}</span>
            </div>
            <div class="legend-bottom">
              <span class="legend-meta">${{row.count}} transactions</span>
              <span class="legend-meta">${{percent.toFixed(1)}}%</span>
            </div>
          </button>
        `;
      }}).join('');

      legend.querySelectorAll('button').forEach((button) => {{
        button.addEventListener('click', () => {{
          const category = button.getAttribute('data-category');
          state.category = state.category === category ? null : category;
          state.pageIndex = 0;
          render();
        }});
      }});
    }}

    function renderBalanceStats(account, baseTransactions, categoryRows) {{
      const legend = document.getElementById('legend');
      const stats = getBalanceStats(account);
      if (!stats) {{
        legend.innerHTML = '<div class="empty-note">No balance points are available for this account.</div>';
        return;
      }}

      const mappingStats = getMappingStats(baseTransactions, categoryRows);
      legend.innerHTML = `
        <div class="line-chart-details">
          <div class="line-metrics">
            <div class="line-metric-card">
              <div class="section-label">Categories</div>
              <div class="metric-value">${{mappingStats.categoryCount}}</div>
              <div class="metric-note">Distinct spending buckets in current view</div>
            </div>
            <div class="line-metric-card">
              <div class="section-label">Mapped Coverage</div>
              <div class="metric-value">${{mappingStats.coverage.toFixed(1)}}%</div>
              <div class="metric-note">Share of spend matched to a named category</div>
            </div>
          </div>
          <div class="chart-footnote">${{stats.count}} balance points</div>
        </div>
      `;
    }}

    function renderTransactions() {{
      const rows = document.getElementById('transactionRows');
      const account = getCurrentAccount();
      if (!shouldShowTransactions(account)) {{
        rows.innerHTML = '';
        return;
      }}

      const items = getVisibleTransactions();
      const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
      state.pageIndex = Math.min(state.pageIndex, totalPages - 1);
      const startIndex = state.pageIndex * state.pageSize;
      const visibleItems = items.slice(startIndex, startIndex + state.pageSize);
      rows.innerHTML = visibleItems.map((item) => `
        <tr>
          <td>${{item.date}}</td>
          <td><span class="badge">${{escapeHtml(item.spendingCategory)}}</span></td>
          <td>${{escapeHtml(item.description)}}</td>
          <td class="amount">${{currency.format(item.amount)}}</td>
        </tr>
      `).join('');

      if (!items.length) {{
        rows.innerHTML = '<tr><td colspan="4" class="empty-note">No transactions for the current filter.</td></tr>';
      }}
    }}

    function renderHeadings(account, baseTransactions) {{
      const monthText = formatMonth(state.month);
      const categoryText = state.category ? `, ${{state.category}} only` : ', all categories';
      document.getElementById('filterSummary').textContent = `${{account.label}}: ${{monthText}}${{categoryText}}.`;

      if (!shouldShowTransactions(account)) {{
        return;
      }}

      const actionLabel = accountActionLabel(account);
      const heading = state.category
        ? `${{state.category}} ${{actionLabel}} in ${{monthText}}`
        : `All ${{actionLabel}} in ${{monthText}}`;
      document.getElementById('tableHeading').textContent = heading;
      const visibleCount = getVisibleTransactions().length;
      const startRow = visibleCount === 0 ? 0 : state.pageIndex * state.pageSize + 1;
      const endRow = Math.min(visibleCount, startRow + state.pageSize - 1);
      document.getElementById('tableNote').textContent = `${{account.label}} source: ${{account.sourcePath}}. Showing ${{startRow}}-${{endRow}} of ${{visibleCount}} rows.`;

      const clearButton = document.getElementById('clearCategoryButton');
      clearButton.disabled = !state.category;
      clearButton.style.opacity = state.category ? '1' : '0.5';
      clearButton.style.cursor = state.category ? 'pointer' : 'default';
    }}

    function renderLayout(account) {{
      const content = document.getElementById('contentSection');
      const transactionPanel = document.getElementById('transactionPanel');
      const monthControl = document.getElementById('monthControl');
      const currentFilterControl = document.getElementById('currentFilterControl');
      const wideChart = account && (account.kind === 'credit_card' || account.kind === 'savings');
      content.classList.toggle('content-wide-chart', Boolean(wideChart));
      transactionPanel.classList.toggle('is-hidden', !shouldShowTransactions(account));
      monthControl.classList.toggle('is-hidden', Boolean(isLineChartAccount(account)));
      currentFilterControl.classList.toggle('is-hidden', Boolean(isLineChartAccount(account)));
    }}

    function render() {{
      const account = getCurrentAccount();
      if (!account) {{
        document.getElementById('summaryCards').innerHTML = '';
        document.getElementById('chartWrap').innerHTML = '<div class="empty-note">No processed accounts are available.</div>';
        document.getElementById('legend').innerHTML = '';
        document.getElementById('transactionRows').innerHTML = '<tr><td colspan="4" class="empty-note">No accounts found.</td></tr>';
        document.getElementById('paginationControls').innerHTML = '';
        renderLayout(null);
        return;
      }}

      const baseTransactions = getMonthFilteredTransactions();
      const categoryRows = aggregateByCategory(baseTransactions);

      if (state.category && !categoryRows.some((row) => row.category === state.category)) {{
        state.category = null;
      }}

      renderSummary(account, baseTransactions, categoryRows);
      renderLayout(account);
      if (shouldShowBalanceChart(account)) {{
        renderBalanceChart(account);
        renderBalanceStats(account, baseTransactions, categoryRows);
      }} else {{
        renderChart(categoryRows);
        renderLegend(categoryRows);
      }}
      renderPageSizeToggle(account);
      renderPaginationControls(account, getVisibleTransactions().length);
      renderTransactions();
      renderHeadings(account, baseTransactions);
    }}

    document.getElementById('clearCategoryButton').addEventListener('click', () => {{
      if (!state.category) {{
        return;
      }}
      state.category = null;
      state.pageIndex = 0;
      render();
    }});

    populateAccountFilter();
    populateMonthFilter();
    render();
  </script>
</body>
</html>
"""


def ensure_parent_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Deprecated; processed accounts are discovered from --processed-dir.")
    parser.add_argument("--processed-dir", default=DEFAULT_PROCESSED_DIR, help="Directory of processed account CSVs to include.")
    parser.add_argument("--account-mappings", default=DEFAULT_ACCOUNT_MAPPINGS, help="Account mappings JSON.")
    parser.add_argument("--mappings", default=DEFAULT_MAPPINGS, help="Description mappings JSON.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="HTML output path.")
    parser.add_argument("--no-questionnaire", action="store_true", help="Do not ask for missing purchase categories.")
    args = parser.parse_args()

    mappings = load_mappings(args.mappings)
    account_mappings = load_account_mappings(args.account_mappings)
    apply_missing_categories_for_processed_accounts(
        args.processed_dir,
        account_mappings,
        mappings,
        ask_missing=not args.no_questionnaire,
    )
    accounts = discover_accounts(args.processed_dir, account_mappings, mappings)
    if not accounts:
        raise ValueError(f"No processed account CSVs found in {args.processed_dir}")
    ensure_parent_dir(args.output)

    html = build_html(
        accounts=accounts,
        processed_dir=os.path.relpath(args.processed_dir, FINANCE_DIR).replace("\\", "/"),
        mappings_path=os.path.relpath(args.mappings, FINANCE_DIR).replace("\\", "/"),
        output_path=os.path.relpath(args.output, FINANCE_DIR).replace("\\", "/"),
    )

    with open(args.output, "w", encoding="utf-8", newline="") as handle:
        handle.write(html)

    all_transactions = [transaction for account in accounts for transaction in account["transactions"]]
    uncategorized = [item for item in all_transactions if item["spendingCategory"] == "Uncategorized"]
    uncategorized_amount = sum(item["amount"] for item in uncategorized)
    print(
      "Wrote {output} with {account_count} accounts and {count} spending transactions; "
      "{uncategorized_count} remain uncategorized "
        "(${uncategorized_amount:,.2f}).".format(
            output=args.output,
        account_count=len(accounts),
        count=len(all_transactions),
            uncategorized_count=len(uncategorized),
            uncategorized_amount=uncategorized_amount,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())