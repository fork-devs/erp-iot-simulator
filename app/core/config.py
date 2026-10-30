from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the telemetry simulator."""

    ENVIRONMENT: str = Field(default="dev", description="Runtime environment (dev, staging, prod)")
    SERVER_PORT: int = Field(default=8089, description="Simulator HTTP control port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Target Ingestion Service
    INGESTION_URL: str = Field(
        default="http://localhost:8087/api/v1/iot/telemetry",
        description="Target erp-iot-ingestion endpoint URL",
    )
    DEVICE_KEY: str = Field(
        default="test-device-key",
        description="Pre-shared device key authenticated by erp-iot-ingestion",
    )
    TENANT_ID: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        description="Default multi-tenant UUID for simulated fleet",
    )

    # Simulation defaults
    DEFAULT_VEHICLES: int = Field(default=10, description="Default number of simulated vehicles in fleet")
    DEFAULT_RATE_LIMIT: int = Field(default=50, description="Default messages per second emission rate")
    DEFAULT_BURST_BATCH_SIZE: int = Field(default=100, description="Batch payload size for high-throughput bursts")
    DEFAULT_RANDOM_SEED: int = Field(default=42, description="Random seed for reproducible telemetry")

    # HTTP Client Performance
    HTTP_POOL_CONNECTIONS: int = Field(default=100, description="Maximum keep-alive connections in HTTP client pool")
    HTTP_TIMEOUT_SECONDS: float = Field(default=5.0, description="HTTP request timeout in seconds")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
