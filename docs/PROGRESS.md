# Progress

Resume with: "Read MISSION.md, docs/PROGRESS.md, docs/DECISIONS.md and continue".

## Phase 1 — closed 2026-10-14

Corpus snapshot `2026-10-14+ed5a49c2…` (`data/corpus/VERSION`): 2,935 documents.

| Bank | Docs | Text coverage | Redistributable |
|---|---|---|---|
| Fed | 535 | statements, minutes, press conferences 2000→ | yes |
| ECB | 575 | statements 1999→, press conferences (Q&A) | statements yes; press conferences no (D8) |
| BoE | 567 | statements 2000→, minutes 2000→ | no |
| RBA | 452 | statements 2000→, minutes 2006→, press conferences 2024→ | yes (CC BY 4.0) |
| MAS | 62 | MPS 2001–Apr 2026 via Internet Archive (D11) | no |
| BI | 256 | statements Apr 2016→, en/id (A5) | no |
| BNM | 280 | MPS 2004→, en/ms | no |
| BoT (opt-in) | 143 | statements + minutes 2021→, th/en (A4) | no |
| PBoC (exploratory) | 65 | MPC communiqués, 53 % of zh 2010→ (D15) | no |

Headline set (D10, D15): Fed, ECB, BoE, RBA, MAS, BI, BNM. Languages en/id/ms (+ th opt-in, zh exploratory).

Shipped:
- [x] Adapters for all nine banks, each with offline tests and `docs/sources/<bank>.md`. Every adapter was
      cross-checked against the bank's meeting schedule (statements/year); the gaps found were fixed or recorded.
- [x] `PoliteFetcher` (robots, rate limits, Crawl-delay, cache, block-page rejection, form POST)
- [x] CLI: `fetch`, `snapshot` (cache only, per-(bank, doc_type) redistribution, short-document QA),
      `decisions`, `markets`, `sample-silver`
- [x] `decisions.parquet`: 1,558 rows. BIS rate changes + holds from meeting dates. MAS rows come from MAS's own
      decision table (D14), and the text extractor is used only after it (2 rows in 2026)
- [x] Markets: 17 daily series; Yahoo FX bad ticks filtered (A7). `data/raw/markets/daily.parquet` is not committed
- [x] FOMC anchor loader (CC-BY-NC, evaluation only, pinned revision)
- [x] SEA silver sample: `data/labels/sea_silver_sample.csv`, 200 sentence ids (MAS 60, BI en/id 35+35,
      BNM en/ms 35+35), seed 20261014. Labels come in Phase 3
