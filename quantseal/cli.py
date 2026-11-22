"""quantseal command line interface.

    quantseal check <file.gguf>     hash a file, print its receipt (or the
                                    honest UNMEASURED answer when none exists)
    quantseal lookup --sha256 <hex> print the receipt for an exact hash
    quantseal list                  list every receipt in the ledger
    quantseal claims                list claim-audit entries

Global option: --ledger <path> (or $QUANTSEAL_LEDGER).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ledger as ledger_mod


def _fmt_measurement(r) -> str:
    f, m = r["file"], r["measured"]
    lines = [
        "VERDICT: %s" % r["verdict"],
        "receipt: %s" % r["receipt_id"],
        "file:    %s (%s bytes)" % (f["filename"], f["size_bytes"]),
        "sha256:  %s" % f["sha256"],
        "model:   %s - %s, published by %s" % (f["model"], f["quant_label"], f["publisher"]),
        "source:  %s" % f["source_repo"],
        "hardware: %s" % r["hardware_profile"]["description"],
        "tools:   llama.cpp %s" % r["tools"]["llama_cpp"],
        "measured (on the hardware above, with the recorded protocol):",
        "  decode speed:  %.2f tok/s (llama-bench %s)" % (
            m["decode_tok_s"]["value"], m["decode_tok_s"]["test"]),
        "  prompt speed:  %.2f tok/s (llama-bench %s)" % (
            m["prompt_tok_s"]["value"], m["prompt_tok_s"]["test"]),
        "  perplexity:    %.4f (+/- %.4f) on %s" % (
            m["perplexity"]["value"], m["perplexity"]["uncertainty"],
            r["protocol"]["corpus"]["name"]),
    ]
    kld = m.get("kld_vs_reference")
    if kld:
        lines.append(
            "  KL divergence vs the FP16 reference file: mean %.6f, median %.6f"
            % (kld["mean"], kld["median"]))
    else:
        lines.append("  KL divergence: not applicable (this file is the reference)")
    probes = m["probes"]
    lines.append(
        "  probes: reasoning %d/%d, instruction-following %d/%d, long-context %d/%d"
        % (probes["reasoning"]["passed"], probes["reasoning"]["total"],
           probes["instruction"]["passed"], probes["instruction"]["total"],
           probes["long_context"]["passed"], probes["long_context"]["total"]))
    lines.append("A receipt covers exactly this file hash, on exactly this "
                 "hardware profile. It says nothing about any other file "
                 "carrying the same quant label.")
    return "\n".join(lines)


def _fmt_unmeasured(digest, path=None) -> str:
    lines = [
        "VERDICT: UNMEASURED",
        "sha256:  %s" % digest,
    ]
    if path:
        lines.insert(1, "file:    %s" % path)
    lines.append(
        "No verified measurement exists for this exact file. A quant label "
        "(for example Q4_K_M) names a family of recipes, not an artifact: "
        "files with the same label from different publishers are different "
        "files, and quality measured for one does not transfer to another.")
    return "\n".join(lines)


def _fmt_claim(r) -> str:
    c = r["claim"]
    lines = [
        "VERDICT: UNMEASURED (claim audit)",
        "receipt: %s" % r["receipt_id"],
        "subject: %s" % c["subject"],
        "claim:   %s" % c["text"],
        "source:  %s" % c["source"],
        "community evidence on record:",
    ]
    for item in r["community_measurements"]:
        lines.append("  - %s: %s (source: %s)" % (
            item["aspect"], item.get("value", "see notes"), item["source"]))
    lines.append("This lab has not reproduced the claim. UNMEASURED means "
                 "exactly that - not false, not verified.")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quantseal", description=__doc__)
    parser.add_argument("--ledger", default=None, help="path to receipts.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="hash a file and print its receipt")
    p_check.add_argument("file")

    p_lookup = sub.add_parser("lookup", help="print the receipt for a hash")
    p_lookup.add_argument("--sha256", required=True)

    sub.add_parser("list", help="list every receipt")
    sub.add_parser("claims", help="list claim-audit entries")

    args = parser.parse_args(argv)
    try:
        receipts = ledger_mod.load_ledger(args.ledger)
    except (OSError, ValueError) as exc:
        print("error: cannot load ledger: %s" % exc, file=sys.stderr)
        return 2

    if args.command == "check":
        path = Path(args.file)
        if not path.is_file():
            print("error: no such file: %s" % path, file=sys.stderr)
            return 2
        digest = ledger_mod.sha256_file(path)
        receipt = ledger_mod.find_by_sha256(receipts, digest)
        if receipt is None:
            print(_fmt_unmeasured(digest, str(path)))
        else:
            print(_fmt_measurement(receipt))
        return 0

    if args.command == "lookup":
        digest = args.sha256.strip().lower()
        receipt = ledger_mod.find_by_sha256(receipts, digest)
        if receipt is None:
            print(_fmt_unmeasured(digest))
        else:
            print(_fmt_measurement(receipt))
        return 0

    if args.command == "list":
        for r in receipts:
            if r.get("kind") == "measurement":
                f = r["file"]
                print("%s  %-9s  %s  %s  %s" % (
                    r["receipt_id"], r["verdict"], f["model"],
                    f["quant_label"], f["publisher"]))
            else:
                print("%s  %-9s  claim audit: %s" % (
                    r["receipt_id"], r["verdict"], r["claim"]["subject"]))
        return 0

    if args.command == "claims":
        audits = [r for r in receipts if r.get("kind") == "claim_audit"]
        if not audits:
            print("no claim-audit entries in the ledger")
            return 0
        print("\n\n".join(_fmt_claim(r) for r in audits))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
