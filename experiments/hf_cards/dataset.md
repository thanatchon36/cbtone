---
license: other
license_name: per-source
license_link: https://github.com/thanatchon36/cbtone/blob/main/docs/sources/LICENSES.md
language:
  - en
  - id
  - ms
task_categories:
  - text-classification
tags:
  - central-banks
  - monetary-policy
  - hawkish-dovish
  - finance
  - silver-labels
pretty_name: cbtone silver sentences (LLM-labelled central-bank sentences)
size_categories:
  - 1K<n<10K
configs:
  - config_name: public
    data_files: public.parquet
    default: true
  - config_name: ids_only
    data_files: ids_only.parquet
---

# cbtone silver sentences

The 3,755 central-bank sentences used to train
[`thanatchon36/cbtone-ft-xlmr`](https://huggingface.co/thanatchon36/cbtone-ft-xlmr), each with a
hawkish / dovish / neutral label assigned by a local LLM (`qwen3:4b`, registered prompt `P1@8bfb4852`,
temperature 0). Companion to the paper *Do Local-LLM Tone Scores of Central-Bank
Communication Carry Policy Signal?* (Chongmankhong, 2026).

📄 [Paper (web)](https://thanatchon36.github.io/cbtone/paper/) · 💻 [Code: `cbtone`](https://github.com/thanatchon36/cbtone) ·
🔖 DOI [10.5281/zenodo.23371641](https://doi.org/10.5281/zenodo.23371641)

> **Silver labels, not gold.** Every label comes from an LLM, not from a human annotator. On the human-labelled
> FOMC test split the same LLM and prompt reach a three-class macro-F1 of 0.48. Treat the labels as a noisy
> reading, suitable for distillation and for studying LLM behaviour, not as ground truth.

## Two configurations, because not every source may be redistributed

| Config | Rows | Text included | Sources |
|---|---|---|---|
| `public` (default) | 1,187 | ✅ | Federal Reserve (public domain), Reserve Bank of Australia (CC BY 4.0), ECB monetary-policy press releases (reproduction permitted with acknowledgement) |
| `ids_only` | 2,568 | ❌ | Bank of England, Monetary Authority of Singapore, Bank Indonesia, Bank Negara Malaysia, ECB press conferences |

The second group's terms do not permit redistributing their text, so `ids_only` gives the document URL, the
document's SHA-256, the sentence position and a SHA-256 of the sentence text, plus the label. With the
[`cbtone`](https://github.com/thanatchon36/cbtone) library (`cbtone fetch` then `cbtone snapshot`) the text is
rebuilt locally from the banks' own websites and can be checked against `sentence_sha256`.

33 further training sentences could not be traced back to a single source document and are omitted, so the
dataset has 3,755 of the model's 3,788 training sentences.

```python
from datasets import load_dataset

public = load_dataset("thanatchon36/cbtone-silver-sentences", "public", split="train")
ids = load_dataset("thanatchon36/cbtone-silver-sentences", "ids_only", split="train")
```

## Fields

| Field | Description |
|---|---|
| `bank` | `fed`, `ecb`, `rba` (public); `boe`, `mas`, `bi`, `bnm`, `ecb` (ids_only) |
| `doc_id` | `bank:date:doc_type:lang`, the `cbtone` document identifier |
| `date` | Release date of the source document |
| `doc_type` | `statement`, `minutes`, `press_conference` or `mps` (MAS Monetary Policy Statement) |
| `para_idx`, `sent_idx` | Position of the sentence in the document's tagged policy text |
| `lang` | `en`, `id` or `ms` |
| `label` | `hawkish`, `dovish` or `neutral` (LLM silver label) |
| `text` | Sentence text (`public` only) |
| `url` | Source document URL |
| `doc_sha256` | SHA-256 of the source document as fetched |
| `source_licence` | Terms of the source (`public` only) |
| `sentence_sha256` | SHA-256 of the UTF-8 sentence text (`ids_only` only), to verify a local rebuild |

## Composition

| Bank | public | ids_only |
|---|---|---|
| Federal Reserve | 374 | — |
| Reserve Bank of Australia | 681 | — |
| European Central Bank | 132 | 67 |
| Bank of England | — | 741 |
| Monetary Authority of Singapore | — | 666 |
| Bank Indonesia | — | 671 |
| Bank Negara Malaysia | — | 423 |

Labels over all 3,788 training sentences: neutral 2,890 · dovish 546 · hawkish 352. Languages: English 3,658 ·
Indonesian 66 · Malay 64.

## How it was built

Sentences come from the policy paragraphs (decision, forward guidance, outlook, risks) of each bank's primary
decision documents, fetched politely (robots.txt, ≥ 2 s per request, cached with SHA-256) by `cbtone`. The FOMC
hawkish/dovish dataset (CC BY-NC) is not included and was not used for training; the 200 Southeast Asian
sentences reserved for evaluation are excluded. The export script is
[`experiments/export_hf.py`](https://github.com/thanatchon36/cbtone/blob/main/experiments/export_hf.py).

## Licence

Per source, as listed above and in
[`docs/sources/LICENSES.md`](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/LICENSES.md). The
labels and the metadata are released under CC BY 4.0. Cite the source institution when reusing its text.

## Citation

Please cite the paper; if you use the `cbtone` library, also cite the software.

```bibtex
@misc{chongmankhong2026reading,
  author = {Chongmankhong, Thanatchon},
  title  = {Do Local-{LLM} Tone Scores of Central-Bank Communication Carry Policy Signal? Pre-registered Evidence from Seven Central Banks in Three Languages},
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
  version = {0.1.4},
  url     = {https://github.com/thanatchon36/cbtone},
  doi     = {10.5281/zenodo.23371641}
}
```

**Disclaimer.** Independent open-source project. Public documents only; represents the views of no institution;
not investment advice.
