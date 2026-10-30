import logging
import time
from typing import List, Optional, Tuple
import httpx

from app.domain.vehicle_model import TelemetryPacket

logger = logging.getLogger(__name__)


class HttpEmitter:
    """Asynchronous HTTP client managing persistent connections to erp-iot-ingestion."""

    def __init__(
        self,
        ingestion_url: str,
        device_key: str,
        timeout_seconds: float = 5.0,
        max_connections: int = 100,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.ingestion_url = ingestion_url
        self.device_key = device_key
        self._custom_client = client is not None
        if client:
            self._client = client
        else:
            limits = httpx.Limits(max_keepalive_connections=max_connections, max_connections=max_connections * 2)
            self._client = httpx.AsyncClient(limits=limits, timeout=timeout_seconds)

    async def send_batch(self, packets: List[TelemetryPacket]) -> Tuple[bool, int, float]:
        """Send a batch of telemetry packets to the ingestion endpoint.

        Returns (is_success, http_status_code, latency_seconds).
        """
        if not packets:
            return True, 200, 0.0

        headers = {
            "Content-Type": "application/json",
            "X-Device-Key": self.device_key,
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
            if not is_success:
                logger.warning(f"Ingestion returned unexpected status {response.status_code}: {response.text}")
            return is_success, response.status_code, duration

        except Exception as exc:
            duration = time.perf_counter() - start_time
            logger.error(f"HTTP emission failure to {self.ingestion_url}: {exc}")
            return False, 0, duration

    async def close(self) -> None:
        """Close persistent HTTP client pool."""
        if not self._custom_client and self._client:
            await self._client.aclose()
