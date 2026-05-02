from fastapi.testclient import TestClient

from backend.config import MissingConfigError
from backend.main import app


def test_app_initializes() -> None:
    assert app.title == "Chart Solar API"


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/api/health" in paths
    assert "/api/forecast" in paths
    assert "/api/forecast/{job_id}" in paths
    assert "/api/irradiance" in paths


def test_missing_config_error_renders_structured_503() -> None:
    """A ``MissingConfigError`` raised from a route must surface as a
    structured JSON 503 — not the plain-text 500 the unhandled
    ``RuntimeError`` would produce.
    """

    @app.get("/__missing_config_probe__")
    def _probe() -> dict[str, str]:  # pragma: no cover — invoked via TestClient
        raise MissingConfigError("PROBE_SECRET")

    probe_path = "/__missing_config_probe__"
    try:
        response = TestClient(app, raise_server_exceptions=False).get(probe_path)
    finally:
        # Drop the probe route from the live router so this test doesn't
        # leak state into others that introspect ``app.routes``.
        app.routes[:] = [r for r in app.routes if getattr(r, "path", "") != probe_path]

    assert response.status_code == 503
    assert response.json() == {"detail": "required setting `PROBE_SECRET` is not configured"}
