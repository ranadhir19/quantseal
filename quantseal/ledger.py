"""Ledger loading and lookup.

The ledger is a JSON Lines file: one receipt per line. It is the project's
single source of truth, and it is small enough to keep in git - receipts
carry hashes and numbers, never model weights.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import schema


def default_ledger_path() -> Path:
    """Locate ledger/receipts.jsonl.

    Resolution order: $QUANTSEAL_LEDGER, then the ledger that ships with a
    source checkout (two levels above this package directory).
    """
    env = os.environ.get("QUANTSEAL_LEDGER")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "ledger" / "receipts.jsonl"


def load_ledger(path=None) -> list:
    path = Path(path) if path else default_ledger_path()
    receipts = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                receipts.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("%s line %d: invalid JSON (%s)" % (path, lineno, exc))
    return receipts


def sha256_file(path, chunk_size=1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def find_by_sha256(receipts, digest):
    """Return the measurement receipt for an exact file hash, or None."""
    for receipt in receipts:
        if receipt.get("kind") != "measurement":
            continue
        if (receipt.get("file") or {}).get("sha256") == digest:
            return receipt
    return None


def check_receipts(receipts) -> list:
    """Schema-validate every receipt; return a list of error strings."""
    errors = []
    seen_ids = set()
    for receipt in receipts:
        rid = receipt.get("receipt_id", "<no id>")
        if rid in seen_ids:
            errors.append("duplicate receipt_id: %s" % rid)
        seen_ids.add(rid)
        for err in schema.validate_receipt(receipt):
            errors.append("%s: %s" % (rid, err))
    return errors
