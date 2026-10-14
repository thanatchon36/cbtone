"""Fast 3-class ordered logit (cut < hold < hike) for rolling-origin evaluation and placebos.

Model: P(y <= j | x) = sigma(theta_j - x.beta), j in {0, 1}, theta_1 = theta_0 + exp(delta).
Fitted by damped Newton-Raphson on the penalised log-likelihood with an analytic gradient and a
finite-difference Hessian (p + 2 <= 8 parameters), warm-startable from a previous fit. A tiny ridge
penalty (``RIDGE`` x ||beta||^2) keeps estimates finite under (quasi-)separation, which small
central-bank samples hit often; on well-posed data the fit matches statsmodels' OrderedModel
(tests/test_eval_ordinal.py). Used instead of statsmodels because the pre-registered placebos need
~10^6 fits (RESEARCH_QUESTIONS.md §0.6).
"""

from __future__ import annotations

import numpy as np

RIDGE = 1e-3
_EPS = 1e-12


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return np.asarray(0.5 * (1.0 + np.tanh(0.5 * z)))


def _unpack(params: np.ndarray, p: int) -> tuple[np.ndarray, float, float]:
    beta = params[:p]
    t0 = float(params[p])
    t1 = t0 + float(np.exp(params[p + 1]))
    return beta, t0, t1


def _probs(x: np.ndarray, params: np.ndarray) -> np.ndarray:
    beta, t0, t1 = _unpack(params, x.shape[1])
    eta = x @ beta
    c0 = _sigmoid(t0 - eta)
    c1 = _sigmoid(t1 - eta)
    return np.column_stack([c0, c1 - c0, 1.0 - c1])


def neg_loglik(params: np.ndarray, x: np.ndarray, y: np.ndarray) -> float:
    pr = _probs(x, params)[np.arange(len(y)), y]
    beta = params[: x.shape[1]]
    return float(-np.sum(np.log(np.maximum(pr, _EPS))) + RIDGE * beta @ beta)


def _grad(params: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = x.shape[1]
    beta, t0, t1 = _unpack(params, p)
    eta = x @ beta
    thr = np.array([-np.inf, t0, t1, np.inf])
    upper = thr[y + 1] - eta
    lower = thr[y] - eta
    fu = np.where(np.isfinite(upper), _sigmoid(upper) * (1 - _sigmoid(upper)), 0.0)
    fl = np.where(np.isfinite(lower), _sigmoid(lower) * (1 - _sigmoid(lower)), 0.0)
    cu = np.where(np.isfinite(upper), _sigmoid(upper), 1.0)
    cl = np.where(np.isfinite(lower), _sigmoid(lower), 0.0)
    pr = np.maximum(cu - cl, _EPS)
    # d loglik / d theta_k = sum over obs whose upper (lower) threshold is theta_k of fu/pr (-fl/pr)
    g_t0 = np.sum(np.where(y == 0, fu / pr, 0.0)) - np.sum(np.where(y == 1, fl / pr, 0.0))
    g_t1 = np.sum(np.where(y == 1, fu / pr, 0.0)) - np.sum(np.where(y == 2, fl / pr, 0.0))
    g_beta = -(x * ((fu - fl) / pr)[:, None]).sum(axis=0)
    e = float(np.exp(params[p + 1]))
    grad_ll = np.concatenate([g_beta, [g_t0 + g_t1, g_t1 * e]])
    grad_pen = np.concatenate([2 * RIDGE * beta, [0.0, 0.0]])
    return np.asarray(-grad_ll + grad_pen)  # gradient of the *negative* penalised loglik


def init_params(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Thresholds from marginal class frequencies, beta = 0."""
    freq = np.bincount(y, minlength=3) + 1.0
    cum = np.cumsum(freq)[:2] / freq.sum()
    t0, t1 = np.log(cum / (1 - cum))
    return np.concatenate([np.zeros(x.shape[1]), [t0, np.log(max(t1 - t0, 1e-3))]])


def fit(
    x: np.ndarray,
    y: np.ndarray,
    init: np.ndarray | None = None,
    max_iter: int = 50,
    tol: float = 1e-7,
) -> np.ndarray:
    """Penalised MLE by damped Newton; returns params (beta..., theta_0, log gap)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=int)
    params = init_params(x, y) if init is None else np.array(init, dtype=float)
    k = len(params)
    h = 1e-5
    f = neg_loglik(params, x, y)
    for _ in range(max_iter):
        g = _grad(params, x, y)
        if np.max(np.abs(g)) < tol:
            break
        hess = np.empty((k, k))
        for j in range(k):
            step = np.zeros(k)
            step[j] = h
            hess[:, j] = (_grad(params + step, x, y) - g) / h
        hess = 0.5 * (hess + hess.T) + 1e-8 * np.eye(k)
        try:
            direction = -np.linalg.solve(hess, g)
        except np.linalg.LinAlgError:
            direction = -g
        if g @ direction >= 0:  # not a descent direction: fall back to gradient step
            direction = -g
        t = 1.0
        while t > 1e-6:
            cand = params + t * direction
            fc = neg_loglik(cand, x, y)
            if fc <= f - 1e-4 * t * abs(g @ direction):
                break
            t *= 0.5
        else:
            break
        if abs(f - fc) < 1e-10:
            params, f = cand, fc
            break
        params, f = cand, fc
    return params


def predict_proba(x: np.ndarray, params: np.ndarray) -> np.ndarray:
    pr = np.clip(_probs(np.asarray(x, dtype=float), params), _EPS, 1.0)
    return np.asarray(pr / pr.sum(axis=1, keepdims=True))
