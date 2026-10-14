"""cbtone command-line interface."""

from __future__ import annotations

import json
import platform
import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, date, datetime
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
import yaml

from cbtone import __version__
from cbtone.schema import Document
from cbtone.sources import registry
from cbtone.sources.base import PoliteFetcher, RawResponse, SourceAdapter

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


@app.command("sample-silver")
def sample_silver_cmd(
    corpus: Annotated[Path, typer.Option(help="Snapshot directory.")] = CORPUS,
    config: ConfigOpt = CONFIG,
    out: Annotated[Path, typer.Option(help="Output CSV (identifiers only).")] = Path(
        "data/labels/sea_silver_sample.csv"
    ),
) -> None:
    """Draw the 200-sentence SEA silver sample (identifiers only; labels come in Phase 3)."""
    import polars as pl

    from cbtone.eval.silver import DEFAULT_QUOTAS, sample_silver

    private = corpus / "private" / "sentences.parquet"
    sents = pl.read_parquet(private if private.exists() else corpus / "sentences.parquet")
    sents = sents.filter(pl.col("text").is_not_null())
    seed = int(_config(config).get("seed", 0))
    df = sample_silver(sents, DEFAULT_QUOTAS, seed)
    version = (corpus / "VERSION").read_text().strip()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# corpus {version}; seed {seed}\n" + df.write_csv())
    typer.echo(f"silver sample: {df.height} sentences -> {out}")


SCORES_DIR = Path("results/scores")
MARKETS = Path("data/raw/markets/daily.parquet")
SCORE_CACHE = Path("data/cache/scores.sqlite")
OLLAMA_URL = "http://localhost:11434"
SCORE_KEY = ["doc_id", "scorer_id", "variant"]


def _fail(msg: str) -> typer.Exit:
    typer.echo(msg, err=True)
    return typer.Exit(2)


def score_variant(masked: bool, temperature: float, prompt: str) -> str:
    """``"masked"`` or ``""``, plus ``|T=<temp>`` and ``|<prompt>`` when not the defaults."""
    variant = "masked" if masked else ""
    if temperature != 0:
        variant += f"|T={temperature:g}"
    if prompt != "P1":
        variant += f"|{prompt}"
    return variant


