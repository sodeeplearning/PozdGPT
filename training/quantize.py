#!/usr/bin/env python3
"""Quantize an HF model checkpoint into GGUF (4/6/8/16-bit) and AWQ 4-bit."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from llmcompressor.modifiers.transform.awq import AWQModifier


GGUF_TYPES = {
    "f16": "F16",
    "q8_0": "Q8_0",
    "q6_k": "Q6_K",
    "q4_k_m": "Q4_K_M",
}

DEFAULT_CONVERT_SCRIPTS = [
    Path.home() / "llama-tools/llama.cpp/convert_hf_to_gguf.py",
    Path.home() / ".unsloth/llama.cpp/convert_hf_to_gguf.py",
]


def find_convert_script(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            sys.exit(f"convert script not found: {p}")
        return p
    for candidate in DEFAULT_CONVERT_SCRIPTS:
        if candidate.is_file():
            return candidate
    sys.exit(
        "Could not locate convert_hf_to_gguf.py. Pass --convert-script /path/to/convert_hf_to_gguf.py"
    )


def find_quantize_bin(explicit: str | None) -> str:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            sys.exit(f"llama-quantize binary not found: {p}")
        return str(p)
    found = shutil.which("llama-quantize")
    if found:
        return found
    sys.exit(
        "Could not locate llama-quantize on PATH. Pass --quantize-bin /path/to/llama-quantize"
    )


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def should_write(path: Path, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        print(f"skip (exists): {path}  -- use --overwrite to regenerate")
        return False
    return True


def make_gguf(checkpoint: Path, out_dir: Path, base_name: str, overwrite: bool,
              convert_script: Path, quantize_bin: str) -> None:
    # 1. Convert HF checkpoint -> f16 GGUF (base for both f16 output and quantization).
    f16_path = out_dir / f"{base_name}-f16.gguf"
    if should_write(f16_path, overwrite):
        run([
            sys.executable, str(convert_script), str(checkpoint),
            "--outtype", "f16", "--outfile", str(f16_path),
        ])
    elif not f16_path.exists():
        sys.exit(f"f16 GGUF missing and not regenerated: {f16_path}")

    # 2. Quantize the f16 GGUF into each lower-precision variant.
    for key in ("q8_0", "q6_k", "q4_k_m"):
        qtype = GGUF_TYPES[key]
        out_path = out_dir / f"{base_name}-{qtype}.gguf"
        if not should_write(out_path, overwrite):
            continue
        run([quantize_bin, str(f16_path), str(out_path), qtype])


def make_awq(checkpoint: Path, out_dir: Path, base_name: str, overwrite: bool,
             num_samples: int, max_seq_len: int) -> None:
    awq_dir = out_dir / f"{base_name}-awq-4bit"
    if awq_dir.exists() and not overwrite:
        print(f"skip (exists): {awq_dir}  -- use --overwrite to regenerate")
        return

    if awq_dir.exists():
        shutil.rmtree(awq_dir)

    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint), trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(checkpoint), torch_dtype="auto", trust_remote_code=True
    )

    # Calibration data for activation-aware scaling.
    ds = load_dataset("HuggingFaceH4/ultrachat_200k", split=f"train_sft[:{num_samples}]")

    def preprocess(sample):
        return {"text": tokenizer.apply_chat_template(sample["messages"], tokenize=False)}

    def tokenize(sample):
        return tokenizer(
            sample["text"],
            padding=False,
            max_length=max_seq_len,
            truncation=True,
            add_special_tokens=False,
        )

    ds = ds.shuffle(seed=42).map(preprocess, remove_columns=ds.column_names)
    ds = ds.map(tokenize, remove_columns=["text"])

    recipe = [
        AWQModifier(duo_scaling="both"),
        QuantizationModifier(ignore=["lm_head"], scheme="W4A16_ASYM", targets=["Linear"]),
    ]

    oneshot(
        model=model,
        dataset=ds,
        recipe=recipe,
        max_seq_length=max_seq_len,
        num_calibration_samples=num_samples,
    )

    model.save_pretrained(str(awq_dir), save_compressed=True)
    tokenizer.save_pretrained(str(awq_dir))
    print(f"AWQ 4-bit model saved to: {awq_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quantize an HF checkpoint to GGUF (4/6/8/16-bit) and AWQ 4-bit.",
    )
    parser.add_argument("checkpoint", help="Path to the HF model checkpoint directory.")
    parser.add_argument(
        "-o", "--out-dir", default=None,
        help="Output directory (default: checkpoint's parent directory).",
    )
    parser.add_argument(
        "-n", "--name", default=None,
        help="Base name for output files (default: checkpoint directory name).",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing output files instead of skipping them.",
    )
    parser.add_argument("--skip-gguf", action="store_true", help="Skip GGUF quantization.")
    parser.add_argument("--skip-awq", action="store_true", help="Skip AWQ quantization.")
    parser.add_argument(
        "--awq-samples", type=int, default=256,
        help="Number of calibration samples for AWQ (default: 256).",
    )
    parser.add_argument(
        "--awq-seq-len", type=int, default=512,
        help="Max sequence length for AWQ calibration (default: 512).",
    )
    parser.add_argument(
        "--convert-script", default=None,
        help="Path to llama.cpp convert_hf_to_gguf.py (auto-detected if omitted).",
    )
    parser.add_argument(
        "--quantize-bin", default=None,
        help="Path to llama-quantize binary (auto-detected from PATH if omitted).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    checkpoint = Path(args.checkpoint).expanduser().resolve()
    if not checkpoint.is_dir():
        sys.exit(f"Checkpoint directory not found: {checkpoint}")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else checkpoint.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.name or checkpoint.name

    if not args.skip_gguf:
        convert_script = find_convert_script(args.convert_script)
        quantize_bin = find_quantize_bin(args.quantize_bin)
        make_gguf(checkpoint, out_dir, base_name, args.overwrite, convert_script, quantize_bin)

    if not args.skip_awq:
        make_awq(checkpoint, out_dir, base_name, args.overwrite,
                 args.awq_samples, args.awq_seq_len)

    print("Done.")


if __name__ == "__main__":
    main()
