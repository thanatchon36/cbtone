"""cbtone command-line interface."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from cbtone import __version__
from cbtone.schema import Document
from cbtone.sources import registry
from cbtone.sources.base import PoliteFetcher, SourceAdapter

app = typer.Typer(help="Hawkish/dovish tone signals from public central-bank communication.")

CONFIG = Path("config/paper.yaml")
CORPUS = Path("data/corpus")

BanksArg = Annotated[
    list[str] | None, typer.Argument(help="Banks to process (default: config banks).")
]
StartOpt = Annotated[int | None, typer.Option(help="First year (default: config start_year).")]
EndOpt = Annotated[int | None, typer.Option(help="Last year (default: config end_year).")]
ConfigOpt = Annotated[Path, typer.Option(help="Run configuration.")]


def _config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def banks_from_config(path: Path = CONFIG) -> list[str]:
    cfg = _config(path)
    banks = list(cfg.get("banks", registry.BANKS))
    if cfg.get("include_bot") and "bot" not in banks:
        banks.append("bot")
    return banks


def _resolve(
    banks: list[str] | None, start: int | None, end: int | None, config: Path
) -> tuple[list[str], int, int]:
    cfg = _config(config)
    return (
        banks or banks_from_config(config),
        start if start is not None else int(cfg.get("start_year", 2000)),
        end if end is not None else int(cfg.get("end_year", date.today().year)),
    )


def collect(
    adapter: SourceAdapter, start_year: int, end_year: int
) -> tuple[list[Document], list[str]]:
    """Run one adapter, keeping going past per-URL failures; returns (documents, errors).

    Adapters that override ``fetch`` (manual-file mode: MAS, PBoC) run as a whole.
    """
    docs: list[Document] = []
    errors: list[str] = []
    if type(adapter).fetch is not SourceAdapter.fetch:
        try:
            docs.extend(adapter.fetch(start_year, end_year))
        except Exception as e:  # report and move on to the next bank
            errors.append(f"{type(e).__name__}: {e}")
        return docs, errors
    listing = iter(adapter.list_urls(start_year, end_year))
    while True:
        try:
            url, hints = next(listing)
        except StopIteration:
            break
        except Exception as e:  # an index page failed: keep what we have, report it
            errors.append(f"listing aborted: {type(e).__name__}: {e}")
            break
        try:
            docs.extend(adapter.parse(adapter.fetcher.get(adapter.bank, url), hints))
        except Exception as e:  # one bad page must not stop a long run
            errors.append(f"{url}: {type(e).__name__}: {e}")
    return docs, errors


def _run(
    banks: list[str], start: int, end: int, fetcher: PoliteFetcher
) -> tuple[list[Document], bool]:
    all_docs: list[Document] = []
    ok = True
    for bank in banks:
        docs, errors = collect(registry.make_adapter(bank, fetcher), start, end)
        typer.echo(f"{bank}: {len(docs)} documents, {len(errors)} errors")
        for err in errors[:20]:
            typer.echo(f"  {err}", err=True)
        all_docs.extend(docs)
        ok = ok and not errors
    return all_docs, ok


@app.command()
def version() -> None:
    """Print the cbtone version."""
    typer.echo(__version__)


@app.command()
def fetch(
    banks: BanksArg = None,
    start: StartOpt = None,
    end: EndOpt = None,
    config: ConfigOpt = CONFIG,
) -> None:
    """Download raw documents into the polite on-disk cache (data/raw/<bank>/)."""
    names, s, e = _resolve(banks, start, end, config)
    _, ok = _run(names, s, e, PoliteFetcher())
    raise typer.Exit(0 if ok else 1)


@app.command()
def snapshot(
    banks: BanksArg = None,
    start: StartOpt = None,
    end: EndOpt = None,
    config: ConfigOpt = CONFIG,
    out: Annotated[Path, typer.Option(help="Snapshot directory.")] = CORPUS,
) -> None:
    """Build the corpus snapshot from the cache only (no network); see DECISIONS D8."""
    from cbtone.sources.snapshot import build_snapshot

    names, s, e = _resolve(banks, start, end, config)
    docs, _ = _run(names, s, e, PoliteFetcher(offline=True))
    ver = build_snapshot(docs, out, registry.REDISTRIBUTABLE)
    typer.echo(f"snapshot {ver}: {len(docs)} documents -> {out}")
    _qa(out / "manifest.parquet")


SHORT_DOC_CHARS = 200


def _qa(manifest: Path) -> None:
    """Flag banks with suspiciously short documents (truncated parses, placeholder pages)."""
    import polars as pl

    short = (
        pl.read_parquet(manifest)
        .filter(pl.col("n_chars") < SHORT_DOC_CHARS)
        .group_by("bank")
        .agg(pl.len().alias("n"), pl.col("doc_id").sort().first().alias("example"))
        .sort("bank")
    )
    for bank, n, example in short.iter_rows():
        typer.echo(f"QA: {bank} has {n} documents under {SHORT_DOC_CHARS} chars (e.g. {example})")


@app.command()
def decisions(
    corpus: Annotated[Path, typer.Option(help="Snapshot directory.")] = CORPUS,
    offline: Annotated[bool, typer.Option(help="Use the cached BIS file only.")] = False,
) -> None:
    """Build decisions.parquet from BIS policy rates, meeting dates and MAS statements."""
    from cbtone.decisions.bis import fetch_bis_csv
    from cbtone.decisions.build import build_from_corpus
    from cbtone.decisions.mas import parse_decision_table
    from cbtone.sources.mas import fetch_decision_table

    fetcher = PoliteFetcher(offline=offline)
    csv = fetch_bis_csv(fetcher)
    raw = fetch_decision_table(fetcher)
    table = parse_decision_table(raw.content) if raw is not None else []
    typer.echo(f"MAS decision table: {len(table)} rows ({raw.url if raw else 'unavailable'})")
    df = build_from_corpus(
        csv, corpus / "documents.parquet", corpus / "decisions.parquet", mas_table=table
    )
    typer.echo(f"decisions: {df.height} rows -> {corpus / 'decisions.parquet'}")


@app.command()
def markets(
    start: StartOpt = None,
    end: EndOpt = None,
    config: ConfigOpt = CONFIG,
    out: Annotated[Path, typer.Option(help="Output parquet.")] = Path(
        "data/raw/markets/daily.parquet"
    ),
) -> None:
    """Fetch daily FX and 2y/10y yields (DECISIONS D9); not committed (Yahoo terms)."""
    import polars as pl

    from cbtone.markets.fx import clean_fx, fetch_fx
    from cbtone.markets.registry import FX_TICKERS
    from cbtone.markets.yields import fetch_all_yields

    _, s, e = _resolve(["-"], start, end, config)
    first, last = date(s, 1, 1), min(date(e, 12, 31), date.today())
    fx = fetch_fx(list(FX_TICKERS), first, last)
    ylds = fetch_all_yields(first, last, PoliteFetcher())
    df, dropped = clean_fx(pl.concat([fx, ylds]).sort("series", "date"))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    dropped.write_csv(out.with_name("dropped_ticks.csv"))  # series, date, reason; no prices
    typer.echo(
        f"markets: dropped {dropped.height} bad FX ticks -> {out.with_name('dropped_ticks.csv')}"
    )
    typer.echo(f"markets: {df.height} rows, {df['series'].n_unique()} series -> {out}")


if __name__ == "__main__":
    app()