@app.command()
def score(
    scorer: Annotated[str, typer.Option(help="dict | fomc-roberta | llm | ft.")],
    banks: BanksArg = None,
    native: Annotated[bool, typer.Option(help="Score the native-language twin.")] = False,
    masked: Annotated[bool, typer.Option(help="Masked input variant (llm only).")] = False,
    prompt: Annotated[str, typer.Option(help="LLM prompt id.")] = "P1",
    model: Annotated[str, typer.Option(help="Ollama model tag (llm).")] = "qwen3:4b",
    temperature: Annotated[float, typer.Option(help="LLM temperature.")] = 0.0,
    cap: Annotated[int, typer.Option(help="Policy-text character cap.")] = 6000,
    quick: Annotated[bool, typer.Option(help="Score the deterministic quick sample.")] = False,
    model_dir: Annotated[Path | None, typer.Option(help="Fine-tuned model dir (ft).")] = None,
    corpus: Annotated[Path, typer.Option(help="Snapshot directory.")] = CORPUS,
    out: Annotated[Path | None, typer.Option(help="Output parquet.")] = None,
) -> None:
    """Score primary-series documents with one scorer; resumable via the score cache."""
    import polars as pl

    from cbtone import corpus as corp
    from cbtone import scorers
    from cbtone.pipeline import Timer, score_documents
    from cbtone.scorers import ScoreCache

    if scorer not in scorers.SCORERS:
        raise _fail(f"unknown scorer {scorer!r}; expected one of {', '.join(scorers.SCORERS)}")
    if masked and scorer != "llm":
        raise _fail("--masked is only supported with --scorer llm")
    if scorer == "ft" and model_dir is None:
        raise _fail("--scorer ft needs --model-dir")
    names = banks or list(corp.HEADLINE)
    unknown = [b for b in names if b not in corp.PRIMARY]
    if unknown:
        raise _fail(f"unknown bank(s): {', '.join(unknown)}")
    if not (corpus / "documents.parquet").exists():
        raise _fail(f"no corpus at {corpus}")

    if quick:
        frame = corp.quick_sample(corp.load_frame(corpus))
        if banks:
            frame = frame.filter(pl.col("bank").is_in(banks))
        docs = corp.to_documents(frame)
    else:
        docs = corp.primary(names, corpus, native=native)

    cache = ScoreCache()
    try:
        kw: dict[str, Any] = {}
        if scorer == "llm":
            kw = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "masked": masked,
                "cache": cache,
            }
        elif scorer == "fomc-roberta":
            kw = {"cache": cache}
        elif scorer == "ft":
            kw = {"model_dir": model_dir}
        try:
            sc = scorers.get_scorer(scorer, **kw)
        except Exception as e:  # missing extras, Ollama down, bad model dir
            raise _fail(f"cannot build scorer {scorer!r}: {type(e).__name__}: {e}") from e

        is_llm = scorer == "llm"
        variant = score_variant(masked, temperature if is_llm else 0.0, prompt if is_llm else "P1")
        stage = f"score:{scorer}" + (":masked" if masked else "")
        with Timer().stage(stage, n_docs=len(docs), quick=quick):
            df = score_documents(docs, sc, variant=variant, cap=cap)
    finally:
        cache.close()
    if out is None:
        suffix = ("-masked" if masked else "") + ("-quick" if quick else "")
        out = SCORES_DIR / f"{scorer}{suffix}.parquet"
    if out.exists():
        old = pl.read_parquet(out).join(df.select(SCORE_KEY), on=SCORE_KEY, how="anti")
        df = pl.concat([old.select(df.columns), df])
    out.parent.mkdir(parents=True, exist_ok=True)
    df.sort("bank", "date", "doc_id").write_parquet(out)
    mine = df.filter(pl.col("scorer_id") == sc.scorer_id, pl.col("variant") == variant)
    n_err = mine["error"].is_not_null().sum()
    typer.echo(f"scored {mine.height - n_err} of {len(docs)} documents, {n_err} errors -> {out}")
    for bank, n in mine.group_by("bank").len().sort("bank").iter_rows():
        typer.echo(f"  {bank}: {n}")


@app.command()
def events(
    banks: BanksArg = None,
    corpus: Annotated[Path, typer.Option(help="Snapshot directory.")] = CORPUS,
    markets_path: Annotated[Path, typer.Option("--markets", help="Daily markets.")] = MARKETS,
    out: Annotated[Path, typer.Option(help="Output parquet.")] = Path("results/events.parquet"),
) -> None:
    """Event timestamps plus signed [t-1, t+1] FX and 2y-yield moves for the primary documents."""
    import polars as pl

    from cbtone import corpus as corp
    from cbtone.events import engine

    names = banks or list(corp.HEADLINE)
    unknown = [b for b in names if b not in corp.PRIMARY]
    if unknown:
        raise _fail(f"unknown bank(s): {', '.join(unknown)}")
    if not (corpus / "documents.parquet").exists():
        raise _fail(f"no corpus at {corpus}")
    ev = engine.build_events(corp.select(corp.load_frame(corpus), names)).sort("bank", "date")
    if markets_path.exists():
        daily = pl.read_parquet(markets_path)
    else:
        typer.echo(f"warning: {markets_path} missing; market moves left null", err=True)
        daily = pl.DataFrame(schema={"date": pl.Date, "series": pl.String, "close": pl.Float64})
    for col, key in (("move_fx", "fx"), ("move_y2", "y2")):
        moves: list[float | None] = [None] * ev.height
        for bank in ev["bank"].unique():
            series = engine.BANK_SERIES.get(bank, {}).get(key)
            if series is None:
                continue
            idx = [i for i, b in enumerate(ev["bank"].to_list()) if b == bank]
            ts = [ev["event_ts_utc"][i] for i in idx]
            for i, m in zip(idx, engine.window_moves(daily, series, ts), strict=True):
                moves[i] = m
        ev = ev.with_columns(pl.Series(col, moves, dtype=pl.Float64))
    out.parent.mkdir(parents=True, exist_ok=True)
    ev.write_parquet(out)
    typer.echo(f"events: {ev.height} -> {out}")
    for bank, n, fx_n, y2_n in (
        ev.group_by("bank")
        .agg(pl.len(), pl.col("move_fx").count(), pl.col("move_y2").count())
        .sort("bank")
        .iter_rows()
    ):
        typer.echo(f"  {bank}: {n} events, {fx_n} with fx move, {y2_n} with y2 move")
    flags = ev.group_by("timing").len().sort("timing")
    typer.echo("timing: " + ", ".join(f"{t}={n}" for t, n in flags.iter_rows()))


