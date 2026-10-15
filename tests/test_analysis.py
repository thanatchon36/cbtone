from datetime import UTC, date, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from cbtone.analysis import rq1, rq2, rq345
from cbtone.analysis.common import decision_frame, tone_wide

LABELS = {"dict": ("dict-v1", ""), "llm": ("llm", "")}


def _synthetic(bank="fed", n=140, seed=0, informative=True):
    rng = np.random.default_rng(seed)
    dates = [date(2005, 1, 1) + timedelta(days=45 * i) for i in range(n)]
    tone = rng.normal(size=n)
    dirs = []
    for v in tone:
        z = (1.8 * v if informative else 0.0) + rng.logistic()
        dirs.append("hike" if z > 1.3 else "cut" if z < -1.3 else "hold")
    # decision at t is dirs[t-1]'s successor: next_direction[t] = dirs[t]
    decisions = pl.DataFrame(
        {
            "bank": [bank] * n,
            "date": dates,
            "direction": ["hold", *dirs[:-1]],
            "next_direction": dirs,
            "source": ["bis"] * n,
        }
    )
    rows = []
    for d, v in zip(dates, tone, strict=True):
        for sid, val in (("llm", v), ("dict-v1", 0.3 * v + rng.normal(scale=1.0))):
            rows.append(
                {
                    "doc_id": f"{bank}:{d}:statement:en",
                    "bank": bank,
                    "date": d,
                    "doc_type": "statement",
                    "language": "en",
                    "scorer_id": sid,
                    "variant": "",
                    "prompt_id": "P1@x",
                    "model_digest": "d",
                    "hawkish_p": 0.4,
                    "dovish_p": 0.3,
                    "neutral_p": 0.3,
                    "index": float(np.tanh(val)),
                    "error": None,
                }
            )
    return decisions, pl.DataFrame(rows)


def test_decision_frame_and_tone_wide():
    dec, sc = _synthetic(n=50)
    dec = pl.concat([dec, dec.head(1).with_columns(source=pl.lit("mas_text"), bank=pl.lit("fed"))])
    f = decision_frame(dec, "fed")
    assert f.height == 50 and set(f.columns) == {"date", "last_direction", "next_direction"}
    w = tone_wide(sc, "fed", LABELS)
    assert w.columns == ["date", "tone_dict", "tone_llm"] and w.height == 50


def test_rq1_bank_rows_and_verdict():
    dec, sc = _synthetic()
    rows, long = rq1.bank_rows(dec, sc, "fed", LABELS, perms=20, workers=1)
    by = {r["scorer"]: r for r in rows}
    assert set(by) == {"persistence", "dict", "llm"}
    assert by["llm"]["dll_vs_pers"] > 0 and by["llm"]["dll_vs_dict"] > 0
    assert by["llm"]["placebo_tone_n"] == 20 and np.isfinite(by["llm"]["placebo_labels_p95"])
    assert long["scorer"].n_unique() == 3
    v = rq1.verdict(rows)
    assert v["verdict"] == "untestable" and v["n_powered"] <= 1  # one bank only


def test_rq1_verdict_majority():
    rows = []
    for b, good in [("a", True), ("b", True), ("c", False)]:
        rows.append(
            {
                "bank": b,
                "scorer": "llm",
                "powered": True,
                "dll_vs_pers": 0.2 if good else -0.1,
                "p_vs_pers": 0.001 if good else 0.6,
                "dll_vs_dict": 0.1 if good else -0.1,
                "p_vs_dict": 0.001 if good else 0.6,
                "placebo_tone_p95": 0.01,
                "placebo_labels_p95": 0.01,
            }
        )
    v = rq1.verdict(rows)
    assert v["verdict"] == "supported" and v["n_success"] == 2


def _market(series, start, n, step):
    days = [start + timedelta(days=i) for i in range(n)]
    return pl.DataFrame(
        {"date": days, "series": [series] * n, "close": [100 + step * i for i in range(n)]}
    )


