from datetime import datetime, timezone
import math
import random
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class GPSLocation(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    altitude: Optional[float] = None
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0)


class OBDData(BaseModel):
    engine_rpm: int = Field(default=0, ge=0)
    speed_kmh: float = Field(default=0.0, ge=0.0)
    coolant_temp_c: Optional[int] = None
    fuel_level_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    throttle_position: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    battery_voltage: Optional[float] = Field(default=None, ge=0.0, le=30.0)
    dtcs: List[str] = Field(default_factory=list)


class TelemetryPacket(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    vehicle_id: str
    device_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: GPSLocation
    obd: OBDData
    metadata: Dict[str, str] = Field(default_factory=dict)


class SimulatedVehicle:
    """Stateful vehicle model simulating kinematic motion and engine thermodynamics."""

    def __init__(
        self,
        tenant_id: str,
        vehicle_id: str,
        device_id: str,
        initial_lat: float = -12.0464,
        initial_lon: float = -77.0428,
    ):
        self.tenant_id = tenant_id
        self.vehicle_id = vehicle_id
        self.device_id = device_id
        self.latitude = initial_lat
        self.longitude = initial_lon
        self.speed_kmh = 50.0
        self.engine_rpm = 2200
        self.coolant_temp_c = 90
        self.battery_voltage = 13.8
        self.fuel_level_percent = 75.0
        self.heading = 90.0  # Heading east initially
        self.active_dtcs: List[str] = []

    def tick(
        self,
        delta_seconds: float,
        rng: random.Random,
        target_temp: Optional[int] = None,
        target_voltage: Optional[float] = None,
        injected_dtcs: Optional[List[str]] = None,
        target_rpm: Optional[int] = None,
    ) -> TelemetryPacket:
        """Advance vehicle state by delta_seconds with physical continuity."""
        # 1. Kinematic speed and RPM adjustment
        if target_rpm is not None:
            self.engine_rpm = target_rpm
            self.speed_kmh = min(120.0, self.engine_rpm / 40.0)
        else:
            speed_delta = rng.uniform(-3.0, 3.0)
            self.speed_kmh = max(10.0, min(110.0, self.speed_kmh + speed_delta))
            # Calculate RPM from speed with slight variation
            self.engine_rpm = int(max(800, self.speed_kmh * 35.0 + rng.uniform(-50, 50)))

        # 2. Heading and Geographic movement (approx 1 deg lat ~ 111 km)
        self.heading = (self.heading + rng.uniform(-5.0, 5.0)) % 360.0
        heading_rad = math.radians(self.heading)
        distance_km = (self.speed_kmh / 3600.0) * delta_seconds
        d_lat = (distance_km / 111.0) * math.cos(heading_rad)
        d_lon = (distance_km / (111.0 * math.cos(math.radians(self.latitude)))) * math.sin(heading_rad)

        self.latitude = max(-90.0, min(90.0, self.latitude + d_lat))
        self.longitude = max(-180.0, min(180.0, self.longitude + d_lon))

        # 3. Thermodynamics (Coolant temperature)
        if target_temp is not None:
            if self.coolant_temp_c < target_temp:
                self.coolant_temp_c += min(2, target_temp - self.coolant_temp_c)
            elif self.coolant_temp_c > target_temp:
                self.coolant_temp_c -= min(1, self.coolant_temp_c - target_temp)
        else:
            # Steady nominal temperature around 90-93°C
            self.coolant_temp_c = int(90 + rng.uniform(-1, 2))

        # 4. Electrical Battery Voltage
        if target_voltage is not None:
            self.battery_voltage = target_voltage
        else:
            self.battery_voltage = round(13.8 + rng.uniform(-0.2, 0.3), 1)

        # 5. Fuel consumption
        self.fuel_level_percent = max(0.0, self.fuel_level_percent - 0.005 * delta_seconds)

        # 6. DTC injection
        if injected_dtcs is not None:
            self.active_dtcs = injected_dtcs
        else:
            self.active_dtcs = []

        return TelemetryPacket(
            tenant_id=self.tenant_id,
            vehicle_id=self.vehicle_id,
            device_id=self.device_id,
            timestamp=datetime.now(timezone.utc),
            location=GPSLocation(
                latitude=round(self.latitude, 6),
                longitude=round(self.longitude, 6),
                altitude=round(120.0 + rng.uniform(-2, 2), 1),
                heading=round(self.heading, 1),
            ),
            obd=OBDData(
                engine_rpm=self.engine_rpm,
                speed_kmh=round(self.speed_kmh, 1),
                coolant_temp_c=self.coolant_temp_c,
                battery_voltage=self.battery_voltage,
                fuel_level_percent=round(self.fuel_level_percent, 1),
                throttle_position=round(min(100.0, max(0.0, self.speed_kmh * 0.8)), 1),
                dtcs=self.active_dtcs,
            ),
            metadata={"source": "erp-iot-simulator"},
        )
