"""Deterministic in-memory `TariffProvider`.

Defaults cover US + GB with a flat rate; tests pre-populate the
registry via `.register()` to inject tiered / TOU / edge-case shapes."""

from __future__ import annotations

from backend.providers.tariff import TariffQuery, TariffSchedule


class FakeTariffProvider:
    """Looks up by `(country, utility, zip_code)` tuple. Falls through
    to a country default if no match registered."""

    name: str = "fake-tariff"

    def __init__(self) -> None:
        self._registry: dict[tuple[str, str | None, str | None], TariffSchedule] = {}
        self._defaults: dict[str, TariffSchedule] = {
            "US": TariffSchedule(
                name="US default flat",
                utility="utility-default",
                country="US",
                currency="USD",
                structure="flat",
                fixed_monthly_charge=10.0,
                flat_rate_per_kwh=0.16,
            ),
            "GB": TariffSchedule(
                name="GB default flat",
                utility="utility-default",
                country="GB",
                currency="GBP",
                structure="flat",
                fixed_monthly_charge=8.0,
                flat_rate_per_kwh=0.27,
            ),
        }

    def register(self, query: TariffQuery, schedule: TariffSchedule) -> None:
        self._registry[(query.country, query.utility, query.zip_code)] = schedule

    async def fetch(self, query: TariffQuery) -> TariffSchedule:
        key = (query.country, query.utility, query.zip_code)
        if key in self._registry:
            return self._registry[key]
        if query.country in self._defaults:
            return self._defaults[query.country]
        raise LookupError(
            f"FakeTariffProvider has no default for country={query.country!r}; "
            f"call .register() in the test setup"
        )
