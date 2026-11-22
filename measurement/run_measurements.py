#!/usr/bin/env python3
"""Run the full quantseal measurement protocol over a set of GGUF files.

For each model file, in order (the FP16 reference first, because the KLD
base logits come from it):

  1. SHA-256 and byte size of the file.
  2. llama-bench (pp512 + tg128, JSON output) for prompt/decode speed and
     peak RSS of the bench process.
  3. llama-perplexity on the frozen corpus slice. The reference run also
     saves all logits (--save-all-logits); later runs compute KL divergence
     against them (--kl-divergence --kl-divergence-base).
  4. measurement/probe_runner.py for the reasoning, instruction-following
     and long-context probe suites.

Every raw log is kept in the results directory; summary.json collects the
parsed numbers. Receipts in ledger/receipts.jsonl are composed from
summary.json - no number enters a receipt that is not in a raw log here.

Usage:
    python3 measurement/run_measurements.py \
        --tools-dir /path/to/llama-b12590 \
        --corpus /path/to/wikitext2_test_slice.txt \
        --probes-dir probes --results-dir results \
        --reference qwen_fp16.gguf \
        --model qwen_fp16.gguf --model qwen_q4km.gguf ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PPL_RE = re.compile(r"Final estimate: PPL = ([\d.]+) \+/- ([\d.]+)")
CHUNKS_RE = re.compile(r"perplexity over (\d+) chunks")
KLD_MEAN_RE = re.compile(r"Mean\s+KLD:\s*([\d.]+)")
KLD_MEDIAN_RE = re.compile(r"Median\s+KLD:\s*([\d.]+)")
KLD_P95_RE = re.compile(r"95\.0%\s+KLD:\s*([\d.]+)")
KLD_P99_RE = re.compile(r"99\.0%\s+KLD:\s*([\d.]+)")
KLD_MAX_RE = re.compile(r"Maximum\s+KLD:\s*([\d.]+)")
KLD_PPL_Q_RE = re.compile(r"Mean PPL\(Q\)\s*:\s*([\d.]+) \+/- ([\d.]+)")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(cmd, log_path):
    print("+ %s" % " ".join(cmd), flush=True)
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SystemExit("command failed (%d), see %s" % (proc.returncode, log_path))
    return Path(log_path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools-dir", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--probes-dir", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--reference", required=True,
                    help="filename (in --models-dir) of the FP16 reference")
    ap.add_argument("--models-dir", required=True)
    ap.add_argument("--model", action="append", required=True,
                    help="filename in --models-dir; repeat per file")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    tools = Path(args.tools_dir)
    models_dir = Path(args.models_dir)
    results = Path(args.results_dir)
    results.mkdir(parents=True, exist_ok=True)
    bench = str(tools / "llama-bench")
    perplexity = str(tools / "llama-perplexity")
    cli = str(tools / "llama-completion")
    rss_wrapper = str(HERE / "run_with_rss.py")
    kld_base = results / "kld_base_logits.bin"

    summary = {"corpus": args.corpus, "threads": args.threads, "models": {}}
    ordered = [args.reference] + [m for m in args.model if m != args.reference]

    for name in ordered:
        path = models_dir / name
        tag = path.stem.replace(".", "_")
        entry = {"file": name, "sha256": sha256_file(path),
                 "size_bytes": path.stat().st_size}
        print("=== %s (%s bytes, sha256 %s) ===" % (name, entry["size_bytes"],
                                                    entry["sha256"]), flush=True)

        rss_file = results / ("%s_bench_rss.txt" % tag)
        bench_json = run(
            [sys.executable, rss_wrapper, str(rss_file),
             bench, "-m", str(path), "-t", str(args.threads), "-o", "json"],
            results / ("%s_bench.log" % tag))
        rows = json.loads(bench_json[bench_json.index("["):])
        for row in rows:
            if row.get("n_prompt", 0) and not row.get("n_gen", 0):
                entry["prompt_tok_s"] = row["avg_ts"]
            if row.get("n_gen", 0) and not row.get("n_prompt", 0):
                entry["decode_tok_s"] = row["avg_ts"]
        entry["bench_peak_rss_kib"] = int(rss_file.read_text().strip())

        is_reference = name == args.reference
        # Plain perplexity run for every file: the comparable PPL number.
        # The reference run also saves the logits the KLD runs consume.
        ppl_cmd = [perplexity, "-m", str(path), "-f", args.corpus,
                   "-t", str(args.threads)]
        if is_reference:
            ppl_cmd += ["--save-all-logits", str(kld_base)]
        ppl_log = run(ppl_cmd, results / ("%s_perplexity.log" % tag))
        match = PPL_RE.search(ppl_log)
        if not match:
            raise SystemExit("perplexity parse failed for %s" % name)
        entry["perplexity"] = {"value": float(match.group(1)),
                               "uncertainty": float(match.group(2))}
        chunks = CHUNKS_RE.search(ppl_log)
        entry["perplexity_chunks"] = int(chunks.group(1)) if chunks else None

        if not is_reference:
            # KLD run: divergence of this file's next-token distribution
            # from the reference file's, on identical tokens.
            kld_log = run(
                [perplexity, "-m", str(path), "-f", args.corpus,
                 "-t", str(args.threads),
                 "--kl-divergence", "--kl-divergence-base", str(kld_base)],
                results / ("%s_kld.log" % tag))

            def grab(rx):
                m = rx.search(kld_log)
                return float(m.group(1)) if m else None

            entry["kld"] = {"mean": grab(KLD_MEAN_RE),
                            "median": grab(KLD_MEDIAN_RE),
                            "p95": grab(KLD_P95_RE),
                            "p99": grab(KLD_P99_RE),
                            "max": grab(KLD_MAX_RE)}
            ppl_q = KLD_PPL_Q_RE.search(kld_log)
            if ppl_q:
                entry["perplexity_in_kld_run"] = {
                    "value": float(ppl_q.group(1)),
                    "uncertainty": float(ppl_q.group(2))}

        probes_out = results / ("%s_probes.json" % tag)
        run([sys.executable, str(HERE / "probe_runner.py"),
             "--llama-bin", cli, "--model", str(path),
             "--probes-dir", args.probes_dir, "--out", str(probes_out),
             "--threads", str(args.threads)],
            results / ("%s_probes.log" % tag))
        entry["probes_file"] = probes_out.name
        summary["models"][name] = entry
        (results / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print("--- %s done ---" % name, flush=True)

    print("wrote %s" % (results / "summary.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
