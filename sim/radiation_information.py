"""Independent forecast inputs and delayed observations, isolated from policy code."""
from dataclasses import asdict, dataclass, replace
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.special import ndtr

from radiation.anatomical_environment import ORGANS, load_environment
from .background_radiation import interval as gcr_interval
from .anatomical_reference import dose_vector
from .informed_config import InformedConfig
from bayes_estimator.longitudinal import (GENES, MARKERS, generate_reading, log_likelihood,
                                         normalize_posterior, quantile, normal_draw)

D_IN_EVA_MARKERS = ('H2AX', '53BP1', *GENES)


class ForecastEnsemble:
    """A configured forecast, never constructed by inspecting the true scenario."""
    def __init__(self, spec):
        self.spec = spec
        templates = (spec.historical_template, *spec.alternative_templates)
        self.members = tuple((template, offset, factor) for template in templates
                             for offset in spec.timing_offsets_h for factor in spec.magnitude_factors)
        weights = spec.magnitude_weights or (1.,) * len(spec.magnitude_factors)
        prior = np.tile(weights, len(templates) * len(spec.timing_offsets_h))
        self.prior = prior / prior.sum()
        self.prior.setflags(write=False)
        self.tables = {}
        severity = int(spec.severity.rsplit('-', 1)[1])
        for template in templates:
            source = load_environment(template)
            source = source[source.scenario.eq(spec.severity) & source.timing_variant.eq('gt10MeV__log_linear')]
            if source.empty:
                raise ValueError('Unknown forecast severity')
            for depth in (0.4, 20.0):
                frame = source[source.shielding_g_cm2.eq(depth)].sort_values('hour')
                totals = np.array(dose_vector(spec.anatomy, severity, depth)) * spec.spe_scale
                weights = frame.normalized_bin_weight.to_numpy() / frame.bin_duration_h.to_numpy()
                rates = weights[:, None] * totals
                durations = frame.bin_duration_h.to_numpy()
                edges = np.r_[frame.hour.iloc[0], frame.hour_end.to_numpy()]
                self.tables[template, depth] = (edges, np.vstack((np.zeros(4), np.cumsum(rates * durations[:, None], axis=0))))
        self.start_h = max(self.tables[t, 0.4][0][0] - spec.profile_origin_h + offset for t, offset, _ in self.members)
        self.end_h = min(self.tables[t, 0.4][0][-1] - spec.profile_origin_h + offset for t, offset, _ in self.members)
        if self.start_h > 0 or self.end_h <= 0:
            raise ValueError('Forecast ensemble must cover mission hour zero')
        self.rate_changes_h = np.unique(np.concatenate([
            self.tables[template, 0.4][0] - spec.profile_origin_h + offset
            for template, offset in dict.fromkeys((t, o) for t, o, _ in self.members)
        ]))

    @lru_cache(maxsize=8192)
    def interval(self, start, end, depth):
        if not self.start_h <= start <= end <= self.end_h:
            raise ValueError('Requested interval exceeds forecast coverage')
        doses = []
        for template, offset, factor in self.members:
            edges, cumulative = self.tables[template, depth]
            bounds = np.array([start, end]) + self.spec.profile_origin_h - offset
            doses.append([factor * np.diff(np.interp(bounds, edges, cumulative[:, column]))[0]
                          for column in range(4)])
        result = np.array(doses)
        # Same explicitly configured background in every forecast member; storm
        # timing/magnitude perturbations must not shift or amplify cosmic rays.
        result += gcr_interval(start, end, depth, self.spec.gcr_scale)
        result.setflags(write=False)
        return result

    @lru_cache(maxsize=8192)
    def current_rate(self, hour, depth):
        """Dose rate in the current bin of each estimated storm, including GCR."""
        if not self.start_h <= hour <= self.end_h:
            raise ValueError('Current rate requested outside forecast coverage')
        rates = []
        for template, offset, factor in self.members:
            edges, cumulative = self.tables[template, depth]
            profile_hour = hour + self.spec.profile_origin_h - offset
            index = min(len(edges) - 2, max(0, np.searchsorted(edges, profile_hour, side='right') - 1))
            rates.append(factor * (cumulative[index + 1] - cumulative[index])
                         / (edges[index + 1] - edges[index]))
        result = np.array(rates) + gcr_interval(0, 1, depth, self.spec.gcr_scale)
        result.setflags(write=False)
        return result


