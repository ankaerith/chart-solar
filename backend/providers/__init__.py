"""Ports + adapters for upstream data sources.

Each subpackage defines a `Protocol` in `__init__.py` and ships
adapters per upstream. Tests use fakes against the same Protocol so the
engine never imports a concrete adapter directly. See
`docs/ENGINEERING.md § Backend layout`.
"""
