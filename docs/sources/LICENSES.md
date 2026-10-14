# Source licences and terms of use

Per MISSION §0: when a source's terms forbid redistributing the text, only URLs + hashes + the fetch
script are committed. Code is Apache-2.0; this file covers **data**.

## Labelled anchor data and models (checked 2026-10-14 via the Hugging Face API)

| Asset | Licence | Use in cbtone |
|---|---|---|
| `gtfintechlab/fomc_communication` (Shah, Paturi & Chava 2023 — hawkish/dovish/neutral FOMC sentences; train.csv/test.csv) | **CC-BY-NC-4.0** | **Evaluation only** (RQ4b, RQ5). Not redistributed: downloaded at run time into `data/cache/`. Never used to train a released model; the `FineTunedScorer` released weights train on silver labels only. A local-only variant that uses it for training may exist for comparison, but its weights are never published. |
| `gtfintechlab/FOMC-RoBERTa` (model) | **CC-BY-NC-4.0** | Used as a scorer at run time (downloaded by the user). Non-commercial; the README warns commercial users. Not redistributed. |
| `Moritz-Pfeifer/CentralBankRoBERTa-sentiment-classifier`, `-agent-classifier` | MIT | Scorer at run time. |

## Central-bank websites

Filled in per bank from `docs/sources/<bank>.md` as each adapter lands.

| Bank | Terms | Redistribute text? | Committed |
|---|---|---|---|
| Fed | federalreserve.gov/disclaimer.htm: public domain unless otherwise indicated; cite the Board | Yes | Text |
| ECB | ecb.europa.eu disclaimer: reproduction permitted with source acknowledged; prior authorisation for documents bearing authors' names | Press releases: yes. Press conferences: no (D8) | Statements: text. Press conferences: URL + SHA-256 |
| MAS | mas.gov.sg terms of use: prior written permission for any reproduction | No | URL + SHA-256 (manual files, D7) |
| PBoC | Not verified; robots.txt disallows all crawlers | No (assumed) | Nothing; out of headline (D10) |
