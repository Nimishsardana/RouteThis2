"""
State machine for WiFi troubleshooting conversation flow.

States:
  DIAGNOSIS    - Gathering info about the user's WiFi problem
  DECISION     - Deciding whether a reboot is appropriate
  REBOOT_GUIDE - Walking the user through the reboot process
  POST_CHECK   - Checking if the reboot resolved the issue
  EXIT         - Conversation is complete

Transitions are deterministic based on LLM classification + step counters.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class State(str, Enum):
    DIAGNOSIS = "DIAGNOSIS"
    DECISION = "DECISION"
    REBOOT_GUIDE = "REBOOT_GUIDE"
    POST_CHECK = "POST_CHECK"
    EXIT = "EXIT"


class RebootDecision(str, Enum):
    REBOOT_APPROPRIATE = "reboot_appropriate"
    REBOOT_NOT_APPROPRIATE = "reboot_not_appropriate"
    NEED_MORE_INFO = "need_more_info"


class PostCheckOutcome(str, Enum):
    RESOLVED = "resolved"
    NOT_RESOLVED = "not_resolved"
    UNCLEAR = "unclear"


@dataclass
class ConversationState:
    """Holds all state for a single troubleshooting session."""

    session_id: str
    state: State = State.DIAGNOSIS
    reboot_decision: Optional[RebootDecision] = None
    reboot_method: Optional[str] = None          # soft_reboot | web_ui_reboot | factory_reset
    reboot_step_index: int = 0                   # which step we're on in the reboot guide
    diagnosis_turn_count: int = 0
    total_turns: int = 0
    resolved: Optional[bool] = None
    messages: list = field(default_factory=list)  # full conversation history for LLM

    def add_message(self, role: str, content: str):
        """Append a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
        if role == "user":
            self.total_turns += 1
            if self.state == State.DIAGNOSIS:
                self.diagnosis_turn_count += 1

    def transition_to(self, new_state: State):
        """Explicitly transition to a new state with logging."""
        old_state = self.state
        logger.info(
            f"[{self.session_id}] State transition: {old_state} → {new_state}"
        )
        self.state = new_state
        
        # Record metrics
        try:
            from infra.metrics import MetricsCollector
            MetricsCollector.record_state_transition(old_state.value, new_state.value)
        except ImportError:
            pass  # Metrics not available

    def to_dict(self) -> dict:
        """Serialize state for API responses."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "reboot_decision": self.reboot_decision.value if self.reboot_decision else None,
            "reboot_method": self.reboot_method,
            "reboot_step_index": self.reboot_step_index,
            "total_turns": self.total_turns,
            "resolved": self.resolved,
        }


def create_session(session_id: str) -> ConversationState:
    """Factory: create a fresh conversation state."""
    return ConversationState(session_id=session_id)
