# Phase G.3 — LoRA fine-tune Qwen2.5 (ship notes)

Goal: move from "AI Engineer who calls pretrained models" to "AI
Engineer who can actually fine-tune." Train a small style-transfer LoRA
on Qwen2.5-3B-Instruct, merge it, serve it through the existing Ollama
provider with zero backend changes, and measure the before/after in the
eval harness.

## Why Qwen2.5-3B-Instruct + LoRA + GGUF + Ollama

Decision stack, with tradeoffs:

| Choice | Why | Alternative we rejected |
|---|---|---|
| LoRA (not full fine-tune) | Fits on free GPUs; <1% of params trained | Full FT needs 24 GB+ VRAM and is slow |
| Qwen2.5-3B-Instruct | Apache-2.0, fast on T4, Ollama-compatible | Llama-3.2-3B (Meta community license restrictions); Qwen-7B (too big for free T4) |
| 4-bit quant for training | ~6 GB VRAM peak; stays on free tier | fp16 (12 GB+ peak — OOMs on T4 with batch size > 1) |
| GGUF Q4_K_M for inference | ~2 GB file, runs on CPU + 8 GB RAM | Safetensors fp16 — requires a GPU at inference |
| Ollama as the server | Backend already has the provider; zero code change | vLLM / TGI — more performance but new auth, new Docker, new env var plumbing |

## What shipped

**Training code**
- `finetune/prepare_dataset.py` — validate + split a chat-format JSONL.
  Rejects empty content, invalid roles, or missing turns. Writes
  `train.jsonl` / `eval.jsonl`.
- `finetune/train.py` — HF `transformers` + `peft` + `trl`. Uses the
  model's native chat template so Ollama compatibility stays intact.
  4-bit quant on CUDA, fp32 fallback on CPU. LoRA target modules cover
  all attention + MLP projections so the adapter has enough capacity to
  actually change behavior. Writes adapter, metrics, and 3 qualitative
  samples.
- `finetune/merge_export.py` — merges the adapter into the base, writes
  a merged HF safetensors folder, optionally converts to GGUF via
  `llama.cpp/convert_hf_to_gguf.py` + `llama-quantize`, and emits an
  Ollama Modelfile customized to the produced GGUF.
- `finetune/Modelfile.template` — Qwen chat template + the project's
  default system prompt baked in. Keeps the fine-tune's learned style
  from fighting the runtime prompt.
- `finetune/train.ipynb` — Colab/Kaggle-ready notebook walking the
  whole flow in 8 cells.
- `finetune/dataset_example.jsonl` — 25 rows in "concise voice
  assistant" style; smoke-test the pipeline, do not cite the numbers.
- `finetune/requirements.txt` — training deps isolated from backend.

**Eval integration**
- `eval/runners/eval_llm_compare.py` — runs the LLM eval against base
  and fine-tuned Ollama models by flipping `OLLAMA_MODEL` and reloading
  the provider factory. Emits a single JSON with side-by-side summaries
  and a Δ on every judge dimension.

## End-to-end user flow

```
dataset_example.jsonl
      |
      v
prepare_dataset.py  ----------->  train.jsonl + eval.jsonl
      |
      v
train.py (Colab T4, ~15 min)  -->  finetune/out/adapter/
                                   finetune/out/metrics.json
                                   finetune/out/samples.jsonl
      |
      v
merge_export.py  ------------->    finetune/out/merged/   (HF)
                                   finetune/out/merged.gguf
                                   finetune/out/Modelfile
      |
      v
ollama create voice-assistant-ft -f finetune/out/Modelfile
      |
      v
backend/.env: OLLAMA_MODEL=voice-assistant-ft
      |
      v
eval_llm_compare.py base=qwen2.5:3b finetuned=voice-assistant-ft
```

## Metrics we expect to move

On the 25-row smoke set, expect:
- `judge.mean_conciseness` up (the rubric specifically rewards short
  replies, and the dataset is full of them).
- `judge.mean_relevance` ~unchanged (base Qwen is already on-topic).
- `judge.mean_correctness` could regress slightly on facts the
  fine-tune never saw — style transfer is not knowledge transfer.
- Latency unchanged (same size model).
- Keyword accuracy slightly up because the fine-tune learns to be more
  literal in common Q&A patterns.

On a real 200-500 row dataset, the conciseness + relevance gains are
typically 0.3–0.8 on the 1–5 scale. Anything bigger is usually overfit;
verify by eyeballing `samples.jsonl`.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Overfit on small data | Default 3 epochs + eval-loss watching. Notebook cell 5 prints qualitative samples — if they look memorized, lower epochs. |
| Colab disconnect mid-training | `save_strategy="no"` + metrics emit at end means nothing saves on disconnect. Workaround: run shorter epochs and checkpoint between; or train on Kaggle which is more stable. |
| GGUF conversion fails | Conversion is guarded — merge still produces the HF model even if llama.cpp is missing. Users can convert later on a different machine. |
| `eval_llm_compare` uses the wrong provider | Runner forces `LLM_PROVIDER=ollama` and reloads the factory singleton so both halves use the same provider code path. |
| Style learned ≠ style wanted | Inspect `samples.jsonl` before merging. If the fine-tune is verbose on eval, adjust the dataset (remove long references) and retrain. |
| License confusion | Qwen2.5 is Apache-2.0. The adapter and the merged model inherit that. The dataset license is yours. |

## Rollback

- Unset `OLLAMA_MODEL=voice-assistant-ft` in `backend/.env` (or flip to
  `qwen2.5:3b`). Backend falls back to the base model immediately.
- Remove the local Ollama entry: `ollama rm voice-assistant-ft`.
- Delete `finetune/out/` artifacts. No schema change, no migration.

## What this slice does NOT do

- **No DPO / RLHF.** Pure SFT. Preference optimization is a separate
  phase once we have human feedback data.
- **No multi-language fine-tune.** English only in the sample data.
  Indic fine-tune would pair with Phase C's Piper voices.
- **No automated hyperparam sweep.** The defaults are reasonable, not
  tuned. A sweep would want ≥ 500 examples first.
- **No dataset versioning.** `dataset_example.jsonl` is committed; a
  real pipeline would use DVC / LFS for anything > a few MB.
- **No CI integration.** Training on CI is expensive; the eval compare
  runs locally post-training. We could add a nightly cron that retrains
  + runs compare once the dataset stabilizes.

## Follow-ups worth doing next

- Grow the dataset to 200+ curated rows in your chosen domain.
- Switch to Qwen2.5-7B-Instruct on Kaggle P100 once the 3B pipeline is
  solid — larger base, same flow.
- Add a DPO pass after SFT using the judge rubric as preferences.
- Push the adapter to HuggingFace Hub so the repo has a second URL
  (nice résumé signal).
- Wire a CI job that fails if the judge overall Δ goes negative by >
  0.3 after a dataset edit.
