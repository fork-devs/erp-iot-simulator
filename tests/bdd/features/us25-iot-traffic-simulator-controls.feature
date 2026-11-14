@US25 @EP10 @erp-iot-simulator
# User Story: US25 - Execute synthetic IoT telemetry traffic simulations
Feature: IoT Telemetry Traffic Simulator Controls
  As a workshop administrator or QA engineer
  I want to start deterministic telemetry simulations, trigger stress bursts, inspect status, and stop simulations
  So that the ingestion pipeline capacity can be verified under controlled load

  Background:
    Given the "erp-iot-simulator" REST API is available at "/api/v1/simulator"

  @US25 @happy-path
  # User Story: US25 - Start, inspect status, and stop synthetic IoT simulation
  Scenario: Workshop administrator starts a continuous simulation, checks status, and stops it
    Given an authenticated user with role "WORKSHOP_ADMIN"
    When the client sends a "POST" request to "/api/v1/simulator/start" with JSON payload:
      """
      {
        "vehicleCount": 5,
        "intervalMs": 1000,
        "seed": 42
      }
      """
    Then the response status code should be 202
    When the client sends a "GET" request to "/api/v1/simulator/status"
    Then the response status code should be 200
    And the JSON response field "running" should be true
    When the client sends a "POST" request to "/api/v1/simulator/stop"
    Then the response status code should be 200
    And the JSON response field "running" should be false

  @US25 @negative
  # User Story: US25 - Reject burst generation with invalid vehicle count
  Scenario: Triggering a telemetry burst with zero or negative vehicle count returns HTTP 422 or 400
    Given an authenticated user with role "WORKSHOP_ADMIN"
    When the client sends a "POST" request to "/api/v1/simulator/burst" with JSON payload:
      """
      {
        "vehicleCount": 0,
        "eventsPerVehicle": -10
      }
      """
    Then the response status code should be 422
    And the JSON response should contain validation error details
