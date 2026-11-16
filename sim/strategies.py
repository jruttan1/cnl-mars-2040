
from typing import Literal, List
from dataclasses import dataclass, field
from mission_simulator import EVA, Astronaut, Scenario

Decision = Literal["start", "wait", "abort", "continue"]


@dataclass
class State:
    current_mission_time: int  # hours since SPE start
    available_astronauts: List[Astronaut]
    scenario: Scenario
    progress: List[EVA] = field(default_factory=list)


def strategy_a(state: State) -> Decision:
    # Immediate conservative response
    ...


def strategy_b(state: State) -> Decision:
    # Radiation forecast-informed scheduling
    ...


def strategy_c(state: State) -> Decision:
    # Forecasts + conventional biodosimetry
    ...


def strategy_d(state: State) -> Decision:
    # Forecasts + multimodal biodosimetry
    ...
