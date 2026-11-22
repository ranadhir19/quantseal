# quantseal

**Verified quality-cost receipts for the exact LLM files people download.**

A quant label is not an artifact. Three publishers can ship three different
files that all call themselves `Q4_K_M` - different sizes, different
calibration data, measurably different drift from the original model - and
every guide, leaderboard and calculator that speaks in labels is answering
a question about a file that may not be the file on your disk.

quantseal is a neutral measurement ledger that fixes the unit of record:
the **file**, identified by SHA-256. Each receipt binds one exact file to
one hardware profile and records what was actually measured on it - file
size, decode and prompt speed, perplexity and KL divergence against the
full-precision reference file, and a frozen task-probe suite that includes
reasoning, instruction-following and long-context retrieval probes. Every
entry is stamped:

- **MEASURED** - this lab ran the protocol on this file; numbers and repro
  commands are in the receipt.
- **REFUTED** - a specific recorded claim about the file was tested and
  did not hold.
- **UNMEASURED** - no verified measurement exists. This is the honest
  answer the CLI gives for any file whose hash is not in the ledger, and
  the stamp on claim-audit entries for public claims the lab has not
  reproduced. UNMEASURED means *not verified*, never *false*.

## The hash-check CLI

```bash
# from a checkout of this repository
python3 -m quantseal check ~/Downloads/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

If a verified receipt exists for that exact file, you get the receipt. If
not, you get `VERDICT: UNMEASURED` - before you run the file, not after
you notice the output feels off.

```bash
python3 -m quantseal lookup --sha256 <hex>   # receipt for an exact hash
python3 -m quantseal list                    # everything in the ledger
python3 -m quantseal claims                  # claim-audit entries
```

Pure Python standard library. No dependencies, no telemetry, no network.

## First receipts (2026-11-20)

One model, one label, three publishers - the label gap, measured. All
files are Qwen2.5-1.5B-Instruct (Apache-2.0) labelled Q4_K_M, plus the
FP16 reference file. Hardware profile: `vm-epyc-9d25-cpu` - a shared
virtual CPU (AMD EPYC 9D25, 4 threads), CPU-only. These receipts describe
that profile; they do not describe your machine. Full numbers, hashes and
protocols are in `ledger/receipts.jsonl`; the method is in
`measurement/PROTOCOL.md`.

| File | Publisher | Size (bytes) | Decode tok/s | Perplexity | KL vs FP16 (mean / median) | Reasoning | Instruction | Long-context |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| FP16 (reference) | Qwen (official) | 3,560,416,288 | 3.17 | 9.9889 | — | 5/12 | 5/10 | 3/3 |
| Q4_K_M | Qwen (official) | 1,117,320,736 | 7.68 | 10.5168 | 0.0411 / 0.0288 | 4/12 | 3/10 | 3/3 |
| Q4_K_M | bartowski | 986,048,768 | 8.49 | 10.1247 | 0.0465 / 0.0297 | 4/12 | 4/10 | 3/3 |
| Q4_K_M | mradermacher | 986,048,960 | 7.35 | 10.4390 | 0.0625 / 0.0443 | 4/12 | 2/10 | 3/3 |

**The spread at one label:** three files all sold as "Q4_K_M" of the same
model differ by 13.3% in size, 15% in decode speed and 52% in mean KL
divergence from the reference (0.0411 vs 0.0625) — and the metrics
disagree about the ranking: the official file is largest and has the
worst perplexity yet the *lowest* KL divergence; bartowski's has the
best perplexity and speed but mid-pack KL; mradermacher's is within 192
bytes of bartowski's yet diverges half again as much and scores worst
on instruction probes. No single number — and certainly not the label —
tells you which file you are actually getting. The hash does.

Receipt #1 in the ledger is a claim audit, not a measurement: the AirLLM
headline "run a 70B model on a single 4GB GPU" is recorded as UNMEASURED,
with the community measurements that exist (independent reports put 70B
decode at roughly 0.07-0.7 tokens/second on consumer setups) cited as
community evidence - because this lab has not reproduced the claim, and
will not stamp it as anything else until it has.

## Repository layout

- `ledger/receipts.jsonl` - the ledger. One JSON receipt per line.
- `quantseal/` - the CLI and receipt schema (stdlib only).
- `probes/` - the frozen probe suites (reasoning, instruction-following,
  long-context) and the deterministic generator for the long-context
  documents.
- `measurement/` - the protocol (`PROTOCOL.md`) and the exact scripts that
  produced the receipts, built on llama.cpp's own tooling.
- `validate.py` - the validation harness: schema, ledger consistency,
  probe integrity, CLI fixture tests, repository hygiene.
- `NAME_CHECK.md`, `COMPLIANCE.md` - the name collision record and the
  IP/legal compliance record.

## Validate

```bash
python3 validate.py
```

## What a receipt is not

A receipt is not a ranking and not a recommendation. It does not say a
file is "good"; it says what was measured, on what hardware, with what
tools, under a published protocol - and it refuses to say anything about
files it has not measured. That refusal is the product.

## License

MIT. Measured model files are third-party artifacts under their own
licenses (see `COMPLIANCE.md`); no model weights are distributed here -
receipts carry hashes and numbers, never weights.
