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


def test_heading_numbering_skips_abstract_and_references():
    md = "## Abstract\n\n## Intro\n\n### Sub\n\n### Sub2\n\n## Data\n\n### Sub\n\n## References\n"
    out = build.number_headings(md)
    assert "## Abstract" in out and "## References" in out
    assert "## 1 Intro" in out and "### 1.1 Sub" in out and "### 1.2 Sub2" in out
    assert "## 2 Data" in out and "### 2.1 Sub" in out
