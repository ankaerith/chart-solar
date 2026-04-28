"""Irradiance source adapters (NSRDB / PVGIS / Open-Meteo).

Phase 1a: pluggable IrradianceProvider returning hourly GHI/DNI/DHI +
ambient temperature + wind speed for the user's lat/lon. Cached per-bucket
in Postgres. NREL PSM3 for US, PVGIS for UK/EU, Open-Meteo as global fallback.
"""
