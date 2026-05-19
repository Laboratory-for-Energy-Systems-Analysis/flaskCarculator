import os


def _get_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


workers = _get_int("WEB_CONCURRENCY", 1)
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = _get_int("GUNICORN_THREADS", 2)

# LCA calculations are expensive; this timeout is Gunicorn's worker heartbeat
# timeout, not a user-facing request SLA.
timeout = _get_int("GUNICORN_TIMEOUT", 300)
graceful_timeout = _get_int("GUNICORN_GRACEFUL_TIMEOUT", 60)
keepalive = _get_int("GUNICORN_KEEPALIVE", 5)

# Recycle workers periodically to release memory held by native scientific
# libraries after repeated LCA calculations.
max_requests = _get_int("GUNICORN_MAX_REQUESTS", 100)
max_requests_jitter = _get_int("GUNICORN_MAX_REQUESTS_JITTER", 20)

