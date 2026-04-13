"""
Input validation: sanitize and validate user messages.

Responsibilities:
- Check message length
- Detect common attack patterns
- Filter profanity/safety issues (optional integration with external services)
- Return validation errors with helpful messages
"""

import logging
import re
from typing import Tuple, Optional
from infra.config import ConfigManager

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """Validates user input messages."""
    
    # Common control characters and unusual whitespace
    CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    
    # Potentially malicious patterns (SQL injection-like, command injection)
    INJECTION_PATTERNS = [
        r'(;|&&|\|\||\||`|<|>)\s*(cat|ls|grep|curl|wget|python|bash|sh|exec)',
        r"'\s*(OR|AND)\s*'",
        r'DROP\s+(TABLE|DATABASE)',
    ]
    
    # Common profanity/unsafe terms (minimal set - could integrate with external library)
    UNSAFE_TERMS = [
        # This is intentionally small; in production use a proper profanity filter
        # or a content moderation API like Azure Content Moderator
    ]
    
    @staticmethod
    def validate(message: str, session_id: str = "unknown") -> Tuple[bool, str]:
        """
        Validate a user message.
        
        Returns:
            (is_valid, error_message_or_empty_string)
        """
        max_length = ConfigManager.get_max_message_length()
        
        # Check empty
        if not message or not message.strip():
            return False, "Message cannot be empty."
        
        # Check length
        if len(message) > max_length:
            return False, f"Message exceeds maximum length of {max_length} characters."
        
        # Check for control characters
        if InputValidator.CONTROL_CHAR_PATTERN.search(message):
            logger.warning(f"[{session_id}] Detected control characters in message")
            return False, "Message contains invalid characters."
        
        # Check for injection attempts
        for pattern in InputValidator.INJECTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                logger.warning(f"[{session_id}] Potential injection attempt detected")
                return False, "Message contains suspicious content. Please stick to WiFi-related questions."
        
        # Check for unsafe terms (minimal check)
        message_lower = message.lower()
        for term in InputValidator.UNSAFE_TERMS:
            if term in message_lower:
                logger.info(f"[{session_id}] Detected unsafe term")
                return False, "Please keep messages appropriate and focused on WiFi troubleshooting."
        
        return True, ""
    
    @staticmethod
    def sanitize(message: str) -> str:
        """
        Lightly sanitize message for safety (could be extended).
        For now, just strip leading/trailing whitespace and normalize newlines.
        """
        # Strip whitespace
        message = message.strip()
        
        # Normalize newlines (collapse multiple to single)
        message = re.sub(r'\n{3,}', '\n\n', message)
        
        return message
