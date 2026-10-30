import random
from typing import List
import uuid
from app.domain.scenarios import SimulationScenario, get_scenario_params
from app.domain.vehicle_model import SimulatedVehicle, TelemetryPacket


class FleetGenerator:
    """Manages a fleet of simulated vehicles, generating reproducible telemetry."""

    def __init__(self, tenant_id: str, vehicle_count: int = 10, seed: int = 42):
        self.tenant_id = tenant_id
        self.vehicle_count = max(1, vehicle_count)
        self.seed = seed
        self.rng = random.Random(seed)
        self.vehicles: List[SimulatedVehicle] = []
        self._init_fleet()

    def _init_fleet(self) -> None:
        """Initialize vehicles distributed across Lima, Peru coordinates."""
        base_lat = -12.0464
        base_lon = -77.0428

        self.vehicles.clear()
        for i in range(self.vehicle_count):
            # Seed-controlled slight offset per vehicle
            v_lat = base_lat + self.rng.uniform(-0.05, 0.05)
            v_lon = base_lon + self.rng.uniform(-0.05, 0.05)
            v_uuid = str(uuid.UUID(int=self.rng.getrandbits(128)))
            d_id = f"OBD-SIM-{i+1:04d}"

            v = SimulatedVehicle(
                tenant_id=self.tenant_id,
                vehicle_id=v_uuid,
                device_id=d_id,
                initial_lat=v_lat,
                initial_lon=v_lon,
            )
            v.heading = self.rng.uniform(0.0, 360.0)
            self.vehicles.append(v)

    def generate_tick(
        self, delta_seconds: float = 1.0, scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING
    ) -> List[TelemetryPacket]:
        """Generate one tick of telemetry for all vehicles in the fleet."""
        params = get_scenario_params(scenario)
        packets: List[TelemetryPacket] = []

        for v in self.vehicles:
            packet = v.tick(
                delta_seconds=delta_seconds,
                rng=self.rng,
                target_temp=params.target_coolant_temp_c,
                target_voltage=params.target_battery_voltage,
                target_rpm=params.target_engine_rpm,
                injected_dtcs=params.injected_dtcs if params.injected_dtcs else None,
            )
            packets.append(packet)

        return packets

    def generate_burst_batch(
        self, batch_size: int, scenario: SimulationScenario = SimulationScenario.HIGH_THROUGHPUT_BURST
    ) -> List[TelemetryPacket]:
        """Generate a synthesized batch of packets for high-throughput stress testing."""
        params = get_scenario_params(scenario)
        packets: List[TelemetryPacket] = []

        for _ in range(batch_size):
            # Round-robin or random vehicle selection from fleet
            v = self.rng.choice(self.vehicles)
            packet = v.tick(
                delta_seconds=0.1,
                rng=self.rng,
                target_temp=params.target_coolant_temp_c,
                target_voltage=params.target_battery_voltage,
                target_rpm=params.target_engine_rpm,
                injected_dtcs=params.injected_dtcs if params.injected_dtcs else None,
            )
            packets.append(packet)

        return packets
