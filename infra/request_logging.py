"""
Request/Response Logging Middleware: structured logging for all API calls.

Logs:
- Request details (method, path, client IP)
- Response status and duration
- Sensitive fields redacted (tokens, session IDs partially masked)
"""

import logging
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log incoming requests and outgoing responses."""
    
    # Paths to skip logging (health checks, metrics)
    SKIP_LOGGING_PATHS = ["/health", "/metrics", "/openapi.json", "/docs", "/redoc"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response."""
        
        # Skip logging for certain paths
        if any(request.url.path.startswith(path) for path in self.SKIP_LOGGING_PATHS):
            return await call_next(request)
        
        # Read request body if it's JSON
        request_body = {}
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    import json
                    request_body = json.loads(body)
                    # Redact sensitive fields
                    RequestLoggingMiddleware._redact_sensitive_fields(request_body)
                # Re-bind the body so it can be read again by the endpoint
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.debug(f"Could not parse request body: {e}")
        
        # Record start time
        start_time = time.time()
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Log incoming request
        logger.info(
            f"[REQUEST] {request.method} {request.url.path} | "
            f"Client: {client_ip} | "
            f"Body keys: {list(request_body.keys())}"
        )
        
        # Call the next middleware/endpoint
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                f"[RESPONSE_ERROR] {request.method} {request.url.path} | "
                f"Duration: {time.time() - start_time:.2f}s | "
                f"Error: {type(e).__name__}: {e}"
            )
            raise
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"[RESPONSE] {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {duration:.2f}s"
        )
        
        # Log errors (4xx, 5xx)
        if response.status_code >= 400:
            logger.warning(
                f"[ERROR_RESPONSE] {request.method} {request.url.path} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.2f}s"
            )
        
        return response
    
    @staticmethod
    def _redact_sensitive_fields(obj):
        """Recursively redact sensitive fields from request body."""
        sensitive_keys = {
            "session_id", "token", "password", "api_key", "secret",
            "authorization", "x-api-key",
        }
        
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if key.lower() in sensitive_keys:
                    if isinstance(obj[key], str) and len(obj[key]) > 4:
                        # Mask: show first and last char, rest as asterisks
                        obj[key] = obj[key][0] + "*" * (len(obj[key]) - 2) + obj[key][-1]
                else:
                    RequestLoggingMiddleware._redact_sensitive_fields(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                RequestLoggingMiddleware._redact_sensitive_fields(item)
