# Disclaimer

`cbtone` is an **independent open-source project** by Thanatchon Chongmankhong.

1. **Independent project.** It is developed in the author's personal capacity. It is not
   produced on behalf of, endorsed by, or affiliated with any institution.
2. **Author context.** The author works at a central bank. This project **does not represent the
   views of that institution or of any other**, and uses no knowledge obtained through that
   employment.
3. **Public documents only.** Every document comes from a central bank's public website or a
   public mirror. Each document's URL and SHA-256 hash is listed in
   `data/corpus/manifest.parquet`. No non-public, internal or confidential information of any
   kind is used, and if a fact cannot be derived from a public URL in that manifest it does not
   belong in this repository.
4. **No commentary on policy.** The project measures properties of published text and reports
   statistical results. It does **not** comment on, evaluate, criticise or predict any individual
   central bank's policy choices. Tone scores describe wording, not the merits of a decision.
5. **Bank of Thailand.** The Bank of Thailand adapter is **opt-in** and is **excluded from the
   headline results** by default (`config/paper.yaml: include_bot: false`). It is implemented
   like every other adapter; excluding it from the headline configuration is a design choice
   about presentation, not a statement about any bank.
6. **Not investment advice.** Nothing in this repository, its documentation, its paper or its
   outputs is investment, trading, legal or financial advice. Tone scores are noisy research
   signals with documented limitations (see `docs/ANOMALIES.md` and the paper's Threats to
   Validity). Use them at your own risk.
7. **Data terms.** Corpus text remains subject to each source's own terms of use
   (`docs/sources/LICENSES.md`). Where those terms forbid redistribution, only URLs, hashes and
   the fetch code are published. Some third-party models and datasets are non-commercial; check
   their licences before commercial use.
8. **No warranty.** The software is provided "as is" under the Apache-2.0 licence, without
   warranty of any kind.
