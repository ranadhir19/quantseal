#!/usr/bin/env python3
"""quantseal validation harness.

Run from the repository root:  python3 validate.py
Exit code 0 only if every check passes. Checks:

 1. The shipped ledger parses and every receipt passes the schema.
 2. Ledger internal consistency: probe totals match the frozen suites;
    every KL-divergence receipt points at the ledger's one FP16 reference
    receipt; the label-gap exhibit is present (>= 3 publishers, same model,
    same Q4_K_M label, distinct file hashes); at least one claim audit.
 3. The frozen probe suites are intact: the long-context documents match
    their manifest hashes and contain their planted code exactly once.
 4. The hash-check CLI works end to end on fixture files: a file with a
    receipt prints MEASURED, a file without one prints UNMEASURED, and
    lookup/list/claims behave.
 5. Repository hygiene: no model weights in the tree (only the two tiny
    fixture files), no file over 1 MB.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from quantseal import ledger as ledger_mod  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                       (" - " + detail) if detail else ""))


def load_jsonl(path):
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def main() -> int:
    # ---- 1. shipped ledger: schema -------------------------------------
    ledger_path = ROOT / "ledger" / "receipts.jsonl"
    try:
        receipts = ledger_mod.load_ledger(ledger_path)
        check("ledger loads", True, "%d receipts" % len(receipts))
    except Exception as exc:  # noqa: BLE001
        check("ledger loads", False, str(exc))
        receipts = []
    errors = ledger_mod.check_receipts(receipts)
    check("ledger schema", not errors, "; ".join(errors[:4]))

    fixture_path = ROOT / "tests" / "fixtures" / "fixture_ledger.jsonl"
    fixture_receipts = load_jsonl(fixture_path)
    errors = ledger_mod.check_receipts(fixture_receipts)
    check("fixture ledger schema", not errors, "; ".join(errors[:4]))

    # ---- 2. ledger internal consistency --------------------------------
    reasoning = json.loads((ROOT / "probes" / "reasoning.json").read_text())
    instruction = json.loads((ROOT / "probes" / "instruction.json").read_text())
    manifest = json.loads((ROOT / "probes" / "long_context" / "manifest.json").read_text())
    totals = {"reasoning": len(reasoning["items"]),
              "instruction": len(instruction["items"]),
              "long_context": len(manifest["cases"])}

    measurements = [r for r in receipts if r.get("kind") == "measurement"]
    audits = [r for r in receipts if r.get("kind") == "claim_audit"]

    totals_ok = all(
        r["measured"]["probes"][name]["total"] == totals[name]
        for r in measurements for name in totals)
    check("probe totals match frozen suites", totals_ok)

    references = [r for r in measurements if r.get("reference") is None]
    check("exactly one reference receipt", len(references) == 1,
          "%d found" % len(references))
    if references:
        ref_hash = references[0]["file"]["sha256"]
        kld_ok = all(
            r["reference"]["sha256"] == ref_hash
            for r in measurements
            if r["measured"].get("kld_vs_reference") is not None)
        check("all KLD receipts reference the FP16 receipt", kld_ok)
        check("reference receipt has no KLD block",
              references[0]["measured"].get("kld_vs_reference") is None)

    q4 = [r for r in measurements if r["file"]["quant_label"] == "Q4_K_M"]
    publishers = {r["file"]["publisher"] for r in q4}
    hashes = {r["file"]["sha256"] for r in q4}
    models = {r["file"]["model"] for r in q4}
    check("label-gap exhibit: >=3 publishers, one model, one label, distinct files",
          len(publishers) >= 3 and len(hashes) == len(q4) and len(models) == 1,
          "%d publishers, %d files" % (len(publishers), len(q4)))
    check("at least one claim audit (AirLLM)", len(audits) >= 1)

    # ---- 3. frozen probe integrity --------------------------------------
    lc_ok = True
    for case in manifest["cases"]:
        text = (ROOT / "probes" / "long_context" / case["file"]).read_text()
        if hashlib.sha256(text.encode()).hexdigest() != case["sha256"]:
            lc_ok = False
        if text.count(case["code"]) != 1 or case["code_occurrences"] != 1:
            lc_ok = False
    check("long-context documents match manifest, code planted exactly once", lc_ok)
    check("reasoning answers present",
          all(isinstance(i["answer"], (int, float)) for i in reasoning["items"]))
    check("instruction checks typed",
          all(i["check"]["type"] in ("exact", "lines", "csv_tokens", "json_kv",
                                     "last_number")
              for i in instruction["items"]))

    # ---- 4. CLI fixture tests -------------------------------------------
    def run_cli(*argv):
        proc = subprocess.run(
            [sys.executable, "-m", "quantseal", "--ledger", str(fixture_path),
             *argv],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    fa = ROOT / "tests" / "fixtures" / "fixture-a.gguf"
    fb = ROOT / "tests" / "fixtures" / "fixture-b.gguf"
    fa_hash = hashlib.sha256(fa.read_bytes()).hexdigest()
    fixture_entry = ledger_mod.find_by_sha256(fixture_receipts, fa_hash)
    check("fixture file hash matches fixture ledger",
          fixture_entry is not None and
          fixture_entry["file"]["size_bytes"] == fa.stat().st_size)

    rc, out = run_cli("check", str(fa))
    check("CLI check: file with receipt -> MEASURED",
          rc == 0 and "VERDICT: MEASURED" in out and "qs-fixture-a" in out)
    rc, out = run_cli("check", str(fb))
    check("CLI check: file without receipt -> UNMEASURED",
          rc == 0 and "VERDICT: UNMEASURED" in out)
    rc, out = run_cli("lookup", "--sha256", fa_hash)
    check("CLI lookup by hash -> MEASURED", rc == 0 and "VERDICT: MEASURED" in out)
    rc, out = run_cli("lookup", "--sha256", "0" * 64)
    check("CLI lookup unknown hash -> UNMEASURED",
          rc == 0 and "VERDICT: UNMEASURED" in out)
    rc, out = run_cli("list")
    check("CLI list shows fixture receipts",
          rc == 0 and "qs-fixture-a" in out and "qs-fixture-claim" in out)
    rc, out = run_cli("claims")
    check("CLI claims shows the fixture audit",
          rc == 0 and "Fixture claim" in out)
    rc, out = run_cli("check", str(ROOT / "tests" / "fixtures" / "missing.gguf"))
    check("CLI check on missing file -> exit 2", rc == 2)

    # ---- 5. repository hygiene -------------------------------------------
    ggufs = [p for p in ROOT.rglob("*.gguf") if ".git" not in p.parts]
    check("only fixture .gguf files in tree",
          sorted(p.name for p in ggufs) == ["fixture-a.gguf", "fixture-b.gguf"],
          ", ".join(p.name for p in ggufs))
    check("fixture files are tiny", all(p.stat().st_size < 4096 for p in ggufs))
    big = [p for p in ROOT.rglob("*")
           if p.is_file() and ".git" not in p.parts and p.stat().st_size > 1 << 20]
    check("no file over 1 MB in tree", not big,
          ", ".join(str(p.relative_to(ROOT)) for p in big))

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d passed, %d failed" % (
        len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
