"""RQ worker: consumes the `forecasts` queue and runs the engine pipeline.

The worker is responsible for the network-IO portion of a forecast (fetching
TMY weather data) and then handing the pre-fetched ``TmyData`` to the
sync engine pipeline. Keeping the engine sync lets it run inside RQ
without an event loop and stay easily testable with synthetic weather.

TMY responses are cached in Postgres bucketed by 4-decimal lat/lon ×
provider source; subsequent forecasts at the same bucket reuse the
cached payload. See ``backend.db.tmy_cache`` for the schema + helpers.
"""

import asyncio
from typing import Any

from rq import Worker, get_current_job

import backend.database as _db
from backend.db.tmy_cache import lookup_cached_tmy, store_cached_tmy
from backend.engine.inputs import ForecastInputs
from backend.engine.pipeline import run_forecast
from backend.infra.logging import configure_logging, get_logger, set_correlation_id
from backend.providers.irradiance import TmyData, pick_provider
from backend.workers.queue import get_queue, get_redis

log = get_logger(__name__)


def run_forecast_job(payload: dict[str, Any]) -> dict[str, Any]:
    job = get_current_job()
    job_id = job.id if job else None
    set_correlation_id(job.meta.get("correlation_id") if job else None)

    log.info("forecast.start", job_id=job_id)
    inputs = ForecastInputs.model_validate(payload)
    tmy = _fetch_tmy(inputs)
    result = run_forecast(inputs, tmy=tmy)
    log.info("forecast.complete", job_id=job_id)
    # Pydantic models in artifacts need explicit JSON serialisation; RQ
    # only knows how to pickle, but downstream consumers want JSON.
    return {
        "artifacts": {
            key: artifact.model_dump(mode="json") if hasattr(artifact, "model_dump") else artifact
            for key, artifact in result.artifacts.items()
        }
    }


def _fetch_tmy(inputs: ForecastInputs) -> TmyData:
    """Resolve the TMY for this forecast's lat/lon, hitting the bucketed
    Postgres cache first.

    The auto-router decides which provider's slice to consult; on a
    miss we call the live provider and write the result back. Wrapped
    in ``asyncio.run`` because RQ workers run sync but both the
    irradiance Protocol and the AsyncSession-based cache are async.
    """
    return asyncio.run(_fetch_tmy_async(inputs))


async def _fetch_tmy_async(inputs: ForecastInputs) -> TmyData:
    provider = pick_provider(inputs.system.lat, inputs.system.lon)

    async with _db.SessionLocal() as session:
        cached = await lookup_cached_tmy(
            session,
            lat=inputs.system.lat,
            lon=inputs.system.lon,
            source=provider.name,
        )
    if cached is not None:
        log.info("tmy.cache_hit", source=provider.name)
        return cached

    log.info("tmy.cache_miss", source=provider.name)
    tmy = await provider.fetch_tmy(inputs.system.lat, inputs.system.lon)
    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, tmy)
    return tmy


def main() -> None:
    configure_logging("worker")
    worker = Worker([get_queue()], connection=get_redis())
    worker.work()


if __name__ == "__main__":
    main()
