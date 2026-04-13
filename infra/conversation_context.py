"""
Conversation Context: structured context object threaded through handlers.

This object captures diagnostic state, user intent, and prior actions
to enable smarter decision-making without re-parsing the conversation.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class IssueSeverity(str, Enum):
    CRITICAL = "critical"      # No internet at all, blocking
    MODERATE = "moderate"      # Intermittent or slow
    MINOR = "minor"            # Single device or website-specific


class UserDeviceType(str, Enum):
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    MOBILE_PHONE = "mobile_phone"
    TABLET = "tablet"
    IOT = "iot"
    OTHER = "other"


class PriorAction(str, Enum):
    RESTARTED_DEVICE = "restarted_device"
    RESTARTED_MODEM = "restarted_modem"
    REBOOTED_ROUTER = "rebooted_router"
    CHECKED_CABLES = "checked_cables"
    CHECKED_PASSWORD = "checked_password"
    UPDATED_FIRMWARE = "updated_firmware"
    FACTORY_RESET = "factory_reset"
    CONTACTED_ISP = "contacted_isp"


@dataclass
class ConversationContext:
    """
    Rich context for a troubleshooting session.
    Passed through state handlers to enable smarter decisions.
    """
    session_id: str
    
    # Diagnostic info
    issue_severity: IssueSeverity = IssueSeverity.MODERATE
    affected_devices: Optional[int] = None  # 1 = single device, 2+ = multiple
    affected_all_devices: bool = False
    
    # User tech level (inferred from language/behavior)
    user_is_technical: bool = False
    
    # Hardware/connectivity details
    primary_device_type: Optional[UserDeviceType] = None
    has_wired_connection: bool = False
    can_access_admin_panel: bool = False
    
    # Router state info
    router_power_state: Optional[str] = None  # "steady", "blinking_slow", "blinking_fast"
    internet_light_state: Optional[str] = None  # "on", "blinking", "off"
    
    # Prior actions user has already taken
    prior_actions: list[PriorAction] = field(default_factory=list)
    
    # Decision history
    last_reboot_method_attempted: Optional[str] = None  # "soft_reboot", "web_ui_reboot", "factory_reset"
    reboot_attempts_count: int = 0
    
    # ISP/network context
    isp_outage_reported: bool = False
    recent_firmware_update: bool = False
    
    @property
    def has_attempted_soft_reboot(self) -> bool:
        """Convenience check."""
        return PriorAction.REBOOTED_ROUTER in self.prior_actions
    
    @property
    def has_contacted_isp(self) -> bool:
        """User already tried ISP support."""
        return PriorAction.CONTACTED_ISP in self.prior_actions
    
    @property
    def should_recommend_factory_reset(self) -> bool:
        """Factory reset only if previous reboots failed and no firmware update in progress."""
        return (
            self.reboot_attempts_count >= 2
            and not self.recent_firmware_update
        )
    
    @property
    def severity_ordinal(self) -> int:
        """For sorting/thresholding."""
        return {"critical": 3, "moderate": 2, "minor": 1}[self.issue_severity.value]
    
    def get_safe_reboot_method(self) -> str:
        """
        Determine safest reboot method based on context.
        Applies escalation logic:
        1. First attempt: soft_reboot
        2. If soft_reboot failed: web_ui_reboot (if user can access admin)
        3. If both failed: factory_reset (only with strong justification)
        """
        if self.reboot_attempts_count == 0:
            return "soft_reboot"
        
        if self.reboot_attempts_count == 1:
            if self.can_access_admin_panel or self.user_is_technical:
                return "web_ui_reboot"
            else:
                # Can't access admin, stick with soft_reboot again
                return "soft_reboot"
        
        if self.should_recommend_factory_reset:
            return "factory_reset"
        
        return "soft_reboot"  # Safe default
