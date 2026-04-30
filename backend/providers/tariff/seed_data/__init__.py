"""Bundled tariff seed snapshots.

This package exists so ``importlib.resources`` can locate the JSON
seed files when the backend is installed from a wheel; the empty
``__init__.py`` makes ``backend.providers.tariff.seed_data`` a real
package rather than a plain directory.

Refresh procedure:
1. Pull the latest URDB JSON via ``openei.org/services/doc/rest/util_rates/``
   for each of the top-10 utility keys.
2. Hand-curate down to one default residential rate per utility (most
   common for that utility's customer base — TOU in CA, tiered in
   AZ / WA / CO, flat elsewhere).
3. Save under ``urdb_top10_<year>q<quarter>.json``; bump
   ``SEED_RESOURCE_FILENAME`` in ``urdb.py`` so the rotation is an
   explicit code change, not an implicit data drift.
"""
