from dataclasses import dataclass
from typing import Literal
import pandas as pd
from pathlib import Path

EVA_DURATION = 7  # hours

DATA_PATH = (
    Path(__file__).resolve().parent
    / "data/processed/mission_radiation_environment.csv"
)

radiation_data = pd.read_csv(DATA_PATH)

RepairType = Literal["communications", "monitoring", "propulsion"]
EngineType = Literal["NTP", "NEP"]


RADIATION_ABORT_THRESHOLD_MGY = 1000.0

@dataclass
class Scenario:
    shielding: int = 0.4 # default shielding for outside ship
    severity: str = "sapphire_100yr" # default SPE severity

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


def get_hourly_exposure(
    hour: int,
    scenario: Scenario
) -> float:

    result = radiation_data[
        (radiation_data["hour_since_emergency"] == hour)
        & (radiation_data["shielding_g_cm2"] == scenario.shielding)
        & (radiation_data["scenario_id"] == scenario.severity)
    ]

    if len(result) != 1:
        raise ValueError(
            f"Expected one dose for hour {hour}, "
            f"shielding {scenario.shielding}, scenario {scenario.severity}; "
            f"found {len(result)}"
        )

    return float(result.iloc[0]["absorbed_dose_rate_mGy_h"])


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


def abort_eva(
    astronaut: Astronaut,
    projected_hourly_dose: float = 0.0
) -> bool:
    return (
        astronaut.accumulated_radiation + projected_hourly_dose
        >= RADIATION_ABORT_THRESHOLD_MGY
    )


def update_eva(
    eva: EVA,
    current_time: int,
    scenario: Scenario
) -> None:

    # Don't update an EVA that has already ended
    if eva.reported_end_time is not None:
        return
    if current_time <= eva.start_time:
        return

    hourly_dose = get_hourly_exposure(hour=current_time - 1, scenario=scenario)

    if abort_eva(eva.astronaut, hourly_dose):
        eva.completed = False
        eva.reported_end_time = current_time - 1
        return

    eva.astronaut.accumulated_radiation += hourly_dose

    # Check if the EVA has finished
    if current_time >= eva.scheduled_end_time:
        eva.completed = True
        eva.reported_end_time = current_time
        return

    # Check if the EVA must be aborted
    if abort_eva(eva.astronaut):
        eva.completed = False
        eva.reported_end_time = current_time
