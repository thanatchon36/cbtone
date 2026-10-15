# Design decisions

Each entry: **what**, **why**, **alternatives rejected**. Newest at the bottom.

## D1 — Packaging and toolchain (2026-10-14)
- **What:** `uv` + hatchling, Python ≥ 3.11, `src/` layout, PyPI name `cbtone`, Apache-2.0,
  core deps kept small (pydantic, typer, polars, httpx, bs4/lxml, pypdf, pyyaml); heavy stacks
  (`torch`, `transformers`, `peft`, `anthropic`) in extras.
- **Why:** `pip install cbtone` must work on a laptop without pulling torch; all deps have arm64 wheels.
- **Rejected:** PyMuPDF for PDFs (AGPL clashes with Apache-2.0 redistribution); poetry (uv is faster
  and already the house standard).

## D2 — Polite fetcher is the only network path (2026-10-14)
- **What:** `PoliteFetcher` enforces robots.txt, ≥ 2 s per host, a descriptive User-Agent, and
  caches raw bytes + sidecar JSON (url, content type, SHA-256, fetched_at) under `data/raw/<bank>/`.
  401/403/429 → `BlockedError`; the adapter stops and writes `docs/sources/NEEDED_<bank>.md`.
- **Why:** MISSION §0; makes every downstream step offline-reproducible from the cache.
- **Rejected:** headless browser or retries with other user agents for blocked sites: that would be
  getting around the block.

## D3 — `Document.date` is the decision/meeting date (2026-10-14)
- **What:** for minutes and transcripts, `date` = the meeting the document belongs to; the release
  time goes into `published_at_utc`.
- **Why:** joins to `decisions.parquet` on (bank, date); the market event uses the release time.
- **Rejected:** keying by release date (minutes come out about 3 weeks later and would join to the wrong decision).

## D4 — Raw cache bodies git-ignored, sidecars committed (2026-10-14)
- **What:** `data/raw/**/*.bin` ignored; `.json` sidecars (URL + hash) committed.
- **Why:** MISSION §0, "commit only URLs + hashes" when the terms forbid redistribution; the sidecars are
  enough to verify a re-fetch. The text goes into `data/corpus/` only where the terms allow it.

## D5 — Non-commercial anchor data are evaluation-only (2026-10-14)
- **What:** the FOMC hawkish/dovish set and FOMC-RoBERTa are CC-BY-NC-4.0. cbtone downloads them at run
  time, uses them for evaluation and as a scorer, and never redistributes them or trains released
  weights on them.
- **Why:** MISSION §1.4; Apache-2.0 users may be commercial.
- **Rejected:** vendoring the CSVs in `tests/fixtures` (that would be redistribution). Tests use a 5-row synthetic
  stand-in with the same schema.

## D6 — Policy-rate decisions from BIS WS_CBPOL (2026-10-14)
- **What:** rate changes come from the BIS daily policy-rate series (1999→); holds come from meeting
  dates (statement/MPS documents) with no change within +3 days (ECB +7 days, because changes take
  effect up to about 6 days after announcement). The US is reported as the upper bound of the target
  range (BIS midpoint + 12.5 bp from 2008-12-16). For the euro area, BIS switches from the main
  refinancing rate (MRO) to the deposit facility rate (DFR) on 2024-09-18; the -60 bp step there is
  replaced by the observed 25 bp DFR cut, and the switch is documented. Changes below 0.5 bp are
  treated as rounding noise.
- **Why:** one public, consistent source for all rate-setting banks; the meeting calendars come from
  our own corpus, so they cross-check it.
- **Rejected:** scraping each bank's rate-history page (different formats, and the BIS series is the
  better-documented public standard).

## D7 — Bot-protection pages served with HTTP 200 count as blocked (2026-10-14)
- **What:** `PoliteFetcher` treats HTML whose `<title>` matches maintenance/captcha/access-denied
  interstitials as `BlockedError` and never caches it. MAS (www.mas.gov.sg) serves an ~850 KB
  "Maintenance" page to the cbtone User-Agent while robots.txt allows crawling, so MAS is treated as
  blocked; the URLs are listed in `docs/sources/NEEDED.md` for manual download.
- **Why:** an earlier project silently produced a 0 % rate from bad input; caching a block page as a
  "document" would be the same failure. MISSION §0 forbids getting around a block.
- **Rejected:** retrying with a browser User-Agent or a headless browser (that gets around the block); using
  the Internet Archive's copies of MAS pages without the author's say-so (an allowed "public mirror"
  under §0, but it would get around the bank's own access choice, so it's left to the author).

