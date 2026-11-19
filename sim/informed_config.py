"""Explicit experimental settings; none establish instrument or clinical performance."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ForecastSpec:
    historical_template: str = 'august_1972'
    severity: str = 'SAPPHIRE-1-in-100'
    profile_origin_h: float = 48.0
    timing_offsets_h: tuple[float, ...] = (-6.0, 0.0, 6.0)
    magnitude_factors: tuple[float, ...] = (0.7, 1.0, 1.3)
    gcr_scale: float = 1.0
    anatomy: str = 'MAX'
    alternative_templates: tuple[str, ...] = ()
    spe_scale: float = 1.0
    magnitude_weights: tuple[float, ...] = ()

    def __post_init__(self):
        templates = (self.historical_template, *self.alternative_templates)
        if len(set(templates)) != len(templates) or not set(templates) <= {'august_1972', 'october_2003_goes10'}:
            raise ValueError('Forecast templates must be distinct supported profiles')
        if not isfinite(self.spe_scale) or self.spe_scale <= 0:
            raise ValueError('Forecast SPE scale must be finite and positive')
        if self.anatomy not in ('MAX', 'FAX'):
            raise ValueError('Forecast anatomy must be MAX or FAX')
        if not isfinite(self.gcr_scale) or self.gcr_scale < 0:
            raise ValueError('GCR forecast scale must be finite and nonnegative')
        if not isfinite(self.profile_origin_h):
            raise ValueError('Forecast origin must be finite')
        if not self.timing_offsets_h or not all(isfinite(value) for value in self.timing_offsets_h):
            raise ValueError('Supply finite forecast timing offsets')
        if not self.magnitude_factors or not all(isfinite(value) and value > 0 for value in self.magnitude_factors):
            raise ValueError('Supply positive finite forecast magnitudes')
        if self.magnitude_weights and (
                len(self.magnitude_weights) != len(self.magnitude_factors)
                or not all(isfinite(value) and value > 0 for value in self.magnitude_weights)):
            raise ValueError('Supply one positive finite weight per forecast magnitude')


@dataclass(frozen=True)
class InformedConfig:
    forecast: ForecastSpec = ForecastSpec()
    upper_probability: float = 0.95
    restart_risk_fraction: float = 0.5  # After an abort: half the normal risk tolerance, explicit hysteresis assumption.
    bfo_reference_mGy_eq: float = 250.0
    skin_reference_mGy_eq: float = 1500.0
    lens_reference_mGy_eq: float = 1000.0
    search_horizon_h: float = 24.0
    departure_step_h: float = 1.0
    sampling_step_h: float = 1.0
    in_eva_monitoring: bool = True  # D's hypothetical repeated in-suit samples.
    matched_current_rate: bool = False  # Common policy for measuring the value of different measurements.
    forecast_launch_veto: bool = True
    share_storm_evidence: bool = False
    cabin_sampling_interval_h: float = 6.0  # Exploratory scheduled C/D panels while sheltered.
    conventional_lab_delay_h: float = 5.0
    lymphocyte_processing_delay_h: float = 0.1
    automated_foci_delay_h: float = 1.0
    instrument_delays_h: tuple[tuple[str, float], ...] = ()
    unavailable_markers: tuple[str, ...] = ()
    measurement_availability: float = 1.0
    sampling_burden_h: float = 0.0
    group_log_sd: float = 0.20
    individual_log_sd: float = 0.20
    reading_log_sd: float = 0.15
    conflict_standard_deviations: float = 3.0
    seed: int = 21
    restart_quiet_hours: float | None = None
    # After a radiation abort every strategy (not only C) holds that repair until the common
    # restart review passes. Requires restart_quiet_hours. Off keeps the legacy per-strategy rules.
    retry_after_abort: bool = False
    # 'current_rate': B assumes today's estimated rate persists. 'ensemble': B integrates the same
    # configured forecast ensemble as C/D (still no biology), so C/D gains cannot come from a better forecast.
    b_projection: str = 'current_rate'

    def __post_init__(self):
        if type(self.matched_current_rate) is not bool:
            raise ValueError('Matched current-rate mode must be enabled or disabled')
        if type(self.in_eva_monitoring) is not bool:
            raise ValueError('In-EVA monitoring must be enabled or disabled')
        if type(self.forecast_launch_veto) is not bool:
            raise ValueError('Forecast launch veto must be enabled or disabled')
        if type(self.share_storm_evidence) is not bool:
            raise ValueError('Storm evidence sharing must be enabled or disabled')
        if not isfinite(self.restart_risk_fraction) or not 0 < self.restart_risk_fraction <= 1:
            raise ValueError('Restart risk fraction must be in (0, 1]')
        if type(self.retry_after_abort) is not bool or self.b_projection not in ('current_rate', 'ensemble'):
            raise ValueError('Invalid retry_after_abort or b_projection setting')
        if self.restart_quiet_hours is not None and (
                not (self.matched_current_rate or self.retry_after_abort) or not isfinite(self.restart_quiet_hours)
                or self.restart_quiet_hours <= 0):
            raise ValueError('A positive restart review duration requires matched current-rate mode or retry_after_abort')
        if self.retry_after_abort and self.restart_quiet_hours is None:
            raise ValueError('retry_after_abort requires restart_quiet_hours')
        if not 0 <= self.measurement_availability <= 1:
            raise ValueError('Measurement availability must be between zero and one')
        if not isfinite(self.sampling_burden_h) or not 0 <= self.sampling_burden_h < self.sampling_step_h:
            raise ValueError('Sampling burden must be finite, nonnegative and shorter than sampling cadence')
        positive = (self.bfo_reference_mGy_eq, self.skin_reference_mGy_eq,
                    self.lens_reference_mGy_eq, self.search_horizon_h,
                    self.departure_step_h, self.sampling_step_h, self.cabin_sampling_interval_h,
                    self.individual_log_sd, self.reading_log_sd,
                    self.conflict_standard_deviations)
        if not all(isfinite(value) and value > 0 for value in positive):
            raise ValueError('Policy durations, references and noise scales must be positive and finite')
        if not 0.5 < self.upper_probability < 1:
            raise ValueError('Upper probability must lie between 0.5 and 1')
        if not isfinite(self.group_log_sd) or self.group_log_sd < 0:
            raise ValueError('Group noise must be finite and nonnegative')
        if any(not isfinite(delay) or delay < 0 for delay in
               (self.conventional_lab_delay_h, self.lymphocyte_processing_delay_h,
                self.automated_foci_delay_h)):
            raise ValueError('Lab delay must be finite and nonnegative')
        names = [name for name, _ in self.instrument_delays_h]
        if len(names) != len(set(names)) or any(not isfinite(delay) or delay < 0 for _, delay in self.instrument_delays_h):
            raise ValueError('Instrument delays require unique names and finite nonnegative hours')

    @property
    def references(self):
        return (self.bfo_reference_mGy_eq, self.skin_reference_mGy_eq, self.lens_reference_mGy_eq)
