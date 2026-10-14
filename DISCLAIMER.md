# Disclaimer

`cbtone` is an **independent open-source project** by Thanatchon Chongmankhong.

- It is built **only from publicly available documents** published on central banks' public
  websites (or public mirrors). Every document's URL and hash is listed in
  `data/corpus/manifest.parquet`. No non-public information is used.
- The author is employed by a central bank. This project **does not represent the views of any
  institution**, including the author's employer, and was not produced on its behalf.
- The project measures properties of published text and reports statistical results. It does
  **not** comment on, evaluate or predict any individual central bank's policy choices.
- Nothing here is **investment advice**. Tone scores are noisy research signals; see the paper's
  Threats to Validity and `docs/ANOMALIES.md`.
- The Bank of Thailand adapter is opt-in and excluded from the headline results by default
  (`config/paper.yaml: include_bot: false`).