## D8 — Redistribution per document type; ECB press conferences committed as URLs + hashes (2026-10-14)
- **What:** `redistributable` is decided per (bank, doc_type). ECB decision press releases ("Reproduction
  is permitted provided that the source is acknowledged") are committed with their text; ECB press
  conferences are committed as URL + SHA-256 only, because the ECB disclaimer requires prior
  authorisation for "documents bearing the names of their authors" and the introductory statement is
  delivered by the named President. `make fetch` rebuilds the full text locally.
- **Why:** when the terms are unclear, choose the reading that can't be a licence breach.
- **Rejected:** committing everything with attribution only.

## D9 — Market coverage: yields only where a free daily official source exists (2026-10-14)
- **What:** 2y/10y yields: US (FRED H.15), EA (ECB AAA curve, 2004-09→), UK (BoE spot-curve archive),
  AU (RBA F2, 2013→). SEA banks: FX only (no login-free daily yield files found). FX from Yahoo via
  `yfinance`, modelled as 17:00 New York closes; the raw FX parquet is not committed (Yahoo terms).
  Event day `t` = the first close strictly after the release in the series' own timezone.
- **Why:** MISSION §1.3; daily windows need daily data; FRED's non-US yields are monthly.
- **Consequence for RQ2:** the yield leg is tested for Fed/ECB/BoE/RBA only; the SEA legs use FX. Pre-registered as such.

## D10 — PBoC cut from the headline set; headline = 7 banks, 3 live languages (2026-10-14)
- **What:** `pbc.gov.cn/robots.txt` disallows every crawler except Baiduspider, so PBoC cannot be
  fetched. `cbtone.sources.pboc` runs in manual-file mode only (files listed in `docs/sources/NEEDED.md`);
  its selectors are unverified against real pages (synthetic fixture). PBoC is removed from
  `config/paper.yaml`. Headline banks: Fed, ECB, BoE, RBA, MAS, BI, BNM. MAS also depends on manual
  files (D7): if they are not supplied before pre-registration (`prereg-v1`), MAS is dropped too and
  the prereg says so. Languages: en (all), id (BI), ms (BNM); th (BoT) opt-in. The MISSION's
  "~8 banks in 4 languages" framing becomes "7 banks (6 if MAS stays blocked), 3 languages + Thai opt-in".
- **Why:** MISSION §0 forbids getting around robots.txt; §7 prefers clean evidence on fewer banks.
  A zh leg built on unverified selectors would be uncheckable.
- **Rejected:** fetching anyway, a Baiduspider User-Agent, third-party mirrors without the author's say-so.

## D11 — MAS text from Internet Archive copies (2026-10-14)
- **What:** the author approved Internet Archive (Wayback Machine) copies for MAS (D7 left this to
  the author). `MasAdapter` lists archived Monetary Policy Statement URLs with the Wayback CDX API
  and fetches the raw snapshot (`web.archive.org/web/<timestamp>id_/<mas url>`) through
  `PoliteFetcher`, which applies robots.txt, rate limits, caching and block-page rejection. It never
  requests mas.gov.sg itself. `Document.url` is the snapshot URL, and the original MAS URL is
  recoverable from it. Hand-saved files in `data/raw/mas/manual/` still take precedence.
- **Checks:** a snapshot is accepted only if it is a 200 capture of a statement page whose parsed date
  matches the date in its slug. Captures that show the MAS "Maintenance" page are skipped, and the
  next capture of that URL is tried instead.
- **Licence:** unchanged. MAS terms require permission to redistribute, so MAS stays URL + SHA-256 only.
- **Why:** MAS is the only headline SEA bank with an exchange-rate-based framework, and MISSION §0 lists public
  mirrors as allowed. The author made the call on the bank's own access choice.
- **Not extended to PBoC:** PBoC remains manual-only (D10) unless the author says otherwise.

## D12 — PBoC text from Internet Archive copies (author-approved, 2026-10-14)
- **What:** the author approved Wayback Machine copies for PBoC as well. `PbocAdapter` gets the same
  archive mode as MAS (D11): it lists captures with CDX and fetches `id_` raw snapshots via
  `PoliteFetcher`, never pbc.gov.cn. `Document.url` is the snapshot URL, and hand-saved files take
  precedence. Captures are accepted only when the parsed meeting date matches, and block or empty
  pages are skipped.
- **Note:** unlike MAS (a bot page; robots.txt allowed crawling), pbc.gov.cn's robots.txt disallows
  crawlers. The archive's copies are a public mirror (MISSION §0), and the author made the call on the bank's
  stated crawler policy. cbtone itself still never crawls pbc.gov.cn.
- **Headline:** amends D10. PBoC rejoins the headline set (8 banks, 4 languages) only if the archive
  yields ≥ 80 % of MPC communiqués from 2010 onward *and* the selectors validate on real archived pages.
  Otherwise it stays an optional extension. This is decided and recorded before `prereg-v1`.
- **Licence:** terms unverified, so treated as not redistributable (URL + SHA-256 only).

## D13 — MAS stance gold labels come from MAS's published decision table (2026-10-14)
- **What:** the 20-row gold set for the MAS stance extractor takes `label_direction` and
  `label_parameters` from MAS's "past monetary policy decisions" table (archived copies, D11),
  not from hand labelling. Paragraphs are verbatim from the archived statements. #20 (27 Jul 2026,
  no usable capture) is replaced by 12 Oct 2018.
