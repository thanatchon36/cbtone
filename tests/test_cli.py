from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from cbtone import cli
from cbtone.schema import Document
from cbtone.sources import registry
from cbtone.sources.base import BlockedError, PoliteFetcher, RawResponse, SourceAdapter
from cbtone.sources.ecb import EcbAdapter

runner = CliRunner()
FETCHED = datetime(2026, 1, 2, tzinfo=UTC)


def _raw(url: str) -> RawResponse:
    return RawResponse(url, b"x", "text/html", "ab" * 32, FETCHED, from_cache=True)


class FakeFetcher(PoliteFetcher):
    def __init__(self, bad: set[str] = frozenset(), **_: object) -> None:  # type: ignore[assignment]
        self.bad = bad

    def get(self, bank: str, url: str) -> RawResponse:
        if url in self.bad:
            raise FileNotFoundError(url)
        return _raw(url)


class FakeAdapter(SourceAdapter):
    bank = "fed"

    def list_urls(self, start_year: int, end_year: int) -> Iterable[tuple[str, dict[str, str]]]:
        for y in range(start_year, end_year + 1):
            yield f"https://example.org/{y}", {"date": f"{y}-03-20"}

    def parse(self, raw: RawResponse, hints: dict[str, str]) -> list[Document]:
        return [
            Document.model_validate(
                {
                    "bank": "fed",
                    "date": hints["date"],
                    "doc_type": "statement",
                    "language": "en",
                    "title": "t",
                    "text": "Rates were held. Inflation eased.",
                    "url": raw.url,
                    "sha256": raw.sha256,
                    "fetched_at": raw.fetched_at,
                }
            )
        ]


class ManualAdapter(FakeAdapter):
    bank = "mas"

    def fetch(self, start_year: int, end_year: int) -> Iterator[Document]:
        raise BlockedError("no manual files")


def test_adapter_class_resolves_by_bank():
    assert registry.adapter_class("ecb") is EcbAdapter


def test_adapter_class_unknown_bank():
    with pytest.raises(ValueError, match="unknown bank"):
        registry.adapter_class("xyz")


def test_redistributable_map_is_fail_closed_for_mas_and_ecb_press_conferences():
    flags = registry.REDISTRIBUTABLE
    assert flags[("ecb", "press_conference")] is False
    assert flags["mas"] is False
    assert "pboc" not in flags or flags["pboc"] is False


def test_collect_skips_failed_urls_and_reports_them():
    adapter = FakeAdapter(FakeFetcher(bad={"https://example.org/2001"}))
    docs, errors = cli.collect(adapter, 2000, 2002)
    assert [d.date for d in docs] == [date(2000, 3, 20), date(2002, 3, 20)]
    assert len(errors) == 1 and "2001" in errors[0]


def test_collect_uses_overridden_fetch_and_reports_block():
    docs, errors = cli.collect(ManualAdapter(FakeFetcher()), 2000, 2001)
    assert docs == [] and "no manual files" in errors[0]


def test_default_banks_follow_config(tmp_path: Path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("include_bot: false\nbanks: [fed, ecb]\n")
    assert cli.banks_from_config(cfg) == ["fed", "ecb"]
    cfg.write_text("include_bot: true\nbanks: [fed]\n")
    assert cli.banks_from_config(cfg) == ["fed", "bot"]


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch):
    classes = {"fed": FakeAdapter, "mas": ManualAdapter}
    monkeypatch.setattr(registry, "adapter_class", lambda b: classes[b])
    monkeypatch.setattr(cli, "PoliteFetcher", FakeFetcher)


def test_fetch_command_reports_counts_and_exit_code(fake_registry: None):
    res = runner.invoke(cli.app, ["fetch", "fed", "--start", "2000", "--end", "2001"])
    assert res.exit_code == 0, res.output
    assert "fed: 2 documents, 0 errors" in res.output
    res = runner.invoke(cli.app, ["fetch", "fed", "mas", "--start", "2000", "--end", "2000"])
    assert res.exit_code == 1
    assert "mas: 0 documents, 1 errors" in res.output


def test_snapshot_command_writes_corpus(fake_registry: None, tmp_path: Path):
    out = tmp_path / "corpus"
    res = runner.invoke(
        cli.app, ["snapshot", "fed", "--start", "2000", "--end", "2001", "--out", str(out)]
    )
    assert res.exit_code == 0, res.output
    m = pl.read_parquet(out / "manifest.parquet")
    assert m.height == 2
    assert (out / "VERSION").exists()


def test_version():
    res = runner.invoke(cli.app, ["version"])
    assert res.exit_code == 0 and res.output.strip()


def test_markets_command_concatenates_fx_and_yields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from cbtone.markets import fx, yields

    def frame(series: str) -> pl.DataFrame:
        return pl.DataFrame(
            {"date": [date(2020, 1, 2)], "series": [series], "close": [1.0]},
            schema=fx.empty_frame().schema,
        )

    monkeypatch.setattr(fx, "fetch_fx", lambda tickers, a, b: frame("USDSGD=X"))
    monkeypatch.setattr(yields, "fetch_all_yields", lambda a, b, f: frame("US2Y"))
    monkeypatch.setattr(cli, "PoliteFetcher", FakeFetcher)
    out = tmp_path / "m.parquet"
    res = runner.invoke(cli.app, ["markets", "--start", "2020", "--end", "2020", "--out", str(out)])
    assert res.exit_code == 0, res.output
    assert sorted(pl.read_parquet(out)["series"]) == ["US2Y", "USDSGD=X"]


def test_decisions_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from cbtone.decisions import bis, build

    seen: dict[str, object] = {}
    monkeypatch.setattr(bis, "fetch_bis_csv", lambda f: b"csv")

    def fake_build(csv: bytes, docs: Path, out: Path) -> pl.DataFrame:
        seen.update(csv=csv, docs=docs, out=out)
        return pl.DataFrame({"x": [1, 2]})

    monkeypatch.setattr(build, "build_from_corpus", fake_build)
    monkeypatch.setattr(cli, "PoliteFetcher", FakeFetcher)
    res = runner.invoke(cli.app, ["decisions", "--corpus", str(tmp_path), "--offline"])
    assert res.exit_code == 0, res.output
    assert "decisions: 2 rows" in res.output
    assert seen == {
        "csv": b"csv",
        "docs": tmp_path / "documents.parquet",
        "out": tmp_path / "decisions.parquet",
    }
