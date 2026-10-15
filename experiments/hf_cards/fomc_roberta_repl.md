---
license: cc-by-nc-4.0
language:
  - en
base_model: FacebookAI/roberta-large
pipeline_tag: text-classification
tags:
  - finance
  - central-banking
  - hawkish-dovish-classification
  - replication
library_name: transformers
---

# cbtone-fomc-roberta-repl

**A replication, not the original.** This is *not* `gtfintechlab/FOMC-RoBERTa`, and it carries none of its
weights. It is an independent fine-tune of `FacebookAI/roberta-large` on the public train split of the
hawkish/dovish FOMC sentence data of Shah, Paturi and Chava (2023), following the recipe in their paper.
It exists because the authors' checkpoint is gated and access was not granted for the study that needed it
([cbtone](https://github.com/thanatchon36/cbtone), decision D21). Use their model if you have access; this
one is for reproducing the cbtone paper, and for anyone who cannot obtain theirs.

Please cite **Shah, Paturi and Chava (2023)** for the task, the data and the recipe. The credit for the
method is theirs; the errors in this re-implementation are ours.

## What it does

Three-way stance classification of a single English sentence from central-bank communication:
`hawkish`, `dovish` or `neutral`. Label order is the model's own `id2label`, so no external mapping is
needed (unlike the original checkpoint, whose `LABEL_0/1/2` ids must be read from the authors' README).

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

name = "thanatchon36/cbtone-fomc-roberta-repl"
tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name).eval()

text = "The Committee decided to raise the target range for the federal funds rate."
enc = tok(text, return_tensors="pt", truncation=True, max_length=256)
with torch.inference_mode():
    probs = model(**enc).logits.softmax(-1)
print({model.config.id2label[i]: round(p.item(), 3) for i, p in enumerate(probs[0])})
```

In `cbtone` it loads through the fine-tuned scorer interface:

```bash
cbtone score --scorer ft --model-dir <local copy> fed ecb boe --out scores.parquet
```

## Training

| | |
|---|---|
| Base model | `FacebookAI/roberta-large`, revision `722cf37b1afa9454edce342e7895e588b6ff1d59` |
| Data | `gtfintechlab/fomc_communication`, revision `6b0283f5…`, **train split only** (1,984 sentences) |
| Split | stratified 20 % of train held out for validation; the test split was never trained on |
| Optimiser | AdamW, lr 1e-5, weight decay 0.01, 6 % linear warm-up then linear decay, grad clip 1.0 |
| Batch | 16 (as four micro-batches of 4 with gradient accumulation), max length 256 |
| Stopping | early stopping on validation macro-F1, patience 3, at most 10 epochs |
| Seeds | 3 trained; **selection on validation macro-F1 only** |
| Hardware | Apple M4, 16 GB, MPS; about 2 hours for three seeds |

The released weights are seed `20261014`, best epoch 7, validation macro-F1 0.734. The authors searched a
grid over learning rate and batch size; we did not, so this is a faithful-recipe replication rather than a
tuned one. Rebuild it with `make fomc-roberta` in the cbtone repository.

## Evaluation

Three-class macro-F1 on the 496-sentence FOMC **test** split, with 95 % bootstrap intervals over sentences:

| Scorer | Macro-F1 [95 % CI] |
|---|---|
| **This model** | **0.71** [0.67, 0.75] |
| Local LLM, `qwen3:4b` zero-shot | 0.48 [0.43, 0.53] |
| `cbtone-ft-xlmr` (XLM-R on LLM labels) | 0.41 [0.36, 0.45] |
| Word-list dictionary (`dict-v1`) | 0.27 [0.24, 0.30] |
| Original FOMC-RoBERTa, as published by Shah et al. (2023) | ≈ 0.72 (weighted F1) ᵃ |

ᵃ Their reported metric is weighted F1 on the same split, so it is not strictly comparable with the
macro-F1 values above; it is given for orientation.

Across the three seeds, test macro-F1 is **0.70 ± 0.02**, so the released seed is typical. Seventeen test
sentences also occur verbatim in train (a property of the dataset, which the original model shares);
dropping them leaves the score at 0.71.

## Limitations and intended use

- **In-distribution.** It is trained on the same corpus the test split comes from, so 0.71 is a ceiling for
  FOMC text, not a general accuracy.
- **It transfers worse than the number suggests.** On Southeast Asian central-bank sentences its macro-F1
  falls by about 0.25 for the Monetary Authority of Singapore (measured against LLM-produced silver labels,
  which carry their own error). A word-list dictionary loses nothing on the same text.
- **It carries no policy signal.** In the cbtone study this model predicts the next policy decision no
  better than a persistence baseline at any adequately powered bank, the Fed included, and explains the
  announcement-window market move no better than the much weaker LLM scorer. Reading sentences well does
  not make a tone index predictive.
- **English only**, single sentences, Fed register. Document-level use averages sentence probabilities.
- **Not investment advice.** It is a research instrument for measuring communication, nothing more.

## Licence

**CC-BY-NC-4.0**, inherited from the training data (`gtfintechlab/fomc_communication`). Non-commercial use
only, attribution required. The base model is MIT. The cbtone code is Apache-2.0.

## Citation

```bibtex
@inproceedings{shah2023trillion,
  author    = {Shah, Agam and Paturi, Suvan and Chava, Sudheer},
  title     = {Trillion Dollar Words: A New Financial Dataset, Task \& Market Analysis},
  booktitle = {Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics},
  year      = {2023}
}

@misc{chongmankhong2026reading,
  author = {Chongmankhong, Thanatchon},
  title  = {Reading the Room: Do Local-{LLM} Tone Scores of Central-Bank Communication Carry Policy Signal? Pre-registered Evidence from Seven Central Banks in Three Languages},
  year   = {2026},
  note   = {Preprint},
  url    = {https://thanatchon36.github.io/cbtone/paper/}
}
```