def test_rq2_pipeline_on_synthetic_events():
    rng = np.random.default_rng(3)
    n = 60
    dates = [date(2010, 1, 4) + timedelta(days=14 * i) for i in range(n)]
    # FX responds to the tone surprise: build closes so each event window moves with the surprise
    days = [date(2009, 12, 1) + timedelta(days=i) for i in range(14 * n + 80)]
    close = np.full(len(days), 100.0)
    sur = rng.normal(size=n)
    for d, s in zip(dates, sur, strict=True):
        i = days.index(d)
        close[i + 1 :] *= np.exp(0.01 * s)
    market = pl.DataFrame({"date": days, "series": ["DX-Y.NYB"] * len(days), "close": close})
    docs = pl.DataFrame(
        {
            "doc_id": [f"fed:{d}:statement:en" for d in dates],
            "bank": ["fed"] * n,
            "date": dates,
            "doc_type": ["statement"] * n,
            "language": ["en"] * n,
            "published_at_utc": [
                datetime.combine(d, datetime.min.time(), tzinfo=UTC) + timedelta(hours=19)
                for d in dates
            ],
        }
    )
    rows_sc = []
    for d, s in zip(dates, sur, strict=True):
        for sid, val in (
            ("llm", s),
            ("dict-v1", rng.normal()),
            ("fomc-roberta-repl", rng.normal()),
        ):
            rows_sc.append(
                {
                    "doc_id": f"fed:{d}:statement:en",
                    "bank": "fed",
                    "date": d,
                    "doc_type": "statement",
                    "language": "en",
                    "scorer_id": sid,
                    "variant": "",
                    "prompt_id": None,
                    "model_digest": None,
                    "hawkish_p": 0.4,
                    "dovish_p": 0.3,
                    "neutral_p": 0.3,
                    "index": float(val),
                    "error": None,
                }
            )
    sc = pl.DataFrame(rows_sc)
    ev = rq2.bank_events(docs, sc, market, "fed", LABELS)
    assert {"move_fx", "surprise_llm", "timing"} <= set(ev.columns)
    rows = rq2.bank_rows(ev, market, "fed", LABELS, dates, placebo_draws=50)
    llm_all = next(
        r for r in rows if r["scorer"] == "llm" and r["subset"] == "all" and r["kind"] == "fx"
    )
    assert llm_all["n_events"] >= 40 and llm_all["beta"] > 0 and llm_all["dr2_vs_dict"] > 0
    assert "dr2_vs_transformer" not in llm_all  # no transformer scores in LABELS
    with_tr = LABELS | {"fomc_roberta": ("fomc-roberta-repl", "")}
    ev_tr = rq2.bank_events(docs, sc, market, "fed", with_tr)
    rows_tr = rq2.bank_rows(ev_tr, market, "fed", with_tr, dates, placebo_draws=50)
    llm_tr = next(
        r for r in rows_tr if r["scorer"] == "llm" and r["subset"] == "all" and r["kind"] == "fx"
    )
    assert llm_tr["dr2_vs_transformer"] > 0 and llm_tr["dr2_tr_lo"] > 0
    assert llm_tr["n_vs_transformer"] == llm_tr["n_events"]
    assert llm_tr["dr2_vs_dict"] == pytest.approx(
        llm_all["dr2_vs_dict"]
    )  # unchanged by the extra scorer
    assert all("dr2_vs_transformer" not in r for r in rows_tr if r["scorer"] != "llm")
    v = rq2.verdict(rows)
    assert v["h2a"]["verdict"] == "untestable"  # one cell only


def test_delta_r2_test_detects_difference():
    rng = np.random.default_rng(1)
    x = rng.normal(size=200)
    y = x + rng.normal(scale=0.5, size=200)
    d, lo, _hi, p = rq2.delta_r2_test(y, x, rng.normal(size=200), reps=300)
    assert d > 0.5 and lo > 0 and p < 0.01


