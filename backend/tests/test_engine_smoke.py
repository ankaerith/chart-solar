from backend.engine.inputs import ForecastInputs
from backend.engine.pipeline import ForecastResult, run_forecast


def test_run_forecast_round_trips_inputs(example_inputs: ForecastInputs) -> None:
    result = run_forecast(example_inputs)
    assert isinstance(result, ForecastResult)
    assert result.inputs == example_inputs


def test_engine_steps_import_cleanly() -> None:
    import backend.engine.steps as steps  # noqa: F401
