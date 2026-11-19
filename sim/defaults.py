"""Advanced simulator defaults; everyday mission settings are in assumptions.py.

These preserve existing operational and radiation-reference choices. They do not
modify the frozen radiation baseline or establish medical safety limits.
"""
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class SimulatorDefaults:
    max_simultaneous_evas: int = 1              # Team; sequential model.
    crew_rotation: bool = True                 # Team: fewest previous attempts first.
    allow_consecutive_evas: bool = False        # Team: no automatic consecutive assignment.
    required_repair_types: tuple[str, ...] = ('monitoring', 'propulsion_initial', 'propulsion', 'communications')
    # Team reference workload: monitoring, two propulsion-system tasks, communications.
    default_spe_severity: str = 'SAPPHIRE-1-in-100'
    worst_case_spe_severity: str = 'SAPPHIRE-1-in-1000'
    external_shielding_g_cm2: float = 0.4        # Idealized aluminium-sphere references.
    cabin_shielding_g_cm2: float = 20.0
    spe_scale: float = 1.0                     # Synthetic proton-fluence multiplier, not a return period.
    gcr_scale: float = 1.0                     # Published GCR reference; 0 disables for SPE-only comparisons.
    anatomy: str = 'MAX'                      # MAX male or FAX female reference cohort.
    time_step_hours: float = 1.0                # Team numerical choice.
    max_hours: float = 264.0                    # Default mission ceiling; selected template supplies the data boundary.
    historical_template_1972: str = 'august_1972'
    historical_template_2003: str = 'october_2003_goes10'
    historical_template: str = historical_template_1972  # Select one template for each run.
    timing_variant: str = 'gt10MeV__log_linear' # Existing central model member.
    storm_start_hour: float = 48.0             # Existing illustrative emergency origin.
    engine_type: str = 'NTP'                    # Team demonstration choice.
    # None follows planned duration; a shorter independent operational cap is optional.
    max_continuous_eva_hours: float | None = None
    # Optional explicitly configured experimental BFO absorbed-dose budget, NOT a NASA/medical exposure limit.
    radiation_abort_threshold_mGy: float | None = None
    estimated_external_rate_mGy_h: float | None = None  # No reliable estimate by default.
    estimated_cabin_rate_mGy_h: float = 0.0      # Optional estimate only, not true cabin dose.
    operational_restrictions: tuple[tuple[float, float], ...] = ()
    return_to_airlock_h: float = 0.5
    # Fraction of EVA work hours credited to a repair when the EVA is aborted. 0 keeps the
    # legacy all-or-nothing repair; 1 retains all work done. Team assumption, not a CNL fact.
    abort_progress_credit: float = 0.0
    minimum_rest_h: float = 1.0
    observation_end_h: float | None = None
    continued_shelter_feasible: bool = False
    # Optional engine-specific priority overrides; otherwise use required_repair_types.
    repair_order_ntp: tuple[str, ...] | None = None
    repair_order_nep: tuple[str, ...] | None = None

    @property
    def eva_time_limit_hours(self) -> float:
        return float('inf') if self.max_continuous_eva_hours is None else self.max_continuous_eva_hours

