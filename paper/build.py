"""Build the paper from paper/paper.md and results/summary.json.

Outputs:
  paper/paper.filled.md   placeholders resolved (git-ignored; what pandoc reads)
  paper/paper.pdf         pandoc → typst, numeric citations (paper/csl/ieee.csl)
  docs/site/paper/        web reader (index.html), a standalone page built by pandoc with
                          paper/reader.html: masthead, results strip from summary.json, contents,
                          numbered sections and captions, [n] citations linked to the references;
                          the SVG figures and the PDF are copied next to it

Placeholders: ``{{dotted.path}}`` or ``{{dotted.path|fmt}}``. ``fmt`` is a Python format spec
(e.g. ``.2f``, ``d``, ``,``), ``pct`` / ``pct1`` for a percentage, ``yn`` for yes/no, or ``min`` for
seconds rendered as whole minutes. List elements are addressed by one or more ``key=value``
selectors, e.g. ``{{rq4.rq4b.rows[scorer=llm].macro_f1}}`` or
``{{rq1.rows[bank=ecb,scorer=llm].auroc}}``. A missing key fails the build; no number in the paper
is typed by hand (MISSION §5).
"""

from __future__ import annotations

import html
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
READER_DIR = ROOT / "docs" / "site" / "paper"
READER = ROOT / "paper" / "reader.html"
FIGURES = ROOT / "results" / "figures"
TEMPLATE = ROOT / "paper" / "templates" / "default.typst"
REPO_URL = "https://github.com/thanatchon36/cbtone"
REPO = f"{REPO_URL}/blob/main"
ZENODO_DOI = "10.5281/zenodo.23371641"
PAPER_URL = "https://thanatchon36.github.io/cbtone/paper/"
TAGS = {"ref": "refuted", "null": "untestable", "nf": "no finding", "pos": "supported"}

TOKEN = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}")
STEP = re.compile(r"([^.\[]+)(?:\[([^\]]+)\])?")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
IMAGE = re.compile(r"^(!\[)(.*?)(\]\(.*?\)(?:\{[^}]*\})?)[ \t]*$", re.MULTILINE)
TABLE = re.compile(r"((?:^\|.*\n)+)\n(: (?:.+\n)+)", re.MULTILINE)


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


def pandoc(args: list[str], stdin: str | None = None) -> str:
    return subprocess.run(
        ["pandoc", *args], input=stdin, text=True, check=True, capture_output=True, cwd=ROOT
    ).stdout