- [x] MAS stance gold set (labels from MAS's table, D13). Extractor accuracy is development accuracy only (D14)
- [x] `make test lint`: 361 tests, 96 % coverage, ruff + mypy clean
- [x] DECISIONS D1–D15, ANOMALIES A1–A7, LICENSES per-bank table

Cut / known gaps:
- BI before Apr 2016 (no index; A5). BoT before 2021 (A4). PBoC 2016–2022 (anti-bot shells; D15)
- MAS 27 Jul 2026 (all captures are maintenance pages) and 14 Oct 2026 (not yet archived)
- BoE minutes of the special 19 Mar 2020 meeting (not in the sitemap)
- FX before Dec 2003 for most pairs, so MAS 2001–2003 statements have no FX window (A7)

## Phase 2 — closed 2026-10-14

- [x] `docs/RESEARCH_QUESTIONS.md` committed and tagged `prereg-v1` (D16): RQ1–RQ5, power rules,
      release-date rule (§0.4), data-gap treatments, budget ladder

## Phase 3 — library: built (2026-10-14)
- [x] Scorers: dictionary (dict-v1, 167-term cited lexicon), FOMC-RoBERTa (built, gated: waiting on owner),
      Ollama LLM (P1–P5, structured output, cache, masked variant, aggregation), fine-tuned XLM-R trainer
- [x] text.paragraphs (tagger + pre-registered policy_text), text.mask reviewed and extended (D19)
- [x] events engine, eval (stats, fast ordered logit, rolling origin, rules), analysis RQ1–RQ5
- [x] CLI: score / events / parse / doctor / schemas; JSON schemas; results/hardware.json
- [x] Docs site (mkdocs), README, DISCLAIMER, CONTRIBUTING, CITATION, CI + release workflows, mini corpus

## Phase 4 — closed 2026-10-14 (experiments)
Backend D20: qwen3:4b (digest `359d7dd4`) on the owner's RTX 4070 Ti; pre-registered defaults, no ladder step
(cap 6000, RQ4a 1,000 sentences, masked for every LLM result, evidence off). Wall time: documents ≈ 35 min,
silver 5 min, RQ4a 71 min, fine-tune 6 min (MPS, 642 steps, val macro-F1 0.61). Sanity gate: 3 flags, all explained.

- [x] Document scores: llm / llm-native / llm-masked / llm-masked-native / dict / ft (+ native), 0 errors
- [x] FOMC test (496), silver (200), RQ4a (7,000 sentence scores, 21 JSON failures recorded as missing; 840 doc
      scores; 360 aggregations)
- [x] `make experiments` → results/summary.json, results/figures/*.png (+ CSV table views), SANITY.md
- [x] ANOMALIES A9–A12 (BI AUROC 1.000 at n=20; BI negative FX β; mean≈decision-weighted by construction;
      FOMC source index not unique → id fixed, no threshold touched)

Verdicts (pre-registered thresholds, Holm across powered banks):
- **H1 refuted**: 0/4 powered banks (best: ECB ΔLL +0.058, Holm p 0.13). Not robust under masking.
- **H2a refuted** (1/11 cells: RBA AU2Y), **H2b refuted** (0/11). Pooled FX β ≈ 0.
- **H3 refuted**: BI ρ 0.61, BNM ρ 0.53 (< 0.70); flips ≈ 2 %.
- **H4a refuted**: prompts α 0.42 (sentences), 0.65 (documents) < 0.667; temperature α 0.81 / 0.92; model tag
  α −0.03 / 0.46; aggregation ρ 0.62–0.98 (not all ≥ 0.70).
- **H4b refuted**: LLM macro-F1 0.48 [0.43, 0.53] < 0.50, though above the dictionary (0.27) with CI excluding 0.
- **H4c**: no RQ1/RQ2 finding is robust (masked check fails; post-cutoff N small).
- **H5 untestable** (FOMC-RoBERTa gated; BI-en/BNM-en 35 sentences < 50).

## Phase 5 — closed 2026-10-14 (write-up)
- [x] `paper/paper.md` results, abstract and conclusion; every number injected from summary.json (`make paper` →
      paper/paper.pdf via pandoc + typst). `build.py` gained compound selectors and `yn`/`pct1` formats
- [x] Refuted hypotheses reported as refuted; MAS extractor accuracy described as development accuracy (D14)
- [x] `docs/EXEC_SUMMARY.md` (one page, incl. GPU vs laptop cost)
- [x] `docs/posts/`: launch + 9 single-finding drafts (706–1,030 chars each, ≤ 1,300)
- [x] README results table + headline chart; docs site results/FAQ/reproducibility updated (`mkdocs build --strict` ok)

## Phase 6 — release (2026-10-14)
- [x] Fresh-clone `make reproduce` (commit fefdb16): exit 0, 23 min on the M4 with the score cache; no verdict
      changed (A13: ft retrain not bit-identical on MPS; 7 previously failed RQ4a calls succeeded on retry)
- [x] `uv build`: wheel + sdist; wheel installs and `cbtone --help` runs in a clean venv; sdist holds no withheld text
- [x] CITATION.cff date-released 2026-10-14; `cbtone doctor` honours CBTONE_SCORE_CACHE; hardware.json regenerated
- [x] Pushed by the owner: main @ fefdb16 and tag prereg-v1 are on GitHub
- [x] Tag v0.1.0 (local; push with `git push origin main --tags`)
- [x] Pushed by the owner: main @ 895323c and tags prereg-v1, v0.1.0; CI green on main and the tag
- [x] PyPI: trusted publisher configured by the owner; release run 38550417594 re-run → cbtone 0.1.0 (wheel + sdist)
      on https://pypi.org/project/cbtone/
- [ ] FOMC-RoBERTa: HF login done (user thanatchon36); access requested 2026-10-14, pending approval. When granted:
      score FOMC test + silver, rerun rq4/rq5, refresh paper → v0.1.1

## Post-release polish (2026-10-14, after v0.1.0)

- [x] PyPI: `cbtone 0.1.0` published through the trusted publisher; `pip install cbtone==0.1.0` verified in a
      fresh venv (import and `cbtone --help` work).
- [x] Paper rewritten in full (`paper/paper.md`): formal register, numbered sections, equations for the RQ1/RQ2
      estimators, a sample table, a hypotheses table with verdicts, and a discussion section. Numeric
      citations (IEEE CSL, `paper/csl/ieee.csl`) in the PDF and on the web; all 33 references are cited.
      Every number is still a `{{...}}` placeholder resolved from `results/summary.json`.
- [x] Figures redone (`experiments/figures.py`): paper font (Libertinus Serif, vendored in `paper/fonts/`,
      OFL), SVG + 300-dpi PNG + CSV per figure, full-width layout, hollow markers for underpowered cells, a
      two-panel RQ2 figure (FX and 2-year yield), a bubble cross-lingual plot and a new RQ4a stability figure.
- [x] Web version of the paper: `paper/build.py` also writes `docs/site/paper.md` (numbered captions and
      headings, citations resolved to `[n]` links, reference list) and copies the SVGs to
      `docs/site/figures/`; added to the mkdocs nav.
- [x] Pandoc 3.8's typst template deletes every link that is not a coloured label link (its `show link`
      rule returns `none`), which silently removed citations, DOIs and URLs from the PDF. A patched copy is
      vendored in `paper/templates/` and used by `make paper`.

- [x] GitHub Pages enabled 2026-10-14 (source: GitHub Actions); `.github/workflows/docs.yml` deploys the site on
      every push to main. Paper online at https://thanatchon36.github.io/cbtone/paper/

- [x] v0.1.1 (2026-10-14): rewritten paper, publication figures, online paper; no change to any result or
      verdict. Tagged locally; the release workflow publishes to PyPI when the tag is pushed.

- [x] v0.1.1 pushed; PyPI 0.1.1 published and installed in a fresh venv; GitHub Release v0.1.1 created; Zenodo
      DOI minted: concept 10.5281/zenodo.23371641 (v0.1.1: 10.5281/zenodo.23371642), added to CITATION.cff
      and README.

- [x] Hugging Face (2026-10-14): model `thanatchon36/cbtone-ft-xlmr` (the paper's checkpoint, sha256
      f16943a3…; re-downloaded and re-scored: FOMC macro-F1 0.41, as reported) and dataset
      `thanatchon36/cbtone-silver-sentences` (config `public`: 1,187 sentences with text from Fed, RBA and ECB
      press releases; config `ids_only`: 2,568 sentences as ids + hashes + labels, no text, for BoE, MAS, BI,
      BNM and ECB press conferences; 33 sentences not traceable to one document omitted). Built by
      `experiments/export_hf.py`; cards in `experiments/hf_cards/`.

- [x] v0.1.2 (2026-10-14): citations only. README, docs home page, web paper, Hugging Face cards and
      CITATION.cff (`preferred-citation`) give BibTeX for the paper (exact title, web URL; no DOI yet) and for
      the software (`cbtone`, Zenodo concept DOI); generated by `paper/build.py:citations()` and kept in sync
      by a test. `.zenodo.json` links each Zenodo version to the paper ("is documented by"). Repository
      homepage set to the web paper. No change to any result, verdict or library behaviour.
- [x] v0.1.2 pushed; PyPI 0.1.2 published (description carries both BibTeX entries); GitHub Release v0.1.2;
      Zenodo v0.1.2 DOI 10.5281/zenodo.23373854, metadata from `.zenodo.json` incl. the paper link.

## Waiting on owner
- **git push is blocked for the agent** (deny rule in `~/.claude/settings.json`). The owner pushes with
  `! git push origin main --tags`.
- **FOMC-RoBERTa is gated on Hugging Face:** logged in and access requested on 2026-10-14; waiting for the model
  owner's approval (the chat-pasted token was revoked and replaced on 2026-10-14). Until then RQ4b/RQ5 report it as "not run (gated)". The scorer is built,
  pinned to revision `aa3bc428…`, and checks its label map at load time.

Open items for the author:
- BoE: academic re-use permission could be requested to make BoE text redistributable.

- The BoE ~100-char decision releases for 2000–2006 are complete, not truncated (A6).
