"""Edit these four settings for the reference mission.

Advanced options are inherited from sim/defaults.py; scheduling is unchanged.
"""
from dataclasses import dataclass
from sim.defaults import SimulatorDefaults


@dataclass(frozen=True)
class MissionAssumptions(SimulatorDefaults):
    crew_size: int = 5                 # Team assumption.
    astronauts_per_eva: int = 1        # Current model supports one person per EVA.
    eva_duration_hours: float = 7.0    # CNL: approximately seven hours.
    turnaround_hours: float = 1.0      # Team assumption: return/deploy gap.


DEFAULT_ASSUMPTIONS = MissionAssumptions()
