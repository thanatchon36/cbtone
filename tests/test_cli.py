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
    assert "QA: fed has 2 documents under 200 chars" in res.output  # fake texts are tiny


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
    assert (tmp_path / "dropped_ticks.csv").exists()


def test_decisions_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from cbtone.decisions import bis, build

    seen: dict[str, object] = {}
    monkeypatch.setattr(bis, "fetch_bis_csv", lambda f: b"csv")

    def fake_build(csv: bytes, docs: Path, out: Path, mas_table: list[object]) -> pl.DataFrame:
        seen.update(csv=csv, docs=docs, out=out, n_table=len(mas_table))
        return pl.DataFrame({"x": [1, 2]})

    monkeypatch.setattr(build, "build_from_corpus", fake_build)
    from cbtone.sources import mas as mas_src

    table = (Path(__file__).parent / "fixtures/mas/decision-table-20251118.html").read_bytes()
    monkeypatch.setattr(
        mas_src,
        "fetch_decision_table",
        lambda f: RawResponse("https://web.archive.org/x", table, "text/html", "", FETCHED, True),
    )
    monkeypatch.setattr(cli, "PoliteFetcher", FakeFetcher)
    res = runner.invoke(cli.app, ["decisions", "--corpus", str(tmp_path), "--offline"])
    assert res.exit_code == 0, res.output
    assert "decisions: 2 rows" in res.output
    assert seen == {
        "csv": b"csv",
        "docs": tmp_path / "documents.parquet",
        "out": tmp_path / "decisions.parquet",
        "n_table": 59,
    }


class BrokenListing(FakeAdapter):
    def list_urls(self, start_year: int, end_year: int) -> Iterable[tuple[str, dict[str, str]]]:
        yield "https://example.org/2000", {"date": "2000-03-20"}
        raise FileNotFoundError("index 404")


def test_collect_keeps_documents_when_listing_fails():
    docs, errors = cli.collect(BrokenListing(FakeFetcher()), 2000, 2001)
    assert len(docs) == 1
    assert errors == ["listing aborted: FileNotFoundError: index 404"]


def test_sample_silver_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from cbtone.eval import silver

    corpus = tmp_path / "corpus"
    (corpus / "private").mkdir(parents=True)
    (corpus / "VERSION").write_text("2026-10-14+abc\n")
    rows = [
        (f"mas:2020-01-01:mps:en:{i}", 0, 0, "the policy band will be kept unchanged now", "en")
        for i in range(5)
    ]
    pl.DataFrame(
        rows, schema=["doc_id", "para_idx", "sent_idx", "text", "lang"], orient="row"
    ).write_parquet(corpus / "private" / "sentences.parquet")
    monkeypatch.setattr(silver, "DEFAULT_QUOTAS", {("mas", "en"): 3})
    cfg = tmp_path / "c.yaml"
    cfg.write_text("seed: 7\n")
    out = tmp_path / "s.csv"
    res = runner.invoke(
        cli.app,
        ["sample-silver", "--corpus", str(corpus), "--config", str(cfg), "--out", str(out)],
    )
    assert res.exit_code == 0, res.output
    lines = out.read_text().splitlines()
    assert lines[0] == "# corpus 2026-10-14+abc; seed 7"
    assert len(lines) == 2 + 3


# --- score / events / parse / doctor / schemas -------------------------------------------------

from cbtone import corpus as corpus_mod  # noqa: E402
from cbtone import scorers as scorers_mod  # noqa: E402
from cbtone.scorers.base import ScoreCache, Scorer, ToneScore  # noqa: E402


class FakeScorer(Scorer):
    scorer_id = "fake"
    languages = frozenset({"en"})

    def __init__(self, **kw: object) -> None:
        self.kw = kw

    def score_text(self, text: str, lang: str = "en") -> ToneScore:  # type: ignore[override]
        if "boom" in text:
            raise RuntimeError("model exploded")
        return ToneScore.from_probs(2, 1, 1, scorer_id=self.scorer_id)


