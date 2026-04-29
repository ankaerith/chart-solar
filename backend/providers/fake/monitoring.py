"""Deterministic in-memory `MonitoringProvider`.

Holds a tiny in-memory production series per registered site so audit
flows can exercise the "ingest → compare to forecast" loop without
hitting Enphase / SolarEdge / etc."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from backend.providers.monitoring import (
    MonitoringProvider,
    MonitoringReading,
    MonitoringSite,
)


class FakeMonitoringProvider:
    """All sites + all readings are in-process state. Tests register
    sites + production via `.add_site()` / `.add_readings()`. Credentials
    are ignored (every credential dict resolves the same store)."""

    name: str = "fake-monitoring"

    def __init__(self) -> None:
        self._sites: dict[str, MonitoringSite] = {}
        self._production: dict[str, list[MonitoringReading]] = {}

    def add_site(self, site: MonitoringSite) -> None:
        self._sites[site.site_id] = site
        self._production.setdefault(site.site_id, [])

    def add_readings(self, site_id: str, readings: list[MonitoringReading]) -> None:
        self._production.setdefault(site_id, []).extend(readings)

    async def list_sites(
        self,
        credential: dict[str, str],  # noqa: ARG002 — fakes ignore credentials
    ) -> list[MonitoringSite]:
        return list(self._sites.values())

    async def fetch_production(
        self,
        credential: dict[str, str],  # noqa: ARG002
        site_id: str,
        start: date,
        end: date,
    ) -> list[MonitoringReading]:
        if site_id not in self._sites:
            raise LookupError(f"unknown monitoring site: {site_id!r}")
        start_ts = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
        end_ts = datetime.combine(end, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
        return [r for r in self._production[site_id] if start_ts <= r.timestamp_utc < end_ts]


_: MonitoringProvider = FakeMonitoringProvider()
