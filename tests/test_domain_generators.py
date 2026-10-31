from app.domain.generators import FleetGenerator
from app.domain.scenarios import SimulationScenario


def test_seed_deterministic_reproducibility():
    gen1 = FleetGenerator(tenant_id="tenant-1", vehicle_count=5, seed=12345)
    gen2 = FleetGenerator(tenant_id="tenant-1", vehicle_count=5, seed=12345)

    packets1 = gen1.generate_tick(delta_seconds=1.0)
    packets2 = gen2.generate_tick(delta_seconds=1.0)

    assert len(packets1) == len(packets2) == 5
    for p1, p2 in zip(packets1, packets2):
        assert p1.vehicle_id == p2.vehicle_id
        assert p1.location.latitude == p2.location.latitude
        assert p1.location.longitude == p2.location.longitude
        assert p1.obd.speed_kmh == p2.obd.speed_kmh
        assert p1.obd.engine_rpm == p2.obd.engine_rpm


def test_scenario_engine_overheat():
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=3, seed=42)
    # Run multiple ticks to allow temperature to escalate
    packets = []
    for _ in range(15):
        packets = gen.generate_tick(delta_seconds=1.0, scenario=SimulationScenario.ENGINE_OVERHEAT)

    for p in packets:
        assert p.obd.coolant_temp_c >= 105
        assert "P0217" in p.obd.dtcs
        assert "P0118" in p.obd.dtcs


def test_scenario_powertrain_misfire():
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=2, seed=42)
    packets = gen.generate_tick(delta_seconds=1.0, scenario=SimulationScenario.POWERTRAIN_MISFIRE)

    for p in packets:
        assert "P0300" in p.obd.dtcs
        assert "P0171" in p.obd.dtcs


def test_scenario_electrical_failure():
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=2, seed=42)
    packets = gen.generate_tick(delta_seconds=1.0, scenario=SimulationScenario.ELECTRICAL_FAILURE)

    for p in packets:
        assert p.obd.battery_voltage < 11.8
        assert "P0562" in p.obd.dtcs
        assert "U0100" in p.obd.dtcs


def test_generate_burst_batch():
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=5, seed=42)
    batch = gen.generate_burst_batch(batch_size=100)

    assert len(batch) == 100
    for p in batch:
        assert p.tenant_id == "tenant-1"
        assert p.location.latitude != 0.0
        assert p.obd.speed_kmh >= 0.0


def test_monotonic_odometer_progression():
    branch_id = "branch-lima-01"
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=1, seed=42, branch_id=branch_id)
    vehicle = gen.vehicles[0]

    assert vehicle.branch_id == branch_id
    initial_odo = vehicle.odometer_km
    assert initial_odo > 0

    odo_readings = []
    for _ in range(10):
        packet = vehicle.tick(delta_seconds=2.0, rng=gen.rng)
        odo_readings.append(packet.obd.odometer_km)
        assert packet.branch_id == branch_id
        assert packet.metadata.get("branch_id") == branch_id

    # Verify strictly monotonic increasing
    for i in range(1, len(odo_readings)):
        assert odo_readings[i] >= odo_readings[i - 1]
    assert odo_readings[-1] > initial_odo


def test_generate_telemetry_batch_structure():
    gen = FleetGenerator(tenant_id="tenant-xyz", vehicle_count=2, seed=99)
    batch = gen.generate_telemetry_batch(
        snapshot_count=15,
        scenario=SimulationScenario.ENGINE_OVERHEAT,
        delta_seconds=1.0,
    )

    assert batch.tenant_id == "tenant-xyz"
    assert batch.obd2_device_id.startswith("OBD-SIM-")
    assert len(batch.snapshots) == 15

    # Check non-decreasing odometer in batch snapshots
    for i in range(len(batch.snapshots) - 1):
        assert batch.snapshots[i + 1].odometer_km >= batch.snapshots[i].odometer_km

    # Check camelCase serialization aliases
    batch_json = batch.model_dump(by_alias=True, mode="json")
    assert "obd2DeviceId" in batch_json
    assert "snapshots" in batch_json
    first_snapshot = batch_json["snapshots"][0]
    assert "speedKmh" in first_snapshot
    assert "odometerKm" in first_snapshot
    assert "fuelLevelPercent" in first_snapshot
    assert "createdAt" in first_snapshot
    assert "dtcCodes" in first_snapshot
    assert len(first_snapshot["dtcCodes"]) >= 1
    assert "dtcCode" in first_snapshot["dtcCodes"][0]
    assert "severity" in first_snapshot["dtcCodes"][0]
