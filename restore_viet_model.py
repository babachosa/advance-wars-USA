"""Generate local ViT5 diacritic suggestions, without editing the translation."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
CSV = BASE / "advance_wars_en_vi.csv"
PREDICTIONS = BASE / "viet_diacritic_predictions.jsonl"
MODEL_ID = "nrl-ai/vn-diacritic-vit5-base"
MODEL_DIR = Path(tempfile.gettempdir()) / "aw_vi_vit5_model"
BREAK_RE = re.compile(r"\{PAGE\}|\{0E\}")
TOKEN_RE = re.compile(r"\{[^}]+\}")


def pages() -> list[str]:
    with CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    unique = set()
    for row in rows:
        if not row["vietnamese"]:
            continue
        for page in BREAK_RE.split(row["vietnamese"]):
            plain = " ".join(TOKEN_RE.sub(" ", page).split())
            if plain and re.search("[AEIOUYaeiouy]", plain):
                unique.add(plain)
    return sorted(unique, key=lambda item: (len(item), item))


def loaded() -> dict[str, str]:
    result = {}
    if PREDICTIONS.exists():
        for line in PREDICTIONS.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            result[item["source"]] = item["prediction"]
    return result


def model_and_tokenizer():
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    torch.set_num_threads(min(8, os.cpu_count() or 4))
    path = snapshot_download(
        MODEL_ID, local_dir=MODEL_DIR,
        allow_patterns=("config.json", "generation_config.json", "model.safetensors",
                        "special_tokens_map.json", "spiece.model", "tokenizer.json",
                        "tokenizer_config.json"),
    )
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSeq2SeqLM.from_pretrained(path).eval()
    return torch, tokenizer, model


def predict(texts: list[str], torch, tokenizer, model) -> list[str]:
    batch = tokenizer(texts, return_tensors="pt", padding=True, truncation=True,
                      max_length=256)
    with torch.inference_mode():
        ids = model.generate(**batch, max_new_tokens=160, num_beams=1)
    return tokenizer.batch_decode(ids, skip_special_tokens=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("sample", "run"))
    args = parser.parse_args()
    torch, tokenizer, model = model_and_tokenizer()
    if args.action == "sample":
        samples = ["Mung den Advance Wars!", "Chao mung den Ban Do Chien Dau.",
                   "Ban da co hai don vi bo binh.", "Toi se noi them ve xe tang va bo binh."]
        for source, prediction in zip(samples, predict(samples, torch, tokenizer, model), strict=True):
            print(source, "=>", prediction.encode("unicode_escape").decode())
        return
    done = loaded()
    pending = [page for page in pages() if page not in done]
    print(f"unique pages: {len(done) + len(pending)}, pending: {len(pending)}", flush=True)
    with PREDICTIONS.open("a", encoding="utf-8", newline="\n") as file:
        for start in range(0, len(pending), 8):
            group = pending[start:start + 8]
            outputs = predict(group, torch, tokenizer, model)
            for source, prediction in zip(group, outputs, strict=True):
                file.write(json.dumps({"source": source, "prediction": prediction},
                                      ensure_ascii=False) + "\n")
            file.flush()
            if start % 80 == 0 or start + 8 >= len(pending):
                print(f"processed {min(start + 8, len(pending))}/{len(pending)}", flush=True)


if __name__ == "__main__":
    main()
