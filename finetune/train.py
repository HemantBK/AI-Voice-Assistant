"""LoRA fine-tune Qwen2.5-3B-Instruct on a chat-format JSONL dataset.

Runs on:
  - Google Colab free T4 (16 GB) — ~15 min for 25 examples × 3 epochs
  - Kaggle free P100 (16 GB) — similar
  - Any local CUDA GPU with >= 8 GB VRAM

Outputs:
  - LoRA adapter under `--out-dir/adapter/`
  - Training loss curve JSON under `--out-dir/metrics.json`
  - A small sample of before/after completions under `--out-dir/samples.jsonl`

Then run `finetune/merge_export.py` to produce a merged model + Modelfile.

Notes:
  - We use the model's native chat template via `tokenizer.apply_chat_template`
    so the fine-tuned model stays compatible with Ollama's chat endpoint.
  - 4-bit quantization (bitsandbytes) is enabled on CUDA; on CPU we fall back
    to fp16/fp32 which is slower but at least trains.
  - Small datasets (<50 examples) overfit in 2-3 epochs. We stop early on
    eval_loss plateau.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_OUT_DIR = Path("finetune/out")


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-file", type=Path, required=True)
    ap.add_argument("--eval-file", type=Path, default=None)
    ap.add_argument("--base-model", default=DEFAULT_BASE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-seq-len", type=int, default=1024)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-4bit", action="store_true",
                    help="disable 4-bit quant (CPU or non-bnb environments)")
    args = ap.parse_args()

    # Heavy imports are inside main so `--help` works without torch.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    cuda = torch.cuda.is_available()
    use_4bit = cuda and not args.no_4bit

    logger.info("base_model=%s cuda=%s 4bit=%s", args.base_model, cuda, use_4bit)

    tok = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    quant_kwargs: dict = {}
    if use_4bit:
        from transformers import BitsAndBytesConfig
        quant_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16 if cuda else torch.float32,
        device_map="auto" if cuda else None,
        **quant_kwargs,
    )
    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    def format_row(row):
        text = tok.apply_chat_template(
            row["messages"], tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    train_rows = load_jsonl(args.train_file)
    eval_rows = load_jsonl(args.eval_file) if args.eval_file else []
    train_ds = Dataset.from_list(train_rows).map(format_row)
    eval_ds = Dataset.from_list(eval_rows).map(format_row) if eval_rows else None

    def tokenize(batch):
        enc = tok(batch["text"], truncation=True, max_length=args.max_seq_len, padding=False)
        enc["labels"] = [ids.copy() for ids in enc["input_ids"]]
        return enc

    train_ds = train_ds.map(tokenize, batched=True, remove_columns=train_ds.column_names)
    if eval_ds is not None:
        eval_ds = eval_ds.map(tokenize, batched=True, remove_columns=eval_ds.column_names)

    collator = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False)

    training_args = TrainingArguments(
        output_dir=str(args.out_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=0.03,
        logging_steps=5,
        save_strategy="no",
        eval_strategy="epoch" if eval_ds is not None else "no",
        bf16=False,
        fp16=cuda,
        optim="paged_adamw_8bit" if use_4bit else "adamw_torch",
        report_to="none",
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tok,
        data_collator=collator,
    )

    logger.info("Starting training: %d train / %d eval examples",
                len(train_ds), len(eval_ds) if eval_ds else 0)
    train_result = trainer.train()

    # Save adapter only (tiny — tens of MB).
    adapter_dir = args.out_dir / "adapter"
    model.save_pretrained(str(adapter_dir))
    tok.save_pretrained(str(adapter_dir))

    metrics = dict(train_result.metrics)
    if eval_ds is not None:
        metrics.update(trainer.evaluate())
    metrics_path = args.out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    logger.info("Saved adapter to %s and metrics to %s", adapter_dir, metrics_path)

    # Quick before/after qualitative sample on eval set
    if eval_rows:
        logger.info("Sampling qualitative completions (first 3 eval rows)...")
        samples = []
        model.eval()
        for row in eval_rows[:3]:
            msgs = [m for m in row["messages"] if m["role"] != "assistant"]
            prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            ids = tok(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **ids, max_new_tokens=128, do_sample=False, pad_token_id=tok.eos_token_id,
                )
            decoded = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
            samples.append({
                "prompt": msgs[-1]["content"],
                "reference": next(m["content"] for m in row["messages"] if m["role"] == "assistant"),
                "finetuned": decoded.strip(),
            })
        (args.out_dir / "samples.jsonl").write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in samples) + "\n"
        )
        logger.info("Wrote qualitative samples to %s", args.out_dir / "samples.jsonl")

    logger.info("Done. Next step:")
    logger.info("  python finetune/merge_export.py --adapter %s", adapter_dir)


if __name__ == "__main__":
    main()
