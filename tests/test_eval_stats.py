import numpy as np
import polars as pl
import pytest

from cbtone.eval import rules
from cbtone.eval.rolling import add_features, auroc_hike_vs_cut, initial_window, rolling_origin
from cbtone.eval.stats import (
    block_bootstrap_ci,
    cross_lingual,
    holm,
    icc_2_1,
    krippendorff_alpha_interval,
    macro_f1,
    macro_f1_ci,
    mean_diff_ci,
)


def test_block_bootstrap_mean_ci_covers_truth():
    rng = np.random.default_rng(0)
    x = rng.normal(1.0, 1.0, size=400)
    point, lo, hi = mean_diff_ci(x, reps=500)
    assert lo < 1.0 < hi and lo < point < hi
    with pytest.raises(ValueError):
        block_bootstrap_ci(np.mean, [1.0, 2.0], [1.0])


def test_holm_matches_textbook():
    adj = holm([0.01, 0.04, 0.03, 0.005])
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_icc_perfect_and_noise():
    base = np.linspace(-1, 1, 30)
    assert icc_2_1(np.column_stack([base, base, base])) == pytest.approx(1.0)
    rng = np.random.default_rng(1)
    noisy = np.column_stack([rng.normal(size=200) for _ in range(3)])
    assert abs(icc_2_1(noisy)) < 0.1
    with pytest.raises(ValueError):
        icc_2_1(np.array([[1.0, np.nan], [2.0, 3.0]]))


def test_krippendorff_known_values():
    base = np.linspace(-1, 1, 50)
    assert krippendorff_alpha_interval(np.column_stack([base, base])) == pytest.approx(1.0)
    # Krippendorff (2004) style: alpha ~ 0 for unrelated coders, missing values tolerated
    rng = np.random.default_rng(2)
    r = np.column_stack([rng.normal(size=300), rng.normal(size=300)])
    r[0, 1] = np.nan
    assert abs(krippendorff_alpha_interval(r)) < 0.12
    assert np.isnan(krippendorff_alpha_interval(np.array([[1.0, np.nan]])))
    # alpha close to ICC on clean data with small noise
    noisy = np.column_stack([base, base + rng.normal(0, 0.1, 50)])
    assert krippendorff_alpha_interval(noisy) == pytest.approx(icc_2_1(noisy), abs=0.03)


def test_cross_lingual_metrics():
    a = [0.5, -0.5, 0.2, 0.0, 0.9]
    b = [0.4, 0.5, 0.25, 0.05, 0.8]  # one strong flip (pair 2)
    r = cross_lingual(a, b)
    assert r.n == 5 and r.flip_rate == pytest.approx(0.2)
    with pytest.raises(ValueError):
        cross_lingual([1.0], [1.0])


def test_macro_f1_and_ci():
    t = ["hawkish", "dovish", "neutral"] * 30
    assert macro_f1(t, t) == pytest.approx(1.0)
    p = ["neutral"] * 90
    point, lo, _hi = macro_f1_ci(t, t, y_pred_ref=p, reps=200)
    assert point > 0.7 and lo > 0


def _bank(n=120, seed=0, informative=True):
    rng = np.random.default_rng(seed)
    tone = rng.normal(size=n)
    nxt = []
    for v in tone:
        z = (1.5 * v if informative else 0.0) + rng.logistic()
        nxt.append("hike" if z > 1.2 else "cut" if z < -1.2 else "hold")
    last = ["hold", *nxt[:-1]]
    dates = pl.date_range(
        pl.date(2000, 1, 1), pl.date(2000, 1, 1) + pl.duration(days=n - 1), eager=True
    )
    return add_features(
        pl.DataFrame({"date": dates, "tone": tone, "next_direction": nxt, "last_direction": last})
    )


def test_rolling_origin_beats_persistence_when_tone_is_informative():
    df = _bank()
    model = rolling_origin(df, ["tone", "dtone"])
    base = rolling_origin(df, None)
    assert model.height == base.height == 120 - initial_window(120)
    assert model["logloss"].mean() < base["logloss"].mean()
    assert auroc_hike_vs_cut(model) > 0.75
    assert (model["p_cut"] + model["p_hold"] + model["p_hike"]).to_numpy() == pytest.approx(1.0)


def test_rolling_origin_falls_back_and_short_series():
    df = _bank(n=60, informative=False).with_columns(next_direction=pl.lit("hold"))
    out = rolling_origin(df, ["tone"])
    assert out["fallback"].all()  # only one class in training: ordered logit impossible
    assert rolling_origin(_bank(n=20), ["tone"]).height == 0
    assert np.isnan(auroc_hike_vs_cut(out))


def test_rules():
    assert rules.rq1_powered(40, 8, 8) and not rules.rq1_powered(40, 7, 8)
    v = rules.majority(
        {"a": True, "b": True, "c": False, "d": False},
        {"a": True, "b": True, "c": True, "d": False},
    )
    assert (v.verdict, v.n_powered, v.n_success) == ("supported", 3, 2)
    assert rules.majority({"a": True}, {"a": True, "b": True}).verdict == "untestable"
    assert (
        rules.majority(
            {"a": False, "b": True, "c": False}, {"a": True, "b": True, "c": True}
        ).verdict
        == "refuted"
    )
    assert rules.sanity_flags("x", 1.0) == ["x: exactly 1.0"]
    assert rules.sanity_flags("c", 0.97, "corr")
    assert rules.sanity_flags("fomc_f1_dictionary", 0.2)
    assert rules.sanity_flags("fomc_f1_dictionary", 0.45) == []
    assert rules.sanity_flags("n", float("nan")) == ["n: NaN"]
    assert rules.ci_excludes_zero_positive(0.1, 0.3) and not rules.ci_excludes_zero_positive(
        -0.1, 0.3
    )
    assert rules.rq2_powered(30) and rules.rq3_powered(30)
