from typing import Literal

Decision = Literal["start", "wait", "abort", "continue"]


def strategy_a(state) -> Decision:
    # Immediate conservative response
    ...


def strategy_b(state) -> Decision:
    # Radiation forecast-informed scheduling
    ...


def strategy_c(state) -> Decision:
    # Forecasts + conventional biodosimetry
    ...


def strategy_d(state) -> Decision:
    # Forecasts + multimodal biodosimetry
    ...