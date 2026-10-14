# FAQ

**Is this endorsed by, or does it speak for, any central bank?**
No. It is an independent open-source project built only from public documents. See the
[disclaimer](https://github.com/thanatchon36/cbtone/blob/main/DISCLAIMER.md). The author works at a central bank; the project uses no
non-public information and does not comment on any bank's policy choices.

**Is it investment advice?**
No. Tone scores are noisy research signals with documented limitations.

**Why is the Bank of Thailand excluded from the headline results?**
Its adapter is opt-in (`include_bot: false` in `config/paper.yaml`). It is implemented like every
other adapter and can be included for appendix analyses.

**Why does `fetch` report MAS as blocked?**
MAS blocks automated access, and the library does not try to get around a block. Save the pages
listed in [NEEDED.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/NEEDED.md) by hand and the adapter parses them.

**Can I redistribute the corpus?**
Only where the source's terms allow it. Fed text is public domain, RBA text is CC BY 4.0, and ECB
statements may be reproduced with acknowledgement. For the other banks the repository holds URLs
and hashes only. Details: [LICENSES.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/LICENSES.md).

**Can I use FOMC-RoBERTa commercially?**
No: it is CC-BY-NC-4.0 and gated on Hugging Face. It is used as a run-time scorer and for
evaluation only, and is never redistributed here.

**Do I need a GPU?**
No. The target machine is a laptop without CUDA. The LLM scorer runs a small model (4B
parameters or fewer) through Ollama.

**How do I know an LLM score is not just memory?**
Every LLM result comes with a masked-text variant and a post-cutoff split, and predictive
claims are made only where both survive. See [Scorers](scorers.md#contamination).

**Where are the results?**
Not yet available. The study is pre-registered; results will be reported against the
pre-registered thresholds, including those that refute it.

**What happens when a number looks too good?**
A headline metric at exactly 0, 1 or 100 %, a correlation above 0.95, or a value more than 2x
outside the literature range fails the build until explained in
[ANOMALIES.md](https://github.com/thanatchon36/cbtone/blob/main/docs/ANOMALIES.md).

**How do I add a bank, scorer, language or market series?**
See [CONTRIBUTING.md](https://github.com/thanatchon36/cbtone/blob/main/CONTRIBUTING.md).
