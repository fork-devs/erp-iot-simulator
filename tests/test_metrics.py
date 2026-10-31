from app.core.metrics import (
    ACTIVE_VEHICLES,
    CURRENT_THROUGHPUT,
    EMISSION_DURATION,
    HTTP_FAILURES,
    PACKETS_SENT,
    get_metrics_content,
    get_metrics_content_type,
)


def test_prometheus_metrics_registry():
    # Test setting values and observing metrics
    ACTIVE_VEHICLES.set(25)
    CURRENT_THROUGHPUT.set(150.5)
    PACKETS_SENT.labels(mode="STREAM", scenario="NORMAL_DRIVING", status="success").inc(10)
    PACKETS_SENT.labels(mode="BATCH", scenario="ENGINE_OVERHEAT", status="failed").inc(5)
    EMISSION_DURATION.labels(mode="STREAM", endpoint="/api/v1/iot/telemetry").observe(0.045)
    HTTP_FAILURES.labels(status_code="500").inc(1)

    content = get_metrics_content().decode("utf-8")
    content_type = get_metrics_content_type()

    assert "text/plain" in content_type
    assert "iot_simulator_active_vehicles 25.0" in content
    assert "iot_simulator_current_throughput_mps 150.5" in content
    assert 'iot_simulator_packets_sent_total{mode="STREAM",scenario="NORMAL_DRIVING",status="success"}' in content
    assert 'iot_simulator_packets_sent_total{mode="BATCH",scenario="ENGINE_OVERHEAT",status="failed"}' in content
    assert 'iot_simulator_http_failures_total{status_code="500"}' in content
