"""Snow loss model (latitude-dependent).

Phase 1a: applies pvlib's snow-coverage model to AC output for sites where
snow cover is non-trivial. No-op below ~35° lat.
"""
