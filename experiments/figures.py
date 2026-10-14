"""Publication figures for the paper: results/figures/<name>.{svg,png,csv}.

Design rules (dataviz reference, validated palette): colour follows the scorer, never its rank
(dict = blue, llm = orange, ft = green; grey ink for anything that is not a scorer); thin marks;
recessive grid; a legend wherever two series share an axis; selective direct labels; no in-figure
titles (the caption carries them, panels get "(a)"/"(b)"); one CSV table view per figure.
Typography matches the typeset paper: Libertinus Serif from paper/fonts, so figure text and body
text are set in the same face. SVG text is written as outlines, so the files render identically
everywhere; PNG at 300 dpi is kept for the README and the docs site.
"""

from __future__ import annotations

import json
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl
from _common import CUTOFF, HEADLINE_LLM, RESULTS, SCORES
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory as blend

FIG = RESULTS / "figures"
FONT_DIR = Path("paper/fonts")
WIDTH = 6.3  # inches; the paper's text width is 16.6 cm
SURFACE = "#ffffff"
INK, INK2, INK3, GRID, BAND = "#141414", "#4f4f4f", "#8c8c8c", "#dcdcdc", "#f4f4f2"
SLOT = {"dict": "#2a78d6", "llm": "#eb6834", "ft": "#1baf7a"}
NAMES = {"dict": "Dictionary (dict-v1)", "llm": "Local LLM (qwen3:4b)", "ft": "Fine-tuned XLM-R"}
BANK_NAMES = {
    "fed": "Fed",
    "ecb": "ECB",
    "boe": "BoE",
    "rba": "RBA",
    "mas": "MAS",
    "bi": "BI",
    "bnm": "BNM",
}
BANK_LONG = {
    "fed": "Federal Reserve",
    "ecb": "European Central Bank",
    "boe": "Bank of England",
    "rba": "Reserve Bank of Australia",
    "mas": "Monetary Authority of Singapore",
    "bi": "Bank Indonesia",
    "bnm": "Bank Negara Malaysia",
}
DOC_TYPES = {
    "statement": "decision statement",
    "minutes": "MPC minutes",
    "mps": "monetary policy statement",
}
# Pre-registered thresholds (docs/RESEARCH_QUESTIONS.md); drawn as reference lines only.
ALPHA_MIN, RHO_MIN, F1_MIN = 0.667, 0.70, 0.50
# Published FOMC references, weighted F1 on the same test split (Shah, Paturi & Chava 2023).
SHAH = {
    "Rule-based baseline, Shah et al. (2023)": 0.50,
    "Zero-shot ChatGPT-3.5, Shah et al. (2023)": 0.587,
    "Fine-tuned RoBERTa-large, Shah et al. (2023)": 0.717,
}


def _fonts() -> None:
    for p in sorted(FONT_DIR.glob("LibertinusSerif-*.otf")):
        fm.fontManager.addfont(str(p))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Libertinus Serif", "DejaVu Serif"],
            "font.size": 8,
            "axes.titlesize": 8.5,
            "axes.labelsize": 8,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "axes.edgecolor": GRID,
            "axes.linewidth": 0.6,
            "axes.labelcolor": INK2,
            "xtick.color": INK2,
            "ytick.color": INK2,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "text.color": INK,
            "svg.fonttype": "path",
            "savefig.dpi": 300,
            "savefig.facecolor": SURFACE,
            "figure.facecolor": SURFACE,
        }
    )


