import logging
import os
import time

import sentry_sdk
import structlog
from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from sentry_sdk.integrations.logging import LoggingIntegration
from starlette.middleware.base import BaseHTTPMiddleware


# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)


def configure_structlog():
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(10),
    )


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = getattr(response, "status_code", 500)
            return response
        finally:
            resp_time = time.time() - start_time
            endpoint = request.url.path or "-"
            REQUEST_COUNT.labels(request.method, endpoint, str(status_code)).inc()
            REQUEST_LATENCY.labels(request.method, endpoint).observe(resp_time)


# Simple helper to expose metrics in-process
def metrics_response():
    # If using multiprocess servers (for example, Gunicorn) the registry setup
    # differs; this helper is for single-process setups used in development.
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


def init(app):
    # Configure structlog
    configure_structlog()

    # Initialize Sentry if DSN is provided
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        # Capture errors and optionally traces
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )
        # compute traces sampling rate separately to keep lines short
        traces_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
        environment = os.getenv("SENTRY_ENV", "development")

        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[sentry_logging],
            traces_sample_rate=traces_rate,
            environment=environment,
        )

    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint
    @app.get("/metrics")
    async def _metrics():
        return metrics_response()

    # Readiness endpoint
    @app.get("/ready")
    async def _ready():
        # Optionally check DB connectivity via env var
        from .session import engine

        try:
            # we only need to ensure we can acquire a connection; don't assign it to an
            # unused variable to satisfy linters
            with engine.connect():
                return {"ready": True}
        except Exception as exc:  # pragma: no cover - best-effort readiness
            structlog.get_logger().error("readiness_check_failed", error=str(exc))
            return Response(status_code=503, content="not ready")
