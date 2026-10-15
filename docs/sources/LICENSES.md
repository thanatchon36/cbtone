# Source licences and terms of use

Per MISSION §0: when a source's terms forbid redistributing the text, only URLs + hashes + the fetch
script are committed. Code is Apache-2.0; this file covers **data**.

## Labelled anchor data and models (checked 2026-10-14 via the Hugging Face API)

| Asset | Licence | Use in cbtone |
|---|---|---|
| `gtfintechlab/fomc_communication` (Shah, Paturi & Chava 2023 — hawkish/dovish/neutral FOMC sentences; train.csv/test.csv) | **CC-BY-NC-4.0** | **Evaluation only** (RQ4b, RQ5). Not redistributed: downloaded at run time into `data/cache/`. Never used to train a released model; the `FineTunedScorer` released weights train on silver labels only. A local-only variant that uses it for training may exist for comparison, but its weights are never published: the FOMC-RoBERTa replication (`experiments/train_fomc_roberta.py`, D21) is that variant; its weights stay in `data/models/` (git-ignored). |
| `gtfintechlab/FOMC-RoBERTa` (model) | **CC-BY-NC-4.0** | Used as a scorer at run time (downloaded by the user). Non-commercial; the README warns commercial users. Not redistributed. **Gated on Hugging Face (manual approval)**: the user must request access and run `hf auth login` before `TransformerScorer` can load it. Revision pinned to commit `aa3bc428...` (`model_digest`). Label map LABEL_0 dovish / 1 hawkish / 2 neutral comes from the authors' GitHub README and dataset card, because the gated model card was not readable anonymously. |
| `Moritz-Pfeifer/CentralBankRoBERTa-sentiment-classifier`, `-agent-classifier` | MIT | Scorer at run time, **`-sentiment-classifier` not registered as a stance scorer**: it is a binary positive/negative sentiment model (`id2label` {0: negative, 1: positive}, no neutral class; positive or negative "for households, firms, the financial sector or the government", Pfeifer & Marohl 2023), not hawkish/dovish, and its card does not support positive=hawkish / negative=dovish (a tightening is negative for households and firms but is the hawkish act). Commit `5055d180...`. |
| Loughran & McDonald master dictionary (Negative / Positive / Uncertainty lists; `sraf.nd.edu/loughranmcdonald-master-dictionary/`, page checked 2026-10-14, version "Updated: March, 2026") | No licence text. Page states: "free for use in academic research. For commercial licenses, please contact us" (loughranmcdonald@gmail.com) | **Not redistributed** (no redistribution grant; not packaged or committed). Downloaded at run time into `data/cache/` by `cbtone.scorers.dictionary.fetch_lm_master_dictionary`. Only the three lists are used, as an optional feature of `DictionaryScorer`; they never enter the index. Commercial users must obtain their own licence. |

## Central-bank websites

Filled in per bank from `docs/sources/<bank>.md` as each adapter lands.

| Bank | Terms | Redistribute text? | Committed |
|---|---|---|---|
| Fed | federalreserve.gov/disclaimer.htm: public domain unless otherwise indicated; cite the Board | Yes | Text |
| ECB | ecb.europa.eu disclaimer: reproduction permitted with source acknowledged; prior authorisation for documents bearing authors' names | Press releases: yes. Press conferences: no (D8) | Statements: text. Press conferences: URL + SHA-256 |
| BoE | bankofengland.co.uk/legal: personal/internal non-commercial use; re-use by permission on request | No (unless permission granted) | URL + SHA-256 |
| RBA | rba.gov.au/copyright: CC BY 4.0 with attribution (excludes logo, banknotes, third-party material, data, multimedia) | Yes (transcripts, not AV) | Text |
| BI | No terms page found; footer "© Bank Indonesia", all rights reserved | No (until BI confirms) | URL + SHA-256 |
| BNM | bnm.gov.my/terms-of-use: no reproduction or redistribution without written permission | No | URL + SHA-256 |
| BoT | bot.or.th/en/terms-and-condition.html: download and copy for user's own use; no republication right | No | URL + SHA-256 |
| MAS | mas.gov.sg terms of use: prior written permission for any reproduction | No | URL + SHA-256 (manual files, D7) |
| PBoC | Not verified; robots.txt disallows all crawlers | No (assumed) | Nothing; out of headline (D10) |
