"""Build the paper from paper/paper.md and results/summary.json.

Outputs:
  paper/paper.filled.md   placeholders resolved (git-ignored; what pandoc reads)
  paper/paper.pdf         pandoc → typst, numeric citations (paper/csl/ieee.csl)
  docs/site/paper.md      web version for the documentation site: the same text with numbered
                          sections and captions, citations resolved to [n] links and the reference
                          list appended; the SVG figures are copied to docs/site/figures/

Placeholders: ``{{dotted.path}}`` or ``{{dotted.path|fmt}}``. ``fmt`` is a Python format spec
(e.g. ``.2f``, ``d``, ``,``), ``pct`` / ``pct1`` for a percentage, ``yn`` for yes/no, or ``min`` for
seconds rendered as whole minutes. List elements are addressed by one or more ``key=value``
selectors, e.g. ``{{rq4.rq4b.rows[scorer=llm].macro_f1}}`` or
``{{rq1.rows[bank=ecb,scorer=llm].auroc}}``. A missing key fails the build; no number in the paper
is typed by hand (MISSION §5).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "paper" / "paper.md"
OUT_MD = ROOT / "paper" / "paper.filled.md"
OUT_PDF = ROOT / "paper" / "paper.pdf"
OUT_WEB = ROOT / "docs" / "site" / "paper.md"
WEB_FIGURES = ROOT / "docs" / "site" / "figures"
FIGURES = ROOT / "results" / "figures"
TEMPLATE = ROOT / "paper" / "templates" / "default.typst"
REPO = "https://github.com/thanatchon36/cbtone/blob/main"

TOKEN = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}")
STEP = re.compile(r"([^.\[]+)(?:\[([^\]]+)\])?")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
IMAGE = re.compile(r"^(!\[)(.*?)(\]\(.*?\)(?:\{[^}]*\})?)[ \t]*$", re.MULTILINE)
TABLE = re.compile(r"((?:^\|.*\n)+)\n(: (?:.+\n)+)", re.MULTILINE)
HEADING = re.compile(r"^(#{2,3}) (.+?)\s*$", re.MULTILINE)
UNNUMBERED = {"abstract", "references"}


def lookup(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        m = STEP.fullmatch(part)
        if m is None:
            raise KeyError(path)
        key, sel = m.groups()
        cur = cur[key]
        if sel is not None:
            conds = [c.split("=", 1) for c in sel.split(",")]
            matches = [x for x in cur if all(str(x.get(k)) == v for k, v in conds)]
            if len(matches) != 1:
                raise KeyError(f"{path}: {len(matches)} rows match [{sel}]")
            cur = matches[0]
    return cur


def fmt(value: Any, spec: str | None) -> str:
    if value is None:
        return "n/a"
    if spec == "pct":
        return f"{100 * float(value):.0f}%"
    if spec == "pct1":
        return f"{100 * float(value):.1f}%"
    if spec == "yn":
        return "yes" if value else "no"
    if spec == "min":
        return f"{float(value) / 60:.0f}"
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


def front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown document into its YAML metadata and body."""
    m = FRONT.match(text)
    if m is None:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end() :]


def number_captions(body: str) -> str:
    """Prefix figure and table captions with "Figure n." / "Table n." in order of appearance.

    Typst numbers them itself in the PDF; the web page needs the numbers in the text. Table captions
    (pandoc ``: caption`` blocks after the table) are moved above the table, as in the PDF.
    """
    fig = iter(range(1, 1000))
    tab = iter(range(1, 1000))
    body = IMAGE.sub(lambda m: f"{m.group(1)}Figure {next(fig)}. {m.group(2)}{m.group(3)}", body)

    def table(m: re.Match[str]) -> str:
        caption = " ".join(line.removeprefix(": ").strip() for line in m.group(2).splitlines())
        return f"**Table {next(tab)}.** {caption}\n\n{m.group(1)}"

    return TABLE.sub(table, body)


def number_headings(md: str) -> str:
    """Number ``##`` / ``###`` headings 1, 1.1, ... (web page; the PDF is numbered by typst)."""
    counters = [0, 0]

    def sub(m: re.Match[str]) -> str:
        hashes, title = m.groups()
        if title.strip().lower() in UNNUMBERED:
            return m.group(0)
        level = len(hashes) - 2
        counters[level] += 1
        if level == 0:
            counters[1] = 0
        label = ".".join(str(c) for c in counters[: level + 1])
        return f"{hashes} {label} {title}"

    return HEADING.sub(sub, md)


def pandoc(args: list[str], stdin: str | None = None) -> str:
    return subprocess.run(
        ["pandoc", *args], input=stdin, text=True, check=True, capture_output=True, cwd=ROOT
    ).stdout


def web_page(filled: str) -> str:
    meta, body = front_matter(filled)
    body = number_captions(body).replace("results/figures/", "figures/")
    cite_meta = {k: meta[k] for k in ("bibliography", "csl", "link-citations") if k in meta}
    html_md = pandoc(
        [
            "--from",
            "markdown",
            "--to",
            "gfm",
            "--citeproc",
            "--wrap=none",
            "--shift-heading-level-by=1",
            "--resource-path",
            str(ROOT),
        ],
        stdin=f"---\n{yaml.safe_dump(cite_meta)}---\n{body}",
    )
    head = (
        f"# {meta.get('title', 'Paper')}\n\n"
        f"*{meta.get('author', '')}* · {meta.get('date', '')} · "
        f"[PDF]({REPO}/paper/paper.pdf) · [Markdown source]({REPO}/paper/paper.md) · "
        f"[`results/summary.json`]({REPO}/results/summary.json)\n\n"
        '!!! info "About this page"\n'
        "    Generated by `make paper` from `paper/paper.md`. Every number is injected from\n"
        "    `results/summary.json`; citations are numbered in order of first appearance\n"
        "    (IEEE style) and link to the reference list at the end. The typeset version is\n"
        "    the PDF.\n\n"
        f"## Abstract\n\n{str(meta.get('abstract', '')).strip()}\n\n"
    )
    return head + number_headings(html_md)


def main() -> int:
    data = json.loads((ROOT / "results" / "summary.json").read_text())
    filled = fill(SRC.read_text(), data)
    OUT_MD.write_text(filled)
    if shutil.which("pandoc") is None:
        print("pandoc not found; wrote", OUT_MD)
        return 0
    cmd = [str(OUT_MD), "-o", str(OUT_PDF), "--resource-path", str(ROOT), "--citeproc"]
    if shutil.which("typst"):
        # Vendored pandoc template: fixes a show rule that deletes links (citations, DOIs).
        cmd += ["--pdf-engine", "typst", "--template", str(TEMPLATE)]
    pandoc(cmd)
    print("wrote", OUT_PDF)
    WEB_FIGURES.mkdir(parents=True, exist_ok=True)
    for svg in sorted(FIGURES.glob("*.svg")):
        shutil.copyfile(svg, WEB_FIGURES / svg.name)
    OUT_WEB.write_text(web_page(filled))
    print("wrote", OUT_WEB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
