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

## Phase 3 — in progress (library)
- [ ] Specs in docs/specs/ for scorers, events, eval, text (paragraph tagger), cli, docs
- [ ] `cbtone doctor` + `results/hardware.json`

## Waiting on owner
- **git push is blocked:** `~/.claude/settings.json` has `"deny": ["Bash(git push *)"]`, and a deny overrides
  allow rules. All work is committed locally. To publish, remove that deny rule (or run `! git push origin main --tags`).
  Commits since `0132cf6` and the tag `prereg-v1` are local only.

Open items for the author:
- BoE: academic re-use permission could be requested to make BoE text redistributable.
- The BoE ~100-char decision releases for 2000–2006 are complete, not truncated (A6).
