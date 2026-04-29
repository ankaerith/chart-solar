"""Cell-temperature derating.

Handled inside ``engine.dc_production`` by pvlib's ``ModelChain.with_pvwatts``
(SAPM cell-temperature model + ``gamma_pdc`` coefficient). No standalone
step; see ADR 0006.
"""
