#!/usr/bin/env python3
"""Generate an interactive spending summary HTML file for main checking."""
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
DEFAULT_MAPPINGS = os.path.join(FINANCE_DIR, "config", "description_mappings.json")
DEFAULT_OUTPUT = os.path.join(
    FINANCE_DIR,
    "accounts",
    "checking",
    "main-checking",
    "spending_summary.html",
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
  "Rent",
  "Shopping",
  "Subscriptions",
  "Other",
]


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
    for label, value in (
        ("Transactions", str(details["count"])),
        ("Date", date_text),
        ("Total amount", f"${Decimal(details['amount']):,.2f}"),
        ("Example amounts", amount_text),
    ):
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


def apply_missing_purchase_categories(csv_path: str, mappings: list[dict[str, object]], ask_missing: bool) -> None:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "purchase_category" not in fieldnames:
        fieldnames.append("purchase_category")

    changed = False
    unknown_descriptions: dict[str, dict[str, object]] = {}
    for row in rows:
        if (row.get("category") or "").strip() != "Debit":
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
          {"count": 0, "amount": Decimal("0"), "dates": set(), "amounts": []},
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
            if (row.get("category") or "").strip() != "Debit":
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


def load_transactions(csv_path: str, mappings: list[dict[str, object]]) -> list[dict[str, object]]:
    transactions: list[dict[str, object]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("category") or "").strip() != "Debit":
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
                    "matched": matched,
                }
            )

    transactions.sort(key=lambda item: (item["date"], item["amount"]), reverse=True)
    return transactions


