"""
Session persistence layer: abstract interface for session storage.

Implementations:
- MemorySessionStore: In-memory (development, single-process)
- RedisSessionStore: Redis-backed (production, distributed)

Enables session recovery on server restarts and multi-process deployments.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.state_machine import ConversationState

logger = logging.getLogger(__name__)


class SessionStore(ABC):
    """Abstract base for session persistence."""
    
    @abstractmethod
    async def save(self, session: ConversationState) -> None:
        """Persist a session."""
        pass
    
    @abstractmethod
    async def load(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve a session. Returns None if not found."""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Remove a session (e.g., on exit)."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self, ttl_hours: int = 24) -> int:
        """Delete sessions older than ttl_hours. Returns count deleted."""
        pass


class MemorySessionStore(SessionStore):
    """Simple in-memory store (development only)."""
    
    def __init__(self):
        self._sessions: dict[str, tuple[ConversationState, datetime]] = {}
        logger.info("MemorySessionStore initialized (development mode)")
    
    async def save(self, session: ConversationState) -> None:
        """Save session with timestamp."""
        self._sessions[session.session_id] = (session, datetime.utcnow())
        logger.debug(f"[{session.session_id}] Saved to memory")
    
    async def load(self, session_id: str) -> Optional[ConversationState]:
        """Load session from memory."""
        if session_id in self._sessions:
            session, _ = self._sessions[session_id]
            logger.debug(f"[{session_id}] Loaded from memory")
            return session
        return None
    
    async def delete(self, session_id: str) -> None:
        """Remove session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"[{session_id}] Deleted from memory")
    
    async def cleanup_expired(self, ttl_hours: int = 24) -> int:
        """Remove sessions older than ttl_hours."""
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        expired = [
            sid for sid, (_, ts) in self._sessions.items()
            if ts < cutoff
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)


# ════════════════════════════════════════════════════════════════════════════════
# REDIS SESSION STORE (COMMENTED OUT - Not currently used)
# ════════════════════════════════════════════════════════════════════════════════
# Redis support is available but not enabled. To use Redis:
# 1. Install redis: pip install redis
# 2. Set SESSION_STORE_TYPE=redis in .env
# 3. Set REDIS_URL in .env (default: redis://localhost:6379/0)
# 
# class RedisSessionStore(SessionStore):
#     """Redis-backed store for production / multi-process."""
#     
#     def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 86400):
#         """
#         Initialize Redis store.
#         
#         Args:
#             redis_url: Redis connection string
#             ttl_seconds: Session expiration time (default 24h)
#         """
#         try:
#             import redis
#             self.redis = redis.from_url(redis_url, decode_responses=True)
#             self.ttl_seconds = ttl_seconds
#             self.prefix = "wifi_session:"
#             
#             # Test connection
#             self.redis.ping()
#             logger.info(f"RedisSessionStore initialized: {redis_url}")
#         except ImportError:
#             raise ImportError("redis package not installed. Install with: pip install redis")
#         except Exception as e:
#             logger.error(f"Redis connection failed: {e}")
#             raise
#     
#     async def save(self, session: ConversationState) -> None:
#         """Serialize and save session to Redis with TTL."""
#         key = f"{self.prefix}{session.session_id}"
#         data = json.dumps({
#             "session_id": session.session_id,
#             "state": session.state.value,
#             "reboot_decision": session.reboot_decision.value if session.reboot_decision else None,
#             "reboot_method": session.reboot_method,
#             "reboot_step_index": session.reboot_step_index,
#             "diagnosis_turn_count": session.diagnosis_turn_count,
#             "total_turns": session.total_turns,
#             "resolved": session.resolved,
#             "messages": session.messages,
#         })
#         try:
#             self.redis.setex(key, self.ttl_seconds, data)
#             logger.debug(f"[{session.session_id}] Saved to Redis (TTL: {self.ttl_seconds}s)")
#         except Exception as e:
#             logger.error(f"[{session.session_id}] Redis save failed: {e}")
#             raise
#     
#     async def load(self, session_id: str) -> Optional[ConversationState]:
#         """Deserialize and load session from Redis."""
#         key = f"{self.prefix}{session_id}"
#         try:
#             data = self.redis.get(key)
#             if not data:
#                 return None
#             
#             obj = json.loads(data)
#             session = ConversationState(
#                 session_id=obj["session_id"],
#                 state=obj["state"],
#                 reboot_decision=obj.get("reboot_decision"),
#                 reboot_method=obj.get("reboot_method"),
#                 reboot_step_index=obj.get("reboot_step_index", 0),
#                 diagnosis_turn_count=obj.get("diagnosis_turn_count", 0),
#                 total_turns=obj.get("total_turns", 0),
#                 resolved=obj.get("resolved"),
#                 messages=obj.get("messages", []),
#             )
#             logger.debug(f"[{session_id}] Loaded from Redis")
#             return session
#         except Exception as e:
#             logger.error(f"[{session_id}] Redis load failed: {e}")
#             return None
#     
#     async def delete(self, session_id: str) -> None:
#         """Remove session from Redis."""
#         key = f"{self.prefix}{session_id}"
#         try:
#             self.redis.delete(key)
#             logger.debug(f"[{session_id}] Deleted from Redis")
#         except Exception as e:
#             logger.error(f"[{session_id}] Redis delete failed: {e}")
#     
#     async def cleanup_expired(self, ttl_hours: int = 24) -> int:
#         """
#         Redis handles expiration automatically via TTL.
#         This is a no-op for Redis, but provided for interface consistency.
#         """
#         logger.debug("Redis cleanup_expired: no-op (TTL handled by Redis)")
#         return 0
