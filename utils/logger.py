"""
Logging configuration for the WiFi Troubleshooter.
Outputs structured logs to console and a rotating file.
"""

import logging
import logging.handlers
import os
from pathlib import Path

_configured = False


def setup_logging(level: str = None, console: bool = True):
    """Configure application-wide logging. Call once at startup.
    
    Args:
        level: Log level (default from LOG_LEVEL env var or INFO)
        console: If False, suppress console output (useful for CLI to avoid log interference)
    """
    global _configured
    if _configured:
        return

    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Ensure logs directory exists
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Formatter
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (only if console=True)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(fmt)
        root_logger.addHandler(console_handler)

    # Rotating file handler (5MB max, keep 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info(f"Logging initialized at level={log_level}")