@app.command()
def parse(
    bank: Annotated[str, typer.Argument(help="Bank whose adapter parses the file.")],
    file: Annotated[Path, typer.Option("--file", help="Saved raw file (cache or manual).")],
    url: Annotated[str, typer.Option(help="URL to record on the documents.")] = "file://local",
    hint: Annotated[list[str] | None, typer.Option(help="Adapter hint key=value.")] = None,
) -> None:
    """Parse one saved file with the bank's adapter (debugging aid for adapter authors)."""
    import hashlib

    if not file.exists():
        raise _fail(f"no such file: {file}")
    try:
        adapter = registry.make_adapter(bank, PoliteFetcher(offline=True))
    except Exception as e:
        raise _fail(f"{type(e).__name__}: {e}") from e
    hints = dict(h.split("=", 1) for h in hint or [] if "=" in h)
    content = file.read_bytes()
    ctype = "application/pdf" if file.suffix.lower() == ".pdf" else "text/html"
    raw = RawResponse(
        url, content, ctype, hashlib.sha256(content).hexdigest(), datetime.now(UTC), True
    )
    try:
        docs = adapter.parse(raw, hints)
    except Exception as e:
        typer.echo(f"parse failed: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"{len(docs)} document(s)")
    for d in docs:
        typer.echo(f"{d.doc_id}\n  title: {d.title}\n  {d.text[:300]!r}")


def _run_cmd(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True).stdout.strip()


def _ram_bytes() -> int:
    if sys.platform == "darwin":
        return int(_run_cmd("sysctl", "-n", "hw.memsize"))
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    raise OSError("RAM unknown")


def _pkg_version(name: str) -> dict[str, Any]:
    try:
        return {"ok": True, "version": metadata.version(name)}
    except metadata.PackageNotFoundError:
        return {"ok": False, "error": "not installed"}


def _probe_system() -> dict[str, Any]:
    info: dict[str, Any] = {"platform": platform.platform(), "machine": platform.machine()}
    if sys.platform == "darwin":
        info["macos"] = platform.mac_ver()[0]
        try:
            info["cpu"] = _run_cmd("sysctl", "-n", "machdep.cpu.brand_string")
        except Exception as e:
            info["cpu"] = None
            info["cpu_error"] = str(e)
    else:
        info["cpu"] = platform.processor() or None
    try:
        info["ram_gb"] = round(_ram_bytes() / 2**30, 1)
    except Exception as e:
        info["ram_gb"] = None
        info["ram_error"] = str(e)
    info["ok"] = info.get("cpu") is not None and info["ram_gb"] is not None
    return info


def _probe_software() -> dict[str, Any]:
    out: dict[str, Any] = {"python": {"ok": True, "version": platform.python_version()}}
    out["cbtone"] = {"ok": True, "version": __version__}
    for pkg in ("polars", "torch", "transformers"):
        out[pkg] = _pkg_version(pkg)
    if out["torch"]["ok"]:
        try:
            import torch

            out["mps"] = {"ok": True, "available": bool(torch.backends.mps.is_available())}
        except Exception as e:
            out["mps"] = {"ok": False, "error": str(e)}
    else:
        out["mps"] = {"ok": False, "error": "torch not installed"}
    return out


def _probe_ollama() -> dict[str, Any]:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        r.raise_for_status()
        models = [
            {"name": m.get("name"), "digest": m.get("digest")} for m in r.json().get("models", [])
        ]
        return {"ok": True, "url": OLLAMA_URL, "models": models}
    except Exception as e:
        return {"ok": False, "url": OLLAMA_URL, "error": f"{type(e).__name__}: {e}"}


def _probe_storage() -> dict[str, Any]:
    out: dict[str, Any] = {"disk_free_gb": round(shutil.disk_usage(".").free / 2**30, 1)}
    cache: dict[str, Any] = {"path": str(SCORE_CACHE)}
    if SCORE_CACHE.exists():
        cache["size_mb"] = round(SCORE_CACHE.stat().st_size / 2**20, 2)
        try:
            db = sqlite3.connect(f"file:{SCORE_CACHE}?mode=ro", uri=True, timeout=2)
            try:
                cache["rows"] = int(db.execute("SELECT COUNT(*) FROM scores").fetchone()[0])
            finally:
                db.close()
            cache["ok"] = True
        except Exception as e:
            cache.update(ok=False, error=f"{type(e).__name__}: {e}")
    else:
        cache.update(ok=False, error="missing")
    out["score_cache"] = cache
    version = CORPUS / "VERSION"
    out["corpus"] = (
        {"ok": True, "version": version.read_text().strip()}
        if version.exists()
        else {"ok": False, "error": f"{version} missing"}
    )
    return out


@app.command()
def doctor(
    json_out: Annotated[
        Path | None, typer.Option("--json", help="Also write the report as JSON.")
    ] = None,
) -> None:
    """Probe hardware, software, Ollama, caches and corpus; never fails hard."""
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "system": _probe_system(),
        "software": _probe_software(),
        "ollama": _probe_ollama(),
        "storage": _probe_storage(),
    }
    sysi, ol, st = report["system"], report["ollama"], report["storage"]
    typer.echo(f"platform: {sysi['platform']}  cpu: {sysi.get('cpu')}  ram: {sysi['ram_gb']} GB")
    for name, p in report["software"].items():
        typer.echo(f"{name}: {p.get('version', p.get('available', p.get('error')))}")
    if ol["ok"]:
        typer.echo(f"ollama: ok, {len(ol['models'])} models")
        for m in ol["models"]:
            typer.echo(f"  {m['name']}  {m['digest']}")
    else:
        typer.echo(f"ollama: missing ({ol['error']})")
    c = st["score_cache"]
    typer.echo(f"disk free: {st['disk_free_gb']} GB")
    typer.echo(
        f"score cache: {c['rows']} rows, {c['size_mb']} MB"
        if c.get("ok")
        else f"score cache: missing ({c.get('error')})"
    )
    corpus_p = st["corpus"]
    typer.echo(f"corpus: {corpus_p.get('version', 'missing')}")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2, default=str) + "\n")
        typer.echo(f"wrote {json_out}")


@app.command()
def schemas(
    out: Annotated[Path, typer.Option(help="Schema directory.")] = Path("schemas"),
) -> None:
    """Write JSON Schema files for Document, ToneScore, Decision and EventResult."""
    from pydantic import TypeAdapter

    from cbtone.decisions.schema import Decision
    from cbtone.events.engine import EventResult
    from cbtone.scorers.base import ToneScore

    out.mkdir(parents=True, exist_ok=True)
    built = {
        "Document": Document.model_json_schema(),
        "ToneScore": ToneScore.model_json_schema(),
        "Decision": Decision.model_json_schema(),
        "EventResult": TypeAdapter(EventResult).json_schema(),
    }
    for name, schema in built.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        typer.echo(f"wrote {path}")


if __name__ == "__main__":
    app()
