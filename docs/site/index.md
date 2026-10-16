# cbtone

`cbtone` turns **public** central-bank communications (statements, minutes, press-conference
text) into hawkish/dovish tone signals, and provides the evaluation tools to test whether those
signals carry information about later policy decisions and market reactions.

```bash
pip install cbtone
cbtone fetch fed ecb mas
cbtone snapshot
cbtone score --scorer llm
cbtone events
```

(`snapshot` builds the corpus from the download cache; see the [CLI reference](cli.md).)

## What is in the box

- **Adapters** that fetch documents politely (robots.txt, at most one request per 2 s per host,
  cached with SHA-256) into one schema: [Adapters](adapters.md).
- **Four scorer families**: dictionary, finance-tuned transformer, local LLM, fine-tuned small
  model, all returning the same `ToneScore`: [Scorers](scorers.md).
- **Evaluation**: rolling-origin ordered-logit tests of policy signal, event studies around
  releases, cross-lingual and contamination checks: [Concepts](concepts.md).
- **A pre-registered study** run with it. Its questions and thresholds are fixed in
  [RESEARCH_QUESTIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/RESEARCH_QUESTIONS.md).

## Results in one line

Every testable pre-registered hypothesis was refuted: local-LLM tone did not beat persistence at predicting the
next decision (0 of 4 powered banks), explained the market move in 1 of 11 bank–market cells, agreed only
moderately between Indonesian/Malay and English versions (ρ 0.61 / 0.53), and moved with the prompt wording.
Details: [paper](paper/index.html) (read online; [PDF](https://github.com/thanatchon36/cbtone/blob/main/paper/paper.pdf)), [one-page summary](https://github.com/thanatchon36/cbtone/blob/main/docs/EXEC_SUMMARY.md),
[`results/summary.json`](https://github.com/thanatchon36/cbtone/blob/main/results/summary.json).

## Where to start

| I want to... | Go to |
|---|---|
| score my own text | [Cookbook: score your own text](cookbook.md#score-your-own-text) |
| add a central bank | [Cookbook: add a central bank in 30 lines](cookbook.md#add-a-central-bank-in-30-lines) |
| run an event study | [Cookbook: run an event study](cookbook.md#run-an-event-study) |
| rebuild the paper's numbers | [Reproducibility](reproducibility.md) |

## How to cite

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

## Disclaimer

Independent open-source project; public documents only; represents no institution's view; not
investment advice. The author works at a central bank, and the project never comments on any
bank's policy choices. Full text: [DISCLAIMER.md](https://github.com/thanatchon36/cbtone/blob/main/DISCLAIMER.md).
