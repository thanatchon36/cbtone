# cbtone

Hawkish/dovish tone signals from **public** central-bank communication, with the evaluation
machinery to test whether those signals carry information about later policy decisions and market
reactions.

> **Status: pre-release (0.1.0 in preparation).** The library and the pre-registered study are
> being built in the open; headline results do not exist yet (see [Results](#results)).

## Why this exists

Text-based tone indices for central banks are widely used, but three practical problems recur:

1. **Coverage.** Most public tooling targets the Fed and the ECB in English. Statements from
   other banks, in other languages, are rarely available in one comparable format.
2. **Contamination.** A large language model may have seen both a statement and what happened
   next. A score that looks predictive may reflect memory rather than reading.
   `cbtone` pairs every LLM result with a masked-text variant and a post-training-cutoff split.
3. **Weak evaluation.** Tone scores are often reported without a pre-registered test, a baseline
   or a check against simple alternatives.

`cbtone` fetches documents politely from central-bank websites, turns them into one schema, scores
them with four scorer families (dictionary, finance-tuned transformer, local LLM, fine-tuned small
model), and provides event-study and ordinal-regression tools. The research questions, metrics
and decision thresholds are fixed before scoring, in
[`docs/RESEARCH_QUESTIONS.md`](docs/RESEARCH_QUESTIONS.md) (tag `prereg-v1`).

## Quickstart

```bash
pip install cbtone

cbtone fetch fed ecb mas        # polite, cached download into data/raw/<bank>/
cbtone score --scorer llm       # local LLM via Ollama; resumable, cached by content hash
cbtone events                   # event timestamps plus signed FX and 2-year-yield moves
```

Notes on what the three commands assume:

- Between `fetch` and `score`, build the corpus snapshot from the cache with `cbtone snapshot`
  (no network). `score` and `events` read `data/corpus` by default (`--corpus` changes it).
- `--scorer llm` needs a running [Ollama](https://ollama.com) with the model pulled
  (default `qwen3:4b`; `--model` changes it). Other scorers: `dict`, `fomc-roberta`, `ft`.
- `events` leaves market moves empty unless `cbtone markets` has produced
  `data/raw/markets/daily.parquet` first.
- MAS blocks automated access to its own site, so `cbtone fetch mas` reads Internet Archive copies
  of the statements (DECISIONS D11) and never requests mas.gov.sg. Hand-saved files in
  `data/raw/mas/manual/` take precedence (`docs/sources/NEEDED.md`).

Try the scorer without any download, on the tiny committed corpus (Fed and RBA only, no network):

```bash
cbtone score --scorer dict fed rba --corpus tests/fixtures/corpus_mini --out /tmp/quick.parquet
```

## Install

```bash
pip install cbtone                      # core: fetch, snapshot, dictionary scorer, events, analysis
pip install "cbtone[transformers]"      # FOMC-RoBERTa and other Hugging Face scorers (torch)
pip install "cbtone[api]"               # reserved for an optional hosted-API scorer (not needed to reproduce)
pip install "cbtone[finetune]"          # fine-tune a small model (transformers, torch, peft)
pip install "cbtone[docs]"              # build the documentation site (mkdocs-material)
```

An optional `[thai]` extra adds Thai word segmentation. Python 3.11 or newer. For development use
`uv sync` (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## Supported banks and languages

Counts are from corpus snapshot `2026-10-14+ed5a49c2…` (2,935 documents; `docs/PROGRESS.md`).
Per-bank details: [`docs/sources/`](docs/sources/).

| Bank | Documents | Languages | Coverage | Text redistributable | Role |
|---|---|---|---|---|---|
| Federal Reserve (Fed) | 535 | en | statements, minutes, press conferences, 2000 onwards | yes | headline |
| European Central Bank (ECB) | 575 | en | statements 1999 onwards, press conferences | statements yes; press conferences no | headline |
| Bank of England (BoE) | 567 | en | statements and minutes, 2000 onwards | no | headline |
| Reserve Bank of Australia (RBA) | 452 | en | statements 2000 onwards, minutes 2006 onwards, press conferences 2024 onwards | yes (CC BY 4.0) | headline |
| Monetary Authority of Singapore (MAS) | 62 | en | monetary policy statements 2001 to Apr 2026, via Internet Archive | no | headline |
| Bank Indonesia (BI) | 256 | en, id | statements from Apr 2016 | no | headline |
| Bank Negara Malaysia (BNM) | 280 | en, ms | monetary policy statements from 2004 | no | headline |
| Bank of Thailand (BoT) | 143 | th, en | statements and minutes from 2021 | no | **opt-in; excluded from headline results** |
| People's Bank of China (PBoC) | 65 | zh | MPC communiques, about half of 2010 onwards | no | **exploratory** |

Where text cannot be redistributed, the repository holds URLs and SHA-256 hashes plus the fetch
code, and you rebuild the text locally. See [`docs/sources/LICENSES.md`](docs/sources/LICENSES.md).
Known gaps are listed in `docs/PROGRESS.md` and `docs/ANOMALIES.md`.

## Results

<!-- RESULTS: filled in Phase 5. Headline chart (figure path) and the summary table go here. -->

*No results are reported yet.* The study is pre-registered and will be reported against its
thresholds, including any result that contradicts the pre-registration. Every LLM result will
carry a masked-text variant and a post-cutoff split. Headline numbers appear here only once
`make reproduce` has produced them.

<!-- RESULTS-CHART: ![Headline chart](results/figures/headline.png) -->

## Disclaimer

`cbtone` is an **independent open-source project**. It is built **only from public documents**
published by central banks. It **represents no institution's view**, including that of any
organisation the author works for, and it is **not investment advice**. The text of the project
describes measurable properties of documents and statistical results; it does not comment on any
bank's policy choices. The Bank of Thailand adapter is opt-in and excluded from the headline
results. Full statement: [DISCLAIMER.md](DISCLAIMER.md).

## Documentation

Site sources are in [`docs/site/`](docs/site/) (build with `make docs`). Design decisions are
recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md), data anomalies in
[`docs/ANOMALIES.md`](docs/ANOMALIES.md), and the pre-registered questions in
[`docs/RESEARCH_QUESTIONS.md`](docs/RESEARCH_QUESTIONS.md).

## Citation

```bibtex
@software{chongmankhong_cbtone,
  author  = {Chongmankhong, Thanatchon},
  title   = {cbtone: hawkish/dovish tone signals from public central-bank communication},
  year    = {TODO},
  version = {0.1.0},
  url     = {https://github.com/thanatchon36/cbtone},
  note    = {Zenodo DOI: TODO}
}
```

GitHub also reads [`CITATION.cff`](CITATION.cff).

## Licences

- **Code:** Apache-2.0 ([LICENSE](LICENSE)).
- **Corpus text:** under each source's own terms, not under Apache-2.0. See
  [`docs/sources/LICENSES.md`](docs/sources/LICENSES.md).
- **Third-party models and data:** some evaluation anchors and models (for example FOMC-RoBERTa
  and the FOMC communication dataset) are CC-BY-NC-4.0 and are used for evaluation only; they are
  not redistributed. Check the same file before commercial use.
