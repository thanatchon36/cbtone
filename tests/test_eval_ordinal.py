import numpy as np
import pytest

from cbtone.eval import ordinal


def _data(n=400, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 2))
    z = x @ np.array([1.2, -0.7]) + rng.logistic(size=n)
    y = np.digitize(z, [-1.0, 1.0])
    return x, y


def test_gradient_matches_finite_differences():
    x, y = _data(80)
    params = np.array([0.3, -0.2, -0.5, np.log(1.5)])
    g = ordinal._grad(params, x, y)
    num = np.array([
        (ordinal.neg_loglik(params + e, x, y) - ordinal.neg_loglik(params - e, x, y)) / 2e-6
        for e in np.eye(4) * 1e-6
    ])
    assert g == pytest.approx(num, rel=1e-4, abs=1e-4)


def test_matches_statsmodels():
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    x, y = _data()
    params = ordinal.fit(x, y)
    res = OrderedModel(y, x, distr="logit").fit(method="bfgs", disp=False, maxiter=500)
    sm_probs = np.asarray(res.model.predict(res.params, exog=x[:20]))
    ours = ordinal.predict_proba(x[:20], params)
    assert ours == pytest.approx(sm_probs, abs=2e-3)
    assert params[:2] == pytest.approx(res.params[:2], abs=0.02)


def test_separation_stays_finite_and_warm_start_agrees():
    x = np.array([[-2.0], [-1.0], [0.0], [1.0], [2.0], [3.0]])
    y = np.array([0, 0, 1, 1, 2, 2])  # perfectly separated
    params = ordinal.fit(x, y)
    assert np.all(np.isfinite(params))
    xs, ys = _data(300, seed=5)
    cold = ordinal.fit(xs, ys)
    warm = ordinal.fit(xs, ys, init=cold + 0.05)
    assert warm == pytest.approx(cold, abs=1e-3)
    pr = ordinal.predict_proba(xs, cold)
    assert pr.sum(axis=1) == pytest.approx(1.0)
