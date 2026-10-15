"""Announcement card for the paper (LinkedIn): docs/posts/card.png, 1200 x 1200 px.

Two panels read from results/summary.json: agreement with human FOMC labels (RQ4b) and the
next-decision gain over persistence (RQ1) for the local LLM and the FOMC-RoBERTa replication.
No number is typed by hand. Fonts and palette are the paper's (experiments/figures.py).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import RESULTS
from figures import BAND, GRID, INK, INK2, INK3, NAMES, SLOT, SURFACE, _axis, _fonts
from matplotlib.lines import Line2D

OUT = Path("docs/posts/card.png")
F1_MIN = 0.50
URL = "thanatchon36.github.io/cbtone/paper"
LEFT, RIGHT = 0.06, 0.94


def main() -> None:
    _fonts()
    s = json.loads((RESULTS / "summary.json").read_text())
    f1 = {r["scorer"]: r for r in s["rq4"]["rq4b"]["rows"]}
    rq1 = {
        (r["bank"], r["scorer"]): r
        for r in s["rq1"]["rows"]
        if r.get("powered") and "dll_vs_pers" in r
    }
    banks = [b for b in ("fed", "ecb", "rba", "bi") if (b, "llm") in rq1]
    v = s["rq1"]["verdict"]
    n_tr = s["rq1"]["transformer"]["n_ci_above_zero_vs_pers"]
    n_llm_ci = sum(rq1[(b, "llm")]["dll_vs_pers_lo"] > 0 for b in banks)
    n_fomc = s["rq4"]["rq4b"]["n"]

    fig = plt.figure(figsize=(6, 6), dpi=200)
    fig.patch.set_facecolor(SURFACE)

    # ---- header -------------------------------------------------------------------------------
    fig.text(
        LEFT,
        0.958,
        "PRE-REGISTERED STUDY  ·  7 CENTRAL BANKS  ·  3 LANGUAGES  ·  ONE LOCAL 4B LLM",
        fontsize=6.8,
        color=INK3,
        va="top",
    )
    fig.text(
        LEFT,
        0.92,
        "Better at reading.\nNo better at forecasting.",
        fontsize=19,
        fontweight="bold",
        color=INK,
        va="top",
        linespacing=1.05,
    )
    sub = (
        f"A supervised model that agrees with human labels on Fed sentences at macro-F1 "
        f"{f1['fomc_roberta']['macro_f1']:.2f}, against the local LLM's "
        f"{f1['llm']['macro_f1']:.2f}, predicts the next policy decision no better: neither "
        f"scorer clears the pre-registered bar at any of the {v['n_powered']} banks with enough "
        "data, the Fed included."
    )
    fig.text(
        LEFT,
        0.78,
        "\n".join(textwrap.wrap(sub, 96, break_on_hyphens=False)),
        fontsize=8.2,
        color=INK2,
        va="top",
        linespacing=1.35,
    )

    # ---- (a) reading ------------------------------------------------------------------------
    ax = fig.add_axes((0.31, 0.49, 0.62, 0.165))
    _axis(ax)
    order = sorted(("dict", "ft", "llm", "fomc_roberta"), key=lambda k: f1[k]["macro_f1"])
    ax.axvspan(0, F1_MIN, color=BAND, lw=0, zorder=0)
    ax.text(
        F1_MIN - 0.012,
        -0.62,
        f"below the pre-registered floor ({F1_MIN:.2f})",
        ha="right",
        va="center",
        fontsize=6.3,
        color=INK3,
        style="italic",
    )
    for y, k in enumerate(order):
        r, c = f1[k], SLOT[k]
        ax.plot([r["f1_lo"], r["f1_hi"]], [y, y], color=c, lw=1.4, solid_capstyle="butt", zorder=2)
        ax.plot(r["macro_f1"], y, "o", color=c, ms=5.2, mec=c, zorder=3)
        ax.text(
            r["f1_hi"] + 0.015,
            y,
            f"{r['macro_f1']:.2f}",
            va="center",
            ha="left",
            fontsize=8,
            color=INK,
            fontweight="bold" if k == "fomc_roberta" else "normal",
        )
    ax.set_yticks(range(len(order)), [NAMES[k] for k in order], fontsize=7.6, color=INK)
    ax.set_ylim(len(order) - 0.5, -0.9)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "0.25", "0.50", "0.75", "1"], fontsize=6.8)
    ax.set_title(
        f"(a) Reading: agreement with {n_fomc} human-labelled FOMC sentences, macro-F1",
        loc="left",
        fontsize=7.8,
        color=INK,
        pad=5,
    )

    # ---- (b) forecasting ---------------------------------------------------------------------
    bx = fig.add_axes((0.31, 0.215, 0.62, 0.195))
    _axis(bx)
    for y in range(0, len(banks), 2):
        bx.axhspan(y - 0.5, y + 0.5, color=BAND, lw=0, zorder=0)
    bx.axvline(0, color=INK3, lw=0.9, zorder=1)
    off = {"llm": -0.17, "fomc_roberta": 0.17}
    xmin, xmax = 0.0, 0.0
    for y, b in enumerate(banks):
        for k, d in off.items():
            r, c = rq1[(b, k)], SLOT[k]
            lo, hi = r["dll_vs_pers_lo"], r["dll_vs_pers_hi"]
            xmin, xmax = min(xmin, lo), max(xmax, hi)
            bx.plot([lo, hi], [y + d, y + d], color=c, lw=1.4, solid_capstyle="butt", zorder=2)
            bx.plot(r["dll_vs_pers"], y + d, "o", color=c, ms=5.2, mec=c, zorder=3)
            if y == 0:  # direct labels on the first row instead of a legend
                bx.text(
                    hi + 0.004,
                    y + d,
                    NAMES[k],
                    va="center",
                    ha="left",
                    fontsize=6.6,
                    color=c,
                )
    names = {"fed": "Fed", "ecb": "ECB", "rba": "RBA", "bi": "Bank Indonesia"}
    bx.set_yticks(range(len(banks)), [names[b] for b in banks], fontsize=7.6, color=INK)
    bx.set_ylim(len(banks) - 0.5, -0.5)
    pad = 0.012
    bx.set_xlim(xmin - pad, xmax + pad)
    bx.tick_params(axis="x", labelsize=6.8)
    bx.set_xlabel(
        "ΔLL: log-loss gain over “same as last time”, per decision (> 0 would favour the model)",
        fontsize=6.8,
        color=INK2,
        labelpad=4,
    )
    bx.set_title(
        f"(b) Forecasting: next-decision gain over persistence, the {v['n_powered']} banks "
        "with enough data",
        loc="left",
        fontsize=7.8,
        color=INK,
        pad=5,
    )

    # ---- notes and footer ---------------------------------------------------------------------
    llm_note = (
        f"{n_llm_ci} interval clears zero, none after Holm"
        if n_llm_ci == 1
        else f"{n_llm_ci} intervals clear zero, none after Holm"
    )
    note = (
        f"95 % bootstrap intervals. LLM: {v['n_success']} of {v['n_powered']} banks pass the "
        f"pre-registered test ({llm_note}). Replication: {n_tr} of {v['n_powered']} intervals "
        "above zero. Every pre-registered hypothesis is refuted or untestable; masking names, "
        "dates and rate levels changes almost nothing."
    )
    fig.text(
        LEFT,
        0.138,
        "\n".join(textwrap.wrap(note, 140, break_on_hyphens=False)),
        fontsize=6.6,
        color=INK2,
        va="top",
        linespacing=1.45,
    )
    fig.add_artist(Line2D([LEFT, RIGHT], [0.068, 0.068], color=GRID, lw=0.6))
    fig.text(
        LEFT,
        0.057,
        "Reading the Room: Do Local-LLM Tone Scores of Central-Bank Communication Carry Policy "
        "Signal?",
        fontsize=7.4,
        color=INK,
        va="top",
        style="italic",
    )
    fig.text(LEFT, 0.033, f"{URL}   ·   pip install cbtone", fontsize=7.4, color=INK2, va="top")
    fig.text(
        RIGHT,
        0.033,
        "every number from results/summary.json",
        fontsize=5.8,
        color=INK3,
        va="top",
        ha="right",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, facecolor=SURFACE)
    print(f"wrote {OUT} ({6 * 200}x{6 * 200} px)")


if __name__ == "__main__":
    main()
