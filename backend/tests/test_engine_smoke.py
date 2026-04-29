from backend.engine.inputs import ForecastInputs
from backend.engine.pipeline import ForecastResult, run_forecast
from backend.providers.fake import synthetic_tmy


def test_run_forecast_round_trips_inputs(example_inputs: ForecastInputs) -> None:
    tmy = synthetic_tmy(
        lat=example_inputs.system.lat,
        lon=example_inputs.system.lon,
    )
    result = run_forecast(example_inputs, tmy=tmy)
    assert isinstance(result, ForecastResult)
    assert result.inputs == example_inputs


def test_engine_steps_import_cleanly() -> None:
    import backend.engine.steps as steps  # noqa: F401
