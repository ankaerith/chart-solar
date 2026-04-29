"""Soiling loss.

Wraps ``pvlib.soiling`` (HSU / Kimber models) once monthly precipitation
is routed through the irradiance providers. Until that data layer
lands, this step is a no-op; see ADR 0006 and chart-solar-743.
"""
