from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel


class SimulationScenario(str, Enum):
    NORMAL_DRIVING = "NORMAL_DRIVING"
    ENGINE_OVERHEAT = "ENGINE_OVERHEAT"
    POWERTRAIN_MISFIRE = "POWERTRAIN_MISFIRE"
    ELECTRICAL_FAILURE = "ELECTRICAL_FAILURE"
    HIGH_THROUGHPUT_BURST = "HIGH_THROUGHPUT_BURST"


class ScenarioParams(BaseModel):
    target_coolant_temp_c: Optional[int] = None
    target_battery_voltage: Optional[float] = None
    target_engine_rpm: Optional[int] = None
    injected_dtcs: List[str] = []


def get_scenario_params(scenario: SimulationScenario) -> ScenarioParams:
    """Return physical parameters and DTC overrides for a given scenario."""
    if scenario == SimulationScenario.ENGINE_OVERHEAT:
        # Escalates to 118°C triggering critical overheating and P0217 code
        return ScenarioParams(
            target_coolant_temp_c=118,
            injected_dtcs=["P0217"],
        )

    if scenario == SimulationScenario.POWERTRAIN_MISFIRE:
        # Injects random multiple misfire and lean code
        return ScenarioParams(
            target_coolant_temp_c=98,
            injected_dtcs=["P0300", "P0171"],
        )

    if scenario == SimulationScenario.ELECTRICAL_FAILURE:
        # Drops battery voltage below 11.8V in motion to trigger alternator alert
        return ScenarioParams(
            target_battery_voltage=11.2,
            injected_dtcs=["P0562"],
        )

    if scenario == SimulationScenario.HIGH_THROUGHPUT_BURST:
        return ScenarioParams(
            target_engine_rpm=2800,
        )

    # NORMAL_DRIVING has no forced degradation
    return ScenarioParams()