@dataclass(frozen=True)
class ExposureOption:
    astronaut: str
    departure_h: float
    end_h: float
    upper_mGy_eq: tuple[float, float, float]
    acceptable: bool
    reason: str
    reference_exceedance_probability: float = 0.0
    forecast_exceedance_probability: float = 0.0
    forecast_upper_reference_fraction: float = 0.0
    repairs: tuple[str, ...] = ()  # Repairs whose remaining work this departure option sizes; empty means any.


@dataclass(frozen=True)
class RadiationObservation:
    strategy: str
    options: tuple[ExposureOption, ...]
    current: tuple[ExposureOption, ...]
    pending_results: int
    forecast_end_h: float
    references: tuple[float, float, float] = InformedConfig().references
    launch_risk_tolerance: float = 0.05
    post_eva_review_pending: tuple[str, ...] = ()
    live_markers: tuple[str, ...] = ()
    immediate_return: ExposureOption | None = None
    forecast_launch_veto: bool = True
    radiation_held_repairs: tuple[str, ...] = ()
    matched_current_rate: bool = False
    restart_ready_repairs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RestartReview:
    return_h: float
    abort_upper_fraction: float
    planned_hours: float = 0.0


class RadiationInformation:
    """Trusted sensor adapter; returns frozen estimates, never truth or a simulator handle."""
    def __init__(self, strategy, config, names):
        self.strategy, self.config = strategy, config
        # Policies that assume today's estimated rate persists through the EVA and return.
        self.current_rate_projection = (config.matched_current_rate
                                        or (strategy == 'B' and config.b_projection == 'current_rate'))
        self.forecast = ForecastEnsemble(config.forecast)
        self.histories = {name: [] for name in names}
        self.pending, self.returned, self.scheduled = [], [], []
        self.processed = self.finished = 0
        self.next_sampling_h = 0.0
        self.next_cabin_sampling = {name: 0.0 for name in names}
        self.log, self.estimate_log = [], []
        self.weights = {}
        self.conflicts = {}
        self.preflight_samples = set()
        self.reassessment_witnesses = {}
        self.radiation_held_repairs = set()
        self.restart_reviews = {}
        self.post_eva_reviews = {}
        self.likelihood_cache = {}
        unknown = (set(dict(config.instrument_delays_h)) | set(config.unavailable_markers)) - set(MARKERS)
        if unknown:
            raise ValueError(f'Unknown instrument delays: {sorted(unknown)}')

    def record_radiation_abort(self, name, now, return_h, *, repair=None, planned_hours=None, eva_depth=0.4):
        """Crew-wide restart review, using observations only, never true dose.

        Witness weights describe shared storm hypotheses, not the witness's personal
        accumulated dose. Prospective replacement crew retain their own histories.
        """
        self.reassessment_witnesses[name] = (now, return_h)
        if (self.strategy == 'C' or self.config.matched_current_rate or self.config.retry_after_abort) and repair is not None:
            self.radiation_held_repairs.add(repair)
            if self.config.restart_quiet_hours is not None and planned_hours is not None and now <= self.forecast.end_h:
                _, upper = self._environmental_restart_risk(now, planned_hours, eva_depth)
                self.restart_reviews[repair] = RestartReview(return_h, upper, planned_hours)

    def _environmental_restart_risk(self, now, planned_hours, eva_depth):
        # Use the common forecast prior and a full EVA's added dose, independent
        # of crew selection, previous personal exposure and biological readings.
        fractions = self.forecast.current_rate(now, eva_depth)[:, 1:] * planned_hours / self.config.references
        worst_organ = fractions.max(axis=1)
        prior = self.forecast.prior
        return (float(prior @ (worst_organ >= 1)),
                quantile(worst_organ, prior, self.config.upper_probability))

    def _restart_ready(self, now, operational, eva_depth):
        reviews = self.restart_reviews
        if not reviews:
            return ()
        start = now - self.config.restart_quiet_hours
        candidates = [repair for repair in operational.outstanding_repairs
                      if repair in reviews and start >= reviews[repair].return_h]
        if not candidates:
            return ()
        # The hourly profiles are piecewise constant. Check every estimated rate
        # in the cooldown window, including between simulation decision times.
        changes = self.forecast.rate_changes_h
        edges = changes[np.searchsorted(changes, start, side='right'):np.searchsorted(changes, now, side='left')]
        # Sample between breakpoints to avoid rounding across a fractional profile boundary.
        boundaries = np.r_[start, edges, now]
        checks = np.r_[(boundaries[:-1] + boundaries[1:]) / 2, now]
        tolerance = (1 - self.config.upper_probability) * self.config.restart_risk_fraction
        remaining = dict(operational.repair_work_remaining_h)
        ready = []
        for repair in candidates:
            # Each repair is assessed for the work it still needs, so a mostly finished
            # task is not judged as a full EVA; improvement is compared per planned hour.
            work = remaining.get(repair)
            planned = (operational.planned_eva_hours if work is None else
                       self.projected_duration(work, operational.return_to_airlock_h))
            risks = [self._environmental_restart_risk(hour, planned, eva_depth) for hour in checks]
            if any(probability > tolerance + 1e-12 for probability, _ in risks):
                continue
            review = reviews[repair]
            upper = max(upper for _, upper in risks)
            previous = review.abort_upper_fraction / review.planned_hours if review.planned_hours else review.abort_upper_fraction
            current = upper / planned if review.planned_hours else upper
            if current < previous:
                ready.append(repair)
        return tuple(ready)

    def _sample(self, state, name, marker_name):
        sampled = state.current_mission_time
        available = ndtr(normal_draw(self.config.seed, name, marker_name, sampled, 'availability'))
        if marker_name in self.config.unavailable_markers or available >= self.config.measurement_availability:
            self.log.append(dict(event='unavailable', astronaut=name, marker=marker_name, sampled_h=sampled))
            return
        marker = MARKERS[marker_name]
        history = [record for record in state.exposure_history if record['astronaut'] == name]
        starts = [record['start_hour'] for record in history]
        ends = [record['end_hour'] for record in history]
        truth = [record['bfo_absorbed_dose_mGy'] for record in history]
        default_delay = self.config.conventional_lab_delay_h if self.strategy == 'C' else 0.0
        # Processing begins at collection; biological response and follow-up timing
        # remain separate. Explicit per-marker overrides still take precedence.
        if marker_name == 'lymphocytes':
            default_delay = self.config.lymphocyte_processing_delay_h
        elif self.strategy == 'D' and marker_name in ('H2AX', '53BP1'):
            default_delay = self.config.automated_foci_delay_h
        delay = dict(self.config.instrument_delays_h).get(marker_name, default_delay)
        reading = generate_reading(name, marker, sampled, sampled + self.config.sampling_burden_h + delay,
                                   starts, ends, truth, self.config)
        self.pending.append(reading)
        self.log.append(dict(event='sampled', **asdict(reading)))

    def _collect(self, state, name, markers):
        for marker in markers:
            self._sample(state, name, marker)
        burden = self.config.sampling_burden_h
        if burden == 0 or all(marker in self.config.unavailable_markers for marker in markers):
            return
        now = state.current_mission_time
        active = state.active_eva
        if active and active.astronaut.name == name and active.return_started_h is None:
            active.scheduled_end_time += burden
            active.sampling_busy_until_h = now + burden
        else:
            person = next(person for person in state.astronauts if person.name == name)
            person.available_from = max(now, person.available_from) + burden
        self.log.append(dict(event='sampling_burden', astronaut=name, sampled_h=now, duration_h=burden))

    def projected_duration(self, work_hours, return_hours):
        uses_panels = (self.strategy == 'D' and self.config.in_eva_monitoring
                       and not set(D_IN_EVA_MARKERS) <= set(self.config.unavailable_markers))
        burden = self.config.sampling_burden_h if uses_panels else 0
        panels = np.ceil(work_hours / (self.config.sampling_step_h - burden))
        return float(work_hours + panels * burden + return_hours)

    def before_launch(self, state, astronaut):
        key = (astronaut, len(state.progress))
        if self.strategy == 'D' and key not in self.preflight_samples:
            self.preflight_samples.add(key)
            self._collect(state, astronaut, ('H2AX', '53BP1'))

    def update(self, state):
        now = state.current_mission_time
        for record in state.exposure_history[self.processed:]:
            start, end = record['start_hour'], record['end_hour']
            if end > self.forecast.end_h:
                continue
            doses = self.forecast.interval(start, end, record['shielding_g_cm2'])
            self.histories[record['astronaut']].append((start, end, doses))
        self.processed = len(state.exposure_history)
        for eva in state.progress[self.finished:]:
            if self.strategy in ('C', 'D'):
                self.post_eva_reviews[eva.astronaut.name] = eva.reported_end_time
                self.scheduled.append((eva.reported_end_time + 0.5, eva.astronaut.name, 'H2AX'))
                for delay in (12, 24, 48):
                    self.scheduled.append((eva.reported_end_time + delay, eva.astronaut.name, 'lymphocytes'))
                if self.strategy == 'D':
                    self.scheduled.append((eva.reported_end_time + 0.5, eva.astronaut.name, '53BP1'))
        self.finished = len(state.progress)
        outside = state.active_eva.astronaut.name if state.active_eva else None
        for scheduled in tuple(self.scheduled):
            due, name, marker = scheduled
            person = next(person for person in state.astronauts if person.name == name)
            if due <= now and name != outside and person.available_from <= now:
                self._collect(state, name, (marker,))
                self.scheduled.remove(scheduled)
        # Shared scheduled cabin panels allow C/D to learn while sheltering, not
        # only after committing to an EVA. Delays and marker kinetics still apply.
        if self.strategy in ('C', 'D'):
            for person in state.astronauts:
                name = person.name
                if (now >= self.next_cabin_sampling[name] and name != outside
                        and person.available_from <= now):
                    markers = ('H2AX', 'lymphocytes')
                    # Avoid duplicating a scheduled post-EVA sample at the same time.
                    already = {r.marker for r in self.pending + self.returned
                               if r.astronaut == name and r.sampled_h == now}
                    markers = tuple(marker for marker in markers if marker not in already)
                    if markers:
                        self._collect(state, name, markers)
                    self.next_cabin_sampling[name] = now + self.config.cabin_sampling_interval_h
        if now >= self.next_sampling_h:
            if self.strategy == 'D':
                for name in self.histories:
                    if name == outside:
                        if self.config.in_eva_monitoring and state.active_eva.return_started_h is None:
                            self._collect(state, name, D_IN_EVA_MARKERS)
                    elif now >= 24 and next(person.available_from for person in state.astronauts if person.name == name) <= now:
                        self._collect(state, name, ('FDXR',))
            self.next_sampling_h = now + self.config.sampling_step_h
        for reading in tuple(self.pending):
            if reading.available_h <= now:
                self.returned.append(reading)
                self.pending.remove(reading)
                self.log.append(dict(event='returned', received_h=now, **asdict(reading)))
        likelihoods = {}
        latest = {name: {} for name in self.histories}
        for reading in self.returned:
            markers = latest[reading.astronaut]
            if reading.marker not in markers or reading.sampled_h > markers[reading.marker].sampled_h:
                markers[reading.marker] = reading
        for name, history in self.histories.items():
            readings = tuple(latest[name].values())
            cached = self.likelihood_cache.get(name)
            # An arrived sample depends only on the history through collection.
            # Later exposure cannot change the likelihood of that sample.
            if cached is not None and cached[0] == readings:
                _, likelihood, conflict = cached
            else:
                starts, ends, doses = self._arrays(history)
                likelihood, conflict = log_likelihood(readings, starts, ends, doses[:, :, 0], self.config)
                self.likelihood_cache[name] = (readings, likelihood, conflict)
            self.conflicts[name] = conflict
            if not conflict and readings:
                likelihoods[name] = likelihood
        prior = self.forecast.prior
        if self.config.share_storm_evidence and likelihoods:
            # The storm member is common. Conditional on that member, the
            # measurement model draws separate noise for each astronaut.
            # Correlated signals within each person are handled in log_likelihood.
            shared = normalize_posterior(prior, np.sum(list(likelihoods.values()), axis=0))
            self.weights = dict.fromkeys(self.histories, shared)
        else:
            self.weights = {
                name: normalize_posterior(prior, likelihoods[name]) if name in likelihoods else prior
                for name in self.histories
            }

    def _arrays(self, history):
        if not history:
            return [], [], np.zeros((0, len(self.forecast.members), 4))
        starts, ends, doses = zip(*history)
        return starts, ends, np.array(doses)

    def _option(self, name, now, departure, end, eva_depth, cabin_depth, restart=True):
        _, _, increments = self._arrays(self.histories[name])
        past = increments.sum(axis=0)
        if self.current_rate_projection:
            if departure != now:
                raise ValueError('Current-rate policies only assess departure now')
            # Keep the current estimate constant for the work and return. Reassess
            # when the clock advances. Do not integrate the template's future dose.
            future = self.forecast.current_rate(now, eva_depth) * (end - now) if end > now else 0.
        else:
            future = self.forecast.interval(now, departure, cabin_depth) + self.forecast.interval(departure, end, eva_depth)
        total = past + future
        weights = self.weights[name]
        upper = tuple(quantile(total[:, column], weights, self.config.upper_probability)
                      for column in (1, 2, 3))
        reference_fractions = total[:, 1:] / np.asarray(self.config.references)
        exceeds = np.any(reference_fractions >= 1, axis=1)
        probability = float(weights @ exceeds)
        # Joint risk gate avoids three separate 95% gates implying 95% joint coverage.
        acceptable = probability <= 1 - self.config.upper_probability + 1e-12
        conflict = self.conflicts[name]
        current_rate = self.current_rate_projection
        prefix = 'At the estimated current rate, projected' if current_rate else 'Projected'
        reason = ('Biomarkers conflict with forecast hypotheses; hold and reassess' if conflict else
                  f'{prefix} probability of any organ reference exceedance {probability:.1%}; '
                  + ('exceeds configured risk tolerance' if not acceptable else
                     'within configured risk tolerance'))
        if self.reassessment_witnesses and end > departure:
            tolerance = (1 - self.config.upper_probability) * (self.config.restart_risk_fraction if restart else 1.0)
            for witness, (aborted_h, return_h) in self.reassessment_witnesses.items():
                if now < return_h:
                    return ExposureOption(name, departure, end, upper, False,
                                          'Crew reassessment: aborted astronaut has not returned', probability)
                if not self.config.matched_current_rate and self.strategy in ('C', 'D') and not any(
                        reading.astronaut == witness and reading.sampled_h >= return_h
                        and reading.marker == 'H2AX'
                        for reading in self.returned):
                    return ExposureOption(name, departure, end, upper, False,
                                          'Crew reassessment: awaiting post-return H2AX result', probability)
                if self.conflicts[witness]:
                    return ExposureOption(name, departure, end, upper, False,
                                          'Crew reassessment: unresolved conflicting biological evidence', probability)
                # Apply each witness's storm evidence to the candidate's history,
                # NOT the witness's accumulated dose. A personal dose limit need
                # not prohibit a lower-dose replacement; shared uncertainty does.
                probability = max(probability, float(self.weights[witness] @ exceeds))
            acceptable = probability <= tolerance + 1e-12
            reason = (f'Crew reassessment: worst supported candidate risk {probability:.1%}; '
                      + ('within' if acceptable else 'exceeds')
                      + f' {"restart" if restart else "continuation"} tolerance {tolerance:.1%}')
        # Keep a forecast-only check alongside the biomarker-adjusted estimate.
        forecast_upper = quantile(reference_fractions.max(axis=1), self.forecast.prior,
                                  self.config.upper_probability)
        return ExposureOption(name, departure, end, upper, acceptable and not conflict, reason, probability,
                              float(self.forecast.prior @ exceeds), float(forecast_upper))

    def observe(self, state, operational):
        now = state.current_mission_time
        end = min(state.config.max_hours, self.forecast.end_h, state.config.observation_end_h or state.config.max_hours)
        held_repairs = tuple(sorted(self.radiation_held_repairs))
        if now > end:
            return RadiationObservation(self.strategy, (), (), len(self.pending), end,
                                        radiation_held_repairs=held_repairs,
                                        matched_current_rate=self.config.matched_current_rate)
        current = tuple(self._option(name, now, now, now, state.scenario.shielding, state.scenario.cabin_shielding)
                        for name in self.histories)
        for option in current:
            _, _, increments = self._arrays(self.histories[option.astronaut])
            absorbed = increments[:, :, 0].sum(axis=0)
            weights = self.weights[option.astronaut]
            self.estimate_log.append(dict(hour=now, **asdict(option),
                mean_absorbed_mGy=float(absorbed @ weights),
                upper_absorbed_mGy=quantile(absorbed, weights, self.config.upper_probability),
                conflicting_measurements=self.conflicts[option.astronaut]))
        options = []
        live_markers = ()
        immediate_return = None
        if operational.active_eva:
            if self.strategy == 'D' and not operational.active_eva.returning:
                eva = state.active_eva
                live_markers = tuple(sorted({
                    reading.marker for reading in self.returned
                    if reading.astronaut == eva.astronaut.name and reading.sampled_h > eva.start_time
                    and reading.marker in D_IN_EVA_MARKERS
                }))
                return_end = now + operational.return_to_airlock_h
                if not self.config.matched_current_rate and live_markers and return_end <= end:
                    immediate_return = self._option(eva.astronaut.name, now, now, return_end,
                                                    state.scenario.shielding, state.scenario.cabin_shielding,
                                                    restart=False)
            remaining = operational.active_eva.planned_remaining_h
            if remaining is None:
                remaining = max(0, operational.planned_eva_hours - operational.active_eva.elapsed_hours)
            if not operational.active_eva.returning:
                remaining = self.projected_duration(max(0, remaining - operational.return_to_airlock_h),
                                                    operational.return_to_airlock_h)
                remaining = max(remaining, operational.return_to_airlock_h)
            if now + remaining <= end:
                options.append(self._option(operational.active_eva.astronaut, now, now, now + remaining,
                                            state.scenario.shielding, state.scenario.cabin_shielding, restart=False))
        elif operational.launch_allowed:
            groups = {}
            for repair, work in operational.repair_work_remaining_h:
                groups.setdefault(round(work, 9), []).append(repair)
            if not groups:
                groups = {operational.planned_eva_hours - operational.return_to_airlock_h: []}
            for work, repairs in groups.items():
                planned = self.projected_duration(work, operational.return_to_airlock_h)
                latest = min(now + self.config.search_horizon_h, end - planned)
                # B never schedules a future departure; it reassesses as the clock advances.
                if self.current_rate_projection or self.strategy == 'B':
                    departures = (now,) if now <= latest else ()
                else:
                    departures = np.arange(now, latest + 1e-9, self.config.departure_step_h)
                for departure in departures:
                    for name in operational.available_astronauts:
                        option = self._option(name, now, float(departure), float(departure + planned),
                                              state.scenario.shielding, state.scenario.cabin_shielding)
                        options.append(replace(option, repairs=tuple(repairs)))
        tolerance = 1 - self.config.upper_probability
        if self.reassessment_witnesses:
            tolerance *= self.config.restart_risk_fraction
        restart_ready = ()
        if operational.launch_allowed and self.restart_reviews:
            candidates = self._restart_ready(now, operational, state.scenario.shielding)
            eligible = (dict(operational.recovery.eligible_crews) if operational.recovery else
                        dict.fromkeys(candidates, operational.available_astronauts))
            restart_ready = tuple(
                repair for repair in candidates
                if {option.astronaut for option in options
                    if option.acceptable and option.forecast_exceedance_probability <= tolerance + 1e-12
                    and (not option.repairs or repair in option.repairs)}.intersection(eligible.get(repair, ())))
            held_repairs = tuple(repair for repair in held_repairs if repair not in restart_ready)
        reviewed = {reading.astronaut for reading in self.returned if reading.marker == 'H2AX'
                    and reading.astronaut in self.post_eva_reviews
                    and reading.sampled_h >= self.post_eva_reviews[reading.astronaut]}
        pending_review = tuple(name for name in self.post_eva_reviews if name not in reviewed)
        return RadiationObservation(self.strategy, tuple(options), current, len(self.pending), end,
                                    self.config.references, tolerance, pending_review, live_markers, immediate_return,
                                    self.config.forecast_launch_veto, held_repairs, self.config.matched_current_rate,
                                    restart_ready)

    def next_boundary(self, now):
        times = [self.next_sampling_h]
        if self.strategy in ('C', 'D'):
            times.extend(self.next_cabin_sampling.values())
        times.extend(reading.available_h for reading in self.pending)
        times.extend(due for due, _, _ in self.scheduled)
        return min((time for time in times if time > now), default=float('inf'))
