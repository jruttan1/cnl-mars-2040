"""Mission records and the deliberately restricted Strategy A observation."""
from dataclasses import dataclass, field
from typing import Literal
from sim.assumptions import MissionAssumptions, DEFAULT_ASSUMPTIONS
from sim.mission_recovery import RecoveryConfig, RecoveryObservation, RecoveryState

RepairType = Literal['communications', 'monitoring', 'propulsion']
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


    @classmethod
    def from_assumptions(cls, config: MissionAssumptions):
        return cls(config.external_shielding_g_cm2, config.default_spe_severity,
                   config.cabin_shielding_g_cm2, config.timing_variant,
                   config.storm_start_hour, config.engine_type, config.historical_template)


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


@dataclass(frozen=True)
class State:
    """Permitted observation only: no astronaut objects, true dose, CSV or forecast."""
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


@dataclass(frozen=True)
class Decision:
    action: Literal['start', 'wait', 'abort', 'continue', 'conserve_support', 'begin_checkout', 'resume_mission', 'safe_hold', 'abort_mission']
    reason: str
    astronaut: str | None = None
    repair_type: str | None = None


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
    recovery_state: RecoveryState | None = None
