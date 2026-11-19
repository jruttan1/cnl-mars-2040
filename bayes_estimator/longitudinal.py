"""Exploratory history-aware biomarker likelihoods, shared by C and D.

Slide anchors inform response shapes. Interpolation, dose linearity, observation
noise and the blood/BFO proxy are experimental assumptions, not SPE calibration.
"""
from dataclasses import dataclass
import hashlib

import numpy as np
from scipy.special import logsumexp


@dataclass(frozen=True)
class Marker:
    name: str
    group: str
    ages_h: tuple[float, ...]
    responses_per_Gy: tuple[float, ...]
    baseline: float = 1.0
    depletion: bool = False

    def primitive(self, ages):
        ages = np.asarray(ages, dtype=float)
        result = np.zeros_like(ages)
        for left, right, low, high in zip(self.ages_h[:-1], self.ages_h[1:],
                                          self.responses_per_Gy[:-1], self.responses_per_Gy[1:]):
            elapsed = np.clip(ages - left, 0, right - left)
            result += low * elapsed + (high - low) * elapsed ** 2 / (2 * (right - left))
        return result

    def signal(self, sampled_h, starts, ends, absorbed_mGy):
        doses = np.asarray(absorbed_mGy, dtype=float)
        if len(starts) == 0:
            return np.full(doses.shape[1:] or (), self.baseline)
        starts, ends = np.asarray(starts), np.asarray(ends)
        weights = (self.primitive(sampled_h - starts) - self.primitive(sampled_h - ends)) / (ends - starts)
        response = np.tensordot(weights, doses, axes=(0, 0)) / 1000
        return self.baseline * np.exp(-response) if self.depletion else self.baseline + response


MARKERS = {
    'H2AX': Marker('H2AX', 'foci', (0.5, 2, 8), (11, 8.93, 3.89), baseline=0.1),
    '53BP1': Marker('53BP1', 'foci', (0.5, 2), (11, 8.93), baseline=0.1),
    'lymphocytes': Marker('lymphocytes', 'counts', (12, 24, 48), (0.25, 0.5, 0.5), baseline=2, depletion=True),
    'AEN': Marker('AEN', 'genes', (2, 4, 8), (0.6, 3, 4.85)),
    'TRAF4': Marker('TRAF4', 'genes', (4, 8), (2.3, 0.9)),
    'DDB2': Marker('DDB2', 'genes', (4, 8, 24), (0.55, 3.6, 3)),
    'TRIAP1': Marker('TRIAP1', 'genes', (8, 12, 24), (2.45, 2.1, 1.35)),
    'FDXR': Marker('FDXR', 'genes', (24, 48), (1, 1)),
}
GENES = ('AEN', 'TRAF4', 'DDB2', 'TRIAP1')


@dataclass(frozen=True)
class Reading:
    astronaut: str
    marker: str
    sampled_h: float
    available_h: float
    value: float


def normal_draw(seed, *identity):
    digest = hashlib.sha256(repr((seed, identity)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], 'little')).normal()


def generate_reading(name, marker, sampled_h, available_h, starts, ends, true_doses, config):
    """Trusted observation generator; only this side of the boundary sees true doses."""
    expected = float(marker.signal(sampled_h, starts, ends, true_doses))
    noise = (config.group_log_sd * normal_draw(config.seed, name, marker.group)
             + config.individual_log_sd * normal_draw(config.seed, name, marker.name)
             + config.reading_log_sd * normal_draw(config.seed, name, marker.name, sampled_h))
    return Reading(name, marker.name, sampled_h, available_h, expected * np.exp(noise))


def log_likelihood(readings, starts, ends, candidate_doses, config):
    """Evaluate one astronaut's latest returned sample per marker."""
    count = candidate_doses.shape[1]
    latest = {}
    for reading in readings:
        if reading.marker not in latest or reading.sampled_h > latest[reading.marker].sampled_h:
            latest[reading.marker] = reading
    if not latest:
        return np.zeros(count), False
    selected = list(latest.values())
    predicted = np.array([MARKERS[reading.marker].signal(reading.sampled_h, starts, ends, candidate_doses)
                          for reading in selected])
    residual = np.log([reading.value for reading in selected])[:, None] - np.log(predicted)
    groups = np.array([MARKERS[reading.marker].group for reading in selected])
    covariance = (groups[:, None] == groups[None, :]) * float(config.group_log_sd) ** 2
    covariance += np.eye(len(selected)) * (config.individual_log_sd ** 2 + config.reading_log_sd ** 2)
    distance = np.sum(residual * np.linalg.solve(covariance, residual), axis=0)
    conflict = float(distance.min()) > len(selected) * config.conflict_standard_deviations ** 2
    return -0.5 * distance, conflict


def normalize_posterior(prior, likelihood):
    log_weights = np.log(prior) + likelihood
    return np.exp(log_weights - logsumexp(log_weights))


def posterior(readings, starts, ends, candidate_doses, config, prior=None):
    """Use the latest returned sample per marker, not repeated independent evidence."""
    if prior is None:
        count = candidate_doses.shape[1]
        prior = np.full(count, 1 / count)
    likelihood, conflict = log_likelihood(readings, starts, ends, candidate_doses, config)
    if conflict or not readings:
        return prior, conflict
    return normalize_posterior(prior, likelihood), False


def quantile(values, weights, probability):
    order = np.argsort(values)
    position = np.searchsorted(np.cumsum(np.asarray(weights)[order]), probability)
    return float(np.asarray(values)[order[min(position, len(order) - 1)]])
