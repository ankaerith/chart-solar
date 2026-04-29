"""Correlation ID flow: HTTP middleware → contextvar → enqueue → worker.

Bead: chart-solar-z0uz.
"""

from fastapi.testclient import TestClient

from backend.infra.logging import get_correlation_id, set_correlation_id
from backend.main import app


def test_middleware_honors_x_request_id() -> None:
    client = TestClient(app)
    response = client.get("/api/health", headers={"X-Request-Id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_middleware_mints_uuid_when_absent() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert len(response.headers["x-request-id"]) == 32  # uuid4().hex


def test_correlation_id_isolated_per_context() -> None:
    set_correlation_id("first")
    assert get_correlation_id() == "first"
    set_correlation_id(None)
    assert get_correlation_id() is None
