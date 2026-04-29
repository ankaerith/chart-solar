from backend.main import app


def test_app_initializes() -> None:
    assert app.title == "Chart Solar API"


def test_routes_registered() -> None:
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/api/health" in paths
    assert "/api/forecast" in paths
    assert "/api/forecast/{job_id}" in paths
    assert "/api/irradiance" in paths
