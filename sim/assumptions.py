"""Single source of mission defaults; no values here modify the radiation baseline.

Case statements below reflect the supplied CNL case description: approximately
seven-hour EVAs and damage to communication, monitoring and propulsion systems.
Crew, scheduling, repair success and shielding choices are team assumptions.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MissionAssumptions:
    crew_size: int = 5                         # Team assumption.
    astronauts_per_eva: int = 1                # Team assumption; single-person model.
    eva_duration_hours: float = 7.0             # Case: approximately seven hours.
    turnaround_hours: float = 1.0              # Team: return/deploy; preparation overlaps.
    max_simultaneous_evas: int = 1              # Team; sequential model.
    crew_rotation: bool = True                 # Team: fewest previous attempts first.
    allow_consecutive_evas: bool = False        # Team: no automatic consecutive assignment.
    required_repair_types: tuple[str, ...] = ('communications', 'monitoring', 'propulsion')
    # Categories from case; one successful EVA per category is a team simplification.
    default_spe_severity: str = 'SAPPHIRE-1-in-100'
    worst_case_spe_severity: str = 'SAPPHIRE-1-in-1000'
    external_shielding_g_cm2: float = 0.4        # Idealized aluminium-sphere references.
    cabin_shielding_g_cm2: float = 20.0
    time_step_hours: float = 1.0                # Team numerical choice.
    max_hours: float = 264.0                    # Length of the available storm template.
    timing_variant: str = 'gt10MeV__log_linear' # Existing central model member.
    storm_start_hour: float = 48.0             # Existing illustrative emergency origin.
    engine_type: str = 'NTP'                    # Team demonstration choice.
    # None follows planned duration; a shorter independent operational cap is optional.
    max_continuous_eva_hours: float | None = None
    # Hypothetical tissue-target dose budget, NOT a NASA/medical exposure limit.
    radiation_abort_threshold_mGy: float = 1000.0
    estimated_external_rate_mGy_h: float | None = None  # No reliable estimate by default.
    estimated_cabin_rate_mGy_h: float = 0.0      # Optional estimate only, not true cabin dose.
    operational_restrictions: tuple[tuple[float, float], ...] = ()
    # Optional engine-specific priority overrides; otherwise use required_repair_types.
    repair_order_ntp: tuple[str, ...] | None = None
    repair_order_nep: tuple[str, ...] | None = None

    @property
    def eva_time_limit_hours(self) -> float:
        return self.eva_duration_hours if self.max_continuous_eva_hours is None else self.max_continuous_eva_hours


DEFAULT_ASSUMPTIONS = MissionAssumptions()
