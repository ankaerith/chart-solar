"""DC:AC ratio clipping.

Phase 1a: registered modifier that clips DC production at the inverter's
AC limit. Higher ratios (>~1.3) deliberately invite morning/midday clipping
in exchange for shoulder-hour gains; tornado sensitivity will surface this.
"""
