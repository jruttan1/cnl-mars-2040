"""The 'lab'. The ONLY code allowed to see the true dose."""


def read(marker, true_mGy, hrs_after, rng):
    mu = marker.expected(true_mGy, hrs_after)
    return max(float(rng.normal(mu, marker.sd(mu))), 0.0)