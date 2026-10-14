# MISSION: cbtone — Do LLM Tone Scores of Central-Bank Communication Carry Policy Signal?

You are an autonomous research engineer. Build **`cbtone`**, a public, pip-installable Python library that turns central-bank communications (statements, minutes, press-conference text) into hawkish/dovish tone signals with four scorer families — dictionary, finance-tuned transformer, local LLM, fine-tuned small model — plus the evaluation machinery to test whether those signals carry information about future policy and market reactions. Alongside it, run a **pre-registered, reproducible empirical study across ~8 central banks in 4 languages**, with a Southeast-Asia focus the existing literature (Fed/ECB-centric) lacks.

Half library, half research. The library must be usable by a macro analyst or quant tomorrow: `cbtone fetch fed ecb mas && cbtone score --scorer llm && cbtone events`. The paper is evidence that the library works, not the other way round.

Work through all phases without waiting for me. Record every design decision in `docs/DECISIONS.md` (what, why, alternatives rejected). Only stop if truly blocked.

---

## 0. Hard constraints

- **Public communications only.** Every document comes from a central bank's public website or a public mirror. No non-public information of any kind, no internal documents, no personal knowledge of any institution's deliberations. If a fact is not derivable from a public URL in `data/corpus/manifest.parquet`, it does not go in the repo.
- **Author context.** The author is employed by a central bank. The repo must state (README, DISCLAIMER.md, paper) that this is an independent open-source project, built only from public documents, representing no institution's view, and not investment advice. **Bank of Thailand adapter is opt-in**: implement it like any other, but the paper's headline configuration **excludes BoT** and the text never comments on any individual bank's policy choices — only on measurable properties of the text and the statistical results. I may flip this in `config/paper.yaml` (`include_bot: false` by default).
- **Polite, lawful acquisition.** Honour `robots.txt`, rate-limit (≤ 1 request / 2 s per host), identify with a descriptive User-Agent, cache every raw response under `data/raw/<bank>/` with SHA-256. Record each source's terms of use in `docs/sources/LICENSES.md`. If a source's terms forbid redistribution of the text, commit only URLs + hashes + the fetch script, not the text. If a site blocks automated access (MAS is known to), write `docs/sources/NEEDED.md` with exact URLs for me to download manually and continue with every other bank.
- **Pre-registration.** `docs/RESEARCH_QUESTIONS.md` with hypotheses, metrics and decision thresholds is committed and tagged (`prereg-v1`) **before** any scorer is run on the full corpus. Results that contradict it are reported as refuted, not re-framed.
- **Contamination is a first-class threat.** Any LLM scorer may have seen the outcomes in training. Every LLM result must be accompanied by (a) a **masked-text** variant (bank names, dates, numeric rate levels, country names replaced with placeholders) and (b) a **post-cutoff** split (documents dated after the scoring model's documented training cutoff). Claims of predictive signal are made only where they survive both.
- **Every headline number has a sanity test.** A metric exactly at 0, 1, or 100 %, a correlation above 0.95, or a result that differs by more than 2× from the literature's typical range fails the build until explained in `docs/ANOMALIES.md`. (Lesson from the previous project: a truncation bug silently produced a 0 % rate.)
- **Compute target: MacBook Air M4, 16 GB, no CUDA, fanless.** Local LLM scoring via Ollama with a multilingual model ≤ 4B parameters (candidate: `qwen3:4b` or `qwen2.5:3b`; record the exact tag, quantisation and digest in every result). Hosted-API scorers are an optional extra (`[api]`) that is never required for `make reproduce`. All LLM calls are **cached by content hash** and resumable. Full suite ≤ 3 h wall-clock; `make quick` ≤ 5 min on a 60-document sample. Run long targets under `caffeinate -i`. Log per-stage wall time to `results/timing.json`.
- **Reproducibility.** Fixed seeds, pinned deps, `make reproduce` rebuilds every table and figure from the committed corpus snapshot. Corpus snapshot is versioned (`data/corpus/VERSION`) and hashed.
- Python 3.11+, `uv`, `pydantic` v2 schemas, `typer` CLI, `polars` for tables, `pytest` (≥ 85 % coverage on core), `ruff`, `mypy --strict` on core, type hints throughout. Apache-2.0 for code; corpus under per-source terms. All deps need arm64 macOS wheels.

---

## 1. Phase 1 — Corpus, decisions, labels, literature

### 1.1 Source adapters (`src/cbtone/sources/`)
One adapter per bank, each with a docstring listing document types, URL patterns, date range, language(s) and terms-of-use note. Core set (headline):

| Bank | Documents | Languages | Notes |
|---|---|---|---|
| Fed (FOMC) | statements 1994→, minutes, press-conference transcripts | en | public domain |
| ECB | monetary policy decisions, press-conference introductory statements + Q&A | en | |
| BoE (MPC) | monetary policy summaries, minutes | en | |
| RBA | governor's decision statements, minutes | en | |
| MAS | Monetary Policy Statements (semi-annual → quarterly from 2024) | en | **exchange-rate-based policy**: stance = change to S$NEER band slope/width/centre, not a rate — handle explicitly |
| Bank Indonesia | BI-Rate / BI 7-Day RR decision press releases | **id + en** (parallel) | |
| Bank Negara Malaysia | Monetary Policy Statements | **en + ms** (parallel) | |
| PBoC | MPC quarterly meeting communiqués, LPR announcements | **zh + en** (partial parallel) | optional if parsing proves costly; document the decision |
| Bank of Thailand | MPC press releases, edited minutes | **th + en** (parallel) | **opt-in**, excluded from headline by default |

Extension slots documented for RBI, BSP, BoK, BoJ, BoC, SNB, Riksbank, Norges Bank.

Common output: `Document(bank, date, published_at_utc, doc_type, language, parallel_id, title, text, sections, url, sha256, fetched_at)`. Parse HTML and PDF to clean text; split into sentences with a language-aware splitter (Thai needs `pythainlp`; Chinese needs a character-level splitter); keep paragraph structure. Build `data/corpus/documents.parquet`, `sentences.parquet`, `manifest.parquet`.

### 1.2 Policy decisions table (`src/cbtone/decisions/`)
- Primary: the **BIS central bank policy rate** dataset (public, daily) → per-bank decision dates and rate changes.
- Cross-check against each bank's own decision calendar (from the fetched documents).
- MAS: derive categorical stance (tighten / maintain / ease; which parameter) from MPS text with a rule-based extractor, validated by hand on a 20-document sample committed as `tests/fixtures/mas_stance_gold.csv`.
- Output: `decisions.parquet` with `(bank, date, direction ∈ {hike, hold, cut}, magnitude_bp, next_direction, next_date)`.

### 1.3 Market data (`src/cbtone/markets/`)
- FX daily closes via `yfinance` (USDSGD, USDIDR, USDMYR, USDTHB, USDCNY, EURUSD, GBPUSD, AUDUSD, DXY) and 2y/10y government yields where a free daily source exists (FRED for US/UK/AU/EA; bank-published yield pages for SG/MY/TH/ID if reachable). Document each series' source, timezone and holiday calendar.
- Announcement timestamps in UTC with the bank's local release time; define the event window as [t−1 close, t+1 close] by default and justify any bank-specific exception.

### 1.4 Human-labelled anchor data
- Locate the public **FOMC hawkish/dovish sentence dataset** (Shah, Paturi & Chava 2023, "Trillion Dollar Words", HF `gtfintechlab/*`) and any other public labelled set. **Verify the license**; if non-commercial, use it for evaluation only, never redistribute, and keep it out of the training of any released model. Record in `docs/sources/LICENSES.md`.
- Create a small **expert-style gold set of 200 sentences** for the SEA banks (BI, BNM, MAS; BoT only if opted in) labelled by two independent LLM passes with different prompts plus a tie-break rule, clearly marked as *silver* (not human) labels; the paper calls them silver throughout.

### 1.5 Literature review (`docs/literature/REVIEW.md` + `refs.bib`, 25–35 sources)
Central-bank communication measurement (Hansen & McMahon; Hansen, McMahon & Prat; Apel & Blix Grimaldi; Picault & Renault; Gorodnichenko, Pham & Talavera "Voice of Monetary Policy"; Shah et al. FOMC-RoBERTa; Pfeifer & Marohl CentralBankRoBERTa), LLMs for macro/finance text (Lopez-Lira & Tang; Hansen & Kazinnik; Bybee et al.), event-study methodology for announcements (Gürkaynak, Sack & Swanson; Kuttner), MAS exchange-rate policy communication, emerging-market central-bank communication, LLM reliability/prompt sensitivity, and training-data contamination in financial NLP. End with a **gap table**: which (bank × language × scorer × evaluation) cells are untested.

---

## 2. Phase 2 — Research questions (pre-registered)

Write `docs/RESEARCH_QUESTIONS.md`, tag `prereg-v1`. Defaults:

- **RQ1 — Policy signal.** Does document-level tone at decision *t* improve out-of-sample prediction of the **direction of the next decision (t+1)** over a persistence baseline (same as last change) and over the dictionary scorer? Rolling-origin evaluation, ordered logistic with (tone, Δtone, last direction). Metric: AUROC (hike-vs-cut) and multiclass log-loss, bootstrap 95 % CI. Pre-set threshold: LLM beats dictionary by a margin whose CI excludes zero in a pre-set majority of banks.
- **RQ2 — Market reaction.** Does the **tone surprise** (tone minus its AR(1)-expected value) explain 1-day FX and 2y-yield moves around announcements, and does the LLM scorer explain more than dictionary/transformer? Metric: event-study R², sign agreement, HAC-robust t-stats. Report that effect sizes are expected to be small; pre-set what counts as "more".
- **RQ3 — Cross-lingual consistency.** On parallel documents (id/en, ms/en, zh/en, th/en if opted in), how consistent is each scorer between the native and English versions? Metric: Spearman ρ, mean absolute score difference, stance-flip rate. Secondary: is the native-language score closer to the market reaction than the English one?
- **RQ4 — Reliability and contamination.** (a) Stability of LLM scores across 5 paraphrased prompts, 2 model tags, temperature 0 vs 0.7, sentence- vs document-level aggregation: ICC and Krippendorff's α. (b) Agreement with human labels on the FOMC anchor set: macro-F1 per scorer. (c) **Contamination**: do masked-text scores and post-cutoff-period results preserve RQ1/RQ2 findings? Pre-set: a finding is reported as *robust* only if it survives both.
- **RQ5 — Transfer to Southeast Asia.** Does a scorer calibrated on Fed text (dictionary weights, FOMC-RoBERTa, LLM prompt tuned on Fed) keep its RQ1/RQ4b performance on BI, BNM and MAS without re-tuning? Which bank's language is least "Fed-like" (embedding distance + performance drop)? Does MAS's exchange-rate framing break rate-centric scorers?

Each RQ: hypothesis, refuting experiment, metric, threshold, minimum sample size and what is reported if underpowered.

---

## 3. Phase 3 — Library (`src/cbtone/`)

- **`cbtone.sources`** — adapters as above; `fetch` (cached, polite), `parse`, `snapshot` (versioned corpus build with manifest + hashes).
- **`cbtone.text`** — language detection, sentence splitting (en/id/ms/zh/th), masking (`mask_entities(text)` → placeholders for bank names, countries, dates, rate levels), paragraph typing (decision / outlook / risks / forward guidance / boilerplate) with a rule-based tagger.
- **`cbtone.scorers`** — common interface `score(doc | sentences) -> ToneScore(hawkish_p, dovish_p, neutral_p, index ∈ [−1, 1], evidence_spans, scorer_id, model_digest, prompt_id)`:
  - `DictionaryScorer`: Loughran–McDonald + a hawkish/dovish lexicon shipped as a data file with per-term citation; negation handling.
  - `TransformerScorer`: FOMC-RoBERTa (Shah et al.) and CentralBankRoBERTa via `transformers`, MPS/CPU.
  - `LLMScorer`: Ollama backend, structured JSON output, sentence-level with document aggregation strategies (mean, decision-paragraph-weighted, max-|index|), 5 registered prompt variants, content-hash cache, resume; `[api]` extra for hosted models.
  - `FineTunedScorer`: a small classifier (RoBERTa-base-class or a ≤ 0.6B decoder with LoRA via MLX/PEFT) trained on LLM silver labels + permitted public labels; training budget ≤ 30 min on the M4; release weights only if licences allow.
- **`cbtone.decisions`**, **`cbtone.markets`** — as in Phase 1.
- **`cbtone.events`** — event-study engine: alignment, abnormal returns, surprise construction, HAC standard errors, placebo (non-announcement) days.
- **`cbtone.eval`** — rolling-origin prediction, bootstrap CIs, ICC / Krippendorff, cross-lingual consistency, contamination splits, calibration (reliability diagrams for the LLM's probabilities).
- **`cbtone.cli`** — `cbtone fetch | parse | snapshot | decisions | markets | score | events | evaluate | report | doctor` (`doctor` probes Ollama, MPS, disk, cache).
- Ship JSON Schemas for `Document`, `ToneScore`, `Decision`, `EventResult` under `schemas/`. Every public function cites the paper section or literature it implements.

---

## 4. Phase 4 — Experiments (`experiments/`)

- One script per figure/table: `experiments/rqN_*.py` → `results/`. All configuration in `config/paper.yaml` (banks, date range, scorers, prompts, `include_bot`).
- **Budgets** (enforced, logged): document-level LLM scoring on the full corpus with 1 prompt × 1 model; sentence-level LLM scoring only on (i) the human-labelled FOMC set, (ii) the 200-sentence SEA silver set, (iii) a stratified 1,000-sentence sample for RQ4a prompt-perturbation. Full LLM budget ≤ 2 h; if exceeded, shrink the RQ4a sample first and record it.
- **Placebos everywhere:** shuffled-date tone, randomly permuted labels, non-announcement days — reported next to each real result.
- **Multiple comparisons:** Holm correction across banks within an RQ; say so in captions.
- `make experiments` runs everything; `make quick` runs a 60-document sample end-to-end.

---

## 5. Phase 5 — Paper and communications

- `paper/paper.md` → PDF via pandoc. Working title: *Reading the Room: Do LLM Tone Scores of Central-Bank Communication Carry Policy Signal? Evidence from Eight Central Banks in Four Languages.* Sections: Abstract, Introduction, Related Work, Data (corpus, decisions, markets, labels, licences), Method (scorers, masking, event study, rolling evaluation, pre-registration), Results per RQ, Contamination and Reliability, Threats to Validity (small N for SEA banks, silver labels, model cutoff, selection of document types), Reproducibility Statement, Conclusion. Every number injected from `results/summary.json`. Neutral tone; report refuted hypotheses as refuted; no policy commentary on any bank.
- `docs/EXEC_SUMMARY.md` — one page for a CIO / head of macro research: what the signal is worth, where it is unreliable, what it costs to run locally.
- `docs/posts/` — 8–10 LinkedIn drafts (≤ 1,300 chars, one finding each, a chart reference each, no hype, repo link), plus one launch post.

---

## 6. Phase 6 — Packaging and publication

```
cbtone/
├── README.md            # why, 3-command quickstart, headline chart, disclaimer, citation
├── MISSION.md
├── DISCLAIMER.md        # independent project; public documents only; not investment advice
├── LICENSE              # Apache-2.0 (code)
├── pyproject.toml       # uv, pinned; extras: [transformers], [ollama], [api], [finetune], [docs]
├── Makefile             # setup | quick | fetch | snapshot | score | experiments | paper | reproduce | test | lint | docs
├── config/paper.yaml
├── src/cbtone/
├── schemas/
├── data/
│   ├── raw/             # cached responses (git-ignored), hashes committed
│   ├── corpus/          # versioned parquet snapshot + manifest + LICENSES.md (text committed only where terms allow)
│   └── lexicon/
├── experiments/
├── results/             # summary.json + figures/ committed for the headline run
├── paper/
├── docs/                # mkdocs-material: concepts, adapters, scorers, CLI, cookbook ("add a central bank in 30 lines")
├── tests/
└── .github/workflows/   # ci.yml (lint + test + quick on a committed fixture corpus — no network in CI), release.yml
```

- Publish `cbtone` to PyPI on tag `v0.1.0` after `make reproduce` passes on a fresh clone. `CITATION.cff`, Zenodo DOI, GitHub topics (`central-banks`, `monetary-policy`, `nlp`, `llm`, `event-study`, `finance`).
- Optional: upload the redistributable part of the corpus as a Hugging Face dataset with the same manifest and licence notes.
- `CONTRIBUTING.md`: adding a bank adapter, a scorer, a language, a market series.

---

## 7. Working rules

- Plan each phase in `docs/PLAN.md`; close it in `docs/PROGRESS.md` (shipped / cut / open issues). Keep `docs/FUTURE_WORK.md` and `docs/ANOMALIES.md`.
- **Token budget (strict):** the main thread does design, pre-registration, interpretation and writing. Delegate to Sonnet subagents with a written spec (`docs/specs/<module>.md`) and acceptance tests: each source adapter, the sentence splitters, the event-study engine, tests, docs site, CI. One subagent per bank adapter; one per literature cluster. Review diffs, do not redo work. Never load whole PDFs or HTML into context — parse to text files first and read sections on demand. Run only related tests per change; full suite at phase end.
- **Handoff protocol:** update `docs/PROGRESS.md` at every phase end and whenever context passes ~60 %, with a checklist of what remains and every decision not yet in `DECISIONS.md`; commit; a fresh session resumes with "Read MISSION.md, docs/PROGRESS.md, docs/DECISIONS.md and continue".
- Small tested commits; `make test lint` before every commit; push after each phase.
- When choosing between "more banks" and "clean, pre-registered evidence on fewer banks", choose clean evidence. When choosing between "a bigger model" and "a result that survives the contamination checks", choose the latter.
- Before Phase 3, run `cbtone doctor` and commit `results/hardware.json`; cite it in the Reproducibility Statement.

Start now with Phase 1, beginning with the source adapters for Fed and ECB (fastest to validate the pipeline), then the SEA banks.
