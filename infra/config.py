"""
Configuration module: centralized config for API tokens, models, and settings.

Standardizes environment variable handling and provides typed access to config.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single model/token pair."""
    token: str
    model: str
    index: int
    
    def __repr__(self) -> str:
        return f"ModelConfig(index={self.index}, model={self.model}, token_len={len(self.token)})"


class ConfigManager:
    """Manage application configuration from environment variables."""
    
    @staticmethod
    def load_model_configs() -> List[ModelConfig]:
        """
        Load all model/token configurations from environment.
        
        Expects env vars in format:
          GITHUB_TOKEN_1, GITHUB_TOKEN_2, ... (or GITHUB_TOKEN for first)
          MODEL_1, MODEL_2, ...  (or MODEL for first, defaults to openai/gpt-4o-mini)
        
        Returns list of valid configs in order.
        """
        configs = []
        
        # Try numbered format (GITHUB_TOKEN_1, GITHUB_TOKEN_2, ...)
        for i in range(1, 5):
            token = os.getenv(f"GITHUB_TOKEN_{i}")
            if token:
                model = os.getenv(f"MODEL_{i}", "openai/gpt-4o-mini")
                configs.append(ModelConfig(token=token, model=model, index=i))
                logger.debug(f"Loaded config {i}: {model}")
        
        # Fallback: single GITHUB_TOKEN (for backward compatibility)
        if not configs:
            token = os.getenv("GITHUB_TOKEN")
            if token:
                model = os.getenv("MODEL", "openai/gpt-4o-mini")
                configs.append(ModelConfig(token=token, model=model, index=0))
                logger.debug(f"Using fallback single token: {model}")
        
        if not configs:
            raise ValueError(
                "No GitHub tokens configured. Set GITHUB_TOKEN or GITHUB_TOKEN_1, GITHUB_TOKEN_2, etc."
            )
        
        logger.info(f"Loaded {len(configs)} model config(s)")
        return configs
    
    @staticmethod
    def get_log_level() -> str:
        """Get log level from environment."""
        return os.getenv("LOG_LEVEL", "INFO").upper()
    
    @staticmethod
    def get_session_ttl_hours() -> int:
        """Get session TTL in hours."""
        ttl = os.getenv("SESSION_TTL_HOURS", "24")
        try:
            return int(ttl)
        except ValueError:
            logger.warning(f"Invalid SESSION_TTL_HOURS: {ttl}, using default 24")
            return 24
    
    @staticmethod
    def get_session_store_type() -> str:
        """Get session store type: 'memory' or 'redis'."""
        store_type = os.getenv("SESSION_STORE", "memory").lower()
        if store_type not in ("memory", "redis"):
            logger.warning(f"Unknown SESSION_STORE: {store_type}, using 'memory'")
            return "memory"
        return store_type
    
    @staticmethod
    def get_redis_url() -> str:
        """Get Redis URL."""
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    @staticmethod
    def get_max_diagnosis_turns() -> int:
        """Max diagnosis cycles before forcing reboot decision."""
        val = os.getenv("MAX_DIAGNOSIS_TURNS", "6")
        try:
            return int(val)
        except ValueError:
            logger.warning(f"Invalid MAX_DIAGNOSIS_TURNS: {val}, using default 6")
            return 6
    
    @staticmethod
    def get_api_key() -> Optional[str]:
        """Get API key for protecting /chat endpoint (optional)."""
        return os.getenv("API_KEY")
    
    @staticmethod
    def get_rate_limit_per_hour() -> int:
        """Get rate limit per hour per session."""
        val = os.getenv("RATE_LIMIT_PER_HOUR", "100")
        try:
            return int(val)
        except ValueError:
            logger.warning(f"Invalid RATE_LIMIT_PER_HOUR: {val}, using default 100")
            return 100
    
    @staticmethod
    def get_enable_prometheus() -> bool:
        """Enable Prometheus metrics."""
        return os.getenv("ENABLE_PROMETHEUS", "false").lower() in ("true", "1", "yes")
    
    @staticmethod
    def get_max_message_length() -> int:
        """Maximum length of user message."""
        val = os.getenv("MAX_MESSAGE_LENGTH", "2000")
        try:
            return int(val)
        except ValueError:
            logger.warning(f"Invalid MAX_MESSAGE_LENGTH: {val}, using default 2000")
            return 2000
