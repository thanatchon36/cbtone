---
license: apache-2.0
base_model: FacebookAI/xlm-roberta-base
language:
  - en
  - id
  - ms
library_name: transformers
pipeline_tag: text-classification
tags:
  - central-banks
  - monetary-policy
  - hawkish-dovish
  - finance
  - xlm-roberta
datasets:
  - thanatchon36/cbtone-silver-sentences
metrics:
  - f1
model-index:
  - name: cbtone-ft-xlmr
    results:
      - task:
          type: text-classification
          name: Hawkish/dovish/neutral stance (sentence level)
        dataset:
          name: FOMC hawkish/dovish test split (Shah, Paturi & Chava 2023)
          type: gtfintechlab/fomc_communication
          split: test
        metrics:
          - type: f1
            name: Macro-F1 (3 classes)
            value: 0.41
---

# cbtone-ft-xlmr

A small multilingual classifier that labels a central-bank sentence as **hawkish**, **dovish** or **neutral**.
It is XLM-R base fine-tuned on sentence labels produced by a local LLM (`qwen3:4b`), and is the
"fine-tuned XLM-R" scorer reported in the paper *Reading the Room: Do Local-LLM Tone Scores of Central-Bank
Communication Carry Policy Signal?* (Chongmankhong, 2026).