- **Why:** no human labeller is available, and an LLM reading the paragraph would not be
  "hand labels". The bank's own record of each decision is authoritative and independent of the extractor.
- **Rejected:** labels made by the session model (would be silver, not gold, and correlated with the extractor's design).

## D14 — MAS decisions come from MAS's own table; the text extractor is a fallback (2026-10-14)
- **What:** `decisions.parquet` takes MAS rows (`source="mas_table"`) from MAS's "Past Monetary
  Policy Decisions" table, using the newest usable Internet Archive capture (currently 2025-11-18, 59 decisions
  from 2001-02-22 to 2025-10-14; `*` = unscheduled). The rule-based extractor (`source="mas_text"`) is used only for
  statements dated after the table's last row.
- **Why:** validation showed the extractor is not reliable enough to be the primary source.
  - Before any fix: 15/19 on gold decision paragraphs, and 21/40 (53 %) on the full text of the
    other 40 table-covered statements.
  - After four general grammar fixes (passive voice; "has therefore decided"; month-year
    back-references; "from zero … to"): 20/20 gold, 31/40 (78 %) full text.
  - Both sets were used to design those fixes, so **no untouched test set remains**. The figures are
    development accuracy, not validation.
  - The bank's own record is authoritative, and the extractor is not needed where that record exists.
- **Consequence:** at most a handful of post-table MAS decisions rely on the extractor. They are
  flagged by `source` and reported separately. The extractor's limits go into the paper's Threats to Validity.

## D15 — PBoC stays out of the headline set: archive coverage is 53 % (2026-10-14)
- **Result of the D12 rule:** the Internet Archive yields 35 of 66 expected zh MPC communiqués
  for 2010–2026Q3 (53 %, below the pre-set 80 %), plus 16 en (2021→). From May 2016 to about 2022 every
  capture is an anti-bot JavaScript shell with no text. Selectors are now validated on real archived pages
  (three zh layouts, en).
- **Decision:** PBoC remains an optional zh extension, not in `config/paper.yaml`. Headline = 7 banks,
  3 languages (D10). Any PBoC result is reported as exploratory, with the 2016–2022 gap stated.
- Meeting dates for 2009–15 come from PBoC's own meeting-date table (archived): the pages say only
  "日前" ("recently").

## D16 — Pre-registration design choices (2026-10-14, frozen at `prereg-v1`)
- **What:** `docs/RESEARCH_QUESTIONS.md` fixes these choices:
  - **Primary document per bank:** BoE = minutes, because its 2000–2006 releases are one sentence (A6).
    RBA starts Dec 2007, because earlier releases exist only for changes and would select on the outcome (A1).
  - **Release-date rule:** a document with no time is timed at 00:00 local on its release date, so the
    [t−1, t+1] window always contains the release.
  - **Power:** a minimum sample per (bank, RQ). Underpowered cells go to an appendix and are excluded from
    Holm families and majority counts. A majority needs ≥ 3 powered banks.
  - **Model rule:** qwen3:4b, with qwen2.5:3b as the fallback, chosen on timing only.
  - **Cutoff:** the documented training cutoff, or the model's public release date.
  - **Budget ladder** for the 2 h LLM limit.
- **Why:** each of these choices could otherwise be made after seeing results.
- **Rejected:**
  - BoE statements throughout (no tone signal before 2007);
  - RBA from 2000 (outcome-selected);
  - dropping day-level banks (would remove MAS and BI from RQ2).

