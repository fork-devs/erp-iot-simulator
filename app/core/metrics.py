from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Counter for sent telemetry items (streaming packets or batch snapshots)
PACKETS_SENT = Counter(
    "iot_simulator_packets_sent_total",
    "Total number of simulated telemetry packets or snapshots sent",
    ["mode", "scenario", "status"],
)

# Histogram for HTTP request latency duration in seconds
EMISSION_DURATION = Histogram(
    "iot_simulator_emission_duration_seconds",
    "HTTP emission request round-trip latency in seconds",
    ["mode", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Gauge for active simulated vehicles in fleet
ACTIVE_VEHICLES = Gauge(
    "iot_simulator_active_vehicles",
    "Number of active simulated vehicles in the fleet",
)

# Gauge for instantaneous throughput (messages per second)
CURRENT_THROUGHPUT = Gauge(
    "iot_simulator_current_throughput_mps",
    "Real-time message emission throughput in messages per second",
)

# Counter for HTTP emission failures
HTTP_FAILURES = Counter(
    "iot_simulator_http_failures_total",
    "Count of HTTP emission failures grouped by status code",
    ["status_code"],
)


def get_metrics_content() -> bytes:
    """Generate Prometheus exposition text format bytes."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Return the official Prometheus metrics content-type string."""
    return CONTENT_TYPE_LATEST
