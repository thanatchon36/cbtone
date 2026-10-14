# Spec: CLI additions and JSON schemas

Read first: `src/cbtone/cli.py` (the existing `fetch`, `snapshot`, `decisions`, `markets` and `sample-silver`
commands and their style), `src/cbtone/corpus.py`, `src/cbtone/pipeline.py`, `src/cbtone/scorers/__init__.py`,
`src/cbtone/events/engine.py` and `tests/test_cli.py` (test patterns: `CliRunner`, monkeypatched fakes, no network).

## Commands to add (`src/cbtone/cli.py`)
- `cbtone score --scorer {dict,fomc-roberta,llm,ft} [BANKS...] [--native] [--masked] [--prompt P1] [--model qwen3:4b] [--temperature 0] [--cap 3000 (D18)] [--evidence] [--quick] [--out results/scores/<scorer>[-masked].parquet]`
  - Docs: `corpus.primary(banks, native=...)`; `--quick` uses `corpus.quick_sample`.
  - Scorer: `scorers.get_scorer(...)`, with a shared `ScoreCache()`.
  - Runs `pipeline.score_documents` inside `pipeline.Timer().stage("score:<scorer>[:masked]")`.
  - Writes parquet, appending/replacing rows for the same (doc_id, scorer_id, variant), and prints the counts plus the number of errors.
  - `variant` string = `"masked"` or `""`, with `|T=<temp>` and `|<prompt>` added when they differ from the defaults.
  - `--scorer llm` with the `[api]` backend is out of scope.
  - `ft` needs `--model-dir`.
- `cbtone events [BANKS...] [--out results/events.parquet]`
  - `engine.build_events` on the primary docs of the banks.
  - Attach the signed [t−1, t+1] moves for each bank's series in `engine.BANK_SERIES`, from `data/raw/markets/daily.parquet`
    (`--markets` option), as columns `move_fx` and `move_y2` (null where unavailable).
  - Print the per-bank counts and the timing-flag counts.
- `cbtone parse BANK --file PATH`: parse one saved file with the bank adapter's `parse` (from the cache or a manual file) and print
  doc_id, title and the first 300 characters. A debugging aid for adapter authors.
- `cbtone doctor [--json results/hardware.json]`: probe and print the following, and write JSON when `--json` is given:
  - platform, macOS version, CPU (`sysctl -n machdep.cpu.brand_string` when on macOS), RAM;
  - Python version, versions of `cbtone`, `polars`, `torch`/`transformers` if importable, and MPS availability;
  - Ollama reachability at `localhost:11434`, plus the tags and digests of installed models (`/api/tags`);
  - free disk space, and the size of `data/cache/scores.sqlite` and its row count;
  - the corpus `VERSION`.

  It never fails hard: each probe reports ok/missing.
- `cbtone schemas [--out schemas/]`: write JSON Schema files `Document.json`, `ToneScore.json`, `Decision.json` and
  `EventResult.json`. Use pydantic `model_json_schema()`, and `TypeAdapter` for the `EventResult` dataclass.
  Commit the generated `schemas/` files.

## Tests (`tests/test_cli.py`, extend)
Use fakes: a fake scorer (monkeypatch `scorers.get_scorer`), a tiny corpus written to `tmp_path` (documents.parquet
plus VERSION), a fake Ollama via monkeypatched `httpx`, and fake market frames. Cover every new command, including
error paths: unknown scorer, Ollama down in `doctor`, `--quick`. Keep `cli.py` coverage ≥ 85 %.

## Rules
Don't edit anything outside `src/cbtone/cli.py`, `tests/test_cli.py` and `schemas/`. If a library function you need is
missing, report it instead of writing it. Don't commit and don't run `uv add`. Run the cli tests, `ruff check`/`format`
on your files, and `mypy`. Once you're done, run the real `cbtone doctor --json results/hardware.json` and
`cbtone schemas`, and report what they printed.
