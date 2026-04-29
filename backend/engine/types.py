"""Shared engine types.

Lives outside ``backend.engine.steps`` so importing it doesn't trigger
``steps/__init__.py`` (which eagerly imports every step module to fire
their ``@register`` decorators). Putting cross-cutting type aliases
here lets ``inputs.py`` and individual step modules share them without
re-introducing the cycle that motivated the original duplication.
"""

from __future__ import annotations

from typing import Literal

ExportRegime = Literal[
    "nem_one_for_one",
    "nem_three_nbt",
    "seg_flat",
    "seg_tou",
]
