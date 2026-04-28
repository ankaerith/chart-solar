"""Monte Carlo wrapper.

Phase 1a: stochastic axes — rate-escalation path × weather year × degradation
× hold duration. Output is a distribution (P10/P50/P90 fan), never a point
estimate. Sample count and which axes are sampled are configurable.
"""
