from datetime import datetime, timezone
import json
import httpx
import pytest

from app.domain.vehicle_model import GPSLocation, OBDData, TelemetryPacket
from app.services.http_emitter import HttpEmitter


@pytest.fixture
def sample_packet() -> TelemetryPacket:
    return TelemetryPacket(
        tenant_id="00000000-0000-0000-0000-000000000001",
        vehicle_id="11111111-1111-1111-1111-111111111111",
        device_id="OBD-DONGLE-01",
        timestamp=datetime.now(timezone.utc),
        location=GPSLocation(latitude=-12.0464, longitude=-77.0428),
        obd=OBDData(engine_rpm=2200, speed_kmh=60.0),
    )


@pytest.mark.asyncio
async def test_send_batch_success(sample_packet: TelemetryPacket):
    captured_request = {}

    def handler(request: httpx.Request):
        captured_request["headers"] = dict(request.headers)
        captured_request["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(202, json={"status": "accepted", "ingested": 1})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        emitter = HttpEmitter(
            ingestion_url="http://test/api/v1/iot/telemetry",
            device_key="secret-key-123",
            client=client,
        )
        ok, code, duration = await emitter.send_batch([sample_packet])

        assert ok is True
        assert code == 202
        assert duration >= 0.0
        assert captured_request["headers"]["x-device-key"] == "secret-key-123"
        assert len(captured_request["body"]) == 1
        assert captured_request["body"][0]["vehicle_id"] == sample_packet.vehicle_id


@pytest.mark.asyncio
async def test_send_batch_unauthorized(sample_packet: TelemetryPacket):
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"title": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        emitter = HttpEmitter(
            ingestion_url="http://test/api/v1/iot/telemetry",
            device_key="bad-key",
            client=client,
        )
        ok, code, _ = await emitter.send_batch([sample_packet])
        assert ok is False
        assert code == 401


@pytest.mark.asyncio
async def test_send_batch_network_error(sample_packet: TelemetryPacket):
    def handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        emitter = HttpEmitter(
            ingestion_url="http://unreachable/api",
            device_key="test-key",
            client=client,
        )
        ok, code, _ = await emitter.send_batch([sample_packet])
        assert ok is False
        assert code == 0
