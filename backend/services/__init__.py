"""Service orchestration layer.

`backend.services.*` sits between `backend.api.*` (HTTP shapes) and
`backend.workers.*` / `backend.engine.*` (compute + queues). API routes
call into a service module; the service decides what queue to submit
to, what infra probe to run, and how to translate worker-internal
states into stable API vocabulary. Keeping that split lets the
import-linter forbid `api -> workers` directly without losing the
ability to enqueue work — every hop into a queue or worker first goes
through a service entry point.
"""