def test_rq3_rows_and_verdict():
    rows = []
    rng = np.random.default_rng(0)
    for bank, lang in (("bi", "id"), ("bnm", "ms")):
        for i in range(40):
            d = date(2017, 1, 1) + timedelta(days=30 * i)
            v = rng.normal()
            for language, val in (("en", v), (lang, v + rng.normal(scale=0.05))):
                rows.append(
                    {
                        "doc_id": f"{bank}:{d}:statement:{language}",
                        "bank": bank,
                        "date": d,
                        "doc_type": "statement",
                        "language": language,
                        "scorer_id": "llm",
                        "variant": "",
                        "prompt_id": None,
                        "model_digest": None,
                        "hawkish_p": 0.3,
                        "dovish_p": 0.3,
                        "neutral_p": 0.4,
                        "index": float(np.tanh(val)),
                        "error": None,
                    }
                )
    sc = pl.DataFrame(rows)
    out = rq345.rq3_rows(sc, ["bi", "bnm", "fed"], {"llm": ("llm", "")})
    assert rq345.rq3_verdict(out) == "supported"
    assert next(r for r in out if r["bank"] == "fed")["status"] == "not applicable"


def test_stability_and_classification():
    base = np.linspace(-1, 1, 40)
    st = rq345.stability(np.column_stack([base, base + 0.01, base - 0.01]))
    assert st["alpha"] > 0.99 and st["icc_2_1"] > 0.99
    gold = ["hawkish", "dovish", "neutral"] * 20
    rows = rq345.classification_rows(gold, {"dict": ["neutral"] * 60, "llm": gold})
    llm = next(r for r in rows if r["scorer"] == "llm")
    assert llm["macro_f1"] == pytest.approx(1.0) and llm["df1_lo"] > 0


def test_stability_matrix_pivot():
    sc = pl.DataFrame(
        {
            "unit": ["a", "b", "a", "b"],
            "prompt_id": ["P1@1", "P1@1", "P2@2", "P2@2"],
            "variant": ["", "", "", ""],
            "index": [0.1, 0.2, 0.15, 0.25],
        }
    )
    m = rq345.stability_matrix(sc, "unit", {"P1": ("P1", ""), "P2": ("P2", "")})
    assert m.shape == (2, 2)


def test_rq5_rows():
    silver = pl.DataFrame(
        {"bank": ["mas"] * 60, "lang": ["en"] * 60, "label": ["hawkish", "dovish", "neutral"] * 20}
    )
    rows = rq345.rq5_rows({"dict": 0.5}, silver, {"dict": ["neutral"] * 60})
    assert rows[0]["group"] == "mas-en" and rows[0]["powered"] and rows[0]["drop"] > 0


def test_rq4c_rules():
    pred = pl.DataFrame(
        {
            "bank": ["a"] * 40 * 2,
            "date": [date(2025, 6, 1) + timedelta(days=i) for i in range(40)] * 2,
            "scorer": ["llm"] * 40 + ["dict"] * 40,
            "logloss": [0.5] * 40 + [0.7] * 40,
        }
    )
    post = rq345.post_cutoff_dll(pred, date(2025, 4, 29), "llm", "dict")
    assert post["status"] == "ok" and post["dll"] == pytest.approx(0.2)
    assert rq345.survives_post_cutoff(0.2, 0.1, 0.3, post) == "survives"
    assert rq345.survives_post_cutoff(0.2, 0.1, 0.3, {"status": "inconclusive"}) == "inconclusive"
    assert rq345.survives_masked(0.2, 0.1, 0.15, 0.05, 0.25)
    assert not rq345.survives_masked(0.2, 0.1, 0.05, 0.01, 0.1)  # < 50 % of the effect
    assert (
        rq345.post_cutoff_dll(pred.head(0), date(2025, 4, 29), "llm", "dict")["status"]
        == "inconclusive"
    )
