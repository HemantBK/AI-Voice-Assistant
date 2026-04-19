"""Merge a LoRA adapter into the base model and write out the artifacts
Ollama needs: a merged HF model folder, an optional GGUF (quantized),
and an Ollama Modelfile ready for `ollama create`.

Flow:
  1. Load base model + attach adapter.
  2. Merge weights (so we ship a single model, not base + adapter).
  3. Save merged model as HF safetensors.
  4. Optionally convert to GGUF via llama.cpp's convert-hf-to-gguf.py.
  5. Copy + customize Modelfile.template next to the output.

GGUF conversion needs llama.cpp checked out nearby:
    git clone https://github.com/ggerganov/llama.cpp

Pass its path with --llama-cpp-dir. The default Q4_K_M quantization fits
on CPU + 8 GB RAM for the merged 3B model.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


TEMPLATE_PATH = Path(__file__).parent / "Modelfile.template"


def merge_adapter(adapter_dir: Path, base_model: str, merged_dir: Path) -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("Loading base model: %s", base_model)
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    logger.info("Loading + merging adapter: %s", adapter_dir)
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    model = model.merge_and_unload()

    logger.info("Saving merged model to %s", merged_dir)
    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(merged_dir), safe_serialization=True)
    AutoTokenizer.from_pretrained(str(adapter_dir)).save_pretrained(str(merged_dir))


def convert_to_gguf(merged_dir: Path, llama_cpp_dir: Path, quant: str,
                    out_path: Path) -> bool:
    if not llama_cpp_dir.exists():
        logger.warning("llama.cpp not at %s; skipping GGUF conversion", llama_cpp_dir)
        return False
    convert = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not convert.exists():
        # Older layout fallback
        convert = llama_cpp_dir / "convert-hf-to-gguf.py"
    if not convert.exists():
        logger.warning("convert_hf_to_gguf.py not found in %s", llama_cpp_dir)
        return False
    logger.info("Converting to GGUF (%s)...", quant)
    unquant = out_path.with_suffix(".f16.gguf")
    subprocess.run(
        [sys.executable, str(convert), str(merged_dir), "--outfile", str(unquant), "--outtype", "f16"],
        check=True,
    )
    quantize = llama_cpp_dir / "build" / "bin" / "llama-quantize"
    if not quantize.exists():
        quantize = llama_cpp_dir / "llama-quantize"
    if not quantize.exists():
        logger.warning(
            "llama-quantize binary not found; leaving f16 GGUF at %s. "
            "Build llama.cpp to get quantization.", unquant,
        )
        shutil.copy(unquant, out_path)
        return True
    subprocess.run([str(quantize), str(unquant), str(out_path), quant], check=True)
    unquant.unlink(missing_ok=True)
    logger.info("Wrote %s", out_path)
    return True


def write_modelfile(merged_gguf: Path, modelfile_out: Path) -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rel = f"./{merged_gguf.name}"
    customized = template.replace("./merged.gguf", rel)
    modelfile_out.write_text(customized, encoding="utf-8")
    logger.info("Wrote %s", modelfile_out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", type=Path, required=True,
                    help="path to the LoRA adapter directory written by train.py")
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct")
    ap.add_argument("--out-dir", type=Path, default=Path("finetune/out"))
    ap.add_argument("--llama-cpp-dir", type=Path, default=Path("llama.cpp"),
                    help="checkout of https://github.com/ggerganov/llama.cpp")
    ap.add_argument("--quant", default="Q4_K_M",
                    help="GGUF quant level (Q4_K_M, Q5_K_M, Q8_0, ...). Q4_K_M fits ~2GB.")
    ap.add_argument("--skip-gguf", action="store_true",
                    help="only merge HF weights; skip GGUF conversion")
    args = ap.parse_args()

    merged_dir = args.out_dir / "merged"
    merge_adapter(args.adapter, args.base_model, merged_dir)

    gguf_path = args.out_dir / "merged.gguf"
    if not args.skip_gguf:
        converted = convert_to_gguf(merged_dir, args.llama_cpp_dir, args.quant, gguf_path)
        if converted:
            write_modelfile(gguf_path, args.out_dir / "Modelfile")
    else:
        logger.info("Skipped GGUF conversion; merged HF model lives at %s", merged_dir)


if __name__ == "__main__":
    main()
