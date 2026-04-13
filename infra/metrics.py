"""
Prometheus metrics instrumentation: track API performance and outcomes.

Meters:
- LLM call latency and errors
- Chat completion rate (resolved vs not resolved)
- Session duration
- Token usage
- State transitions
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import of Prometheus to avoid hard dependency
_prometheus_available = False
try:
    from prometheus_client import Counter, Histogram, Gauge
    _prometheus_available = True
except ImportError:
    logger.warning("prometheus-client not installed; metrics disabled")


# Prometheus metrics (initialized if available)
_llm_call_duration_seconds = None
_llm_call_errors_total = None
_chat_turns_total = None
_session_resolved_total = None
_session_not_resolved_total = None
_active_sessions_gauge = None
_tokens_used_total = None
_state_transitions_total = None


def _init_metrics():
    """Initialize Prometheus metrics if client is available."""
    global _llm_call_duration_seconds, _llm_call_errors_total, _chat_turns_total, _session_resolved_total, _session_not_resolved_total, _active_sessions_gauge, _tokens_used_total, _state_transitions_total
    
    if not _prometheus_available:
        return
    
    _llm_call_duration_seconds = Histogram(
        "llm_call_duration_seconds",
        "Duration of LLM API calls in seconds",
        ["model", "state"],
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    )
    
    _llm_call_errors_total = Counter(
        "llm_call_errors_total",
        "Total number of LLM API call errors",
        ["model", "error_type"],
    )
    
    _chat_turns_total = Counter(
        "chat_turns_total",
        "Total number of chat turns across all sessions",
    )
    
    _session_resolved_total = Counter(
        "session_resolved_total",
        "Total sessions with resolved issues",
    )
    
    _session_not_resolved_total = Counter(
        "session_not_resolved_total",
        "Total sessions without resolution",
    )
    
    _active_sessions_gauge = Gauge(
        "active_sessions",
        "Number of active sessions",
    )
    
    _tokens_used_total = Counter(
        "tokens_used_total",
        "Total tokens used across all LLM calls",
        ["model", "token_type"],  # token_type: prompt, completion, total
    )
    
    _state_transitions_total = Counter(
        "state_transitions_total",
        "Total state transitions",
        ["from_state", "to_state"],
    )
    
    logger.info("Prometheus metrics initialized")


# Initialize on import
_init_metrics()


class MetricsCollector:
    """Singleton for Prometheus metrics collection."""
    
    @staticmethod
    @contextmanager
    def time_llm_call(model: str, state: str = "unknown"):
        """Context manager to measure LLM call duration and errors."""
        if not _prometheus_available:
            yield
            return
        
        start_time = time.time()
        try:
            yield
            # Success
        except Exception as e:
            error_type = type(e).__name__
            _llm_call_errors_total.labels(model=model, error_type=error_type).inc()
            raise
        finally:
            duration = time.time() - start_time
            _llm_call_duration_seconds.labels(model=model, state=state).observe(duration)
    
    @staticmethod
    def record_llm_tokens(model: str, prompt_tokens: int, completion_tokens: int):
        """Record token usage from LLM call."""
        if not _prometheus_available:
            return
        
        _tokens_used_total.labels(model=model, token_type="prompt").inc(prompt_tokens)
        _tokens_used_total.labels(model=model, token_type="completion").inc(completion_tokens)
        _tokens_used_total.labels(model=model, token_type="total").inc(prompt_tokens + completion_tokens)
    
    @staticmethod
    def record_chat_turn():
        """Increment chat turn counter."""
        if not _prometheus_available:
            return
        _chat_turns_total.inc()
    
    @staticmethod
    def record_session_resolved(resolved: bool):
        """Record session outcome."""
        if not _prometheus_available:
            return
        
        if resolved:
            _session_resolved_total.inc()
        else:
            _session_not_resolved_total.inc()
    
    @staticmethod
    def set_active_sessions(count: int):
        """Update active sessions gauge."""
        if not _prometheus_available:
            return
        _active_sessions_gauge.set(count)
    
    @staticmethod
    def record_state_transition(from_state: str, to_state: str):
        """Record a state transition."""
        if not _prometheus_available:
            return
        _state_transitions_total.labels(from_state=from_state, to_state=to_state).inc()


def get_metrics_endpoint():
    """Return Prometheus metrics in text format (for /metrics endpoint)."""
    if not _prometheus_available:
        return "Prometheus not available\n"
    
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest().decode("utf-8")
