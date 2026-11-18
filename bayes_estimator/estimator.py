"""Bayesian dose estimator. Sees lab results only, never the true dose.

Physical dosimetry is unavailable in this case, so by default the estimator
starts from 'no idea' (flat prior) and lets the biomarkers alone decide."""
import numpy as np
from scipy.stats import norm, lognorm
from . import markers as M

D = np.linspace(0, 3000, 3001)   # candidate doses, mGy


def log_prior(est_mGy=None, gsd=2.0):
    """Default: flat (every dose 0-3000 mGy equally likely), because there is
    no working dosimeter to start from. Optional: a wide log-normal around an
    outside estimate (e.g. a storm forecast), if one ever exists."""
    if est_mGy is None:
        return np.zeros_like(D)
    return lognorm.logpdf(D + 1, s=np.log(gsd), scale=est_mGy + 1)


def log_likelihood(marker, value, hrs_after):
    lo, hi = marker.window_h
    if not lo <= hrs_after <= hi:
        return np.zeros_like(D)          # outside its window: tells us nothing
    mu = marker.expected(D, hrs_after)
    return norm.logpdf(value, mu, marker.sd(mu))


def estimate(readings, est_mGy=None):
    """readings: list of (marker, value, hrs_after) whose results are already back."""
    lp = log_prior(est_mGy)
    for marker, value, hrs in readings:
        lp = lp + log_likelihood(marker, value, hrs)
    p = np.exp(lp - lp.max())
    p /= p.sum()
    cdf = np.cumsum(p)
    q = lambda x: float(D[min(np.searchsorted(cdf, x), len(D) - 1)])
    return {"mean": float((p * D).sum()), "lo95": q(0.025),
            "upper95": q(0.95), "posterior": p}


def decision(cumulative_upper95_mGy):
    """Decide on the UPPER bound so uncertainty always errs toward safety."""
    frac = M.RBE_BFO * cumulative_upper95_mGy / M.NASA_30D_LIMIT_mGyEq
    if frac < 0.6:
        return "proceed"
    if frac < 0.9:
        return "rotate crew"
    if frac < 1.0:
        return "shelter/delay"
    return "abort / treat"