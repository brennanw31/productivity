#!/usr/bin/env python3
"""Minimal CSV transaction parser and sanitizer.

Usage:
    python finance/scripts/parse_transactions.py --input <file_or_dir> [--staging-dir finance/data/tmp] [--dry-run]

This script does a best-effort mapping of common CSV export columns to a canonical schema
and performs light sanitization (masking long digit sequences, emails, and phone numbers).
It is intentionally minimal; extend mappings and sanitizers as needed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import io
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, Iterable, List, Optional


DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"]

# Constant paths (keep these fixed so CLI doesn't need to specify directories)
RAW_DIR = 'finance/raw_data'
DEFAULT_OUTPUT_DIR = 'finance/data/processed'
# Use `finance/data/tmp` for staging processed exports
DEFAULT_STAGING_DIR = 'finance/data/tmp'


def parse_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    # last resort: try ISO parse
    try:
        return datetime.fromisoformat(s).date().isoformat()
    except Exception:
        return s


def parse_date_obj(s: str) -> Optional[datetime.date]:
    iso = parse_date(s)
    try:
        return datetime.fromisoformat(iso).date()
    except Exception:
        return None


def parse_amount(s: str) -> Optional[Decimal]:
    s = (s or "").strip()
    if not s:
        return None
    # remove common currency symbols and commas
    s = s.replace("$", "").replace(",", "")
    try:
        # Decimal preserves accuracy
        return Decimal(s)
    except InvalidOperation:
        # try to strip parentheses for negative numbers: (123.45)
        s2 = s.replace("(", "-").replace(")", "")
        try:
            return Decimal(s2)
        except Exception:
            return None


def mask_long_digit_sequences(text: str) -> str:
    # Mask sequences of 12+ digits (cards/accounts), preserving last 4
    def _mask(m):
        grp = m.group(0)
        digits = re.sub(r"\D", "", grp)
        if len(digits) < 5:
            return grp
        return "****" + digits[-4:]

    # match digits with optional separators
    return re.sub(r"(?:\d[\s\-./]*){12,}", _mask, text)


def redact_emails(text: str) -> str:
    return re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL_REDACTED]", text)


def redact_phones(text: str) -> str:
    # crude phone matcher (international + local patterns)
    return re.sub(r"(\+?\d[\d\-\s\(\)]{7,}\d)", "[PHONE_REDACTED]", text)


def sanitize_text(text: str) -> str:
    if text is None:
        return ""
    out = str(text)
    out = mask_long_digit_sequences(out)
    out = redact_emails(out)
    out = redact_phones(out)
    return out


def canonicalize_row(row: Dict[str, str], headers: Iterable[str], account_kind: Optional[str] = None) -> Dict[str, object]:
    h = {k.lower().strip(): k for k in headers}
    def get_candidate(*names):
        # Prefer the first non-empty exact match
        for n in names:
            if n in h:
                val = row.get(h[n], '')
                if val is not None and str(val).strip() != '':
                    return val
        # Then prefer first non-empty header that contains the candidate token
        for n in names:
            for k in h:
                if n in k:
                    val = row.get(h[k], '')
                    if val is not None and str(val).strip() != '':
                        return val
        # Fallback: first header that contains the candidate token (even if empty)
        for n in names:
            for k in h:
                if n in k:
                    return row.get(h[k], '')
        # Fallback: first exact match even if empty
        for n in names:
            if n in h:
                return row.get(h[n], '')
        return ""

    raw_date = get_candidate('transaction date', 'date', 'posted date', 'post date')
    date = parse_date(raw_date)
    raw_desc = get_candidate('description', 'memo', 'payee')
    raw_balance = get_candidate('balance', 'running balance', 'account balance')
    raw_category = get_candidate('category')
    raw_type = get_candidate('type', 'transaction type')

    # Detect separate Debit/Credit columns first
    debit_val = None
    credit_val = None
    for c in ('amount debit','amount_debit','debit','debit amount'):
        if c in h and str(row.get(h[c], '')).strip() != '':
            debit_val = parse_amount(row.get(h[c], ''))
            break
    for c in ('amount credit','amount_credit','credit','credit amount'):
        if c in h and str(row.get(h[c], '')).strip() != '':
            credit_val = parse_amount(row.get(h[c], ''))
            break

    # Fallback: single amount column
    raw_amount = get_candidate('amount', 'transaction amount', 'transaction amount')
    single_amount = parse_amount(raw_amount)

    # Compute signed amount: debits as negative, credits as positive
    signed_amount = None
    if debit_val is not None:
        try:
            signed_amount = -abs(debit_val)
        except Exception:
            signed_amount = None
    elif credit_val is not None:
        try:
            signed_amount = abs(credit_val)
        except Exception:
            signed_amount = None
    else:
        signed_amount = single_amount

    balance = parse_amount(raw_balance)
    description = sanitize_text(raw_desc)

    purchase_category = ''

    # Apply description simplifications from config (regex match -> full replacement)
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'description_mappings.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as fh:
                mappings = json.load(fh)
            for m in mappings:
                pat = m.get('pattern')
                rep = m.get('replace')
                if pat and rep and re.search(pat, description, flags=re.IGNORECASE):
                    description = rep
                    purchase_category = m.get('category') or ''
                    break
    except Exception:
        pass

    # Determine simplified category based on account kind and available type info
    simplified = ''
    ak = (account_kind or '').lower()
    rt = (raw_type or '').lower()

    # Treat savings like checking accounts for Debit/Credit semantics
    if 'checking' in ak or 'savings' in ak:
        # checking/savings accounts -> Debit/Credit
        if 'debit' in rt:
            simplified = 'Debit'
        elif 'credit' in rt:
            simplified = 'Credit'
        elif signed_amount is not None:
            simplified = 'Debit' if signed_amount < 0 else 'Credit'
    elif 'credit' in ak or 'card' in ak:
        # credit card accounts -> Charge/Payment
        if 'payment' in rt or 'credit' in rt:
            simplified = 'Payment'
        elif 'sale' in rt or 'charge' in rt:
            simplified = 'Charge'
        elif signed_amount is not None:
            simplified = 'Charge' if signed_amount < 0 else 'Payment'
    else:
        # Unknown account kind: attempt reasonable fallbacks
        if 'payment' in rt:
            simplified = 'Payment'
        elif 'charge' in rt:
            simplified = 'Charge'
        elif 'debit' in rt:
            simplified = 'Debit'
        elif 'credit' in rt:
            simplified = 'Credit'
        elif signed_amount is not None:
            simplified = 'Debit' if signed_amount < 0 else 'Credit'

    # Ensure category capitalization
    if isinstance(simplified, str) and simplified:
        simplified = simplified.capitalize()

    return {
        'date': date,
        'signed_amount': signed_amount,  # Decimal or None, keep for balance calc
        'amount': (abs(signed_amount) if signed_amount is not None else None),
        'balance': balance,
        'description': description,
        'category': simplified,
        'purchase_category': purchase_category
    }


def process_file(path: str, output_dir: str, dry_run: bool = False, staging: bool = False, staging_dir: Optional[str] = None) -> str:
    basename = os.path.basename(path)

    os.makedirs(output_dir, exist_ok=True)

    # Read file and detect where the actual CSV header line is (some exports include metadata lines)
    with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        raw_lines = fh.read().splitlines()

    header_idx = None
    header_tokens = {'transaction date','transaction number','date','post date','posted date'}
    for i, line in enumerate(raw_lines[:10]):
        if ',' not in line:
            continue
        toks = [t.strip().lower() for t in line.split(',')]
        if any(tok in header_tokens for tok in toks) or 'description' in toks:
            header_idx = i
            break

    if header_idx is None:
        header_idx = 0

    joined = '\n'.join(raw_lines[header_idx:])
    reader = csv.DictReader(io.StringIO(joined))
    headers = reader.fieldnames or []
    if not headers:
        print(f"Skipping {path}: no headers detected")
        return ''

    rows = list(reader)

    # helpers for mapping
    def load_account_mappings() -> Dict[str, Dict[str, object]]:
        # Default mappings: last4 -> {slug, kind ('checking'|'credit_card'), optional initial_balance}
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
        return defaults

    # Load mappings early so we can validate candidate last-four values
    mappings = load_account_mappings()
    mapping_keys = set(mappings.keys())

    def detect_account_id(rows: List[Dict[str,str]], raw_lines: List[str], filename: str, headers: List[str], mapping_keys: Optional[set] = None) -> Optional[str]:
        # Try headers first: look for any header containing 'account' or 'acct'
        h = [x.lower().strip() for x in (headers or [])]
        acct_col_idx = None
        for i, hh in enumerate(h):
            if 'account' in hh or 'acct' in hh:
                acct_col_idx = i
                break
        if acct_col_idx is not None:
            col = headers[acct_col_idx]
            val = rows[0].get(col, '') if rows else ''
            digits = re.findall(r"(\d{3,})", str(val))
            if digits:
                # Prefer a candidate that matches known mapping keys when available
                for grp in digits:
                    cand = grp[-4:]
                    if mapping_keys is None or cand in mapping_keys:
                        return cand
                # Fallback to last group's last4
                return digits[-1][-4:]

        # card no style headers
        for candidate in ('card no.', 'card no', 'cardnumber', 'card number', 'card'):
            if candidate in h:
                col = headers[h.index(candidate)]
                val = rows[0].get(col, '') if rows else ''
                digits = re.findall(r"(\d{3,})", str(val))
                if digits:
                    for grp in digits:
                        cand = grp[-4:]
                        if mapping_keys is None or cand in mapping_keys:
                            return cand
                    return digits[-1][-4:]

        # Search raw lines for explicit 'Account Number' patterns or any digit groups
        for line in raw_lines[:10]:
            m = re.search(r"Account Number\s*[:\-]?\s*(\d{3,})", line, re.IGNORECASE)
            if m:
                cand = m.group(1)[-4:]
                if mapping_keys is None or cand in mapping_keys:
                    return cand

        # Look for any digit groups in the top of the file and prefer those matching mapping keys
        for line in raw_lines[:10]:
            groups = re.findall(r"(\d{3,})", line)
            for grp in groups:
                cand = grp[-4:]
                if mapping_keys is None or cand in mapping_keys:
                    return cand

        # Fallback: look for mapping keys in the filename (prefer mapping keys over years)
        if mapping_keys:
            for f in re.findall(r"(\d{3,4})", os.path.basename(filename)):
                if f in mapping_keys:
                    return f

        # Last resort: return first 3-4 digit group from filename
        m = re.search(r"(\d{3,4})", os.path.basename(filename))
        if m:
            return m.group(1)

        return None

    acct_id = detect_account_id(rows, raw_lines, path, headers, mapping_keys)
    acct_info = mappings.get(acct_id, None) if acct_id else None
    slug = acct_info.get('slug') if acct_info else None
    kind = acct_info.get('kind') if acct_info else None

    # Determine target year (use max transaction date if present) and produce year-to-date filename
    dates = []
    date_col_candidates = [k for k in headers if k.lower().strip() in ('transaction date','date','post date','posted date')]
    date_col = date_col_candidates[0] if date_col_candidates else (headers[0] if headers else None)
    if date_col:
        for r in rows:
            d = parse_date_obj(r.get(date_col, ''))
            if d:
                dates.append(d)
    year = max(dates).year if dates else datetime.now().year

    # Canonicalize rows
    canonical_rows = [canonicalize_row(r, headers, account_kind=kind) for r in rows]

    # Always emit a per-export processed file into a staging directory; parsing no longer merges
    staging_dir = staging_dir or DEFAULT_STAGING_DIR
    os.makedirs(staging_dir, exist_ok=True)
    base = os.path.splitext(basename)[0]
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    staging_basename = f"{slug or base}__{year}__{ts}.csv"
    staging_path = os.path.join(staging_dir, staging_basename)
    if dry_run:
        print(f"Dry run: would write staging file {staging_path} ({len(canonical_rows)} rows)")
        return staging_path
    with open(staging_path, 'w', newline='', encoding='utf-8') as fh:
        fieldnames = ['date', 'amount', 'balance', 'description', 'category', 'purchase_category', 'source', 'row_index']
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx, r in enumerate(canonical_rows):
            out_row = {
                'date': r.get('date', ''),
                'amount': str(r.get('amount')) if r.get('amount') is not None else '',
                'balance': str(r.get('balance')) if r.get('balance') is not None else '',
                'description': r.get('description', ''),
                'category': r.get('category', ''),
            'purchase_category': r.get('purchase_category', ''),
                # Use mapping-derived slug as the source so downstream aggregator
                # can name processed files according to account_mappings.json
                'source': (slug if slug is not None else base),
                'row_index': str(idx)
            }
            writer.writerow(out_row)
    print(f"Wrote staging file {staging_path}")
    return staging_path


def find_csvs(path: str):
    if os.path.isdir(path):
        for fname in sorted(os.listdir(path)):
            if fname.lower().endswith('.csv'):
                yield os.path.join(path, fname)
    elif os.path.isfile(path) and path.lower().endswith('.csv'):
        yield path


def main():
    p = argparse.ArgumentParser(description='Minimal CSV transaction parser and sanitizer')
    p.add_argument('--input', '-i', required=False, default=RAW_DIR, help='Input file or directory (CSV). Defaults to finance/raw_data')
    p.add_argument('--staging-dir', default=DEFAULT_STAGING_DIR, help='Staging directory for processed outputs (fixed)')
    p.add_argument('--dry-run', action='store_true', help='Do not write files')
    args = p.parse_args()

    inputs = list(find_csvs(args.input))
    if not inputs:
        print('No CSV files found at', args.input)
        return

    for path in inputs:
        process_file(path, DEFAULT_OUTPUT_DIR, dry_run=args.dry_run, staging=True, staging_dir=args.staging_dir)


if __name__ == '__main__':
    main()
