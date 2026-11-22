#!/usr/bin/env python3
"""Run the frozen quantseal probe suites against one GGUF file.

Uses llama-completion in raw completion mode (-no-cnv): the Qwen2.5
ChatML template is embedded in the prompt text itself (identical bytes
for every file under test, since all v1 receipts cover one base model).
This matters: llama.cpp's front-end tools auto-enable conversation mode
when a chat template is available and would otherwise wrap the prompt a
second time. Sampling is greedy (temperature 0, fixed seed) so results
are reproducible, and stdin is /dev/null so interactive mode exits at
end of generation.

Usage:
    python3 measurement/probe_runner.py \
        --llama-bin /path/to/llama-completion --model file.gguf \
        --probes-dir probes --out results.json [--threads 4]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHATML = "<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
PROMPT_TOKENS_RE = re.compile(r"prompt eval time =\s+[\d.]+ ms /\s+(\d+) tokens")


def run_model(llama_bin, model, prompt, max_tokens, threads, ctx=8192):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(prompt)
        prompt_file = fh.name
    cmd = [
        llama_bin, "-m", model, "-f", prompt_file,
        "-c", str(ctx), "-t", str(threads),
        "--temp", "0", "-s", "1234", "-n", str(max_tokens),
        "--no-display-prompt", "--no-escape", "--perf", "-no-cnv",
        "-r", "<|im_end|>",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                              stdin=subprocess.DEVNULL)
    finally:
        Path(prompt_file).unlink(missing_ok=True)
    output = proc.stdout
    # llama-completion renders the EOS token as a trailing "[end of text]"
    # marker in the output stream; it is tool furniture, not model output.
    output = output.replace("[end of text]", "").strip()
    match = PROMPT_TOKENS_RE.search(proc.stderr)
    prompt_tokens = int(match.group(1)) if match else None
    return output, prompt_tokens


def last_number(text):
    nums = NUMBER_RE.findall(text.replace(",", ""))
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None


def check_instruction(check, output) -> bool:
    kind = check["type"]
    expected = check["expected"]
    if kind == "exact":
        return output.strip() == expected
    if kind == "lines":
        return [ln.strip() for ln in output.strip().splitlines() if ln.strip()] == expected
    if kind == "csv_tokens":
        got = [tok.strip() for tok in output.strip().split(",")]
        return got == expected
    if kind == "json_kv":
        try:
            got = json.loads(output.strip())
        except json.JSONDecodeError:
            return False
        return isinstance(got, dict) and all(got.get(k) == v for k, v in expected.items())
    if kind == "last_number":
        value = last_number(output)
        return value is not None and abs(value - float(expected)) < 1e-6
    raise ValueError("unknown check type: %s" % kind)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llama-bin", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--probes-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    probes = Path(args.probes_dir)
    results = {"model": args.model, "suites": {}}

    reasoning = json.loads((probes / "reasoning.json").read_text(encoding="utf-8"))
    items = []
    for item in reasoning["items"]:
        prompt = CHATML.format(system=reasoning["system"], user=item["prompt"])
        output, _ = run_model(args.llama_bin, args.model, prompt, 96, args.threads)
        value = last_number(output)
        passed = value is not None and abs(value - float(item["answer"])) < 1e-6
        items.append({"id": item["id"], "passed": passed, "output": output[:200]})
        print("reasoning %s: %s" % (item["id"], "pass" if passed else "FAIL"), flush=True)
    results["suites"]["reasoning"] = {
        "passed": sum(1 for i in items if i["passed"]),
        "total": len(items), "items": items}

    instruction = json.loads((probes / "instruction.json").read_text(encoding="utf-8"))
    items = []
    for item in instruction["items"]:
        prompt = CHATML.format(system=instruction["system"], user=item["prompt"])
        output, _ = run_model(args.llama_bin, args.model, prompt, 128, args.threads)
        passed = check_instruction(item["check"], output)
        items.append({"id": item["id"], "passed": passed, "output": output[:200]})
        print("instruction %s: %s" % (item["id"], "pass" if passed else "FAIL"), flush=True)
    results["suites"]["instruction"] = {
        "passed": sum(1 for i in items if i["passed"]),
        "total": len(items), "items": items}

    manifest = json.loads((probes / "long_context" / "manifest.json").read_text(encoding="utf-8"))
    items = []
    for case in manifest["cases"]:
        document = (probes / "long_context" / case["file"]).read_text(encoding="utf-8")
        user = document.strip() + "\n\n" + manifest["question"]
        prompt = CHATML.format(
            system="You are a helpful assistant. Answer with just the number.",
            user=user)
        output, prompt_tokens = run_model(
            args.llama_bin, args.model, prompt, 32, args.threads)
        passed = case["code"] in output
        items.append({"id": case["id"], "passed": passed,
                      "prompt_tokens": prompt_tokens, "output": output[:200]})
        print("long_context %s: %s (prompt tokens: %s)" % (
            case["id"], "pass" if passed else "FAIL", prompt_tokens), flush=True)
    results["suites"]["long_context"] = {
        "passed": sum(1 for i in items if i["passed"]),
        "total": len(items), "items": items}

    Path(args.out).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