📄 [Paper (web)](https://thanatchon36.github.io/cbtone/paper/) · ⬇️ [PDF](https://github.com/thanatchon36/cbtone/raw/main/paper/paper.pdf) ·
💻 [Code: `cbtone`](https://github.com/thanatchon36/cbtone) · 📦 [`pip install cbtone`](https://pypi.org/project/cbtone/) ·
🔖 DOI [10.5281/zenodo.23371641](https://doi.org/10.5281/zenodo.23371641) ·
🗂️ [Training data](https://huggingface.co/datasets/thanatchon36/cbtone-silver-sentences)

> **This is a research artefact, not a production model.** It was trained on labels from another model, not on
> human annotation, and it is clearly below the supervised state of the art on the one human-labelled benchmark
> available (see below). Not investment advice; represents the views of no institution.

## Quick start

```python
from transformers import pipeline

clf = pipeline("text-classification", model="thanatchon36/cbtone-ft-xlmr", top_k=None)
clf(
    "The Committee judges that further policy firming may be appropriate to return inflation to 2 percent."
)
```

Labels: `0 = hawkish`, `1 = dovish`, `2 = neutral`. The tone index used in the paper is
`P(hawkish) − P(dovish)` ∈ [−1, 1]. Inputs were truncated to 128 tokens in training.

With the `cbtone` library, the same weights score whole documents (sentence split of the decision,
forward-guidance, outlook and risk paragraphs, probabilities averaged):

```python
from huggingface_hub import snapshot_download
from cbtone.scorers.finetuned import FineTunedScorer

scorer = FineTunedScorer.load(snapshot_download("thanatchon36/cbtone-ft-xlmr"))
scorer.score_text("Bank Indonesia memutuskan untuk mempertahankan BI-Rate sebesar 5,75%.", "id")
```

## Training

| | |
|---|---|
| Base model | `FacebookAI/xlm-roberta-base` (MIT) |
| Training sentences | 3,788 (3,409 train / 379 validation, seeded stratified 10 % split) |
| Sources | Decision statements, minutes and press conferences of the Fed, ECB, BoE, RBA, MAS, Bank Indonesia and Bank Negara Malaysia (2000–2026) |
| Languages | English 3,658 · Indonesian 66 · Malay 64 |
| Labels | neutral 2,890 · dovish 546 · hawkish 352 (imbalanced) |
| Label source | `qwen3:4b` (Ollama digest `359d7dd4…`), temperature 0, registered prompt `P1@8bfb4852`, schema-constrained JSON |
| Excluded | All FOMC hawkish/dovish data (CC BY-NC; evaluation only) and the 200 Southeast Asian evaluation sentences |
| Hyper-parameters | 3 epochs, 642 steps, batch 16, lr 2e-5, max length 128, embeddings frozen, seed 20261014 |
| Hardware | Apple M4 laptop (16 GB, MPS), 6 minutes |
| Weights sha256 | `f16943a319d4732c165faa737b23c6751a82b79da76c70d31893cf70d73908c2` |

The sha256 above is the `model_digest` recorded in the paper's `results/ft_train_report.json`; this upload is
that exact checkpoint. Retraining with `make reproduce` gives a slightly different model, because training on
Apple MPS is not bit-for-bit deterministic (validation macro-F1 0.599 on a fresh-clone rerun).

## Evaluation

| Benchmark | Metric | This model | Local LLM (`qwen3:4b`) | Dictionary | FOMC-RoBERTa |
|---|---|---|---|---|---|
| FOMC test split, 496 human-labelled sentences | 3-class macro-F1 [95 % CI] | **0.41** [0.36, 0.45] | 0.48 [0.43, 0.53] | 0.27 [0.24, 0.30] | ≈ 0.72 ᵃ |
| Held-out validation, 379 sentences (LLM labels) | macro-F1 | 0.61 | 1.00 by construction ᵇ | n/a ᶜ | not run ᵈ |
| Indonesian vs English versions of the same BI statement (128 pairs) | Spearman ρ of document index | 0.44 | 0.61 | n/a (English only) | not run ᵈ (English only) |
| Malay vs English versions of the same BNM statement (139 pairs) | Spearman ρ of document index | 0.54 | 0.53 | n/a (English only) | not run ᵈ (English only) |

ᵃ Not our run: weighted F1 reported on the same split by Shah, Paturi & Chava (2023), so not strictly comparable
with the macro-F1 values beside it.
ᵇ The validation labels *are* the LLM's answers, so the LLM agrees with them perfectly; the number carries no
information.
ᶜ The validation split is drawn at training time and is not stored, and rebuilding the training frame does not
reproduce the same row order, so the exact 379 sentences cannot be recovered for other scorers. For reference, the
dictionary's agreement with the LLM labels over all 3,658 English training sentences is macro-F1 0.33 (it reads
English only).
ᵈ FOMC-RoBERTa is a gated model on the Hugging Face Hub; access was pending when the study ran, so it was not
evaluated on anything.

Scores on the Southeast Asian silver sets (0.46–0.67 macro-F1) are against labels from the same LLM family and
measure self-agreement, not accuracy, so they are not reported as results. In the pre-registered tests of policy
signal (next-decision prediction, announcement-window market reaction) this scorer, like the LLM it imitates, did
not beat simple baselines after multiple-testing correction; see the paper.

## Intended use and limitations

- **Use it for:** research on central-bank communication; a cheap, local, multilingual approximation of an LLM
  stance reader (≈ 270 M parameters, CPU-friendly) for monitoring dashboards; a baseline.
- **Do not use it for:** trading or forecasting decisions; any claim of human-level stance accuracy; languages or
  banks far outside the training set without validation.
- **Known biases:** over-predicts `neutral` (76 % of training labels); inherits the LLM's reading, including its
  prompt dependence (paper, Section 6.1); English-dominated training data.
- **Source text.** The training sentences come from public central-bank websites. Some sources do not permit
  redistribution of their text; the weights are released, the text is not. The companion dataset ships text only
  for sources that allow it and identifiers for the rest.

## Citation

Please cite the paper; if you use the `cbtone` library, also cite the software.

```bibtex
@misc{chongmankhong2026reading,
  author = {Chongmankhong, Thanatchon},
  title  = {Reading the Room: Do Local-{LLM} Tone Scores of Central-Bank Communication Carry Policy Signal? Pre-registered Evidence from Seven Central Banks in Three Languages},
  year   = {2026},
  note   = {Preprint},
  url    = {https://thanatchon36.github.io/cbtone/paper/}
}
```

```bibtex
@software{chongmankhong_cbtone,
  author  = {Chongmankhong, Thanatchon},
  title   = {cbtone},
  year    = {2026},
  version = {0.1.2},
  url     = {https://github.com/thanatchon36/cbtone},
  doi     = {10.5281/zenodo.23371641}
}
```

**Disclaimer.** Independent open-source project. Public documents only; represents the views of no institution;
not investment advice. The author works at a central bank, and the project makes no comment on any bank's policy
choices.
