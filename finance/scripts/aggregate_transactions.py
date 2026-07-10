#!/usr/bin/env python3
"""Aggregate staging CSVs into year-to-date files, fill balances, and log inconsistencies.

Usage:
    python finance/scripts/aggregate_transactions.py [--staging-dir finance/data/tmp] [--output-dir finance/data/processed] [--log-file finance/scripts/logs/balance_inconsistencies.log] [--dry-run]

This script expects staging CSVs with columns: date,amount,balance,description,category,purchase_category,source
It will group rows by account slug (derived from staging filename or `source`) and transaction year,
merge with any existing year-to-date file, de-duplicate, compute balances by inferring sign from
`category` and account `kind` (from config/account_mappings.json), back-fill and forward-fill when
at least one anchor balance exists, sort newest-first, write the consolidated file to `output_dir`,
and append any balance inconsistencies to the provided log file. Staging files are deleted after
successful merge unless `--dry-run` is used.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import shutil


DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"]

# Default directories (assumed constant)
DEFAULT_STAGING_DIR = 'finance/data/tmp'
DEFAULT_OUTPUT_DIR = 'finance/data/processed'
# Move logs inside finance/scripts
DEFAULT_LOG_PATH = 'finance/scripts/logs/balance_inconsistencies.log'


def parse_date_obj(s: str) -> Optional[datetime.date]:
    s = (s or '').strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def to_decimal(s: str) -> Optional[Decimal]:
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    s = s.replace('$', '').replace(',', '')
    try:
        return Decimal(s)
    except InvalidOperation:
        # try parentheses negative
        s2 = s.replace('(', '-').replace(')', '')
        try:
            return Decimal(s2)
        except Exception:
            return None


def load_account_mappings() -> Dict[str, Dict[str, object]]:
    defaults = {
        '8540': {'slug': 'bills-checking', 'kind': 'checking'},
        '9728': {'slug': 'capital-one-venture', 'kind': 'credit_card'},
        '2144': {'slug': 'amazon-prime-visa', 'kind': 'credit_card'},
        '5628': {'slug': 'main-checking', 'kind': 'checking'}
    }
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'account_mappings.json')
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as fh:
                cfg = json.load(fh)
                for k, v in cfg.items():
                    defaults[k] = v
        except Exception:
            pass
    # Build slug->info mapping from values
    slug_map: Dict[str, Dict[str, object]] = {}
    for v in defaults.values():
        slug = v.get('slug')
        if slug:
            slug_map[slug] = v
    return slug_map


def find_csvs(path: str):
    if os.path.isdir(path):
        for fname in sorted(os.listdir(path)):
            if fname.lower().endswith('.csv'):
                yield os.path.join(path, fname)
    elif os.path.isfile(path) and path.lower().endswith('.csv'):
        yield path


def infer_signed(amount: Optional[Decimal], category: str, kind: Optional[str]) -> Optional[Decimal]:
    if amount is None:
        return None
    cat = (category or '').lower()
    k = (kind or '').lower()
    # Checking and savings accounts: Credit raises balance, Debit lowers
    if 'checking' in k or 'savings' in k:
        if 'credit' in cat:
            return amount
        if 'debit' in cat:
            return -amount
    # Credit cards: Charge increases balance, Payment lowers
    if 'credit' in k or 'card' in k:
        if 'charge' in cat:
            return amount
        if 'payment' in cat or 'credit' in cat:
            return -amount
    # Fallback rules
    if 'debit' in cat:
        return -amount
    if 'credit' in cat or 'charge' in cat:
        return amount
    if 'payment' in cat:
        return -amount
    return None


def write_log(log_path: str, entry: str) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as fh:
        fh.write(f"{datetime.now().isoformat()} {entry}\n")


def aggregate(staging_dir: str, output_dir: str, log_path: str, dry_run: bool = False) -> None:
    slug_map = load_account_mappings()

    # Collect staging rows grouped by (slug, year)
    groups: Dict[Tuple[str, int], List[Dict]] = {}
    staging_files = list(find_csvs(staging_dir)) if os.path.exists(staging_dir) else []

    for sf in staging_files:
        fname = os.path.basename(sf)
        # try to get slug from filename: slug__year__ts.csv
        slug_from_name = fname.split('__')[0] if '__' in fname else os.path.splitext(fname)[0]
        with open(sf, 'r', encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                date_str = (r.get('date') or '').strip()
                date_obj = parse_date_obj(date_str)
                year = date_obj.year if date_obj else datetime.now().year
                slug = (r.get('source') or '').strip() or slug_from_name or 'unknown'
                amount = to_decimal(r.get('amount'))
                balance = to_decimal(r.get('balance'))
                desc = (r.get('description') or '').strip()
                cat = (r.get('category') or '').strip()
                purchase_category = (r.get('purchase_category') or '').strip()
                # preserve original CSV row order to avoid same-day ordering issues
                try:
                    row_index = int((r.get('row_index') or '').strip())
                except Exception:
                    row_index = 0
                key = (slug, year)
                groups.setdefault(key, []).append({
                    'date': date_str,
                    'date_obj': date_obj,
                    'amount': amount,
                    'balance': balance,
                    'description': desc,
                    'category': cat,
                    'purchase_category': purchase_category,
                    'source_file': fname,
                    'row_index': row_index,
                })

    if not groups:
        print('No staging files found to aggregate in', staging_dir)
        return

    os.makedirs(output_dir, exist_ok=True)

    for (slug, year), rows in groups.items():
        out_path = os.path.join(output_dir, f"{slug}_{year}.csv")

        # Load existing rows from out_path for de-duplication
        existing = []
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8', newline='') as fh:
                    er = csv.DictReader(fh)
                    for ex in er:
                        existing.append(ex)
            except Exception:
                existing = []

        # Build merged map keyed by (date, amount, description, category)
        merged: Dict[Tuple[str, str, str, str], Dict] = {}

        def key_of(r):
            return (r.get('date', ''), str(r.get('amount') or ''), (r.get('description') or '').strip(), (r.get('category') or '').strip())

        for ex in existing:
            k = key_of(ex)
            merged[k] = {
                'date': ex.get('date', ''),
                'amount': to_decimal(ex.get('amount')),
                'balance': to_decimal(ex.get('balance')),
                'description': ex.get('description', ''),
                'category': ex.get('category', ''),
                'purchase_category': ex.get('purchase_category', ''),
                'row_index': -1
            }

        # Add new staging rows, preferring entries that include balances
        for r in rows:
            k = (r['date'], str(r['amount'] or ''), r['description'], r['category'])
            entry = {
                'date': r['date'],
                'amount': r['amount'],
                'balance': r['balance'],
                'description': r['description'],
                'category': r['category'],
                'purchase_category': r.get('purchase_category', ''),
                'row_index': r.get('row_index', 0)
            }
            if k in merged:
                existing_entry = merged[k]
                if existing_entry.get('balance') in (None, '') and entry.get('balance') not in (None, ''):
                    entry['purchase_category'] = existing_entry.get('purchase_category') or entry.get('purchase_category', '')
                    merged[k] = entry
                elif not existing_entry.get('purchase_category') and entry.get('purchase_category'):
                    existing_entry['purchase_category'] = entry.get('purchase_category', '')
            else:
                merged[k] = entry

        merged_list = list(merged.values())

        # Ensure date_obj for sorting and computations
        for item in merged_list:
            item['date_obj'] = parse_date_obj(item.get('date') or '')
            if 'row_index' not in item or item['row_index'] is None:
                item['row_index'] = -1

        # Sort chronologically (oldest -> newest) for balance math, prefer original CSV order for same-day items
        merged_list.sort(key=lambda x: (x.get('date_obj') or datetime.min, x.get('row_index'), x.get('description', ''), x.get('amount') or Decimal('0')))

        kind = slug_map.get(slug, {}).get('kind')
        initial_balance = slug_map.get(slug, {}).get('initial_balance') if slug_map.get(slug) else None

        # Compute signed amounts.
        # First, if two adjacent rows both have explicit balances, derive the signed
        # amount from their difference (more reliable than inferring from category).
        for i in range(1, len(merged_list)):
            prev_b = merged_list[i-1].get('balance')
            cur_b = merged_list[i].get('balance')
            if prev_b not in (None, '') and cur_b not in (None, ''):
                try:
                    merged_list[i]['signed'] = (Decimal(cur_b) - Decimal(prev_b))
                except Exception:
                    merged_list[i]['signed'] = None

        # Fallback: infer signed amounts by category and account kind for rows without a computed signed value
        for item in merged_list:
            if 'signed' not in item or item.get('signed') is None:
                item['signed'] = infer_signed(item.get('amount'), item.get('category', ''), kind)

        n = len(merged_list)
        computed: List[Optional[Decimal]] = [None] * n

        # Seed from any explicit balances present
        anchors = [i for i, it in enumerate(merged_list) if it.get('balance') is not None]

        # If initial_balance provided, propagate forward from a virtual anchor before index 0
        if initial_balance is not None:
            try:
                cur = Decimal(str(initial_balance))
                for i in range(n):
                    s = merged_list[i].get('signed')
                    if s is None:
                        break
                    cur = cur + s
                    if computed[i] is None:
                        computed[i] = cur
                    else:
                        # check consistency
                        if abs(computed[i] - cur) >= Decimal('0.01'):
                            write_log(log_path, f"Inconsistency for {slug}_{year} at {merged_list[i].get('date')}: computed {cur} vs existing {computed[i]}")
                # treat as anchor for further propagation
            except Exception:
                pass

        # Set known balances as anchors
        for i in anchors:
            b = merged_list[i].get('balance')
            try:
                computed[i] = Decimal(b) if b not in (None, '') else None
            except Exception:
                computed[i] = None

        # Propagate from each anchor forward and backward
        for anchor in anchors:
            if computed[anchor] is None:
                continue
            # forward
            for j in range(anchor + 1, n):
                s = merged_list[j].get('signed')
                if s is None or computed[j - 1] is None:
                    break
                val = computed[j - 1] + s
                if computed[j] is None:
                    computed[j] = val
                else:
                    if abs(computed[j] - val) >= Decimal('0.01'):
                        write_log(log_path, f"Inconsistency for {slug}_{year} at {merged_list[j].get('date')}: computed {val} vs existing {computed[j]}")
            # backward
            for j in range(anchor - 1, -1, -1):
                s_next = merged_list[j + 1].get('signed')
                if s_next is None or computed[j + 1] is None:
                    break
                val = computed[j + 1] - s_next
                if computed[j] is None:
                    computed[j] = val
                else:
                    if abs(computed[j] - val) >= Decimal('0.01'):
                        write_log(log_path, f"Inconsistency for {slug}_{year} at {merged_list[j].get('date')}: computed {val} vs existing {computed[j]}")

        # Apply computed balances to rows where missing
        for idx, item in enumerate(merged_list):
            if item.get('balance') in (None, '') and computed[idx] is not None:
                item['balance'] = computed[idx]

        # Prepare rows for writing (newest-first)
        out_rows = []
        for item in merged_list:
            out_rows.append({
                'date': item.get('date') or (item.get('date_obj').isoformat() if item.get('date_obj') else ''),
                'amount': str(item.get('amount')) if item.get('amount') is not None else '',
                'balance': str(item.get('balance')) if item.get('balance') is not None else '',
                'description': item.get('description', ''),
                'category': item.get('category', ''),
                'purchase_category': item.get('purchase_category', ''),
            })

        out_rows.sort(key=lambda r: parse_date_obj(r.get('date') or '') or datetime.min, reverse=True)

        if dry_run:
            print(f"Dry run: would write {len(out_rows)} rows to {out_path}")
        else:
            with open(out_path, 'w', newline='', encoding='utf-8') as outfh:
                fieldnames = ['date', 'amount', 'balance', 'description', 'category', 'purchase_category']
                writer = csv.DictWriter(outfh, fieldnames=fieldnames)
                writer.writeheader()
                for r in out_rows:
                    writer.writerow(r)
            print(f"Wrote {len(out_rows)} rows to {out_path}")

    # Remove the entire staging directory after successful merge
    if not dry_run and os.path.exists(staging_dir):
        try:
            shutil.rmtree(staging_dir)
            print(f"Removed staging directory {staging_dir}")
        except Exception:
            print(f"Warning: failed to remove staging directory {staging_dir}")


def main():
    p = argparse.ArgumentParser(description='Aggregate staging CSVs into year-to-date files')
    p.add_argument('--staging-dir', '-s', default=DEFAULT_STAGING_DIR, help='Staging directory containing processed per-export CSVs (assumed constant)')
    p.add_argument('--output-dir', '-o', default=DEFAULT_OUTPUT_DIR, help='Output directory for year-to-date files (assumed constant)')
    p.add_argument('--log-file', '-l', default=DEFAULT_LOG_PATH, help='Path to append balance inconsistency logs (moved to finance/scripts/logs)')
    p.add_argument('--dry-run', action='store_true', help='Do not write files or delete staging')
    args = p.parse_args()

    aggregate(args.staging_dir, args.output_dir, args.log_file, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
