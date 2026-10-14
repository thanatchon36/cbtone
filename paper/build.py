"""Build paper/paper.pdf: inject numbers from results/summary.json into paper/paper.md.

Placeholders: ``{{dotted.path}}`` or ``{{dotted.path|fmt}}`` (``fmt`` = a Python format spec, e.g.
``.2f``, or ``pct`` for a percentage). List elements are addressed by a ``key=value`` selector,
e.g. ``{{rq4.rq4b.rows[scorer=llm].macro_f1|.2f}}``. A missing key fails the build; no number in
the paper is typed by hand (MISSION §5).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "paper" / "paper.md"
OUT_MD = ROOT / "paper" / "paper.filled.md"
OUT_PDF = ROOT / "paper" / "paper.pdf"
TOKEN = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}")
STEP = re.compile(r"([^.\[]+)(?:\[([^=\]]+)=([^\]]+)\])?")


def lookup(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        m = STEP.fullmatch(part)
        if m is None:
            raise KeyError(path)
        key, sel_k, sel_v = m.groups()
        cur = cur[key]
        if sel_k is not None:
            matches = [x for x in cur if str(x.get(sel_k)) == sel_v]
            if len(matches) != 1:
                raise KeyError(f"{path}: {len(matches)} rows match {sel_k}={sel_v}")
            cur = matches[0]
    return cur


def fmt(value: Any, spec: str | None) -> str:
    if value is None:
        return "n/a"
    if spec == "pct":
        return f"{100 * float(value):.0f}%"
    if spec:
        return format(value, spec)
    return str(value)


def fill(text: str, data: Any) -> str:
    missing: list[str] = []

    def sub(m: re.Match[str]) -> str:
        try:
            return fmt(lookup(data, m.group(1)), m.group(2))
        except (KeyError, IndexError, TypeError) as e:
            missing.append(f"{m.group(1)} ({e})")
            return "??"

    out = TOKEN.sub(sub, text)
    if missing:
        raise SystemExit("missing summary keys:\n  " + "\n  ".join(missing))
    return out


def main() -> int:
    data = json.loads((ROOT / "results" / "summary.json").read_text())
    OUT_MD.write_text(fill(SRC.read_text(), data))
    if shutil.which("pandoc") is None:
        print("pandoc not found; wrote", OUT_MD)
        return 0
    engine = "typst" if shutil.which("typst") else None
    cmd = ["pandoc", str(OUT_MD), "-o", str(OUT_PDF), "--resource-path", str(ROOT), "--citeproc"]
    if engine:
        cmd += ["--pdf-engine", engine]
    subprocess.run(cmd, check=True, cwd=ROOT)
    print("wrote", OUT_PDF)
    return 0


if __name__ == "__main__":
    sys.exit(main())
