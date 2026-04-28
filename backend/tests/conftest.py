import pytest

from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)


@pytest.fixture
def example_inputs() -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(lat=47.6, lon=-122.3, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )
