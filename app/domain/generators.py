from datetime import datetime, timezone, timedelta
import random
from typing import List, Optional
import uuid
from app.domain.scenarios import SimulationScenario, get_scenario_params
from app.domain.vehicle_model import SimulatedVehicle, TelemetryBatch, TelemetryPacket, TelemetrySnapshot


class FleetGenerator:
    """Manages a fleet of simulated vehicles, generating reproducible telemetry packets and batches."""

    def __init__(
        self,
        tenant_id: str,
        vehicle_count: int = 10,
        seed: int = 42,
        branch_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.vehicle_count = max(1, vehicle_count)
        self.seed = seed
        self.branch_id = branch_id
        self.rng = random.Random(seed)
        self.vehicles: List[SimulatedVehicle] = []
        self._init_fleet()

    def _init_fleet(self) -> None:
        """Initialize vehicles distributed across Lima, Peru coordinates with monotonic starting odometers."""
        base_lat = -12.0464
        base_lon = -77.0428

        self.vehicles.clear()
        for i in range(self.vehicle_count):
            # Seed-controlled slight offset per vehicle
            v_lat = base_lat + self.rng.uniform(-0.05, 0.05)
            v_lon = base_lon + self.rng.uniform(-0.05, 0.05)
            v_uuid = str(uuid.UUID(int=self.rng.getrandbits(128)))
            d_id = f"OBD-SIM-{i+1:04d}"
            init_odometer = round(15000.0 + (i * 2500.0) + self.rng.uniform(10.0, 500.0), 2)

            v = SimulatedVehicle(
                tenant_id=self.tenant_id,
                vehicle_id=v_uuid,
                device_id=d_id,
                initial_lat=v_lat,
                initial_lon=v_lon,
                initial_odometer_km=init_odometer,
                branch_id=self.branch_id,
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
                injected_dtc_items=params.structured_dtcs if params.structured_dtcs else None,
            )
            packets.append(packet)

        return packets

    def generate_burst_batch(
        self, batch_size: int, scenario: SimulationScenario = SimulationScenario.HIGH_THROUGHPUT_BURST
    ) -> List[TelemetryPacket]:
        """Generate a synthesized batch of packets for high-throughput streaming stress testing."""
        params = get_scenario_params(scenario)
        packets: List[TelemetryPacket] = []

        for _ in range(batch_size):
            v = self.rng.choice(self.vehicles)
            packet = v.tick(
                delta_seconds=0.1,
                rng=self.rng,
                target_temp=params.target_coolant_temp_c,
                target_voltage=params.target_battery_voltage,
                target_rpm=params.target_engine_rpm,
                injected_dtcs=params.injected_dtcs if params.injected_dtcs else None,
                injected_dtc_items=params.structured_dtcs if params.structured_dtcs else None,
            )
            packets.append(packet)

        return packets

    def generate_telemetry_batch(
        self,
        device_id: Optional[str] = None,
        snapshot_count: int = 10,
        scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING,
        delta_seconds: float = 1.0,
    ) -> TelemetryBatch:
        """Generate a structured TelemetryBatch with non-decreasing odometer snapshots for a vehicle."""
        params = get_scenario_params(scenario)
        snapshot_count = min(100, max(1, snapshot_count))

        # Select target vehicle
        vehicle = None
        if device_id:
            vehicle = next((v for v in self.vehicles if v.device_id == device_id), None)
        if not vehicle:
            vehicle = self.vehicles[0]

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(seconds=snapshot_count * delta_seconds)

        snapshots: List[TelemetrySnapshot] = []
        for i in range(snapshot_count):
            t = start_time + timedelta(seconds=i * delta_seconds)
            vehicle.tick(
                delta_seconds=delta_seconds,
                rng=self.rng,
                target_temp=params.target_coolant_temp_c,
                target_voltage=params.target_battery_voltage,
                target_rpm=params.target_engine_rpm,
                injected_dtcs=params.injected_dtcs if params.injected_dtcs else None,
                injected_dtc_items=params.structured_dtcs if params.structured_dtcs else None,
            )
            snapshots.append(vehicle.to_snapshot(timestamp=t))

        return TelemetryBatch(
            tenant_id=self.tenant_id,
            obd2_device_id=vehicle.device_id,
            vehicle_id=vehicle.vehicle_id,
            snapshots=snapshots,
        )

    def generate_fleet_batches(
        self,
        snapshots_per_vehicle: int = 5,
        scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING,
        delta_seconds: float = 1.0,
    ) -> List[TelemetryBatch]:
        """Generate structured batches for all vehicles in the fleet."""
        batches: List[TelemetryBatch] = []
        for vehicle in self.vehicles:
            batch = self.generate_telemetry_batch(
                device_id=vehicle.device_id,
                snapshot_count=snapshots_per_vehicle,
                scenario=scenario,
                delta_seconds=delta_seconds,
            )
            batches.append(batch)
        return batches