def _axis(ax: plt.Axes, grid: str | None = "x", *, left: bool = False) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=2.5 if left else 0, color=GRID)
    ax.tick_params(axis="x", length=2.5, color=GRID)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def _finish(fig: plt.Figure, scorers: list[str] | None = None, note: str | None = None) -> None:
    """Legend (centred) and footnote (left-aligned) under everything already drawn."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    w, h = fig.get_size_inches()
    bb = fig.get_tightbbox(renderer)
    x0, xc, y = bb.x0 / w, (bb.x0 + bb.x1) / (2 * w), bb.y0 / h - 0.015
    if scorers:
        handles = [
            Line2D([], [], color=SLOT[s], marker="o", lw=1.3, ms=4.6, mec=SLOT[s], label=NAMES[s])
            for s in scorers
        ]
        leg = fig.legend(
            handles=handles,
            loc="upper center",
            bbox_to_anchor=(xc, y),
            ncol=len(handles),
            frameon=False,
            handlelength=1.6,
            columnspacing=1.8,
            labelcolor=INK2,
        )
        fig.canvas.draw()
        y = leg.get_window_extent(renderer).y0 / (h * fig.dpi) - 0.015
    if note:
        fig.text(
            x0,
            y,
            textwrap.fill(note, 130),
            fontsize=6.8,
            color=INK2,
            ha="left",
            va="top",
            linespacing=1.35,
        )


def _save(fig: plt.Figure, name: str, table: pl.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.svg", bbox_inches="tight", pad_inches=0.03, metadata={"Date": None})
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", pad_inches=0.03)
    table.write_csv(FIG / f"{name}.csv")
    plt.close(fig)


def _forest(
    ax: plt.Axes,
    rows: list[dict[str, Any]],
    value: str,
    lo: str,
    hi: str,
    scorers: list[str],
    *,
    banks: list[str] | None = None,
    n_key: str | None = None,
    missing: str | None = None,
    annotate: Callable[[plt.Axes, dict[str, Any], float], None] | None = None,
) -> list[dict[str, Any]]:
    """Dot + interval per bank (rows) and scorer (fixed colour); hollow marker = underpowered."""
    banks = banks or [b for b in BANK_NAMES if any(r["bank"] == b for r in rows)]
    _axis(ax)
    for y in range(0, len(banks), 2):
        ax.axhspan(y - 0.5, y + 0.5, color=BAND, lw=0, zorder=0)
    ax.axvline(0, color=INK3, linewidth=0.8, zorder=1)
    off = {s: (i - (len(scorers) - 1) / 2) * 0.28 for i, s in enumerate(scorers)}
    table, powered = [], {}
    for y, b in enumerate(banks):
        for s in scorers:
            r = next(
                (
                    r
                    for r in rows
                    if r["bank"] == b and r["scorer"] == s and r.get(value) is not None
                ),
                None,
            )
            if r is None:
                continue
            p = bool(r.get("powered"))
            powered[b] = powered.get(b, False) or p
            yy, c = y + off[s], SLOT[s]
            ax.plot(
                [r[lo], r[hi]], [yy, yy], color=c, linewidth=1.3, solid_capstyle="butt", zorder=2
            )
            ax.plot(r[value], yy, "o", ms=4.6, mfc=c if p else SURFACE, mec=c, mew=1.1, zorder=3)
            table.append(
                {"bank": b, "scorer": s, value: r[value], lo: r[lo], hi: r[hi], "powered": p}
                | ({n_key: r.get(n_key)} if n_key else {})
            )
            if annotate is not None:
                annotate(ax, r, yy)
        if b not in powered:
            if missing:
                ax.text(
                    0.5,
                    y,
                    missing,
                    transform=blend(ax.transAxes, ax.transData),
                    ha="center",
                    va="center",
                    fontsize=6.8,
                    color=INK3,
                    style="italic",
                )
            continue
        if n_key:
            n = next((r[n_key] for r in rows if r["bank"] == b and r.get(n_key) is not None), None)
            if n is not None:
                ax.text(
                    1.01,
                    y,
                    f"n = {n:,}",
                    transform=blend(ax.transAxes, ax.transData),
                    va="center",
                    ha="left",
                    fontsize=7,
                    color=INK3,
                )
    labels = [BANK_NAMES[b] + (" *" if b in powered and not powered[b] else "") for b in banks]
    ax.set_yticks(range(len(banks)), labels, color=INK, fontsize=8)
    ax.set_ylim(len(banks) - 0.5, -0.5)
    return table


def rq1_dll(rq1: dict[str, Any]) -> None:
    rows = [r for r in rq1.get("rows", []) if r["bank"] in BANK_NAMES]
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    table = _forest(
        ax, rows, "dll_vs_pers", "dll_vs_pers_lo", "dll_vs_pers_hi", ["dict", "llm"], n_key="n_oos"
    )
    ax.set_xlabel("ΔLL = LL(persistence) − LL(model), per decision;  > 0 favours the model")
    _finish(
        fig,
        ["dict", "llm"],
        "Intervals: 95% moving-block bootstrap (block length 4). Hollow markers and *: bank below "
        "the pre-registered minimum (≥ 40 out-of-sample decisions with ≥ 8 hikes and ≥ 8 cuts), "
        "reported but outside the Holm family. n = out-of-sample decisions.",
    )
    _save(fig, "fig_rq1_dll", pl.DataFrame(table))


def rq2_beta(rq2: dict[str, Any]) -> None:
    rows = [
        dict(r)
        for r in rq2.get("rows", [])
        if r["bank"] in BANK_NAMES
        and r["subset"] == "all"
        and r["scorer"] in ("dict", "llm")
        and r.get("beta") is not None
    ]
    if not rows:
        return
    for r in rows:
        r["beta_lo"], r["beta_hi"] = r["beta"] - 1.96 * r["se_hac"], r["beta"] + 1.96 * r["se_hac"]
    fx = [r for r in rows if r["kind"] == "fx"]
    y2 = [r for r in rows if r["kind"] == "y2"]
    banks = [b for b in BANK_NAMES if any(r["bank"] == b for r in rows)]
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(WIDTH, 3.4), gridspec_kw={"width_ratios": [1.3, 1], "wspace": 0.5}
    )

    def flag(ax: plt.Axes, r: dict[str, Any], yy: float) -> None:
        if r.get("h2a_success"):
            ax.text(
                r["beta"],
                yy + 0.2,
                "exceeds placebo R²",
                va="top",
                ha="center",
                fontsize=6.6,
                color=INK2,
                style="italic",
            )

    t_a = _forest(
        ax_a,
        fx,
        "beta",
        "beta_lo",
        "beta_hi",
        ["dict", "llm"],
        banks=banks,
        n_key="n_events",
        annotate=flag,
    )
    t_b = _forest(
        ax_b,
        y2,
        "beta",
        "beta_lo",
        "beta_hi",
        ["dict", "llm"],
        banks=banks,
        n_key="n_events",
        annotate=flag,
        missing="no free daily 2-year series",
    )
    ax_a.set_title("(a) Exchange rate", loc="left", color=INK)
    ax_b.set_title("(b) Two-year government yield", loc="left", color=INK)
    ax_a.set_xlabel("β: two-day log move per unit surprise\n(+ = domestic appreciation)")
    ax_b.set_xlabel("β: basis points per unit surprise")
    _finish(
        fig,
        ["dict", "llm"],
        "Intervals: ±1.96 Newey–West (HAC) standard errors. Hollow markers and *: below the "
        "pre-registered minimum of 30 events. n = announcement events. FX for Singapore, Indonesia "
        "and Malaysia are USD crosses, signed so that + is domestic appreciation.",
    )
    _save(
        fig,
        "fig_rq2_beta",
        pl.DataFrame([r | {"kind": "fx"} for r in t_a] + [r | {"kind": "y2"} for r in t_b]),
    )


def rq3_crosslingual(rq3: dict[str, Any]) -> None:
    en, nat = SCORES / "llm.parquet", SCORES / "llm-native.parquet"
    if not en.exists() or not nat.exists():
        return
    a = pl.read_parquet(en).filter(pl.col("error").is_null(), pl.col("variant") == "")
    b = pl.read_parquet(nat).filter(pl.col("error").is_null(), pl.col("variant") == "")
    stats = {r["bank"]: r for r in rq3.get("rows", []) if r["scorer"] == "llm"}
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 3.25), sharey=True, gridspec_kw={"wspace": 0.12})
    table = []
    for panel, ax, (bank, lang, lang_name) in zip(
        "ab", axes, (("bi", "id", "Indonesian"), ("bnm", "ms", "Malay")), strict=True
    ):
        x = a.filter(pl.col("bank") == bank, pl.col("language") == "en").select(
            "date", pl.col("index").alias("en")
        )
        y = b.filter(pl.col("bank") == bank, pl.col("language") == lang).select(
            "date", pl.col("index").alias("native")
        )
        j = x.join(y, on="date").sort("date")
        counts = (
            j.with_columns(pl.col("en").round(3), pl.col("native").round(3))
            .group_by("en", "native")
            .len()
        )
        _axis(ax, grid=None, left=True)
        ax.set_aspect("equal")
        ax.plot([-1.05, 1.05], [-1.05, 1.05], color=INK3, linewidth=0.7, zorder=1)
        ax.axhline(0, color=GRID, linewidth=0.6, zorder=0)
        ax.axvline(0, color=GRID, linewidth=0.6, zorder=0)
        ax.scatter(
            counts["en"],
            counts["native"],
            s=9 + 7 * counts["len"],
            facecolor=SLOT["llm"],
            edgecolor=SURFACE,
            linewidth=0.7,
            alpha=0.85,
            zorder=3,
        )
        s = stats.get(bank, {})
        label = (
            f"ρ = {s['spearman']:.2f}\nstance flips {100 * s['flip_rate']:.1f}%\n"
            f"mean |Δ| = {s['mean_abs_diff']:.2f}"
            if s
            else ""
        )
        ax.text(
            0.03,
            0.97,
            label,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=7,
            color=INK2,
            linespacing=1.4,
        )
        ax.set_title(f"({panel}) {BANK_LONG[bank]}: {lang_name} vs English", loc="left", color=INK)
        ax.set_xlabel(f"Index of the English version (n = {j.height} pairs)")
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-1.08, 1.08)
        ax.set_xticks([-1, -0.5, 0, 0.5, 1])
        ax.set_yticks([-1, -0.5, 0, 0.5, 1])
        table += [{"bank": bank, "date": d, "en": e, "native": n} for d, e, n in j.iter_rows()]
    axes[0].set_ylabel("Index of the native-language version")
    _finish(
        fig,
        None,
        "Marker area is proportional to the number of statements at that pair of values (the "
        "scorer returns a discrete set of indices). Diagonal: perfect agreement. Statistics from "
        "results/rq3.json.",
    )
    _save(fig, "fig_rq3_crosslingual", pl.DataFrame(table))


def rq4b_fomc_f1(rq4: dict[str, Any]) -> None:
    rows = rq4.get("rq4b", {}).get("rows", [])
    if not rows:
        return
    order = [r for s in ("dict", "llm", "ft") for r in rows if r["scorer"] == s]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.3))
    _axis(ax)
    ax.axvspan(0, F1_MIN, color=BAND, lw=0, zorder=0)
    ax.text(
        F1_MIN - 0.01,
        len(order) - 0.62,
        f"below the pre-registered floor ({F1_MIN:.2f})",
        ha="right",
        va="center",
        fontsize=6.8,
        color=INK3,
        style="italic",
    )
    for y, r in enumerate(order):
        c = SLOT[r["scorer"]]
        ax.plot(
            [r["f1_lo"], r["f1_hi"]],
            [y, y],
            color=c,
            linewidth=1.3,
            solid_capstyle="butt",
            zorder=2,
        )
        ax.plot(r["macro_f1"], y, "o", color=c, ms=5, mec=c, zorder=3)
        ax.text(
            r["f1_lo"] - 0.012,
            y,
            f"{r['macro_f1']:.2f}",
            va="center",
            ha="right",
            fontsize=7.5,
            color=INK2,
        )
    for i, (k, v) in enumerate(SHAH.items()):
        ax.axvline(v, color=INK3, linewidth=0.7, linestyle=(0, (2, 2)), zorder=1)
        top = 1.03 + 0.14 * i
        ax.plot(
            [v, v],
            [1.0, top],
            transform=blend(ax.transData, ax.transAxes),
            color=INK3,
            linewidth=0.7,
            linestyle=(0, (2, 2)),
            clip_on=False,
        )
        ax.text(
            v + 0.006,
            top,
            f"{k}: {v:.2f}",
            transform=blend(ax.transData, ax.transAxes),
            ha="left",
            va="center",
            fontsize=6.8,
            color=INK2,
        )
    ax.set_yticks(range(len(order)), [NAMES[r["scorer"]] for r in order], color=INK, fontsize=8)
    ax.set_ylim(len(order) - 0.5, -0.5)
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        f"Three-class macro-F1 on the FOMC test split (n = {rq4['rq4b'].get('n', '')} sentences)"
    )
    _finish(
        fig,
        None,
        "Intervals: 95% bootstrap over sentences. Dotted lines: weighted F1 reported on the same "
        "split by Shah, Paturi and Chava (2023); their metric is not identical to macro-F1 and is "
        "shown for orientation only.",
    )
    _save(
        fig, "fig_rq4b_fomc_f1", pl.DataFrame(order).select("scorer", "macro_f1", "f1_lo", "f1_hi")
    )


def rq4a_stability(rq4: dict[str, Any]) -> None:
    a = rq4.get("rq4a", {})
    if not a:
        return
    perts = [
        ("prompts", "Five prompt paraphrases"),
        ("temperature", "Temperature 0 vs 0.7"),
        ("model_tag", "Model tag: qwen3:4b vs qwen2.5:3b"),
    ]
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(WIDTH, 2.5), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.75}
    )
    _axis(ax_a)
    table = []
    for y, (key, _label) in enumerate(perts):
        d, s = a["docs"][key], a["sentences"][key]
        ax_a.plot([s["alpha"], d["alpha"]], [y, y], color=GRID, linewidth=1.2, zorder=1)
        ax_a.plot(d["alpha"], y, "o", ms=5, color=INK, zorder=3)
        ax_a.plot(s["alpha"], y, "o", ms=5, mfc=SURFACE, mec=INK, mew=1.1, zorder=3)
        for v, dy in ((d["alpha"], -0.3), (s["alpha"], 0.33)):
            ax_a.text(v, y + dy, f"{v:.2f}", ha="center", va="center", fontsize=6.8, color=INK2)
        table += [
            {
                "panel": "a",
                "pair": key,
                "level": "documents",
                "alpha": d["alpha"],
                "icc_2_1": d.get("icc_2_1"),
                "n": d.get("n_units"),
                "spearman": None,
            },
            {
                "panel": "a",
                "pair": key,
                "level": "sentences",
                "alpha": s["alpha"],
                "icc_2_1": s.get("icc_2_1"),
                "n": s.get("n_units"),
                "spearman": None,
            },
        ]
    ax_a.axvline(ALPHA_MIN, color=INK3, linewidth=0.8, linestyle=(0, (3, 2)), zorder=1)
    ax_a.text(
        ALPHA_MIN + 0.02,
        len(perts) - 0.55,
        f"pre-registered α ≥ {ALPHA_MIN}",
        ha="left",
        va="center",
        fontsize=6.8,
        color=INK2,
    )
    ax_a.set_yticks(range(len(perts)), [p[1] for p in perts], color=INK, fontsize=8)
    ax_a.set_ylim(len(perts) - 0.5, -0.95)
    ax_a.set_xlim(-0.15, 1.0)
    ax_a.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax_a.set_xlabel("Krippendorff's α (interval)")
    ax_a.set_title("(a) Agreement across perturbations", loc="left", color=INK)
    n_docs, n_sent = (
        a["docs"]["prompts"].get("n_units", ""),
        a["sentences"]["prompts"].get("n_units", 0),
    )
    handles = [
        Line2D([], [], color=INK, marker="o", lw=0, ms=5, label=f"documents (n = {n_docs})"),
        Line2D(
            [],
            [],
            color=INK,
            marker="o",
            lw=0,
            ms=5,
            mfc=SURFACE,
            mew=1.1,
            label=f"sentences (n = {n_sent:,})",
        ),
    ]
    ax_a.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        frameon=False,
        fontsize=7,
        labelcolor=INK2,
        handletextpad=0.4,
        borderaxespad=0.1,
    )

    agg = a.get("aggregation", {}).get("spearman", {})
    names = {
        "agg_mean": "mean",
        "agg_decision_weighted": "decision-weighted",
        "agg_max_abs": "max |index|",
        "document": "direct score",
    }
    pairs = sorted(agg.items(), key=lambda kv: -kv[1])
    _axis(ax_b)
    for y, (k, v) in enumerate(pairs):
        ax_b.plot([0, v], [y, y], color=GRID, linewidth=1.2, zorder=1)
        ax_b.plot(v, y, "o", ms=5, color=INK, zorder=3)
        ax_b.text(v + 0.045, y, f"{v:.2f}", ha="left", va="center", fontsize=6.8, color=INK2)
        table.append(
            {
                "panel": "b",
                "pair": k,
                "level": "documents",
                "alpha": None,
                "icc_2_1": None,
                "n": a.get("aggregation", {}).get("n"),
                "spearman": v,
            }
        )
    ax_b.axvline(RHO_MIN, color=INK3, linewidth=0.8, linestyle=(0, (3, 2)), zorder=1)
    ax_b.text(
        RHO_MIN,
        -0.75,
        f"pre-registered ρ ≥ {RHO_MIN:.2f}",
        ha="center",
        va="bottom",
        fontsize=6.8,
        color=INK2,
    )
    ax_b.set_yticks(
        range(len(pairs)),
        [f"{names[k.split('~')[0]]} vs {names[k.split('~')[1]]}" for k, _ in pairs],
        color=INK,
        fontsize=7.5,
    )
    ax_b.set_ylim(len(pairs) - 0.5, -0.95)
    ax_b.set_xlim(0, 1.18)
    ax_b.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax_b.set_xlabel("Spearman ρ between document indices")
    ax_b.set_title(
        f"(b) Sentence-to-document aggregation (n = {a.get('aggregation', {}).get('n', '')})",
        loc="left",
        color=INK,
    )
    _finish(
        fig,
        None,
        "Panel (a): agreement between scores of the same text under each perturbation, at document "
        "and sentence level (ICC(2,1) in the CSV). Panel (b): rank correlation between three "
        "sentence-aggregation strategies and the direct document score, the four of which must all "
        "exceed ρ = 0.70 for H4a to hold.",
    )
    _save(fig, "fig_rq4a_stability", pl.DataFrame(table))


def tone_timeseries() -> None:
    path = SCORES / "llm.parquet"
    if not path.exists():
        return
    from cbtone.corpus import PRIMARY

    df = pl.read_parquet(path).filter(pl.col("error").is_null(), pl.col("variant") == "")
    banks = [b for b in BANK_NAMES if df.filter(pl.col("bank") == b).height]
    fig, axes = plt.subplots(
        len(banks),
        1,
        figsize=(WIDTH, 1.05 * len(banks) + 0.5),
        sharex=True,
        gridspec_kw={"hspace": 0.6},
    )
    cutoff = CUTOFF[HEADLINE_LLM]
    table = []
    for i, (ax, b) in enumerate(zip(axes, banks, strict=True)):
        dt, lang = PRIMARY[b]
        sub = df.filter(
            pl.col("bank") == b, pl.col("doc_type") == dt, pl.col("language") == lang
        ).sort("date")
        _axis(ax, grid="x", left=True)
        ax.axhline(0, color=INK3, linewidth=0.6, zorder=1)
        ax.axvline(cutoff, color=INK3, linewidth=0.7, linestyle=(0, (2, 2)), zorder=1)
        ax.plot(
            sub["date"].to_list(),
            sub["index"].to_list(),
            color=SLOT["llm"],
            linewidth=0.9,
            zorder=3,
        )
        ax.set_ylim(-1.15, 1.15)
        ax.set_yticks([-1, 0, 1])
        ax.set_title(
            f"{BANK_LONG[b]} — {DOC_TYPES.get(dt, dt)}, n = {sub.height}",
            loc="left",
            color=INK,
            fontsize=7.8,
            pad=3,
        )
        if i == 0:
            ax.text(
                cutoff,
                1.02,
                "training cutoff of qwen3:4b (29 Apr 2025) ",
                transform=blend(ax.transData, ax.transAxes),
                ha="right",
                va="bottom",
                fontsize=6.6,
                color=INK2,
            )
        table += [
            {"bank": b, "date": d, "index": v} for d, v in sub.select("date", "index").iter_rows()
        ]
    axes[-1].set_xlabel("Release date")
    fig.supylabel("LLM tone index (hawkish +1 … dovish −1)", fontsize=8, color=INK2, x=0.02)
    _save(fig, "fig_tone_timeseries", pl.DataFrame(table))


def main() -> None:
    _fonts()

    def load(n: str) -> dict[str, Any]:
        p = RESULTS / f"{n}.json"
        return json.loads(p.read_text()) if p.exists() else {}

    rq1, rq2, rq3, rq4 = load("rq1"), load("rq2"), load("rq3"), load("rq4")
    rq1_dll(rq1)
    rq2_beta(rq2)
    rq3_crosslingual(rq3)
    rq4b_fomc_f1(rq4)
    rq4a_stability(rq4)
    tone_timeseries()
    for stale in ("fig_rq2_fx_beta",):  # renamed in this version
        for ext in ("png", "csv", "svg"):
            (FIG / f"{stale}.{ext}").unlink(missing_ok=True)
    print("figures:", sorted(p.name for p in FIG.glob("*.svg")))


if __name__ == "__main__":
    main()
