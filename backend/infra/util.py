"""Cross-cutting helpers that don't deserve their own module yet.

Currently:

* :func:`utc_now` — single source of truth for "now, in UTC, as a
  timezone-aware datetime". Replaces ~4 hand-rolled ``_utc_now`` helpers
  scattered through services + providers.
* :func:`sha256_hex` — sha256 hex digest of bytes-or-str input. Replaces
  the inline ``hashlib.sha256(...).hexdigest()`` triplet that appears
  wherever we hash an opaque token or a canonical request body.

The pure-math layers ``backend.engine`` and ``backend.domain`` are
forbidden from importing ``backend.infra`` (importlinter contract
``engine is pure``); both keep their own minimal local helpers and
deliberately do not call into here. That's an acceptable cost — the
duplication is two-line and on the right side of the purity boundary.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Now, in UTC, as a timezone-aware datetime.

    Preferred over ``datetime.now(UTC)`` at call sites only because every
    service module already wanted a parameterless callable to pass to
    ``Callable[[], datetime] = utc_now`` defaults — naming it once here
    avoids re-declaring the same lambda everywhere.
    """
    return datetime.now(UTC)


def sha256_hex(data: bytes | str) -> str:
    """sha256 hex digest of ``data``.

    Strings are encoded as UTF-8 before hashing; bytes pass through. Use
    this anywhere we hash opaque tokens, canonical request bodies, or
    similar fixed-output identifiers. Not for content-addressed JSON
    snapshots — those need the canonical-JSON pre-pass in
    ``backend.engine.snapshot.hash_canonical``.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