## D17 — Headline LLM settings, chosen on timing only (2026-10-14, after `prereg-v1`, before any scoring)
- **What:** `qwen3:4b` (Ollama digest `359d7dd4bcda…`, GGUF) stays the headline model, with the 6,000-character
  input cap and no budget-ladder step for documents.
  - Calls use Ollama structured output: a JSON schema `{hawkish, dovish, neutral}`, `num_predict=64`,
    `think=false`, temperature 0, `num_ctx=8192`.
  - Throughput on 20 primary documents was 1.3 s/document. Plain `format: "json"` without a schema let the model
    ramble (≈ 500 output tokens, 21.8 s/doc, and 3/20 requests aborted with "token repeat limit").
- **Why:** pre-registered (§0.5, §0.8). The choice was made from timing alone; no scores were inspected
  (outputs were discarded).
- `qwen2.5:3b` was pulled as the second tag for RQ4a.

## D18 — Budget ladder applied; LLM budget overrun recorded (2026-10-14, timing only, before any scoring analysis)
- **Measured on the 60-document quick sample:** Ollama `qwen3:4b` on the M4 processes prompts at about 220 tokens/s and
  generates at about 30 tokens/s.
  - With the 6,000-character cap and evidence quotes, a document took about 7–10 s. The D17 figure of 1.3 s/doc was
    flattered by prompt caching in that 20-document test.
  - The pre-registered workload would take about 6 h at that rate.
- **Ladder (§0.8), applied in order, because each step alone still exceeded 2 h:**
  1. RQ4a sentence sample shrunk to **250** sentences.
  2. Document input cap lowered from 6,000 to **3,000** characters, for every scorer.
  3. Masked variant run only on the **headline primary series**.
- **Also from timing:** document-mode evidence quotes are turned off for the bulk runs (`LLMScorer(evidence=False)`),
  because quote generation alone cost about 5 s/document. Evidence is an output feature, not part of any pre-registered
  analysis. It stays available in the library and is used for the illustrative examples in the docs.
- **Remaining overrun:** measured at about 2.5 s/document, the full LLM workload is projected at about 4.3 h,
  versus the 2 h budget. The pre-registered design is otherwise kept, including the RQ4a document set of 120 and the sentence aggregation.
  The actual wall time is logged in `results/timing.json` and reported in the paper as a budget deviation.
- No scores were inspected for any of these choices. The quick-sample timing runs discarded their outputs.

## D19 — Masking also covers policy-instrument and committee names (2026-10-14, before any masked scoring)
- **What:** `mask_entities` now also masks:
  - named policy instruments (federal funds rate, Bank Rate, cash rate, OPR, BI-Rate, deposit facility rate,
    LPR, …) as `[POLICY_RATE]`;
  - decision bodies (Governing Council, MPC, Reserve Bank Board, Rapat Dewan Gubernur, …) as `[COMMITTEE]`;
  - US-style fractions ("5-1/4"), whose lower bound previously leaked.
- **Why:** these names identify the bank as surely as its name does, so leaving them would weaken the contamination check
  (RESEARCH_QUESTIONS.md RQ4c). Generic framework words that carry the policy meaning itself ("policy band", "slope",
  "policy rate", "the Committee") are kept, because masking them would remove the information being scored.
- **Timing:** reviewed and changed before the masked scoring job started. No masked score was produced with the old rules,
  apart from the discarded timing runs.

## D20 — LLM scoring moved to the owner's GPU; budget ladder re-evaluated; D18 steps reverted (2026-10-14, timing only)
- **What:** the author provided an Ollama server on an RTX 4070 Ti (12 GB) at `192.168.1.174:11434`
  (`CBTONE_OLLAMA_URL`). It runs the same model tags with identical digests (`qwen3:4b` `359d7dd4bcda…`,
  `qwen2.5:3b` `357c53fb659c…`, both Q4_K_M).
- **Re-timing:** the pre-registered default settings were re-timed on the 60-document quick sample (throwaway cache, outputs discarded):
  - documents at cap 6,000: 0.52 s/doc unmasked, 0.49 s masked;
  - sentences: 0.41 s each;
  - the full pre-registered workload is projected at about 1.8 h, inside the 2 h budget.
- **Consequence:** **no budget-ladder step is needed.** D18's steps are reverted to the pre-registered design: input cap
  6,000 characters, RQ4a sentence sample 1,000, masked variant for every LLM result (primary and native). Document-mode
  evidence quotes stay off, because they would add about 2 h and are not part of any analysis.
- **One backend:** every LLM score in the paper is regenerated on this GPU into a separate cache (`CBTONE_SCORE_CACHE=
  data/cache/scores-4070ti.sqlite`). The ~700 documents scored on the M4 before the switch are not mixed in.
- **Compute target:** MISSION §0 names a MacBook Air M4. The M4 timings (D17/D18: ~3.5 s/document at cap 3,000) are kept
  as the "cost to run on a laptop" reference in the README and executive summary. The paper states that the headline run
  used a desktop GPU, and that the laptop path gives the same model and settings, only slower.

