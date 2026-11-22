"""Receipt schema: structural rules for ledger entries.

A receipt is one JSON object. Two kinds exist:

- ``measurement``: this lab measured the exact file named by ``file.sha256``
  on the recorded hardware profile with the recorded tools. The verdict is
  MEASURED (or REFUTED when the measurement contradicts a specific claim
  recorded in the receipt).
- ``claim_audit``: a public claim that the lab has not (yet) reproduced.
  The verdict is UNMEASURED, and the entry carries the community evidence
  that exists so the claim is never presented as bare marketing.

The functions here are deliberately dependency-free and strict: validate.py
runs them over every ledger entry, and the CLI refuses to print a receipt
that fails them.
"""

from __future__ import annotations

import re

VERDICTS = ("MEASURED", "REFUTED", "UNMEASURED")
KINDS = ("measurement", "claim_audit")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def is_sha256(value) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


def _err(errors, msg):
    errors.append(msg)


def validate_receipt(receipt) -> list:
    """Return a list of schema errors for one receipt dict ([] == valid)."""
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]

    rid = receipt.get("receipt_id")
    if not isinstance(rid, str) or not rid:
        _err(errors, "receipt_id missing or not a non-empty string")

    kind = receipt.get("kind")
    if kind not in KINDS:
        _err(errors, "kind must be one of %s" % (KINDS,))
        return errors

    verdict = receipt.get("verdict")
    if verdict not in VERDICTS:
        _err(errors, "verdict must be one of %s" % (VERDICTS,))

    if kind == "measurement":
        errors += _validate_measurement(receipt)
    else:
        errors += _validate_claim_audit(receipt)
    return errors


def _validate_measurement(r) -> list:
    errors = []
    if r.get("verdict") not in ("MEASURED", "REFUTED"):
        _err(errors, "measurement receipts must be MEASURED or REFUTED")

    f = r.get("file")
    if not isinstance(f, dict):
        _err(errors, "file block missing")
        f = {}
    if not is_sha256(f.get("sha256")):
        _err(errors, "file.sha256 must be a 64-char lowercase hex digest")
    if not isinstance(f.get("size_bytes"), int) or f.get("size_bytes", 0) <= 0:
        _err(errors, "file.size_bytes must be a positive integer")
    for key in ("publisher", "model", "quant_label", "source_repo"):
        if not isinstance(f.get(key), str) or not f.get(key):
            _err(errors, "file.%s missing" % key)

    hw = r.get("hardware_profile")
    if not isinstance(hw, dict) or not hw.get("id"):
        _err(errors, "hardware_profile.id missing")

    tools = r.get("tools")
    if not isinstance(tools, dict) or not tools.get("llama_cpp"):
        _err(errors, "tools.llama_cpp version string missing")

    m = r.get("measured")
    if not isinstance(m, dict):
        _err(errors, "measured block missing")
        return errors

    ppl = m.get("perplexity") or {}
    if not isinstance(ppl.get("value"), (int, float)) or ppl.get("value", 0) <= 1.0:
        _err(errors, "measured.perplexity.value must be a number > 1")
    for key in ("decode_tok_s", "prompt_tok_s"):
        block = m.get(key) or {}
        if not isinstance(block.get("value"), (int, float)) or block.get("value", 0) <= 0:
            _err(errors, "measured.%s.value must be a positive number" % key)

    kld = m.get("kld_vs_reference")
    ref = r.get("reference")
    if kld is not None:
        if not isinstance(ref, dict) or not is_sha256(ref.get("sha256")):
            _err(errors, "kld_vs_reference present but reference.sha256 missing/invalid")
        elif ref.get("sha256") == f.get("sha256"):
            _err(errors, "reference.sha256 must differ from file.sha256")
        for key in ("mean", "median"):
            if not isinstance(kld.get(key), (int, float)) or kld.get(key, -1) < 0:
                _err(errors, "kld_vs_reference.%s must be a non-negative number" % key)

    probes = m.get("probes")
    if not isinstance(probes, dict):
        _err(errors, "measured.probes missing")
    else:
        for name in ("reasoning", "instruction", "long_context"):
            block = probes.get(name)
            if not isinstance(block, dict):
                _err(errors, "measured.probes.%s missing" % name)
                continue
            passed, total = block.get("passed"), block.get("total")
            if not isinstance(passed, int) or not isinstance(total, int):
                _err(errors, "probes.%s passed/total must be integers" % name)
            elif total <= 0 or passed < 0 or passed > total:
                _err(errors, "probes.%s must satisfy 0 <= passed <= total, total > 0" % name)
    return errors


def _validate_claim_audit(r) -> list:
    errors = []
    if r.get("verdict") != "UNMEASURED":
        _err(errors, "claim_audit receipts are UNMEASURED until reproduced")
    claim = r.get("claim")
    if not isinstance(claim, dict):
        _err(errors, "claim block missing")
        return errors
    for key in ("subject", "text", "source"):
        if not isinstance(claim.get(key), str) or not claim.get(key):
            _err(errors, "claim.%s missing" % key)
    evidence = r.get("community_measurements")
    if not isinstance(evidence, list) or not evidence:
        _err(errors, "claim_audit must cite at least one community measurement")
    else:
        for i, item in enumerate(evidence):
            if not isinstance(item, dict) or not item.get("aspect") or not item.get("source"):
                _err(errors, "community_measurements[%d] needs aspect and source" % i)
    return errors
