"""DC:AC inverter clipping.

Handled inside ``engine.dc_production`` by pvlib's ``ModelChain.with_pvwatts``
(``inverter_parameters['pdc0']`` saturates the AC output). No standalone
step; see ADR 0006. The audit's "aggressive DC:AC ratio" flag reads
``DcProductionResult.dc_ac_ratio`` from the dc_production step.
"""
