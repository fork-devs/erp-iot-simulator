import asyncio
import logging
import time
from typing import Optional
from pydantic import BaseModel

from app.domain.generators import FleetGenerator
from app.domain.scenarios import SimulationScenario
from app.services.http_emitter import HttpEmitter

logger = logging.getLogger(__name__)


class SimulationStatus(BaseModel):
    is_running: bool = False
    scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING
    vehicle_count: int = 0
    target_rate_per_sec: int = 0
    total_sent: int = 0
    total_success: int = 0
    total_failed: int = 0
    elapsed_seconds: float = 0.0
    current_throughput_mps: float = 0.0
    last_error: Optional[str] = None


class SimulationEngine:
    """Orchestrates fleet simulation execution, rate pacing, and telemetry emission."""

    def __init__(self, emitter: HttpEmitter, tenant_id: str = "00000000-0000-0000-0000-000000000001"):
        self._emitter = emitter
        self._tenant_id = tenant_id
        self._generator: Optional[FleetGenerator] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._start_time: float = 0.0

        # Metrics
        self._scenario = SimulationScenario.NORMAL_DRIVING
        self._vehicle_count = 0
        self._target_rate = 0
        self._total_sent = 0
        self._total_success = 0
        self._total_failed = 0
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(
        self,
        scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING,
        vehicle_count: int = 10,
        rate_per_sec: int = 50,
        seed: int = 42,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Start an asynchronous simulation run."""
        if self._running:
            await self.stop()

        self._scenario = scenario
        self._vehicle_count = vehicle_count
        self._target_rate = max(1, rate_per_sec)
        self._total_sent = 0
        self._total_success = 0
        self._total_failed = 0
        self._last_error = None
        self._start_time = time.perf_counter()

        self._generator = FleetGenerator(
            tenant_id=self._tenant_id,
            vehicle_count=self._vehicle_count,
            seed=seed,
        )

        self._running = True
        self._task = asyncio.create_task(self._execution_loop(duration_seconds))
        logger.info(
            f"Simulation started: scenario={scenario.value}, vehicles={vehicle_count}, rate={rate_per_sec} msg/s, seed={seed}"
        )

    async def stop(self) -> None:
        """Stop active simulation cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulation stopped")

    def get_status(self) -> SimulationStatus:
        """Return real-time operational status and metrics."""
        elapsed = time.perf_counter() - self._start_time if self._running else 0.0
        throughput = (self._total_sent / elapsed) if elapsed > 0 else 0.0

        return SimulationStatus(
            is_running=self._running,
            scenario=self._scenario,
            vehicle_count=self._vehicle_count,
            target_rate_per_sec=self._target_rate,
            total_sent=self._total_sent,
            total_success=self._total_success,
            total_failed=self._total_failed,
            elapsed_seconds=round(elapsed, 2),
            current_throughput_mps=round(throughput, 2),
            last_error=self._last_error,
        )

    async def _execution_loop(self, duration_seconds: Optional[int]) -> None:
        """Main paced emission loop."""
        batch_size = min(100, max(1, self._target_rate // 10))
        interval = batch_size / self._target_rate

        try:
            while self._running:
                loop_start = time.perf_counter()

                # Check duration limit
                if duration_seconds and (loop_start - self._start_time) >= duration_seconds:
                    logger.info(f"Simulation reached configured duration of {duration_seconds}s. Stopping.")
                    break

                # Generate batch
                if self._scenario == SimulationScenario.HIGH_THROUGHPUT_BURST:
                    packets = self._generator.generate_burst_batch(batch_size=batch_size, scenario=self._scenario)
                else:
                    packets = self._generator.generate_tick(delta_seconds=interval, scenario=self._scenario)
                    if len(packets) > batch_size:
                        packets = packets[:batch_size]

                # Emit over HTTP
                ok, status_code, _ = await self._emitter.send_batch(packets)
                self._total_sent += len(packets)
                if ok:
                    self._total_success += len(packets)
                else:
                    self._total_failed += len(packets)
                    self._last_error = f"HTTP status {status_code}"

                # Pacing
                elapsed = time.perf_counter() - loop_start
                sleep_time = interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._last_error = str(exc)
            logger.error(f"Error in simulation execution loop: {exc}", exc_info=True)
        finally:
            self._running = False
