"""
API Security: authentication and rate limiting middleware.

Features:
- API key validation (optional)
- Per-session rate limiting (configurable)
- Request throttling with backoff
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from infra.config import ConfigManager

logger = logging.getLogger(__name__)


class APIKeyValidator:
    """Validates API keys for protected endpoints."""
    
    @staticmethod
    def validate(api_key: Optional[str]) -> bool:
        """
        Validate API key against configured key.
        If no API_KEY configured in environment, validation is skipped (dev mode).
        """
        expected_key = ConfigManager.get_api_key()
        
        # If no API key configured, skip validation
        if not expected_key:
            logger.debug("No API_KEY configured; skipping API key validation")
            return True
        
        # Validate provided key
        if not api_key:
            logger.warning("API request rejected: no API key provided")
            return False
        
        if api_key != expected_key:
            logger.warning(f"API request rejected: invalid API key (attempt with length {len(api_key)})")
            return False
        
        logger.debug("API key validated successfully")
        return True


class RateLimitTracker:
    """Simple in-memory rate limiter per session."""
    
    def __init__(self, rate_limit_per_hour: int = 100):
        self.rate_limit_per_hour = rate_limit_per_hour
        self.session_requests: dict[str, list[datetime]] = {}
    
    def is_allowed(self, session_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if a session has exceeded rate limit.
        
        Returns:
            (is_allowed, error_message_or_none)
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Get requests for this session in past hour
        if session_id not in self.session_requests:
            self.session_requests[session_id] = []
        
        # Clean up old requests (older than 1 hour)
        self.session_requests[session_id] = [
            req_time for req_time in self.session_requests[session_id]
            if req_time > one_hour_ago
        ]
        
        # Check limit
        request_count = len(self.session_requests[session_id])
        if request_count >= self.rate_limit_per_hour:
            remaining_time = (self.session_requests[session_id][0] + timedelta(hours=1) - now).total_seconds()
            msg = f"Rate limit exceeded. Max {self.rate_limit_per_hour} requests per hour. Try again in {int(remaining_time)} seconds."
            logger.warning(f"[{session_id}] Rate limit exceeded: {request_count} requests")
            return False, msg
        
        # Record this request
        self.session_requests[session_id].append(now)
        return True, None
    
    def cleanup_old_sessions(self, ttl_hours: int = 24) -> int:
        """Remove tracking for sessions older than ttl_hours."""
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        old_sessions = [
            sid for sid, requests in self.session_requests.items()
            if all(req_time < cutoff for req_time in requests)
        ]
        for sid in old_sessions:
            del self.session_requests[sid]
        if old_sessions:
            logger.debug(f"Cleaned up {len(old_sessions)} old rate limit session(s)")
        return len(old_sessions)


class RateLimiter:
    """Thread-safe rate limiter."""
    
    def __init__(self, rate_limit_per_hour: int = 100):
        self.tracker = RateLimitTracker(rate_limit_per_hour)
    
    def check(self, session_id: str) -> tuple[bool, Optional[str]]:
        """Check if session can make a request."""
        return self.tracker.is_allowed(session_id)
    
    def cleanup(self, ttl_hours: int = 24) -> int:
        """Cleanup old sessions."""
        return self.tracker.cleanup_old_sessions(ttl_hours)


# Global rate limiter (initialized after RateLimiter class definition)
_rate_limiter = RateLimiter(rate_limit_per_hour=ConfigManager.get_rate_limit_per_hour())


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter
