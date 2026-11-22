#!/usr/bin/env python3
"""Generate the frozen long-context probe documents.

Deterministic: the same script always produces the same three documents.
Each document is a haystack of mundane records text (~3,100 tokens for the
Qwen2.5 tokenizer, measured at protocol freeze time) with one planted
sentence carrying a code at a stated depth. The probe question is appended
by measurement/probe_runner.py at run time, so these files hold document
text only.

Run:  python3 probes/long_context.py   (writes probes/long_context/*)
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

FILLER = [
    "The committee reviewed the quarterly maintenance schedule for the east wing.",
    "A delivery of office paper arrived on Tuesday and was stored in room 204.",
    "The garden club announced that the spring planting will begin in March.",
    "Minutes from the last meeting were circulated to all department heads.",
    "The library extended its opening hours for the examination period.",
    "A new bicycle rack was installed near the north entrance of the building.",
    "The cafeteria menu for next week includes two vegetarian options daily.",
    "Staff were reminded to submit travel requests at least ten days in advance.",
    "The swimming pool will close for repairs during the first week of June.",
    "An updated fire drill procedure was posted on the notice board by the stairs.",
    "The orchestra scheduled an extra rehearsal before the winter concert.",
    "Parking permits for the coming year can be renewed at the front office.",
    "The weather station recorded twelve millimeters of rain over the weekend.",
    "A lost umbrella was handed in at reception and remains unclaimed.",
    "The book club selected a historical novel for its November discussion.",
    "Window cleaning for the upper floors is planned for the end of the month.",
    "The chess tournament drew twenty-four players from the local schools.",
    "New signage was put up along the walking trail by the river.",
    "The archive room received three boxes of donated photographs on Friday.",
    "Volunteers are needed to help with the charity bake sale on Saturday.",
    "The bus timetable changes slightly during the school holidays.",
    "A technician inspected the heating system and reported it in good order.",
    "The art exhibition in the main hall runs until the end of September.",
    "Members voted to keep the annual subscription fee unchanged this year.",
]

NEEDLE_TEMPLATE = (
    "Among the routine entries, the register notes that the special code "
    "for the archive box is {code}."
)

CASES = [
    {"id": "lc1", "code": "7391", "depth": 0.25},
    {"id": "lc2", "code": "5826", "depth": 0.50},
    {"id": "lc3", "code": "9140", "depth": 0.75},
]

TARGET_CHARS = 16400  # approx 3,100 Qwen2.5 tokens; exact count recorded per run


def build_document(code: str, depth: float, seed: int) -> str:
    rng = random.Random(seed)
    sentences = []
    total = 0
    i = 0
    while total < TARGET_CHARS:
        sentence = FILLER[i % len(FILLER)]
        sentences.append(sentence)
        total += len(sentence) + 1
        i += 1
        if i % len(FILLER) == 0:
            rng.shuffle(FILLER)
    needle = NEEDLE_TEMPLATE.format(code=code)
    insert_at = int(len(sentences) * depth)
    sentences.insert(insert_at, needle)
    paragraphs = []
    for j in range(0, len(sentences), 4):
        paragraphs.append(" ".join(sentences[j:j + 4]))
    return "\n\n".join(paragraphs) + "\n"


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "long_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"suite": "quantseal long-context probe v1", "frozen": "2026-11-20",
                "question": "What is the special code for the archive box? "
                            "Answer with just the number.",
                "cases": []}
    for idx, case in enumerate(CASES):
        text = build_document(case["code"], case["depth"], seed=1000 + idx)
        name = "%s.txt" % case["id"]
        (out_dir / name).write_text(text, encoding="utf-8")
        manifest["cases"].append({
            "id": case["id"],
            "file": name,
            "code": case["code"],
            "depth_fraction": case["depth"],
            "chars": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "code_occurrences": text.count(case["code"]),
        })
        print("wrote %s (%d chars, code at %.0f%% depth)" % (
            name, len(text), case["depth"] * 100))
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
