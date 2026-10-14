import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("paper_build", Path("paper/build.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_fill_paths_selectors_and_formats():
    data = {
        "rq4": {"rows": [{"scorer": "llm", "f1": 0.6123}, {"scorer": "dict", "f1": 0.41}]},
        "v": "refuted",
        "share": 0.25,
        "none": None,
        "secs": 4279.98,
        "n": 1179,
    }
    text = "F1 {{rq4.rows[scorer=llm].f1|.2f}} {{v}} {{share|pct}} {{none}} {{secs|min}} {{n|,}}"
    assert build.fill(text, data) == "F1 0.61 refuted 25% n/a 71 1,179"


def test_missing_key_fails():
    with pytest.raises(SystemExit, match="missing summary keys"):
        build.fill("{{nope.x}}", {})


def test_compound_selector_and_ambiguity():
    data = {
        "rows": [
            {"bank": "ecb", "scorer": "llm", "x": 0.0581},
            {"bank": "ecb", "scorer": "dict", "x": 0.007},
            {"bank": "fed", "scorer": "llm", "x": -0.005},
        ]
    }
    assert build.fill("{{rows[bank=ecb,scorer=llm].x|pct1}}", data) == "5.8%"
    with pytest.raises(SystemExit, match="2 rows match"):
        build.fill("{{rows[bank=ecb].x}}", data)


def test_front_matter_and_caption_numbering():
    doc = (
        "---\ntitle: T\nabstract: |\n  Two lines\n  here.\n---\n"
        "# Intro\n\n![First](results/figures/a.svg){width=100%}\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n: A caption that\nwraps.\n\n"
        "![Second](results/figures/b.svg)\n"
    )
    meta, body = build.front_matter(doc)
    assert meta["title"] == "T" and meta["abstract"].startswith("Two lines")
    out = build.number_captions(body)
    assert "![Figure 1. First](results/figures/a.svg){width=100%}" in out
    assert "![Figure 2. Second](results/figures/b.svg)" in out
    assert "**Table 1.** A caption that wraps.\n\n| a | b |" in out
    assert ": A caption" not in out


def test_results_strip_reads_every_verdict_from_summary():
    import json

    data = json.loads(Path("results/summary.json").read_text())
    rows = build.results(data)
    assert [r[0] for r in rows] == ["H1", "H2a", "H2b", "H3", "H4a", "H4b", "H4c", "H5"]
    assert all(k in build.TAGS for _, k, _, _ in rows)


def test_citations_match_the_paper_everywhere():
    import yaml

    title = yaml.safe_load(build.FRONT.match(Path("paper/paper.md").read_text()).group(1))["title"]
    version = yaml.safe_load(Path("CITATION.cff").read_text())["version"]
    paper_bib, software_bib = build.citations(title, version)
    for f in ["README.md", "experiments/hf_cards/model.md", "experiments/hf_cards/dataset.md"]:
        text = Path(f).read_text()
        assert paper_bib in text, f
        assert software_bib in text, f
    cff = yaml.safe_load(Path("CITATION.cff").read_text())
    assert cff["preferred-citation"]["title"] == title
    assert cff["preferred-citation"]["url"] == build.PAPER_URL
    assert cff["doi"] == build.ZENODO_DOI
