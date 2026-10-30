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


def test_generate_burst_batch():
    gen = FleetGenerator(tenant_id="tenant-1", vehicle_count=5, seed=42)
    batch = gen.generate_burst_batch(batch_size=100)

    assert len(batch) == 100
    for p in batch:
        assert p.tenant_id == "tenant-1"
        assert p.location.latitude != 0.0
        assert p.obd.speed_kmh >= 0.0
