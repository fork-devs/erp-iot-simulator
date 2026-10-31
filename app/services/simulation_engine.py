import asyncio
import logging
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.core.metrics import ACTIVE_VEHICLES, CURRENT_THROUGHPUT
from app.domain.generators import FleetGenerator
from app.domain.scenarios import SimulationScenario
from app.services.http_emitter import HttpEmitter

logger = logging.getLogger(__name__)


class SimulationStatus(BaseModel):
    is_running: bool = False
    scenario: SimulationScenario = SimulationScenario.NORMAL_DRIVING
    emission_mode: str = "STREAM"
    branch_id: Optional[str] = None
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

    def __init__(
        self,
        emitter: HttpEmitter,
        tenant_id: str = "00000000-0000-0000-0000-000000000001",
        default_branch_id: Optional[str] = "00000000-0000-0000-0000-000000000002",
        default_emission_mode: str = "STREAM",
    ):
        self._emitter = emitter
        self._tenant_id = tenant_id
        self._default_branch_id = default_branch_id
        self._default_emission_mode = default_emission_mode
        self._generator: Optional[FleetGenerator] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._start_time: float = 0.0

        # Metrics & Settings
        self._scenario = SimulationScenario.NORMAL_DRIVING
        self._emission_mode = default_emission_mode
        self._branch_id = default_branch_id
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
        emission_mode: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> None:
        """Start an asynchronous simulation run."""
        if self._running:
            await self.stop()

        self._scenario = scenario
        self._emission_mode = (emission_mode or self._default_emission_mode).upper()
        self._branch_id = branch_id or self._default_branch_id
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
            branch_id=self._branch_id,
        )

        self._running = True
        ACTIVE_VEHICLES.set(self._vehicle_count)
        self._task = asyncio.create_task(self._execution_loop(duration_seconds))
        logger.info(
            f"Simulation started: scenario={scenario.value}, mode={self._emission_mode}, "
            f"vehicles={vehicle_count}, rate={rate_per_sec} msg/s, seed={seed}"
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
        ACTIVE_VEHICLES.set(0)
        CURRENT_THROUGHPUT.set(0.0)
        logger.info("Simulation stopped")

    def get_status(self) -> SimulationStatus:
        """Return real-time operational status and metrics."""
        elapsed = time.perf_counter() - self._start_time if self._running else 0.0
        throughput = (self._total_sent / elapsed) if elapsed > 0 else 0.0
        if self._running:
            CURRENT_THROUGHPUT.set(round(throughput, 2))

        return SimulationStatus(
            is_running=self._running,
            scenario=self._scenario,
            emission_mode=self._emission_mode,
            branch_id=self._branch_id,
            vehicle_count=self._vehicle_count,
            target_rate_per_sec=self._target_rate,
            total_sent=self._total_sent,
            total_success=self._total_success,
            total_failed=self._total_failed,
            elapsed_seconds=round(elapsed, 2),
            current_throughput_mps=round(throughput, 2),
            last_error=self._last_error,
        )

    async def send_burst(
        self,
        batch_size: int = 50,
        scenario: SimulationScenario = SimulationScenario.HIGH_THROUGHPUT_BURST,
        emission_mode: str = "BATCH",
        branch_id: Optional[str] = None,
        device_id: Optional[str] = None,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Execute a synchronous one-shot burst emission."""
        batch_size = min(100, max(1, batch_size))
        eff_branch_id = branch_id or self._default_branch_id
        eff_mode = emission_mode.upper()

        generator = FleetGenerator(
            tenant_id=self._tenant_id,
            vehicle_count=max(5, (batch_size // 10) + 1),
            seed=seed,
            branch_id=eff_branch_id,
        )

        if eff_mode == "BATCH":
            batch = generator.generate_telemetry_batch(
                device_id=device_id,
                snapshot_count=batch_size,
                scenario=scenario,
                delta_seconds=0.5,
            )
            ok, status_code, duration = await self._emitter.send_telemetry_batch(
                batch, scenario=scenario.value
            )
            count = len(batch.snapshots)
        else:
            packets = generator.generate_burst_batch(batch_size=batch_size, scenario=scenario)
            ok, status_code, duration = await self._emitter.send_batch(
                packets, scenario=scenario.value
            )
            count = len(packets)

        return {
            "success": ok,
            "status_code": status_code,
            "latency_seconds": round(duration, 4),
            "sent_count": count,
            "emission_mode": eff_mode,
            "scenario": scenario.value,
            "branch_id": eff_branch_id,
        }

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

                if self._emission_mode == "BATCH":
                    # Generate batch for round-robin fleet vehicle
                    batch = self._generator.generate_telemetry_batch(
                        snapshot_count=min(20, batch_size),
                        scenario=self._scenario,
                        delta_seconds=interval,
                    )
                    count = len(batch.snapshots)
                    ok, status_code, _ = await self._emitter.send_telemetry_batch(
                        batch, scenario=self._scenario.value
                    )
                else:
                    # Stream mode
                    if self._scenario == SimulationScenario.HIGH_THROUGHPUT_BURST:
                        packets = self._generator.generate_burst_batch(batch_size=batch_size, scenario=self._scenario)
                    else:
                        packets = self._generator.generate_tick(delta_seconds=interval, scenario=self._scenario)
                        if len(packets) > batch_size:
                            packets = packets[:batch_size]
                    count = len(packets)
                    ok, status_code, _ = await self._emitter.send_batch(
                        packets, scenario=self._scenario.value
                    )

                self._total_sent += count
                if ok:
                    self._total_success += count
                else:
                    self._total_failed += count
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
            ACTIVE_VEHICLES.set(0)
            CURRENT_THROUGHPUT.set(0.0)
