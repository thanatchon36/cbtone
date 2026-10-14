"""Static figures for the paper (results/figures/*.png + a CSV table view for each).

Palette: the dataviz reference categorical order, light mode (blue, orange, aqua as slots 1-3,
validated all-pairs for these three). Colour follows the scorer, never its rank: dict = slot 1,
llm = slot 2, ft = slot 3. Thin marks, recessive grid, direct labels, a legend for >= 2 series,
one y-axis per chart.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl
from _common import RESULTS, SCORES

FIG = RESULTS / "figures"
SURFACE = "#fcfcfb"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SLOT = {"dict": "#2a78d6", "llm": "#eb6834", "ft": "#1baf7a"}
NAMES = {"dict": "Dictionary", "llm": "Local LLM (qwen3:4b)", "ft": "Fine-tuned XLM-R"}
BANK_NAMES = {
    "fed": "Fed",
    "ecb": "ECB",
    "boe": "BoE",
    "rba": "RBA",
    "mas": "MAS",
    "bi": "BI",
    "bnm": "BNM",
}


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig: plt.Figure, name: str, table: pl.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    table.write_csv(FIG / f"{name}.csv")
    plt.close(fig)


def forest(
    rows: list[dict],
    value: str,
    lo: str,
    hi: str,
    scorers: list[str],
    title: str,
    xlabel: str,
    name: str,
    ci_note: str = "95% block-bootstrap CIs",
) -> None:
    """Dot + CI per bank (rows) and scorer (fixed colour), zero reference line."""
    banks = [b for b in BANK_NAMES if any(r["bank"] == b for r in rows)]
    fig, ax = plt.subplots(figsize=(6.4, 0.45 * len(banks) + 1.2))
    _style(ax)
    ax.axvline(0, color=INK2, linewidth=1)
    off = {s: (i - (len(scorers) - 1) / 2) * 0.22 for i, s in enumerate(scorers)}
    table = []
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
            yy = y + off[s]
            ax.plot([r[lo], r[hi]], [yy, yy], color=SLOT[s], linewidth=2, solid_capstyle="round")
            ax.plot(
                r[value],
                yy,
                "o",
                color=SLOT[s],
                markersize=6,
                markeredgecolor=SURFACE,
                markeredgewidth=1.5,
            )
            table.append(
                {
                    "bank": b,
                    "scorer": s,
                    value: r[value],
                    lo: r[lo],
                    hi: r[hi],
                    "powered": r.get("powered"),
                }
            )
    labels = [
        BANK_NAMES[b] + ("" if any(r["bank"] == b and r.get("powered") for r in rows) else " *")
        for b in banks
    ]
    ax.set_yticks(range(len(banks)), labels, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    handles = [
        plt.Line2D([], [], color=SLOT[s], marker="o", linewidth=2, label=NAMES[s]) for s in scorers
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower right", labelcolor=INK2)
    fig.text(
        0.01,
        -0.02,
        f"* underpowered (pre-registered minimum not met); {ci_note}",
        fontsize=7,
        color=INK2,
    )
    _save(fig, name, pl.DataFrame(table))


def tone_timeseries() -> None:
    """Small multiples: LLM document tone per headline bank over time (single series each)."""
    path = SCORES / "llm.parquet"
    if not path.exists():
        return
    df = pl.read_parquet(path).filter(pl.col("error").is_null(), pl.col("variant") == "")
    banks = [b for b in BANK_NAMES if df.filter(pl.col("bank") == b).height]
    fig, axes = plt.subplots(len(banks), 1, figsize=(6.4, 1.05 * len(banks) + 0.6), sharex=True)
    table = []
    for ax, b in zip(axes, banks, strict=True):
        from cbtone.corpus import PRIMARY

        dt, lang = PRIMARY[b]
        sub = df.filter(
            pl.col("bank") == b, pl.col("doc_type") == dt, pl.col("language") == lang
        ).sort("date")
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.plot(sub["date"].to_list(), sub["index"].to_list(), color=SLOT["llm"], linewidth=1.5)
        ax.set_ylim(-1.05, 1.05)
        ax.set_yticks([-1, 0, 1])
        ax.text(0.005, 0.85, BANK_NAMES[b], transform=ax.transAxes, color=INK, fontsize=9)
        table += [
            {"bank": b, "date": d, "index": v} for d, v in sub.select("date", "index").iter_rows()
        ]
    axes[0].set_title(
        "LLM tone index of each bank's primary decision document (hawkish +1, dovish -1)",
        color=INK,
        fontsize=10,
        loc="left",
    )
    _save(fig, "fig_tone_timeseries", pl.DataFrame(table))


def fomc_f1(rq4: dict) -> None:
    rows = rq4.get("rq4b", {}).get("rows", [])
    if not rows:
        return
    lit = {
        "Dictionary (Shah et al.)": 0.50,
        "Zero-shot ChatGPT (Shah et al.)": 0.587,
        "Fine-tuned RoBERTa-large (Shah et al.)": 0.717,
    }
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    _style(ax)
    order = [r for s in ("dict", "llm", "ft") for r in rows if r["scorer"] == s]
    for y, r in enumerate(order):
        ax.plot(
            [r["f1_lo"], r["f1_hi"]],
            [y, y],
            color=SLOT[r["scorer"]],
            linewidth=2,
            solid_capstyle="round",
        )
        ax.plot(
            r["macro_f1"],
            y,
            "o",
            color=SLOT[r["scorer"]],
            markersize=7,
            markeredgecolor=SURFACE,
            markeredgewidth=1.5,
        )
        ax.text(
            r["f1_lo"] - 0.01,
            y,
            f"{r['macro_f1']:.2f}",
            va="center",
            ha="right",
            fontsize=8,
            color=INK2,
        )
    trans = matplotlib.transforms.blended_transform_factory(ax.transData, ax.transAxes)
    for i, (k, v) in enumerate(lit.items()):
        ax.axvline(v, color=INK2, linewidth=0.8, linestyle=(0, (2, 2)))
        ax.text(v, 1.02 + 0.09 * i, k, transform=trans, fontsize=6.5, color=INK2, ha="center")
    ax.set_yticks(range(len(order)), [NAMES[r["scorer"]] for r in order], color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        "3-class macro-F1 on the FOMC test split (496 sentences); 95% bootstrap CI",
        color=INK2,
        fontsize=9,
    )
    ax.set_title(
        "Agreement with human labels (RQ4b); dotted = published references",
        color=INK,
        fontsize=10,
        loc="left",
        pad=40,
    )
    _save(
        fig, "fig_rq4b_fomc_f1", pl.DataFrame(order).select("scorer", "macro_f1", "f1_lo", "f1_hi")
    )


def crosslingual() -> None:
    en = SCORES / "llm.parquet"
    nat = SCORES / "llm-native.parquet"
    if not en.exists() or not nat.exists():
        return
    a = pl.read_parquet(en).filter(pl.col("error").is_null(), pl.col("variant") == "")
    b = pl.read_parquet(nat).filter(pl.col("error").is_null(), pl.col("variant") == "")
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.2), sharey=True)
    table = []
    for ax, (bank, lang) in zip(axes, (("bi", "id"), ("bnm", "ms")), strict=True):
        x = a.filter(pl.col("bank") == bank, pl.col("language") == "en").select(
            "date", pl.col("index").alias("en")
        )
        y = b.filter(pl.col("bank") == bank, pl.col("language") == lang).select(
            "date", pl.col("index").alias("native")
        )
        j = x.join(y, on="date")
        _style(ax)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.plot([-1, 1], [-1, 1], color=GRID, linewidth=1)
        ax.plot(
            j["en"],
            j["native"],
            "o",
            color=SLOT["llm"],
            markersize=4,
            alpha=0.8,
            markeredgecolor=SURFACE,
            markeredgewidth=0.8,
        )
        ax.set_title(
            f"{BANK_NAMES[bank]}: {lang} vs en (n={j.height})", color=INK, fontsize=9, loc="left"
        )
        ax.set_xlabel("English-version index", color=INK2, fontsize=8)
        ax.set_xlim(-1.05, 1.05)
        ax.set_ylim(-1.05, 1.05)
        table += [{"bank": bank, "date": d, "en": e, "native": n} for d, e, n in j.iter_rows()]
    axes[0].set_ylabel("Native-version index", color=INK2, fontsize=8)
    _save(fig, "fig_rq3_crosslingual", pl.DataFrame(table))


def main() -> None:
    def load(n: str) -> dict:
        p = RESULTS / f"{n}.json"
        return json.loads(p.read_text()) if p.exists() else {}

    rq1, rq2, rq4 = load("rq1"), load("rq2"), load("rq4")
    hl = set(BANK_NAMES)
    r1 = [r for r in rq1.get("rows", []) if r["bank"] in hl]
    if r1:
        forest(
            r1,
            "dll_vs_pers",
            "dll_vs_pers_lo",
            "dll_vs_pers_hi",
            ["dict", "llm"],
            "Gain in next-decision log-loss over persistence (RQ1)",
            "ΔLL = LL(persistence) - LL(model); > 0 = better than persistence",
            "fig_rq1_dll",
        )
    r2 = [
        r | {"scorer": r["scorer"]}
        for r in rq2.get("rows", [])
        if r["bank"] in hl
        and r["subset"] == "all"
        and r["kind"] == "fx"
        and r.get("beta") is not None
    ]
    if r2:
        for r in r2:
            r["beta_lo"], r["beta_hi"] = (
                r["beta"] - 1.96 * r["se_hac"],
                r["beta"] + 1.96 * r["se_hac"],
            )
        forest(
            r2,
            "beta",
            "beta_lo",
            "beta_hi",
            ["dict", "llm"],
            "FX response to the tone surprise (RQ2)",
            "β: signed 2-day log FX move per unit tone surprise (HAC 95% CI)",
            "fig_rq2_fx_beta",
            ci_note="Newey-West (HAC) 95% CIs",
        )
    tone_timeseries()
    fomc_f1(rq4)
    crosslingual()
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
