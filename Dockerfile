FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY backend ./backend
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000
# ``--no-proxy-headers`` keeps uvicorn from rewriting ``scope["client"]``
# from a client-supplied ``X-Forwarded-For`` — without this, the rate
# limiter's per-IP bucket can be bypassed (chart-solar-gc0o). Deployments
# with a trusted reverse proxy in front should override CMD with
# ``--proxy-headers --forwarded-allow-ips=<proxy-CIDR>`` AND set
# ``TRUST_FORWARDED_FOR_HOPS`` to the matching hop count.
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
