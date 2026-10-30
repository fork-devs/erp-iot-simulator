from app.core.config import Settings


def test_default_config():
    settings = Settings()
    assert settings.SERVER_PORT == 8089
    assert settings.ENVIRONMENT == "dev"
    assert settings.INGESTION_URL == "http://localhost:8087/api/v1/iot/telemetry"
    assert settings.DEFAULT_RANDOM_SEED == 42
    assert settings.DEFAULT_RATE_LIMIT == 50


def test_custom_env_config(monkeypatch):
    monkeypatch.setenv("SERVER_PORT", "9999")
    monkeypatch.setenv("DEFAULT_RATE_LIMIT", "500")
    monkeypatch.setenv("DEFAULT_RANDOM_SEED", "12345")

    settings = Settings()
    assert settings.SERVER_PORT == 9999
    assert settings.DEFAULT_RATE_LIMIT == 500
    assert settings.DEFAULT_RANDOM_SEED == 12345