def results(d: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """(id, kind, statement, detail) per pre-registered hypothesis, all from summary.json."""

    def row(path: str) -> dict[str, Any]:
        out: dict[str, Any] = lookup(d, path)
        return out

    def kind(verdict: str) -> str:
        return {"refuted": "ref", "supported": "pos"}.get(verdict, "null")

    ecb = row("rq1.rows[bank=ecb,scorer=llm]")
    bi, bnm = row("rq3.rows[bank=bi,scorer=llm]"), row("rq3.rows[bank=bnm,scorer=llm]")
    a = d["rq4"]["rq4a"]
    f1 = {r["scorer"]: r["macro_f1"] for r in d["rq4"]["rq4b"]["rows"]}
    h2a, h2b = d["rq2"]["verdict"]["h2a"], d["rq2"]["verdict"]["h2b"]
    v1 = d["rq1"]["verdict"]
    return [
        (
            "H1",
            kind(v1["verdict"]),
            "LLM tone improves next-decision prediction over persistence.",
            f"{v1['n_success']} of {v1['n_powered']} powered banks; nearest: ECB ΔLL "
            f"{ecb['dll_vs_pers']:+.3f}, Holm p {ecb['p_vs_pers_holm']:.2f}",
        ),
        (
            "H2a",
            kind(h2a["verdict"]),
            "The tone surprise explains FX / two-year-yield moves beyond a placebo.",
            f"{h2a['n_success']} of {h2a['n_powered']} bank–market cells",
        ),
        (
            "H2b",
            kind(h2b["verdict"]),
            "The LLM beats the dictionary on announcement-window R².",
            f"{h2b['n_success']} of {h2b['n_powered']} cells after Holm correction",
        ),
        (
            "H3",
            kind(d["rq3"]["verdict"]),
            "Native-language and English versions agree (Spearman ρ ≥ 0.70).",
            f"Indonesian ρ {bi['spearman']:.2f}, Malay ρ {bnm['spearman']:.2f}",
        ),
        (
            "H4a",
            "ref" if not a["docs"]["h4a_prompts_pass"] else "pos",
            "Scores are stable across five prompt paraphrases (α ≥ 0.667).",
            f"α {a['docs']['prompts']['alpha']:.2f} (documents), "
            f"{a['sentences']['prompts']['alpha']:.2f} (sentences)",
        ),
        (
            "H4b",
            kind(d["rq4"]["rq4b"]["verdict"]),
            "FOMC macro-F1 ≥ 0.50 and above the dictionary.",
            f"LLM {f1['llm']:.2f}, fine-tuned {f1['ft']:.2f}, dictionary {f1['dict']:.2f}",
        ),
        (
            "H4c",
            "nf",
            "Findings survive entity masking and a post-cutoff split.",
            "no finding survived to be checked",
        ),
        (
            "H5",
            kind(d["rq5"]["verdict"]),
            "Fed-calibrated scorers transfer poorly to MAS.",
            "FOMC-RoBERTa gated; Southeast Asian English subsets below 50 sentences",
        ),
    ]


def citations(title: str, version: str) -> tuple[str, str]:
    """BibTeX for the paper and for the software. README, CITATION.cff and the Hugging Face cards
    carry the same entries (tests/test_paper_build.py checks they stay in sync)."""
    protected = re.sub(r"\b([A-Z]{2,})\b", r"{\1}", title)
    paper = (
        "@misc{chongmankhong2026reading,\n"
        "  author = {Chongmankhong, Thanatchon},\n"
        f"  title  = {{{protected}}},\n"
        "  year   = {2026},\n"
        "  note   = {Preprint},\n"
        f"  url    = {{{PAPER_URL}}}\n"
        "}"
    )
    software = (
        "@software{chongmankhong_cbtone,\n"
        "  author  = {Chongmankhong, Thanatchon},\n"
        "  title   = {cbtone},\n"
        "  year    = {2026},\n"
        f"  version = {{{version}}},\n"
        f"  url     = {{{REPO_URL}}},\n"
        f"  doi     = {{{ZENODO_DOI}}}\n"
        "}"
    )
    return paper, software


def build_reader(filled: str, data: dict[str, Any]) -> Path:
    """Standalone web reader docs/site/paper/index.html (same text as the PDF)."""
    m = FRONT.match(filled)
    head, body = (filled[: m.end()], filled[m.end() :]) if m else ("", filled)
    version = re.search(
        r'^__version__ = "([^"]+)"', (ROOT / "src" / "cbtone" / "__init__.py").read_text(), re.M
    )
    assert version is not None
    READER_DIR.mkdir(parents=True, exist_ok=True)
    out = READER_DIR / "index.html"
    pandoc(
        [
            "--from=markdown+smart",
            "--to=html5",
            f"--template={READER}",
            "--standalone",
            "--citeproc",
            "--number-sections",
            "--toc",
            "--toc-depth=1",
            "--wrap=none",
            "--metadata=pagetitle:cbtone — paper",
            "-o",
            str(out),
        ],
        stdin=head + number_captions(body),
    )
    meta = (
        f"<b>cbtone v{version.group(1)}</b> · 7 central banks · English, Indonesian, Malay · "
        f"<code>qwen3:4b</code> on a consumer GPU · pre-registered at tag "
        f"<code>prereg-v1</code> · corpus {data['corpus_version'][:19]}…"
    )
    actions = (
        '<li><a href="paper.pdf">Download PDF</a></li>'
        f'<li><a href="{REPO_URL}">Source code</a></li>'
        f'<li><a href="https://doi.org/{ZENODO_DOI}">DOI {ZENODO_DOI}</a></li>'
        '<li><a href="../">Documentation</a></li>'
        f'<li><a href="{REPO}/docs/RESEARCH_QUESTIONS.md">Pre-registration</a></li>'
        '<li><a href="https://huggingface.co/thanatchon36/cbtone-ft-xlmr">Model</a></li>'
        '<li><a href="https://huggingface.co/datasets/thanatchon36/cbtone-silver-sentences">'
        "Dataset</a></li>"
    )
    note = (
        "Pre-registered hypotheses and their verdicts at the frozen thresholds, generated from "
        "<code>results/summary.json</code>."
    )
    items = "\n".join(
        f'<li class="r r-{k}"><span class="r-id">{html.escape(i)}</span>'
        f'<span class="r-text">{html.escape(t)}<small>{html.escape(x)}</small></span>'
        f'<span class="r-tag">{TAGS[k]}</span></li>'
        for i, k, t, x in results(data)
    )
    title = yaml.safe_load(m.group(1))["title"] if m else ""
    paper_bib, software_bib = citations(title, version.group(1))
    cite = (
        "<h2>How to cite</h2>"
        "<p>The paper:</p>"
        f"<pre><code>{html.escape(paper_bib)}</code></pre>"
        f"<p>The software (<code>cbtone</code>, archived on Zenodo, DOI {ZENODO_DOI}):</p>"
        f"<pre><code>{html.escape(software_bib)}</code></pre>"
    )
    colophon = (
        "<p>Library, experiments and manuscript draft by Claude (Anthropic) under the author's "
        "specification; the author is responsible for the content. Independent project: public "
        "documents only, represents the views of no institution, not investment advice.</p>"
        "<p>Rendered from <code>paper/paper.md</code> by <code>make paper</code>. Every number is "
        "injected from <code>results/summary.json</code>; <code>make reproduce</code> regenerates "
        "it from the committed corpus snapshot.</p>"
    )
    page = out.read_text(encoding="utf-8").replace('src="results/figures/', 'src="figures/')
    for marker, value in (
        ("<!--META-->", meta),
        ("<!--ACTIONS-->", actions),
        ("<!--RESULTS-NOTE-->", note),
        ("<!--RESULTS-->", items),
        ("<!--CITE-->", cite),
        ("<!--COLOPHON-->", colophon),
    ):
        assert marker in page, marker
        page = page.replace(marker, value)
    out.write_text(page, encoding="utf-8")
    shutil.copyfile(OUT_PDF, READER_DIR / "paper.pdf")
    figures = READER_DIR / "figures"
    figures.mkdir(exist_ok=True)
    for name in sorted(set(re.findall(r'src="figures/([\w.-]+)"', page))):
        shutil.copyfile(FIGURES / name, figures / name)
    return out


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
    print("wrote", build_reader(filled, data).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
