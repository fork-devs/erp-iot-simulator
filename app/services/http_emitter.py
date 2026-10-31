import logging
import time
from typing import List, Optional, Tuple
import uuid
import httpx

from app.core.metrics import EMISSION_DURATION, HTTP_FAILURES, PACKETS_SENT
from app.domain.vehicle_model import TelemetryBatch, TelemetryPacket

logger = logging.getLogger(__name__)


class HttpEmitter:
    """Asynchronous HTTP client managing persistent connections to erp-iot-ingestion."""

    def __init__(
        self,
        ingestion_url: str,
        batch_ingestion_url: str = "http://localhost:8087/api/v1/telemetry-batches",
        device_key: str = "test-device-key",
        timeout_seconds: float = 5.0,
        max_connections: int = 100,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.ingestion_url = ingestion_url
        self.batch_ingestion_url = batch_ingestion_url
        self.device_key = device_key
        self._custom_client = client is not None
        if client:
            self._client = client
        else:
            limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections * 2)
            self._client = httpx.AsyncClient(limits=limits, timeout=timeout_seconds)

    async def send_batch(
        self, packets: List[TelemetryPacket], scenario: str = "NORMAL_DRIVING"
    ) -> Tuple[bool, int, float]:
        """Send a batch of raw telemetry packets to the streaming ingestion endpoint.

        Returns (is_success, http_status_code, latency_seconds).
        """
        if not packets:
            return True, 200, 0.0

        headers = {
            "Content-Type": "application/json",
            "X-Device-Key": self.device_key,
            "X-Correlation-ID": str(uuid.uuid4()),
        }

        payload = [p.model_dump(mode="json") for p in packets]
        start_time = time.perf_counter()

        try:
            response = await self._client.post(
                self.ingestion_url,
                json=payload,
                headers=headers,
            )
            duration = time.perf_counter() - start_time
            is_success = response.status_code == 202 or (200 <= response.status_code < 300)

            EMISSION_DURATION.labels(mode="STREAM", endpoint="/api/v1/iot/telemetry").observe(duration)
            if is_success:
                PACKETS_SENT.labels(mode="STREAM", scenario=scenario, status="success").inc(len(packets))
            else:
                PACKETS_SENT.labels(mode="STREAM", scenario=scenario, status="failed").inc(len(packets))
                HTTP_FAILURES.labels(status_code=str(response.status_code)).inc()
                logger.warning(f"Streaming ingestion returned status {response.status_code}: {response.text}")

            return is_success, response.status_code, duration

        except Exception as exc:
            duration = time.perf_counter() - start_time
            EMISSION_DURATION.labels(mode="STREAM", endpoint="/api/v1/iot/telemetry").observe(duration)
            PACKETS_SENT.labels(mode="STREAM", scenario=scenario, status="failed").inc(len(packets))
            HTTP_FAILURES.labels(status_code="transport_error").inc()
            logger.error(f"HTTP streaming emission failure to {self.ingestion_url}: {exc}")
            return False, 0, duration

    async def send_telemetry_batch(
        self, batch: TelemetryBatch, scenario: str = "NORMAL_DRIVING"
    ) -> Tuple[bool, int, float]:
        """Send a structured TelemetryBatch envelope to /api/v1/telemetry-batches.

        Returns (is_success, http_status_code, latency_seconds).
        """
        snapshot_count = len(batch.snapshots)
        if snapshot_count == 0:
            return True, 200, 0.0

        headers = {
            "Content-Type": "application/json",
            "X-Device-Key": self.device_key,
            "X-Correlation-ID": str(uuid.uuid4()),
        }

        payload = batch.model_dump(by_alias=True, mode="json")
        start_time = time.perf_counter()

        try:
            response = await self._client.post(
                self.batch_ingestion_url,
                json=payload,
                headers=headers,
            )
            duration = time.perf_counter() - start_time
            is_success = response.status_code == 201 or (200 <= response.status_code < 300)

            EMISSION_DURATION.labels(mode="BATCH", endpoint="/api/v1/telemetry-batches").observe(duration)
            if is_success:
                PACKETS_SENT.labels(mode="BATCH", scenario=scenario, status="success").inc(snapshot_count)
            else:
                PACKETS_SENT.labels(mode="BATCH", scenario=scenario, status="failed").inc(snapshot_count)
                HTTP_FAILURES.labels(status_code=str(response.status_code)).inc()
                logger.warning(f"Batch ingestion returned status {response.status_code}: {response.text}")

            return is_success, response.status_code, duration

        except Exception as exc:
            duration = time.perf_counter() - start_time
            EMISSION_DURATION.labels(mode="BATCH", endpoint="/api/v1/telemetry-batches").observe(duration)
            PACKETS_SENT.labels(mode="BATCH", scenario=scenario, status="failed").inc(snapshot_count)
            HTTP_FAILURES.labels(status_code="transport_error").inc()
            logger.error(f"HTTP batch emission failure to {self.batch_ingestion_url}: {exc}")
            return False, 0, duration

    async def close(self) -> None:
        """Close persistent HTTP client pool."""
        if not self._custom_client and self._client:
            await self._client.aclose()
