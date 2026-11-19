"""Mission records and the deliberately restricted Strategy A observation."""
from dataclasses import dataclass, field
from typing import Literal, TYPE_CHECKING
from sim.assumptions import MissionAssumptions, DEFAULT_ASSUMPTIONS
from sim.mission_recovery import RecoveryConfig, RecoveryObservation

if TYPE_CHECKING:
    from sim.radiation_information import RadiationObservation

RepairType = Literal['communications', 'monitoring', 'propulsion_initial', 'propulsion']
EngineType = Literal['NTP', 'NEP']


@dataclass(frozen=True)
class Scenario:
    shielding: float = DEFAULT_ASSUMPTIONS.external_shielding_g_cm2
    severity: str = DEFAULT_ASSUMPTIONS.default_spe_severity
    cabin_shielding: float = DEFAULT_ASSUMPTIONS.cabin_shielding_g_cm2
    timing_variant: str = DEFAULT_ASSUMPTIONS.timing_variant
    storm_start_hour: float = DEFAULT_ASSUMPTIONS.storm_start_hour  # Mission hour 0 matches the existing emergency window.
    engine_type: EngineType = DEFAULT_ASSUMPTIONS.engine_type
    historical_template: str = DEFAULT_ASSUMPTIONS.historical_template
    gcr_scale: float = DEFAULT_ASSUMPTIONS.gcr_scale
    anatomy: str = DEFAULT_ASSUMPTIONS.anatomy
    spe_scale: float = DEFAULT_ASSUMPTIONS.spe_scale


    @classmethod
    def from_assumptions(cls, config: MissionAssumptions):
        return cls(config.external_shielding_g_cm2, config.default_spe_severity,
                   config.cabin_shielding_g_cm2, config.timing_variant,
                   config.storm_start_hour, config.engine_type, config.historical_template, config.gcr_scale, config.anatomy, config.spe_scale)


@dataclass
class Astronaut:
    name: str
    gender: str = 'unspecified'
    weight: float = 0.0  # Retained descriptive field; no anatomical dose adjustment.
    bfo_initial_absorbed_dose_mGy: float = 0.0
    bfo_absorbed_dose_mGy: float = 0.0
    available_from: float = 0.0
    inside_hours: float = 0.0
    outside_hours: float = 0.0
    estimated_dose_mGy: float | None = None
    bfo_initial_gray_equivalent_mGy_eq: float = 0.0
    bfo_gray_equivalent_mGy_eq: float = 0.0
    medically_fit_for_eva: bool | None = True
    rested_for_eva: bool | None = True
    rest_until_h: float = 0.0

    @property
    def radiation_baseline(self):
        """Legacy accessor: initial BFO absorbed mGy, never tissue-target mGy."""
        return self.bfo_initial_absorbed_dose_mGy

    @radiation_baseline.setter
    def radiation_baseline(self, value):
        self.bfo_initial_absorbed_dose_mGy = value

    @property
    def accumulated_radiation(self):
        """Legacy accessor for BFO absorbed dose only; Gray Equivalent stays separate."""
        return self.bfo_absorbed_dose_mGy

    @accumulated_radiation.setter
    def accumulated_radiation(self, value):
        self.bfo_absorbed_dose_mGy = value


@dataclass
class EVA:
    start_time: float
    scheduled_end_time: float
    reported_end_time: float | None
    completed: bool
    astronaut: Astronaut
    repair_type: RepairType
    engine_type: EngineType
    aborted: bool = False
    end_reason: str = ''
    last_update_time: float | None = None
    bfo_absorbed_dose_mGy: float = 0.0
    bfo_gray_equivalent_mGy_eq: float = 0.0
    return_started_h: float | None = None
    return_end_h: float | None = None
    sampling_busy_until_h: float = 0.0
    work_hours: float = 0.0
    credited_work_h: float = 0.0

    @property
    def modeled_dose_mGy(self):
        return self.bfo_absorbed_dose_mGy

    @modeled_dose_mGy.setter
    def modeled_dose_mGy(self, value):
        self.bfo_absorbed_dose_mGy = value


# Backward-compatible import name; configuration is defined only in assumptions.py.
MissionConfig = MissionAssumptions


@dataclass(frozen=True)
class ActiveEVAObservation:
    astronaut: str
    repair_type: str
    elapsed_hours: float
    estimated_dose_mGy: float | None
    returning: bool = False
    planned_remaining_h: float | None = None


@dataclass(frozen=True)
class State:
    """Permitted operational information and optional estimates; no hidden true dose."""
    current_mission_time: float
    available_astronauts: tuple[str, ...]
    outstanding_repairs: tuple[str, ...]
    completed_repairs: tuple[str, ...]
    active_eva: ActiveEVAObservation | None
    launch_allowed: bool
    restriction_reason: str
    operational_abort: bool
    max_continuous_eva_hours: float
    radiation_abort_threshold_mGy: float | None
    recovery: RecoveryObservation | None = None
    planned_eva_hours: float = DEFAULT_ASSUMPTIONS.eva_duration_hours
    turnaround_hours: float = DEFAULT_ASSUMPTIONS.turnaround_hours
    next_eva_time: float = 0.0
    radiation: 'RadiationObservation | None' = None
    operational_restrictions: tuple[tuple[float, float], ...] = ()
    return_to_airlock_h: float = 0.0
    dose_wait_targets: tuple[tuple[str, float], ...] = ()
    repair_work_remaining_h: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class Decision:
    action: Literal['start', 'wait', 'abort', 'continue', 'stabilize', 'resume_mission', 'safe_hold', 'shelter', 'no_recovery_plan', 'abort_mission']
    reason: str
    astronaut: str | None = None
    repair_type: str | None = None
    dose_wait_until_h: float | None = None


@dataclass
class MissionState:
    scenario: Scenario
    config: MissionConfig
    astronauts: list[Astronaut]
    required_repairs: tuple[str, ...]
    current_mission_time: float = 0.0
    completed_repairs: list[str] = field(default_factory=list)
    active_eva: EVA | None = None
    progress: list[EVA] = field(default_factory=list)
    event_log: list[dict] = field(default_factory=list)
    next_eva_time: float = 0.0
    status: str = 'running'
    exposure_history: list[dict] = field(default_factory=list)
    recovery_config: RecoveryConfig | None = None
    engineering_stabilized: bool = False
    measurement_log: list[dict] = field(default_factory=list)
    estimate_history: list[dict] = field(default_factory=list)
    information_config: dict | None = None
    outcome_hour: float | None = None
    exposure_observation_end_h: float | None = None
    exposure_comparison_basis: str = 'until_termination_only'
    dose_wait_targets: dict[str, float] = field(default_factory=dict)
    work_remaining: dict[str, float] = field(default_factory=dict)
