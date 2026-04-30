"""Cross-step integration helpers.

The pure-math step modules in ``backend.engine.steps`` produce
artefacts that the pipeline consumes independently. Some regulatory
regimes (NBT monthly true-up, UK SEG annual settlement) require
*joining* those artefacts together — netting export credit against
import bills with rollover semantics. Those netting helpers live here
rather than in any one step module: they're integrations, not steps.
"""
