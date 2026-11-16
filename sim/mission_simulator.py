
from dataclasses import dataclass
from typing import Literal

EVA_DURATION = 7  # hours

RepairType = Literal["communications", "monitoring", "propulsion"]
EngineType = Literal["NTP", "NEP"]


radiation_abort_threshold = 100000 #define later

@dataclass
class Astronaut:
    name: str
    gender: str
    weight: int
    radiation_baseline: int
    accumulated_radiation: int

@dataclass
class EVA:
    start_time: int
    scheduled_end_time: int
    reported_end_time: int | None
    completed: bool
    astronaut: Astronaut
    repair_type: RepairType
    engine_type: EngineType


def start_eva(
    start_time: int,
    astronaut: Astronaut,
    repair_type: RepairType,
    engine_type: EngineType
) -> EVA:

    return EVA(
        start_time=start_time,
        scheduled_end_time=start_time + EVA_DURATION,
        reported_end_time=None,
        completed=False,
        astronaut=astronaut,
        repair_type=repair_type,
        engine_type=engine_type
    )


def abort_eva(astronaut: Astronaut,) -> bool:
    
    if astronaut.accumulated_radiation >= radiation_abort_threshold:
        return True
    else:
        return False
    