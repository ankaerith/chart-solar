"""Snow loss.

Wraps ``pvlib.snow`` (``coverage_nrel`` Marion + ``loss_townsend``) once
monthly snowfall + relative humidity are routed through the irradiance
providers. Until that data layer lands, this step is a no-op; see
ADR 0006 and chart-solar-9ji.
"""
