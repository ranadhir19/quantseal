# Measurement protocol v1

Every MEASURED receipt in `ledger/receipts.jsonl` was produced by this
protocol, with the tool versions recorded in the receipt itself. A receipt
covers exactly one file (by SHA-256), on exactly one hardware profile. It
says nothing about any other file carrying the same quant label, and
nothing about any other hardware.

## Tools

- llama.cpp official release binaries (build number and commit recorded in
  each receipt): `llama-bench`, `llama-perplexity`, `llama-cli`.
  llama.cpp is a measurement tool only. It is not a dependency of the
  quantseal package and no llama.cpp code ships in this repository.
- `measurement/run_measurements.py` orchestrates the run and keeps every
  raw log; `measurement/probe_runner.py` runs the probe suites;
  `measurement/run_with_rss.py` records peak child RSS.

## Steps, per file

1. **Identity.** SHA-256 and byte size of the file as downloaded.
2. **Speed.** `llama-bench -t 4 -o json`, default tests (pp512, tg128),
   on the recorded hardware profile. Peak RSS of the bench process is
   recorded alongside.
3. **Perplexity and KL divergence.** `llama-perplexity` on the frozen
   corpus slice (below), context 512, stride 0. Every file gets a plain
   perplexity run - that is the comparable perplexity number across
   receipts. The FP16 reference file's run also saves all logits
   (`--save-all-logits`); each quantized file then gets a second run with
   `--kl-divergence --kl-divergence-base <reference logits>`, yielding
   mean/median/percentile KL divergence of the quantized file's next-token
   distribution against the reference file's, on identical tokens. (The
   KLD run's own "Mean PPL(Q)" is recorded in the raw results as a
   cross-check; it differs slightly from the plain-run estimate because
   KLD mode counts boundary tokens differently - the plain-run number is
   the receipt's perplexity.)
4. **Task probes.** The frozen suites in `probes/` (v1: 12 reasoning
   items, 10 instruction-following items, 3 long-context retrieval items
   at ~3,100 tokens with planted codes at 25/50/75% depth), run through
   `llama-completion` in raw completion mode (`-no-cnv`) with the model's
   ChatML template embedded in the prompt, greedy decoding (temperature
   0, seed 1234). The `-no-cnv` flag is load-bearing: llama.cpp's
   front-end tools auto-enable conversation mode when a chat template is
   available and would otherwise wrap the prompt a second time, which
   invalidates the measurement (found and fixed during the v1 rehearsal,
   before any receipt was issued). Scoring is programmatic; see the
   `scoring` field in each suite file.

## Frozen corpus slice

Perplexity comparability requires identical text for every file.

- Source: WikiText-2 raw v1, test split (`wiki.test.raw`), as distributed
  in the `ggml-org/ci` Hugging Face dataset (`wikitext-2-raw-v1.zip`).
- Slice rule: the first 16,384 bytes of `wiki.test.raw`, truncated back to
  the last newline. Result: 16,328 bytes,
  SHA-256 `10db940a16ea22388da422dbd3222fe6c398ec1a7331aec734e45c1351238fb3`.
- The slice text itself is not redistributed in this repository; the rule
  above reconstructs it exactly from the public source.

## Hardware profiles

Receipts name a profile id and describe the machine in full (CPU model,
threads used, RAM, accelerator, OS). A profile is a specific machine in a
specific allocation, not a product class: a receipt measured on a shared
virtual CPU does not describe a desktop with the same nominal chip, and
the ledger never generalises a receipt beyond its profile.

## Verdicts

- **MEASURED** - this lab ran the protocol on this file; the numbers and
  the raw-log-derived values are in the receipt.
- **REFUTED** - a specific, recorded claim about the file was tested under
  the protocol and did not hold.
- **UNMEASURED** - no verified measurement exists. The CLI prints this for
  any file whose hash is not in the ledger, and claim-audit entries use it
  for public claims the lab has not reproduced. UNMEASURED means "not
  verified", never "false".
