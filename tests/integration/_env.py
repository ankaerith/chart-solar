"""Stdlib .env loader shared by the harness and oracle CLIs."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Populate missing keys in ``os.environ`` from a ``.env`` file.

    Process env wins over file values; missing file is a no-op (we use
    a try/except rather than a pre-check to avoid TOCTOU between the
    existence test and the read).
    """
    try:
        text = path.read_text()
    except FileNotFoundError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
