# CLI reference

Generated from `cbtone --help` and each subcommand's `--help` (`cbtone` 0.0.1 in the working tree).
Banks are positional arguments; with none given, the command uses the banks in `config/paper.yaml`
(`fetch`, `snapshot`) or the headline set (`score`, `events`).

A typical session is `fetch`, then `snapshot`, then `score`, then `events`. `markets` and `decisions`
provide the outcome data for event studies and policy-signal tests.

## cbtone

```text

 Usage: cbtone [OPTIONS] COMMAND [ARGS]...

 Hawkish/dovish tone signals from public central-bank communication.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                │
│ --show-completion             Show completion for the current shell, to copy it or     │
│                               customize the installation.                              │
│ --help                        Show this message and exit.                              │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────╮
│ version        Print the cbtone version.                                               │
│ fetch          Download raw documents into the polite on-disk cache                    │
│                (data/raw/<bank>/).                                                     │
│ snapshot       Build the corpus snapshot from the cache only (no network); see         │
│                DECISIONS D8.                                                           │
│ decisions      Build decisions.parquet from BIS policy rates, meeting dates and MAS    │
│                statements.                                                             │
│ markets        Fetch daily FX and 2y/10y yields (DECISIONS D9); not committed (Yahoo   │
│                terms).                                                                 │
│ sample-silver  Draw the 200-sentence SEA silver sample (identifiers only; labels come  │
│                in Phase 3).                                                            │
│ score          Score primary-series documents with one scorer; resumable via the score │
│                cache.                                                                  │
│ events         Event timestamps plus signed  FX and 2y-yield moves for the primary     │
│                documents.                                                              │
│ parse          Parse one saved file with the bank's adapter (debugging aid for adapter │
│                authors).                                                               │
│ doctor         Probe hardware, software, Ollama, caches and corpus; never fails hard.  │
│ schemas        Write JSON Schema files for Document, ToneScore, Decision and           │
│                EventResult.                                                            │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone fetch

```text

 Usage: cbtone fetch [OPTIONS] [banks]...

 Download raw documents into the polite on-disk cache (data/raw/<bank>/).

╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│   banks      <str>  Banks to process (default: config banks).                          │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --start         <int>   First year (default: config start_year).                       │
│ --end           <int>   Last year (default: config end_year).                          │
│ --config        <path>  Run configuration. [default: config/paper.yaml]                │
│ --help                  Show this message and exit.                                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone snapshot

```text

 Usage: cbtone snapshot [OPTIONS] [banks]...

 Build the corpus snapshot from the cache only (no network); see DECISIONS D8.

╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│   banks      <str>  Banks to process (default: config banks).                          │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --start         <int>   First year (default: config start_year).                       │
│ --end           <int>   Last year (default: config end_year).                          │
│ --config        <path>  Run configuration. [default: config/paper.yaml]                │
│ --out           <path>  Snapshot directory. [default: data/corpus]                     │
│ --help                  Show this message and exit.                                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone decisions

```text

 Usage: cbtone decisions [OPTIONS]

 Build decisions.parquet from BIS policy rates, meeting dates and MAS statements.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --corpus                     <path>  Snapshot directory. [default: data/corpus]        │
│ --offline    --no-offline            Use the cached BIS file only.                     │
│                                      [default: no-offline]                             │
│ --help                               Show this message and exit.                       │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone markets

```text

 Usage: cbtone markets [OPTIONS]

 Fetch daily FX and 2y/10y yields (DECISIONS D9); not committed (Yahoo terms).

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --start         <int>   First year (default: config start_year).                       │
│ --end           <int>   Last year (default: config end_year).                          │
│ --config        <path>  Run configuration. [default: config/paper.yaml]                │
│ --out           <path>  Output parquet. [default: data/raw/markets/daily.parquet]      │
│ --help                  Show this message and exit.                                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone sample-silver

```text

 Usage: cbtone sample-silver [OPTIONS]

 Draw the 200-sentence SEA silver sample (identifiers only; labels come in Phase 3).

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --corpus        <path>  Snapshot directory. [default: data/corpus]                     │
│ --config        <path>  Run configuration. [default: config/paper.yaml]                │
│ --out           <path>  Output CSV (identifiers only).                                 │
│                         [default: data/labels/sea_silver_sample.csv]                   │
│ --help                  Show this message and exit.                                    │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone score

```text

 Usage: cbtone score [OPTIONS] [banks]...

 Score primary-series documents with one scorer; resumable via the score cache.

╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│   banks      <str>  Banks to process (default: config banks).                          │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ *  --scorer                          <str>    dict | fomc-roberta | llm | ft.          │
│                                               [required]                               │
│    --native         --no-native               Score the native-language twin.          │
│                                               [default: no-native]                     │
│    --masked         --no-masked               Masked input variant (llm only).         │
│                                               [default: no-masked]                     │
│    --prompt                          <str>    LLM prompt id. [default: P1]             │
│    --model                           <str>    Ollama model tag (llm).                  │
│                                               [default: qwen3:4b]                      │
│    --temperature                     <float>  LLM temperature. [default: 0.0]          │
│    --cap                             <int>    Policy-text character cap (D18).         │
│                                               [default: 3000]                          │
│    --evidence       --no-evidence             LLM document mode: also ask for quotes.  │
│                                               [default: no-evidence]                   │
│    --quick          --no-quick                Score the deterministic quick sample.    │
│                                               [default: no-quick]                      │
│    --model-dir                       <path>   Fine-tuned model dir (ft).               │
│    --corpus                          <path>   Snapshot directory.                      │
│                                               [default: data/corpus]                   │
│    --out                             <path>   Output parquet.                          │
│    --help                                     Show this message and exit.              │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone events

```text

 Usage: cbtone events [OPTIONS] [banks]...

 Event timestamps plus signed  FX and 2y-yield moves for the primary documents.

╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│   banks      <str>  Banks to process (default: config banks).                          │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --corpus         <path>  Snapshot directory. [default: data/corpus]                    │
│ --markets        <path>  Daily markets. [default: data/raw/markets/daily.parquet]      │
│ --out            <path>  Output parquet. [default: results/events.parquet]             │
│ --help                   Show this message and exit.                                   │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone parse

```text

 Usage: cbtone parse [OPTIONS] {bank}

 Parse one saved file with the bank's adapter (debugging aid for adapter authors).

╭─ Arguments ────────────────────────────────────────────────────────────────────────────╮
│ *    bank      <str>  Bank whose adapter parses the file. [required]                   │
╰────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ *  --file        <path>  Saved raw file (cache or manual). [required]                  │
│    --url         <str>   URL to record on the documents. [default: file://local]       │
│    --hint        <str>   Adapter hint key=value.                                       │
│    --help                Show this message and exit.                                   │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone doctor

```text

 Usage: cbtone doctor [OPTIONS]

 Probe hardware, software, Ollama, caches and corpus; never fails hard.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --json        <path>  Also write the report as JSON.                                   │
│ --help                Show this message and exit.                                      │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

## cbtone schemas

```text

 Usage: cbtone schemas [OPTIONS]

 Write JSON Schema files for Document, ToneScore, Decision and EventResult.

╭─ Options ──────────────────────────────────────────────────────────────────────────────╮
│ --out         <path>  Schema directory. [default: schemas]                             │
│ --help                Show this message and exit.                                      │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```
