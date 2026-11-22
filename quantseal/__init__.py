"""quantseal - verified quality-cost receipts for LLM inference files.

The unit of record is the exact file, identified by SHA-256. Every entry in
the ledger is stamped MEASURED, REFUTED or UNMEASURED: nothing is asserted
that was not measured, and a missing measurement is reported as missing.
"""

__version__ = "0.1.0"
