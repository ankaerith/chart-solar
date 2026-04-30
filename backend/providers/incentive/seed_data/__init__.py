"""Bundled incentive seed snapshots.

This package exists so ``importlib.resources`` can find the seed JSON
when the backend is installed from a wheel; the empty ``__init__.py``
makes ``backend.providers.incentive.seed_data`` a real package rather
than a plain directory.

Refresh procedure:
1. Cross-check each state's program against its energy office page +
   DSIRE entry (CC-BY-SA — license review pending per chart-solar
   Phase 3a, so DSIRE data is *not* embedded directly here).
2. Bump amounts where the program announces a step-down; record the
   next-block rate as a future-dated separate entry rather than
   editing the current one in place (so an audit can reproduce a
   yesterday-dated forecast against the rate that applied then).
3. Save under ``state_incentives_<year>q<quarter>.json``; bump
   ``SEED_RESOURCE_FILENAME`` in ``state_seed.py`` so the rotation
   is an explicit code change, not silent data drift.
"""
