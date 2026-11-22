# Compliance record - quantseal

Prepared before publication, per the project's standing IP/legal gate.

## Original name

`quantseal` was coined for this project (quantization + seal: a stamp
applied only after verification). Collision-checked on GitHub, PyPI and
the web on 2026-11-20; no repository, package, product or company by that
name was found. Full record: `NAME_CHECK.md`.

## Original code and copy

All code and text in this repository were written for this project. The
idea - that inference configurations should carry verified measurements -
came from a landscape analysis of the low-resource inference ecosystem;
no third-party project's name, copy, structure, documentation or code is
reused. The probe items (reasoning problems, instruction checks, filler
text for the long-context documents) are original to this repository.

## License

This project's own code and text: MIT (`LICENSE`).

## Third-party tools (not shipped, not dependencies)

Measurements were produced with the official llama.cpp release binaries
(build 12590, commit 34ff2e047; llama.cpp is MIT-licensed, ggml-org).
llama.cpp is a measurement tool used at lab time only: the quantseal
package imports nothing from it, bundles none of it, and does not require
it at runtime. The release binary was downloaded from the project's
official GitHub releases for measurement and deleted afterwards.

## Measured artifacts (asset provenance)

Receipts describe third-party model files. No model weights are
distributed in this repository - only SHA-256 hashes, byte sizes and
measured numbers. The v1 measured set:

| File | Publisher / source repo | Model license |
|---|---|---|
| Qwen2.5-1.5B-Instruct FP16 GGUF | Qwen - `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | Apache-2.0 |
| Qwen2.5-1.5B-Instruct Q4_K_M GGUF | Qwen - `Qwen/Qwen2.5-1.5B-Instruct-GGUF` | Apache-2.0 |
| Qwen2.5-1.5B-Instruct Q4_K_M GGUF | bartowski - `bartowski/Qwen2.5-1.5B-Instruct-GGUF` | Apache-2.0 |
| Qwen2.5-1.5B-Instruct Q4_K_M GGUF | mradermacher - `mradermacher/Qwen2.5-1.5B-Instruct-GGUF` | Apache-2.0 |

All model files were downloaded from the publishers' public Hugging Face
repositories on 2026-11-20, measured locally, and deleted after the
measurements were recorded. The perplexity corpus is a 16,328-byte slice
of WikiText-2 (test split), reconstructed by the rule in
`measurement/PROTOCOL.md` and not redistributed here.

## Claim-audit sources

The AirLLM claim-audit entry cites the project's public README claim and
community measurements as reported in the 2026-11-20 landscape analysis
(`Low_Resource_Inference_Landscape_and_Gap_Analysis_2026-11-20.md`,
Ranadhir Ghosh's research files). The entry is stamped UNMEASURED: it
records that this lab has not reproduced the claim, and presents the
community evidence as community evidence, attributed as such.

## Secrets scan

The repository tree was scanned before publication with the project's
internal-reference scanner and reviewed for credential-shaped strings.
The codebase contains no credentials, tokens, keys or account
identifiers; the CLI performs no network access.
