from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
import httpx
import pytest

from app.api.deps import get_simulation_engine
from app.api.error_handlers import register_error_handlers
from app.api.v1.simulator import router as simulator_router
from app.domain.scenarios import SimulationScenario
from app.services.simulation_engine import SimulationStatus


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.start = AsyncMock()
    engine.stop = AsyncMock()
    engine.send_burst = AsyncMock(
        return_value={
            "success": True,
            "status_code": 201,
            "latency_seconds": 0.015,
            "sent_count": 50,
            "emission_mode": "BATCH",
            "scenario": "HIGH_THROUGHPUT_BURST",
            "branch_id": "branch-test",
        }
    )
    engine.get_status = MagicMock(
        return_value=SimulationStatus(
            is_running=True,
            scenario=SimulationScenario.NORMAL_DRIVING,
            emission_mode="STREAM",
            branch_id="branch-01",
            vehicle_count=10,
            target_rate_per_sec=50,
            total_sent=150,
            total_success=150,
            total_failed=0,
            elapsed_seconds=3.0,
            current_throughput_mps=50.0,
        )
    )
    return engine


@pytest.fixture
def test_app(mock_engine):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(simulator_router)
    app.dependency_overrides[get_simulation_engine] = lambda: mock_engine
    return app


@pytest.mark.asyncio
async def test_healthz_endpoint(test_app: FastAPI):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "UP"


@pytest.mark.asyncio
async def test_metrics_endpoint(test_app: FastAPI):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "iot_simulator" in res.text


@pytest.mark.asyncio
async def test_start_simulation_endpoint(test_app: FastAPI, mock_engine):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/simulator/start",
            json={
                "scenario": "ENGINE_OVERHEAT",
                "emission_mode": "BATCH",
                "branch_id": "00000000-0000-0000-0000-000000000003",
                "vehicles_count": 25,
                "rate_per_sec": 100,
                "seed": 999,
                "duration_seconds": 60,
            },
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "started"
        assert data["scenario"] == "ENGINE_OVERHEAT"
        assert data["emission_mode"] == "BATCH"
        assert data["branch_id"] == "00000000-0000-0000-0000-000000000003"
        assert data["vehicles_count"] == 25
        assert data["rate_per_sec"] == 100
        assert data["seed"] == 999
        mock_engine.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_burst_endpoint(test_app: FastAPI, mock_engine):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/simulator/burst",
            json={
                "scenario": "HIGH_THROUGHPUT_BURST",
                "batch_size": 50,
                "emission_mode": "BATCH",
                "branch_id": "branch-test",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status_code"] == 201
        assert data["sent_count"] == 50
        mock_engine.send_burst.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_burst_endpoint_validation_error(test_app: FastAPI):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid batch_size (max is 100)
        res = await client.post(
            "/api/v1/simulator/burst",
            json={
                "batch_size": 500,
                "emission_mode": "BATCH",
            },
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_stop_simulation_endpoint(test_app: FastAPI, mock_engine):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/simulator/stop")
        assert res.status_code == 200
        assert res.json()["status"] == "stopped"
        mock_engine.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_simulation_status_endpoint(test_app: FastAPI, mock_engine):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/simulator/status")
        assert res.status_code == 200
        data = res.json()
        assert data["is_running"] is True
        assert data["total_sent"] == 150
        assert data["current_throughput_mps"] == 50.0
        assert data["emission_mode"] == "STREAM"
        assert data["branch_id"] == "branch-01"
