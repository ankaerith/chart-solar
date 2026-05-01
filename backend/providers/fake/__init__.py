"""Hand-curated fakes that satisfy every Provider Protocol.

Each fake is deterministic and offline — no httpx, no DB, no env vars.
Tests import these directly to swap out the live adapters; dev runs
also pick them up by default until live API keys are configured. They
exist precisely so `engine/` stays Protocol-agnostic.
"""

from backend.providers.fake.email import FakeEmailProvider
from backend.providers.fake.geocoding import FakeGeocodingProvider
from backend.providers.fake.incentive import FakeIncentiveProvider
from backend.providers.fake.irradiance import FakeIrradianceProvider, synthetic_tmy
from backend.providers.fake.monitoring import FakeMonitoringProvider
from backend.providers.fake.storage import FakeStorageProvider
from backend.providers.fake.tariff import FakeTariffProvider

__all__ = [
    "FakeEmailProvider",
    "FakeGeocodingProvider",
    "FakeIncentiveProvider",
    "FakeIrradianceProvider",
    "FakeMonitoringProvider",
    "FakeStorageProvider",
    "FakeTariffProvider",
    "synthetic_tmy",
]