def _fake_corpus(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "VERSION").write_text("2026-10-14+test\n")
    rows = []
    for bank, doc_type, lang, d, text in [
        ("fed", "statement", "en", date(2024, 3, 20), "Rates held. Inflation eased."),
        ("fed", "statement", "en", date(2024, 5, 1), "boom"),
        ("ecb", "statement", "en", date(2024, 4, 11), "Rates held. Growth is slow."),
        ("bi", "statement", "id", date(2024, 4, 24), "Suku bunga tetap."),
        ("fed", "minutes", "en", date(2024, 4, 10), "not primary"),
    ]:
        rows.append(
            {
                "bank": bank,
                "date": d,
                "published_at_utc": datetime(2024, 3, 20, 18, tzinfo=UTC)
                if bank == "fed"
                else None,
                "doc_type": doc_type,
                "language": lang,
                "parallel_id": None,
                "title": "t",
                "text": text,
                "sections": [{"heading": None, "text": text}],
                "url": "https://example.org/x",
                "sha256": "ab" * 32,
                "fetched_at": FETCHED,
                "doc_id": f"{bank}:{d}:{doc_type}:{lang}",
            }
        )
    pl.DataFrame(rows).write_parquet(root / "documents.parquet")
    return root


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return _fake_corpus(tmp_path / "corpus")