## D21 — FOMC-RoBERTa replaced by a local replication of the same recipe (2026-10-15, after the main results)
- **What:** the pre-registered reference scorer `gtfintechlab/FOMC-RoBERTa` is gated. Access was requested on
  2026-10-14 and never granted. The owner decided to retrain the model instead of waiting.
  `experiments/train_fomc_roberta.py` fine-tunes RoBERTa-large (`FacebookAI/roberta-large`, revision pinned in
  `results/fomc_roberta_train_report.json`) on the **train split** of `gtfintechlab/fomc_communication` (the
  revision already pinned in `cbtone.eval.anchors`). The scorer id is `fomc-roberta-repl`; tables keep the
  pre-registered `fomc_roberta` slot and label it "FOMC-RoBERTa (replication)".
- **Recipe, fixed before training:** follows Shah, Paturi & Chava (2023): a stratified 20 % validation split of
  train, learning rate 1e-5, early stopping on validation macro-F1 (patience 3, at most 10 epochs; the authors
  allow 100). Batch size is 16 and max length is 256 tokens, which covers every sentence. Three seeds are trained.
  On the M4 (16 GB unified memory) a full batch of 16 overflowed GPU memory (`kIOGPUCommandBufferCallbackError
  OutOfMemory`), which surfaced as NaN losses in the first attempts; micro-batches of 8 still overflowed once in
  epoch 3. Every run that hit a GPU out-of-memory error was discarded before any test-set evaluation. The final run
  processes each batch as four micro-batches of 4 with gradient accumulation (the same effective batch of 16) and
  gradient checkpointing; it is killed on the first out-of-memory message, so no reported model saw one. A guard skips any update whose loss or gradient norm is non-finite, records the count
  (`skipped_steps` in the report) and aborts a seed beyond 1 % of its steps. The learning rate was not changed.
  The scorer is the seed with the best **validation** macro-F1, so the test split plays no part in selection.
  The three-seed test mean ± sd is reported beside the selected seed.
- **Not tuned:** no grid over learning rate or batch size (the authors searched one), to keep the M4 budget.
  The replication may therefore land below the published 0.717 weighted F1. It is reported as it comes out.
- **Caveats:**
  - Like the original, the replication is in-distribution on the FOMC test split, so its H4b number is a
    reference and not a competitor (RESEARCH_QUESTIONS H4b already says this).
  - 17 of the 496 test sentences also occur verbatim in train. This is a property of the dataset and the original
    model saw them too. A deduplicated test F1 (479 sentences) is reported as a sensitivity check.
- **Licence:** the FOMC data are CC-BY-NC-4.0, which permits non-commercial derivative works with attribution.
  Training on the train split is therefore allowed, and so is publishing the result under the same terms.
  0.1.3 chose to keep the weights local; the owner decided on 2026-10-15 to publish them, so that readers
  without access to the gated original can reproduce the paper. They are at
  [`thanatchon36/cbtone-fomc-roberta-repl`](https://huggingface.co/thanatchon36/cbtone-fomc-roberta-repl), CC-BY-NC-4.0, credited to Shah, Paturi & Chava (2023) and
  labelled a replication that carries none of the authors' weights. The dataset itself is still never
  redistributed, and `cbtone.scorers.finetuned.train` still refuses FOMC rows, so the Apache-2.0 `ft-xlmr`
  weights cannot be trained on them.
- **Scope:** every place the pre-registration names the transformer scorer. RQ4b (FOMC test) and RQ5 (English
  silver sentences) came first (0.1.3). RQ1 ("transformer and fine-tuned scorers are reported with the same
  comparisons, as descriptive results") and RQ2 (H2: "the LLM explains more than the dictionary and transformer
  scorers"; "the same comparison against the transformer is reported") were added in 0.1.4, after 0.1.3 had
  wrongly limited the scope to RQ4b/RQ5. The replication scores the English primary documents of every bank
  (`results/scores/fomc-roberta-repl.parquet`). RQ3 reports it as not applicable, as pre-registered for
  English-only scorers. The H1/H2 Holm families contain only the LLM's cells, so adding the scorer cannot change
  any verdict. The LLM vs transformer ΔR² is descriptive, with no Holm correction, as pre-registered.
- **Effect on verdicts:** H4b concerns the LLM and the dictionary, so it is unchanged. H5 still needs ≥ 50 English
  silver sentences for BI and BNM (35 each), so it stays untestable whatever the replication scores.
