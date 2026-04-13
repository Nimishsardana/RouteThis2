"""
Diagnostic detectors: pattern matching for special conditions.

Detects:
- Firmware updates in progress
- ISP outages
- Device-specific issues
- Network vs device issues
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class DiagnosticDetector:
    """Detects specific conditions from user messages."""
    
    # Firmware update keywords
    FIRMWARE_UPDATE_KEYWORDS = [
        "updating", "upgrade", "upgrading", "firmware", "restart", "rebooting",
        "flashing", "verifying", "initializing", "lights blinking slowly",
    ]
    
    # ISP outage keywords
    ISP_OUTAGE_KEYWORDS = [
        "outage", "down", "offline", "isp", "modem", "broadband", "cable", "dsl",
        "fiber", "no internet", "no connection",
    ]
    
    # Device-specific keywords (single device issue)
    DEVICE_SPECIFIC_KEYWORDS = [
        "only phone", "only laptop", "only one", "just my", "specific device",
        "one device", "particular", "single device",
    ]
    
    # Multiple device keywords
    MULTIPLE_DEVICE_KEYWORDS = [
        "all devices", "every device", "everything", "all", "multiple",
        "several", "everyone", "the whole house", "entire network",
    ]
    
    @staticmethod
    def detect_firmware_update(message: str) -> bool:
        """Check if user message indicates firmware update in progress."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in DiagnosticDetector.FIRMWARE_UPDATE_KEYWORDS)
    
    @staticmethod
    def detect_isp_outage_mention(message: str) -> bool:
        """Check if user mentions ISP outage."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in DiagnosticDetector.ISP_OUTAGE_KEYWORDS)
    
    @staticmethod
    def detect_device_specific_issue(message: str) -> bool:
        """Check if issue is specific to one device."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in DiagnosticDetector.DEVICE_SPECIFIC_KEYWORDS)
    
    @staticmethod
    def detect_all_devices_affected(message: str) -> bool:
        """Check if all or multiple devices are affected."""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in DiagnosticDetector.MULTIPLE_DEVICE_KEYWORDS)
    
    @staticmethod
    def detect_reboot_already_attempted(conversation: List[dict]) -> int:
        """Count how many times user has mentioned rebooting/restarting."""
        reboot_keywords = [
            "rebooted", "restarted", "power cycled", "unplugged",
            "already tried", "tried rebooting", "tried restarting",
        ]
        count = 0
        for msg in conversation:
            if msg.get("role") == "user":
                msg_lower = msg.get("content", "").lower()
                for keyword in reboot_keywords:
                    if keyword in msg_lower:
                        count += 1
                        break  # Count once per message
        return count
    
    @staticmethod
    def analyze_conversation(conversation: List[dict]) -> dict:
        """
        Analyze full conversation for diagnostic patterns.
        
        Returns dict with:
        {
            "firmware_update": bool,
            "isp_outage_mentioned": bool,
            "device_specific": bool,
            "all_devices_affected": bool,
            "reboot_attempts": int,
        }
        """
        full_conversation = " ".join(
            msg.get("content", "") for msg in conversation if msg.get("role") == "user"
        )
        
        return {
            "firmware_update": DiagnosticDetector.detect_firmware_update(full_conversation),
            "isp_outage_mentioned": DiagnosticDetector.detect_isp_outage_mention(full_conversation),
            "device_specific": DiagnosticDetector.detect_device_specific_issue(full_conversation),
            "all_devices_affected": DiagnosticDetector.detect_all_devices_affected(full_conversation),
            "reboot_attempts": DiagnosticDetector.detect_reboot_already_attempted(conversation),
        }
