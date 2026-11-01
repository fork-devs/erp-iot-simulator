from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.domain.vehicle_model import DTCCodeItem


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
    injected_dtcs: List[str] = Field(default_factory=list)
    structured_dtcs: List[DTCCodeItem] = Field(default_factory=list)


def get_scenario_params(scenario: SimulationScenario) -> ScenarioParams:
    """Return physical parameters, DTC overrides, and structured DTC items for a given scenario."""
    if scenario == SimulationScenario.ENGINE_OVERHEAT:
        # Escalates to 118°C triggering critical overheating and P0217 / P0118 codes
        return ScenarioParams(
            target_coolant_temp_c=118,
            injected_dtcs=["P0217", "P0118"],
            structured_dtcs=[
                DTCCodeItem(
                    dtc_code="P0217",
                    description="Engine Coolant Over Temperature Condition",
                    severity="CRITICAL",
                ),
                DTCCodeItem(
                    dtc_code="P0118",
                    description="Engine Coolant Temp Circuit High",
                    severity="HIGH",
                ),
            ],
        )

    if scenario == SimulationScenario.POWERTRAIN_MISFIRE:
        # Injects random multiple misfire and lean code
        return ScenarioParams(
            target_coolant_temp_c=98,
            injected_dtcs=["P0300", "P0171"],
            structured_dtcs=[
                DTCCodeItem(
                    dtc_code="P0300",
                    description="Random/Multiple Cylinder Misfire Detected",
                    severity="HIGH",
                ),
                DTCCodeItem(
                    dtc_code="P0171",
                    description="System Too Lean Bank 1",
                    severity="MEDIUM",
                ),
            ],
        )

    if scenario == SimulationScenario.ELECTRICAL_FAILURE:
        # Drops battery voltage below 11.5V in motion to trigger low voltage and lost ECM comms
        return ScenarioParams(
            target_battery_voltage=11.2,
            injected_dtcs=["P0562", "U0100"],
            structured_dtcs=[
                DTCCodeItem(
                    dtc_code="P0562",
                    description="System Voltage Low",
                    severity="HIGH",
                ),
                DTCCodeItem(
                    dtc_code="U0100",
                    description="Lost Communication with ECM",
                    severity="CRITICAL",
                ),
            ],
        )

    if scenario == SimulationScenario.HIGH_THROUGHPUT_BURST:
        return ScenarioParams(
            target_engine_rpm=2800,
            injected_dtcs=[],
            structured_dtcs=[],
        )

    # NORMAL_DRIVING has no forced degradation
    return ScenarioParams()
