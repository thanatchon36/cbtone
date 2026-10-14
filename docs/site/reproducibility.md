# Reproducibility

- **Pinned environment.** `uv.lock` pins every dependency; set up with `uv sync`. Python 3.11 or
  newer. Hardware target: a 16 GB, fanless laptop with no CUDA.
- **Versioned corpus.** `data/corpus/VERSION` has the form `<date>+<sha256 of the manifest>`. The
  manifest lists every document's public URL and the SHA-256 of the raw bytes. The raw cache
  (`data/raw/<bank>/`) keeps bytes git-ignored but its hash sidecars committed, so a rebuilt
  cache can be checked against the manifest.
- **Fixed seeds.** All sampling, bootstraps and permutations use the seed in `config/paper.yaml`
  (20261014).
- **Deterministic LLM calls.** Temperature 0, exact model tag, quantisation and digest recorded
  in every result; calls are cached by content hash in `data/cache/scores.sqlite` and are
  resumable.
- **Timing.** Per-stage wall time is logged to `results/timing.json`; `cbtone doctor` records the
  hardware in `results/hardware.json`.
- **Rebuild.** The Makefile targets are `setup`, `fetch`, `snapshot`, `score`, `experiments`,
  `paper`, `reproduce`, `test`, `lint`, `docs` and `quick`. `make reproduce` is meant to rebuild
  every table and figure from the committed corpus snapshot. Check `make help` for the targets that
  exist in your checkout; targets for later project phases may not be implemented yet.
- **CI without network.** `make quick-ci` scores the committed mini corpus
  (`tests/fixtures/corpus_mini/`, Fed and RBA only) with the dictionary scorer.
- **Text you cannot redistribute.** For banks whose terms forbid it, the repository holds URLs
  and hashes; run `cbtone fetch` then `cbtone snapshot` to rebuild the text locally. MAS needs
  manually saved files ([NEEDED.md](https://github.com/thanatchon36/cbtone/blob/main/docs/sources/NEEDED.md)).
- **Honest reporting.** Deviations (for example the LLM budget ladder, D18) are recorded in
  [DECISIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/DECISIONS.md); anomalies in
  [ANOMALIES.md](https://github.com/thanatchon36/cbtone/blob/main/docs/ANOMALIES.md); the pre-registered questions in
  [RESEARCH_QUESTIONS.md](https://github.com/thanatchon36/cbtone/blob/main/docs/RESEARCH_QUESTIONS.md).

All headline numbers are in [`results/summary.json`](https://github.com/thanatchon36/cbtone/blob/main/results/summary.json); figures (SVG and PNG) and their CSV table
views are in `results/figures/`. The sanity gate's report is `results/SANITY.md`. `make paper` injects the
numbers into `paper/paper.md`, typesets the PDF (pandoc → typst, numeric citations) and regenerates the
[online version of the paper](paper.md).

**Fresh-clone check (2026-10-14):** `make reproduce` on a fresh clone of commit `fefdb16`, with the withheld text,
raw market data and the score cache copied in, finished with exit 0 in 23 minutes on an Apple M4 (LLM backend: the
same cache). No verdict changed; the fine-tuned model's numbers and seven RQ4a cells differ slightly (see
`docs/ANOMALIES.md`, A13).
