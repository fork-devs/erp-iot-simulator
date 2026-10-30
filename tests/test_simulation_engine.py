import asyncio
from unittest.mock import AsyncMock
import pytest

from app.domain.scenarios import SimulationScenario
from app.services.simulation_engine import SimulationEngine


@pytest.mark.asyncio
async def test_simulation_engine_start_stop():
    mock_emitter = AsyncMock()
    mock_emitter.send_batch = AsyncMock(return_value=(True, 202, 0.005))

    engine = SimulationEngine(emitter=mock_emitter, tenant_id="tenant-test")
    assert engine.is_running is False

    await engine.start(
        scenario=SimulationScenario.NORMAL_DRIVING,
        vehicle_count=3,
        rate_per_sec=100,
        seed=42,
    )

    assert engine.is_running is True
    await asyncio.sleep(0.08)

    status = engine.get_status()
    assert status.is_running is True
    assert status.total_sent > 0
    assert status.total_success > 0
    assert status.total_failed == 0

    await engine.stop()
    assert engine.is_running is False
    mock_emitter.send_batch.assert_awaited()


@pytest.mark.asyncio
async def test_simulation_engine_auto_duration():
    mock_emitter = AsyncMock()
    mock_emitter.send_batch = AsyncMock(return_value=(True, 202, 0.001))

    engine = SimulationEngine(emitter=mock_emitter, tenant_id="tenant-test")
    # Start for only 1 second duration
    await engine.start(
        scenario=SimulationScenario.HIGH_THROUGHPUT_BURST,
        vehicle_count=5,
        rate_per_sec=200,
        seed=123,
        duration_seconds=1,
    )

    # Wait 1.1s for auto-stop
    await asyncio.sleep(1.1)
    status = engine.get_status()
    assert status.is_running is False
    assert status.total_sent > 0
