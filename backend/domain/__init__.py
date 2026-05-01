"""Pure domain types — Pydantic / dataclass shapes shared across layers.

`backend.domain` is a deliberately empty package today; downstream
modules (`events`, future `inputs`, `outputs`, …) are imported via
their fully-qualified paths so the namespace stays flat. The intent
is the same as the engine: zero IO, zero framework imports, just
data shapes and pure helpers.
"""
