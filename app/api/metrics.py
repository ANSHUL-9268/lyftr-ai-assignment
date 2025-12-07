"""
Prometheus-style metrics endpoint.
"""
import time
from typing import Callable

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Metrics"])

# Simple in-memory metrics storage
_metrics = {
    "http_requests_total": {},  # {method_path_status: count}
    "http_request_duration_seconds": {},  # {method_path: [durations]}
    "startup_time": None,
}


def record_request(method: str, path: str, status_code: int, duration: float) -> None:
    """Record an HTTP request metric."""
    # Total requests counter
    key = f'{method}_{path}_{status_code}'
    _metrics["http_requests_total"][key] = _metrics["http_requests_total"].get(key, 0) + 1
    
    # Duration histogram (simplified - just track values)
    duration_key = f'{method}_{path}'
    if duration_key not in _metrics["http_request_duration_seconds"]:
        _metrics["http_request_duration_seconds"][duration_key] = []
    
    durations = _metrics["http_request_duration_seconds"][duration_key]
    durations.append(duration)
    
    # Keep only last 1000 durations to prevent memory issues
    if len(durations) > 1000:
        _metrics["http_request_duration_seconds"][duration_key] = durations[-1000:]


def set_startup_time() -> None:
    """Record application startup time."""
    _metrics["startup_time"] = time.time()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Normalize path to avoid high cardinality
        path = request.url.path
        
        record_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration=duration,
        )
        
        return response


def generate_prometheus_metrics() -> str:
    """Generate Prometheus-format metrics output."""
    lines = []
    
    # Application info
    lines.append("# HELP app_info Application information")
    lines.append("# TYPE app_info gauge")
    lines.append('app_info{version="1.0.0"} 1')
    lines.append("")
    
    # Startup time
    if _metrics["startup_time"]:
        lines.append("# HELP app_start_time_seconds Unix timestamp when the app started")
        lines.append("# TYPE app_start_time_seconds gauge")
        lines.append(f'app_start_time_seconds {_metrics["startup_time"]:.3f}')
        lines.append("")
    
    # HTTP requests total
    lines.append("# HELP http_requests_total Total number of HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    for key, count in _metrics["http_requests_total"].items():
        parts = key.rsplit("_", 1)
        method_path = parts[0]
        status = parts[1]
        method_path_parts = method_path.split("_", 1)
        method = method_path_parts[0]
        path = method_path_parts[1] if len(method_path_parts) > 1 else "/"
        lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')
    lines.append("")
    
    # HTTP request duration (simplified histogram summary)
    lines.append("# HELP http_request_duration_seconds HTTP request duration in seconds")
    lines.append("# TYPE http_request_duration_seconds summary")
    for key, durations in _metrics["http_request_duration_seconds"].items():
        if durations:
            parts = key.split("_", 1)
            method = parts[0]
            path = parts[1] if len(parts) > 1 else "/"
            avg = sum(durations) / len(durations)
            count = len(durations)
            total = sum(durations)
            lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}')
            lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}')
    
    return "\n".join(lines)


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Returns metrics in Prometheus exposition format.",
    response_class=Response,
)
async def metrics() -> Response:
    """
    Prometheus-style metrics endpoint.
    
    Returns metrics in Prometheus text format.
    """
    content = generate_prometheus_metrics()
    return Response(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
