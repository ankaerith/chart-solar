"""8760-hour battery dispatch simulation.

Phase 1a: rule-based dispatch (self-consumption / TOU arbitrage / backup).
Inputs: capacity kWh, usable %, round-trip efficiency, max C-rate, reserve %.
Output: hourly SOC, grid import/export, savings vs no-battery baseline.

LP-optimized dispatch is deferred (see PRODUCT_PLAN open items).
"""