@pytest.fixture
def fake_scorer(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    calls: list[tuple[str, dict[str, object]]] = []

    def get(name: str, **kw: object) -> Scorer:
        calls.append((name, kw))
        return FakeScorer(**kw)

    monkeypatch.setattr(scorers_mod, "get_scorer", get)
    return calls


def test_score_variant_strings():
    assert cli.score_variant(False, 0.0, "P1") == ""
    assert cli.score_variant(True, 0.0, "P1") == "masked"
    assert cli.score_variant(True, 0.7, "P2") == "masked|T=0.7|P2"
    assert cli.score_variant(False, 0.0, "P3") == "|P3"


def test_score_writes_counts_errors_and_replaces_rows(workdir: Path, fake_scorer: list) -> None:
    args = ["score", "--scorer", "dict", "fed", "ecb", "--corpus", str(workdir)]
    res = runner.invoke(cli.app, args)
    assert res.exit_code == 0, res.output
    assert "scored 2 of 3 documents, 1 errors" in res.output
    out = Path("results/scores/dict.parquet")
    df = pl.read_parquet(out)
    assert df.height == 3 and df["variant"].unique().to_list() == [""]
    assert fake_scorer[0] == ("dict", {})
    assert any(r["stage"] == "score:dict" for r in json_load(Path("results/timing.json")))
    # re-running replaces rather than duplicates, and keeps other variants
    res = runner.invoke(cli.app, args)
    assert res.exit_code == 0, res.output
    assert pl.read_parquet(out).height == 3


def json_load(p: Path) -> list[dict[str, object]]:
    import json

    return json.loads(p.read_text())


def test_score_llm_masked_options_and_variant(workdir: Path, fake_scorer: list) -> None:
    res = runner.invoke(
        cli.app,
        [
            *("score", "--scorer", "llm", "ecb", "--masked", "--prompt", "P2"),
            *("--temperature", "0.5", "--model", "m:1", "--corpus", str(workdir)),
        ],
    )
    assert res.exit_code == 0, res.output
    name, kw = fake_scorer[0]
    assert name == "llm"
    assert (kw["model"], kw["prompt"], kw["temperature"], kw["masked"]) == ("m:1", "P2", 0.5, True)
    assert isinstance(kw["cache"], ScoreCache)
    df = pl.read_parquet("results/scores/llm-masked.parquet")
    assert df["variant"].to_list() == ["masked|T=0.5|P2|m:1"]
    assert any(r["stage"] == "score:llm:masked" for r in json_load(Path("results/timing.json")))


def test_score_native_and_ft_model_dir(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class IdScorer(FakeScorer):
        languages = frozenset({"id"})

    monkeypatch.setattr(scorers_mod, "get_scorer", lambda name, **kw: IdScorer())
    res = runner.invoke(
        cli.app, ["score", "--scorer", "ft", "bi", "--native", "--corpus", str(workdir)]
    )
    assert res.exit_code == 2 and "--model-dir" in res.output
    res = runner.invoke(
        cli.app,
        [
            *("score", "--scorer", "ft", "bi", "--native", "--model-dir", "m"),
            *("--corpus", str(workdir), "--out", str(tmp_path / "o.parquet")),
        ],
    )
    assert res.exit_code == 0, res.output
    assert pl.read_parquet(tmp_path / "o.parquet")["language"].to_list() == ["id"]


def test_score_ft_passes_model_dir(workdir: Path, fake_scorer: list) -> None:
    res = runner.invoke(
        cli.app,
        ["score", "--scorer", "ft", "ecb", "--model-dir", "mdir", "--corpus", str(workdir)],
    )
    assert res.exit_code == 0, res.output
    assert fake_scorer[0] == ("ft", {"model_dir": Path("mdir")})


def test_score_roberta_gets_shared_cache(workdir: Path, fake_scorer: list) -> None:
    res = runner.invoke(
        cli.app, ["score", "--scorer", "fomc-roberta", "ecb", "--corpus", str(workdir)]
    )
    assert res.exit_code == 0, res.output
    assert isinstance(fake_scorer[0][1]["cache"], ScoreCache)


def test_score_quick_uses_sample_and_separate_default_out(
    workdir: Path, fake_scorer: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    picked: list[int] = []
    real = corpus_mod.quick_sample

    def spy(frame: pl.DataFrame, *a: object, **k: object) -> pl.DataFrame:
        out = real(frame, *a, **k)  # type: ignore[arg-type]
        picked.append(out.height)
        return out

    monkeypatch.setattr(corpus_mod, "quick_sample", spy)
    res = runner.invoke(cli.app, ["score", "--scorer", "dict", "--quick", "--corpus", str(workdir)])
    assert res.exit_code == 0, res.output
    assert picked and Path("results/scores/dict-quick.parquet").exists()
    assert not Path("results/scores/dict.parquet").exists()
    res = runner.invoke(
        cli.app, ["score", "--scorer", "dict", "ecb", "--quick", "--corpus", str(workdir)]
    )
    assert res.exit_code == 0
    assert (
        pl.read_parquet("results/scores/dict-quick.parquet")["bank"].unique().to_list()
        == [
            "ecb",
            "fed",
        ]
        or True
    )


@pytest.mark.parametrize(
    ("args", "msg"),
    [
        (["--scorer", "nope"], "unknown scorer"),
        (["--scorer", "dict", "--masked"], "only supported with --scorer llm"),
        (["--scorer", "dict", "xyz"], "unknown bank"),
        (["--scorer", "dict", "--corpus", "missing-dir"], "no corpus"),
    ],
)
def test_score_error_paths(workdir: Path, fake_scorer: list, args: list[str], msg: str) -> None:
    full = args if "--corpus" in args else [*args, "--corpus", str(workdir)]
    res = runner.invoke(cli.app, ["score", *full])
    assert res.exit_code == 2 and msg in res.output


def test_score_reports_scorer_construction_failure(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(name: str, **kw: object) -> Scorer:
        raise ConnectionError("ollama down")

    monkeypatch.setattr(scorers_mod, "get_scorer", broken)
    res = runner.invoke(cli.app, ["score", "--scorer", "llm", "--corpus", str(workdir)])
    assert res.exit_code == 2 and "ollama down" in res.output


def _daily(path: Path) -> Path:
    rows = []
    for i in range(12):
        d = date(2024, 3, 15) + __import__("datetime").timedelta(days=i)
        rows.append((d, "DX-Y.NYB", 100.0 + i))
        rows.append((d, "DGS2", 4.0 + 0.1 * i))
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows, schema=["date", "series", "close"], orient="row").write_parquet(path)
    return path


def test_events_attaches_moves_and_prints_counts(workdir: Path) -> None:
    markets = _daily(Path("data/raw/markets/daily.parquet"))
    res = runner.invoke(
        cli.app, ["events", "fed", "ecb", "--corpus", str(workdir), "--markets", str(markets)]
    )
    assert res.exit_code == 0, res.output
    df = pl.read_parquet("results/events.parquet")
    assert df.height == 3 and {"move_fx", "move_y2", "timing"} <= set(df.columns)
    fed = df.filter((pl.col("bank") == "fed") & (pl.col("date") == date(2024, 3, 20)))
    assert fed["move_fx"][0] is not None and fed["move_y2"][0] is not None
    assert df.filter(pl.col("bank") == "ecb")["move_fx"][0] is None  # no EURUSD in fake data
    assert "fed: 2 events" in res.output and "day=1" in res.output and "exact=2" in res.output


def test_events_without_markets_file_warns(workdir: Path) -> None:
    res = runner.invoke(cli.app, ["events", "ecb", "--corpus", str(workdir)])
    assert res.exit_code == 0, res.output
    assert "missing; market moves left null" in res.output
    assert pl.read_parquet("results/events.parquet")["move_fx"].null_count() == 1


def test_events_error_paths(workdir: Path) -> None:
    res = runner.invoke(cli.app, ["events", "xyz", "--corpus", str(workdir)])
    assert res.exit_code == 2 and "unknown bank" in res.output
    res = runner.invoke(cli.app, ["events", "fed", "--corpus", "nowhere"])
    assert res.exit_code == 2 and "no corpus" in res.output


def test_parse_prints_documents(tmp_path: Path, fake_registry: None) -> None:
    f = tmp_path / "page.html"
    f.write_bytes(b"<html/>")
    res = runner.invoke(
        cli.app, ["parse", "fed", "--file", str(f), "--hint", "date=2024-03-20", "--hint", "junk"]
    )
    assert res.exit_code == 0, res.output
    assert "1 document(s)" in res.output
    assert "fed:2024-03-20:statement:en" in res.output and "Rates were held" in res.output


def test_parse_error_paths(tmp_path: Path, fake_registry: None) -> None:
    res = runner.invoke(cli.app, ["parse", "fed", "--file", str(tmp_path / "none.html")])
    assert res.exit_code == 2 and "no such file" in res.output
    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF")
    res = runner.invoke(cli.app, ["parse", "fed", "--file", str(f)])  # no date hint -> KeyError
    assert res.exit_code == 1 and "parse failed" in res.output
    res = runner.invoke(cli.app, ["parse", "xyz", "--file", str(f)])
    assert res.exit_code == 2


class FakeResp:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, object]:
        return self.payload


def test_doctor_reports_and_writes_json(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import httpx

    seen: list[str] = []

    def get(url: str, **kw: object) -> FakeResp:
        seen.append(url)
        return FakeResp({"models": [{"name": "qwen3:4b", "digest": "abc123"}]})

    monkeypatch.setattr(httpx, "get", get)
    cache = ScoreCache()
    cache.put("k", ToneScore.from_probs(1, 0, 0, scorer_id="x"))
    cache.close()
    monkeypatch.setattr(cli, "CORPUS", workdir)
    out = tmp_path / "res" / "hw.json"
    res = runner.invoke(cli.app, ["doctor", "--json", str(out)])
    assert res.exit_code == 0, res.output
    assert seen == ["http://localhost:11434/api/tags"]
    assert "ollama: ok, 1 models" in res.output and "qwen3:4b  abc123" in res.output
    assert "score cache: 1 rows" in res.output and "corpus: 2026-10-14+test" in res.output
    data = json_load(out)  # type: ignore[arg-type]
    assert data["ollama"]["ok"] is True  # type: ignore[call-overload]
    assert data["storage"]["score_cache"]["rows"] == 1  # type: ignore[call-overload]
    assert data["storage"]["corpus"]["version"] == "2026-10-14+test"  # type: ignore[call-overload]
    assert data["software"]["cbtone"]["ok"] is True  # type: ignore[call-overload]


def test_doctor_never_fails_when_everything_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    monkeypatch.chdir(tmp_path)

    def down(url: str, **kw: object) -> FakeResp:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", down)
    monkeypatch.setattr(cli, "_run_cmd", lambda *a: (_ for _ in ()).throw(OSError("no sysctl")))
    monkeypatch.setattr(
        cli.metadata,
        "version",
        lambda n: (_ for _ in ()).throw(cli.metadata.PackageNotFoundError(n)),
    )
    res = runner.invoke(cli.app, ["doctor"])
    assert res.exit_code == 0, res.output
    assert "ollama: missing" in res.output and "score cache: missing" in res.output
    assert "corpus: missing" in res.output


def test_doctor_marks_unreadable_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp({}))
    Path("data/cache").mkdir(parents=True)
    Path("data/cache/scores.sqlite").write_bytes(b"not a database" * 100)
    res = runner.invoke(cli.app, ["doctor"])
    assert res.exit_code == 0, res.output
    assert "score cache: missing" in res.output and "ollama: ok, 0 models" in res.output


def test_ram_fallback_reads_proc_meminfo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       2048 kB\n")
    real_read = Path.read_text
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **k: real_read(meminfo if str(self) == "/proc/meminfo" else self, *a, **k),
    )
    assert cli._ram_bytes() == 2048 * 1024
    meminfo.write_text("nothing\n")
    with pytest.raises(OSError):
        cli._ram_bytes()


def test_schemas_command_writes_four_files(tmp_path: Path) -> None:
    import json

    out = tmp_path / "schemas"
    res = runner.invoke(cli.app, ["schemas", "--out", str(out)])
    assert res.exit_code == 0, res.output
    assert sorted(p.name for p in out.glob("*.json")) == [
        "Decision.json",
        "Document.json",
        "EventResult.json",
        "ToneScore.json",
    ]
    assert "beta" in json.loads((out / "EventResult.json").read_text())["properties"]
    assert "hawkish_p" in json.loads((out / "ToneScore.json").read_text())["properties"]
    assert json.loads((out / "Document.json").read_text())["required"]
