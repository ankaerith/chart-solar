"""Small helpers shared across infra/services/providers.

Engine + domain don't import this module — the importlinter contract
``engine is pure`` keeps those layers free of ``backend.infra``, so they
keep their own two-line locals.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Now, in UTC, as a timezone-aware datetime."""
    return datetime.now(UTC)


def sha256_hex(data: bytes | str) -> str:
    """sha256 hex digest of ``data``; strings are encoded as UTF-8.

    Not for content-addressed JSON snapshots — those need the canonical-JSON
    pre-pass in ``backend.engine.snapshot.hash_canonical``.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
