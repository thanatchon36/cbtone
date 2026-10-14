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
    }
    text = "F1 {{rq4.rows[scorer=llm].f1|.2f}} {{v}} {{share|pct}} {{none}}"
    assert build.fill(text, data) == "F1 0.61 refuted 25% n/a"


def test_missing_key_fails():
    with pytest.raises(SystemExit, match="missing summary keys"):
        build.fill("{{nope.x}}", {})