def build_html(
    transactions: list[dict[str, object]],
    input_path: str,
    mappings_path: str,
    output_path: str,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transactions_json = json.dumps(transactions, indent=2)
    title = "Main Checking Spending Summary"

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

    .chart-card,
    .table-card {{
      padding: 20px;
    }}

    .chart-frame {{
      display: grid;
      gap: 18px;
    }}

    #chartWrap {{
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

    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
      flex-wrap: wrap;
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
      <span class="section-label">Main Checking</span>
      <h1>{title}</h1>
      <div class="subtitle">Interactive debit-only breakdown using the processed main-checking ledger plus category metadata from description mappings.</div>
      <div class="meta">Generated {generated_at} from {input_path} using {mappings_path}. Output: {output_path}</div>
    </section>

    <section class="controls">
      <div class="panel control-card">
        <label for="monthFilter">Month Filter</label>
        <select id="monthFilter"></select>
      </div>
      <div class="panel control-card">
        <span class="section-label">Current Filter</span>
        <div id="filterSummary" class="metric-note">All months, all categories.</div>
      </div>
    </section>

    <section id="summaryCards" class="summary"></section>

    <section class="content">
      <div class="panel chart-card">
        <div class="chart-frame">
          <div id="chartWrap"></div>
          <div id="legend" class="legend"></div>
        </div>
      </div>

      <div class="panel table-card">
        <div class="toolbar">
          <div id="tableHeading" class="filter-chip">All debit transactions</div>
          <button id="clearCategoryButton" class="clear-button" type="button">Clear category filter</button>
        </div>
        <div class="empty-note">Transactions remain debits from the processed ledger; credits are excluded from this summary.</div>
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
    </section>
  </div>

  <script>
    const transactions = {transactions_json};
    const palette = [
      '#9c4f2d', '#d96c3f', '#f0a202', '#77966d', '#3d7068', '#467599',
      '#6c5b7b', '#b56576', '#355070', '#588157', '#bc6c25', '#6d597a',
      '#2a9d8f', '#8d99ae', '#7f5539', '#8f2d56'
    ];

    const currency = new Intl.NumberFormat('en-US', {{ style: 'currency', currency: 'USD' }});
    const monthLabel = new Intl.DateTimeFormat('en-US', {{ year: 'numeric', month: 'long', timeZone: 'UTC' }});
    const state = {{ month: 'ALL', category: null }};

    function getMonthOptions() {{
      return Array.from(new Set(transactions.map((item) => item.month))).sort().reverse();
    }}

    function getMonthFilteredTransactions() {{
      return transactions.filter((item) => state.month === 'ALL' || item.month === state.month);
    }}

    function getVisibleTransactions() {{
      return getMonthFilteredTransactions().filter((item) => !state.category || item.spendingCategory === state.category);
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

      select.value = state.month;
      select.addEventListener('change', (event) => {{
        state.month = event.target.value;
        state.category = null;
        render();
      }});
    }}

    function renderSummary(baseTransactions, categoryRows) {{
      const total = baseTransactions.reduce((sum, item) => sum + item.amount, 0);
      const mappedTotal = baseTransactions
        .filter((item) => item.spendingCategory !== 'Uncategorized')
        .reduce((sum, item) => sum + item.amount, 0);
      const uncategorizedTotal = total - mappedTotal;
      const coverage = total === 0 ? 0 : (mappedTotal / total) * 100;

      const cards = [
        {{ label: 'Spending Total', value: currency.format(total), note: `${{baseTransactions.length}} debit transactions` }},
        {{ label: 'Categories', value: String(categoryRows.length), note: 'Distinct spending buckets in current view' }},
        {{ label: 'Mapped Coverage', value: `${{coverage.toFixed(1)}}%`, note: 'Share of spend matched to a named category' }},
        {{ label: 'Uncategorized', value: currency.format(uncategorizedTotal), note: 'Transactions that still need new mapping rules' }},
      ];

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
        container.innerHTML = '<div class="empty-note">No debit transactions available for the current filter.</div>';
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
          render();
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
          render();
        }});
      }});
    }}

    function renderTransactions() {{
      const rows = document.getElementById('transactionRows');
      const items = getVisibleTransactions();
      rows.innerHTML = items.map((item) => `
        <tr>
          <td>${{item.date}}</td>
          <td><span class="badge">${{item.spendingCategory}}</span></td>
          <td>${{item.description}}</td>
          <td class="amount">${{currency.format(item.amount)}}</td>
        </tr>
      `).join('');

      if (!items.length) {{
        rows.innerHTML = '<tr><td colspan="4" class="empty-note">No transactions for the current filter.</td></tr>';
      }}
    }}

    function renderHeadings(baseTransactions) {{
      const monthText = formatMonth(state.month);
      const categoryText = state.category ? `, ${{state.category}} only` : ', all categories';
      document.getElementById('filterSummary').textContent = `${{monthText}}${{categoryText}}.`;

      const heading = state.category
        ? `${{state.category}} transactions in ${{monthText}}`
        : `All debit transactions in ${{monthText}}`;
      document.getElementById('tableHeading').textContent = heading;

      const clearButton = document.getElementById('clearCategoryButton');
      clearButton.disabled = !state.category;
      clearButton.style.opacity = state.category ? '1' : '0.5';
      clearButton.style.cursor = state.category ? 'pointer' : 'default';
    }}

    function render() {{
      const baseTransactions = getMonthFilteredTransactions();
      const categoryRows = aggregateByCategory(baseTransactions);

      if (state.category && !categoryRows.some((row) => row.category === state.category)) {{
        state.category = null;
      }}

      renderSummary(baseTransactions, categoryRows);
      renderChart(categoryRows);
      renderLegend(categoryRows);
      renderTransactions();
      renderHeadings(baseTransactions);
    }}

    document.getElementById('clearCategoryButton').addEventListener('click', () => {{
      if (!state.category) {{
        return;
      }}
      state.category = null;
      render();
    }});

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
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Processed CSV to summarize.")
    parser.add_argument("--mappings", default=DEFAULT_MAPPINGS, help="Description mappings JSON.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="HTML output path.")
    parser.add_argument("--no-questionnaire", action="store_true", help="Do not ask for missing purchase categories.")
    args = parser.parse_args()

    mappings = load_mappings(args.mappings)
    apply_missing_purchase_categories(args.input, mappings, ask_missing=not args.no_questionnaire)
    transactions = load_transactions(args.input, mappings)
    ensure_parent_dir(args.output)

    html = build_html(
        transactions=transactions,
        input_path=os.path.relpath(args.input, FINANCE_DIR).replace("\\", "/"),
        mappings_path=os.path.relpath(args.mappings, FINANCE_DIR).replace("\\", "/"),
        output_path=os.path.relpath(args.output, FINANCE_DIR).replace("\\", "/"),
    )

    with open(args.output, "w", encoding="utf-8", newline="") as handle:
        handle.write(html)

    uncategorized = [item for item in transactions if item["spendingCategory"] == "Uncategorized"]
    uncategorized_amount = sum(item["amount"] for item in uncategorized)
    print(
        "Wrote {output} with {count} debit transactions; {uncategorized_count} remain uncategorized "
        "(${uncategorized_amount:,.2f}).".format(
            output=args.output,
            count=len(transactions),
            uncategorized_count=len(uncategorized),
            uncategorized_amount=uncategorized_amount,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())