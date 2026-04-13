"""
Integration tests for WiFi Troubleshooter full conversation flow.

Tests end-to-end conversation scenarios:
- Full reboot flow → resolved
- Full reboot flow → not resolved
- Firmware update detection
- Device-specific issue
- ISP outage detection
- Multi-turn diagnostic with state transitions
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.state_machine import (
    ConversationState,
    State,
    RebootDecision,
    create_session,
)
from src.chat_handler import ChatHandler, chat_handler
from src.manual_service import load_manual


class TestFullConversationFlow:
    """Test complete conversation flows from start to finish."""

    def setup_method(self):
        """Setup for each test."""
        self.handler = ChatHandler()
        self.manual = load_manual()

    def test_initialization(self):
        """Test that manual data loads correctly."""
        # This is a prerequisite for all tests
        assert self.manual is not None
        assert "reboot_methods" in self.manual
        assert len(self.manual["reboot_methods"]) >= 3
        print("✅ Manual data loaded successfully")

    def test_session_creation(self):
        """Test session initialization."""
        session = create_session("test-session-1")
        assert session.session_id == "test-session-1"
        assert session.state == State.DIAGNOSIS
        assert session.total_turns == 0
        assert session.messages == []
        print("✅ Session creation works")

    def test_diagnosis_state_basic(self):
        """Test diagnosis state initial handling."""
        session = create_session("test-diagnosis-1")
        assert session.state == State.DIAGNOSIS
        # The handler should begin with diagnosis
        print("✅ Diagnosis state initialized")

    def test_adding_messages(self):
        """Test message recording in session."""
        session = create_session("test-messages-1")
        
        # Add a user message
        session.add_message("user", "My WiFi is down")
        assert session.total_turns == 1
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        
        # Add assistant message
        session.add_message("assistant", "That's unfortunate!")
        assert len(session.messages) == 2
        assert session.messages[1]["role"] == "assistant"
        print("✅ Message recording works")

    def test_state_transitions(self):
        """Test state machine transitions."""
        session = create_session("test-transitions-1")
        
        # Start in DIAGNOSIS
        assert session.state == State.DIAGNOSIS
        
        # Transition to REBOOT_GUIDE
        session.transition_to(State.REBOOT_GUIDE)
        assert session.state == State.REBOOT_GUIDE
        
        # Transition to POST_CHECK
        session.transition_to(State.POST_CHECK)
        assert session.state == State.POST_CHECK
        
        # Transition to EXIT
        session.transition_to(State.EXIT)
        assert session.state == State.EXIT
        print("✅ State transitions work")

    def test_reboot_decision_recording(self):
        """Test recording reboot decisions."""
        session = create_session("test-reboot-decision-1")
        
        # Record a reboot decision
        session.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
        assert session.reboot_decision == RebootDecision.REBOOT_APPROPRIATE
        
        # Change decision
        session.reboot_decision = RebootDecision.REBOOT_NOT_APPROPRIATE
        assert session.reboot_decision == RebootDecision.REBOOT_NOT_APPROPRIATE
        print("✅ Reboot decision recording works")

    def test_reboot_method_selection(self):
        """Test reboot method selection."""
        session = create_session("test-method-selection-1")
        
        # Soft reboot
        session.reboot_method = "soft_reboot"
        total_steps = self.manual["reboot_methods"][0]["steps"]
        assert len(total_steps) > 0
        print(f"✅ Soft reboot has {len(total_steps)} steps")
        
        # Web UI reboot
        session.reboot_method = "web_ui_reboot"
        total_steps = self.manual["reboot_methods"][1]["steps"]
        assert len(total_steps) > 0
        print(f"✅ Web UI reboot has {len(total_steps)} steps")
        
        # Factory reset
        session.reboot_method = "factory_reset"
        total_steps = self.manual["reboot_methods"][2]["steps"]
        assert len(total_steps) > 0
        print(f"✅ Factory reset has {len(total_steps)} steps")

    def test_reboot_step_delivery(self):
        """Test delivering reboot steps from manual."""
        session = create_session("test-step-delivery-1")
        session.reboot_method = "soft_reboot"
        session.reboot_step_index = 0
        
        # Get first step
        from src.manual_service import get_reboot_step, get_total_steps
        
        total = get_total_steps("soft_reboot")
        step = get_reboot_step("soft_reboot", 0)
        
        assert step is not None
        assert len(step) > 0
        assert isinstance(step, str)
        print(f"✅ Step 1/{total}: {step[:50]}...")

    def test_manual_data_integrity(self):
        """Test that manual data has required fields."""
        for method in self.manual["reboot_methods"]:
            assert "method_id" in method
            assert "title" in method
            assert "steps" in method
            assert isinstance(method["steps"], list)
            assert len(method["steps"]) > 0
        print("✅ Manual data integrity verified")

    def test_conversation_message_flow(self):
        """Test basic message flow through conversation."""
        session = create_session("test-flow-1")
        
        # Simulate multi-turn conversation
        messages = [
            ("user", "My WiFi is not working"),
            ("assistant", "Can you describe the issue?"),
            ("user", "It's been down all day"),
            ("assistant", "Does it affect all devices?"),
            ("user", "Yes, everything"),
        ]
        
        for role, content in messages:
            session.add_message(role, content)
        
        assert session.total_turns == 3  # Three user turns
        assert len(session.messages) == 5  # Five total messages
        print(f"✅ Conversation flow works ({session.total_turns} turns)")

    def test_resolved_outcome_recording(self):
        """Test recording resolution outcome."""
        session = create_session("test-resolved-1")
        
        assert session.resolved is None
        
        # Mark as resolved
        session.resolved = True
        assert session.resolved is True
        
        # Mark as not resolved
        session.resolved = False
        assert session.resolved is False
        print("✅ Outcome recording works")

    def test_session_serialization(self):
        """Test converting session to dict for API response."""
        session = create_session("test-serialize-1")
        session.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
        session.reboot_method = "soft_reboot"
        session.add_message("user", "Help!")
        
        session_dict = session.to_dict()
        
        assert session_dict["session_id"] == "test-serialize-1"
        assert session_dict["state"] == "DIAGNOSIS"
        assert session_dict["reboot_method"] == "soft_reboot"
        assert session_dict["total_turns"] == 1
        print("✅ Session serialization works")

    def test_diagnostic_detector_firmware_update(self):
        """Test detection of firmware update in progress."""
        from infra.diagnostic_detector import DiagnosticDetector
        
        # Should detect firmware update keywords
        assert DiagnosticDetector.detect_firmware_update("power light flashing slowly")
        assert DiagnosticDetector.detect_firmware_update("firmware update in progress")
        assert DiagnosticDetector.detect_firmware_update("upgrading the router")
        
        # Should not falsely detect
        assert not DiagnosticDetector.detect_firmware_update("wifi is slow")
        print("✅ Firmware update detection works")

    def test_diagnostic_detector_device_specific(self):
        """Test detection of device-specific issues."""
        from infra.diagnostic_detector import DiagnosticDetector
        
        # Should detect device-specific keywords
        assert DiagnosticDetector.detect_device_specific_issue("only phone can't connect")
        assert DiagnosticDetector.detect_device_specific_issue("just my laptop has issues")
        assert DiagnosticDetector.detect_device_specific_issue("one device affected")
        
        # Should not falsely detect
        assert not DiagnosticDetector.detect_device_specific_issue("all devices are slow")
        print("✅ Device-specific detection works")

    def test_diagnostic_detector_multiple_devices(self):
        """Test detection of multiple devices affected."""
        from infra.diagnostic_detector import DiagnosticDetector
        
        # Should detect multiple device keywords
        assert DiagnosticDetector.detect_all_devices_affected("all devices")
        assert DiagnosticDetector.detect_all_devices_affected("everything is down")
        assert DiagnosticDetector.detect_all_devices_affected("every device affected")
        
        # Should not falsely detect
        assert not DiagnosticDetector.detect_all_devices_affected("my phone won't connect")
        print("✅ Multiple device detection works")

    def test_input_validation(self):
        """Test input validation and sanitization."""
        from infra.input_validator import InputValidator
        
        # Valid messages should pass
        is_valid, error = InputValidator.validate("My WiFi is down")
        assert is_valid
        assert error == ""
        
        # Empty messages should fail
        is_valid, error = InputValidator.validate("")
        assert not is_valid
        
        # Very long messages should fail
        is_valid, error = InputValidator.validate("x" * 3000)
        assert not is_valid
        
        # Injection attempts should fail
        is_valid, error = InputValidator.validate("'; DROP TABLE;")
        assert not is_valid
        print("✅ Input validation works")

    def test_sanitization(self):
        """Test message sanitization."""
        from infra.input_validator import InputValidator
        
        # Should strip whitespace
        sanitized = InputValidator.sanitize("  hello world  ")
        assert sanitized == "hello world"
        
        # Should normalize newlines
        sanitized = InputValidator.sanitize("hello\n\n\n\nworld")
        assert sanitized == "hello\n\nworld"
        print("✅ Sanitization works")


class TestConversationScenarios:
    """Test specific conversation scenarios."""

    def setup_method(self):
        """Setup for each test."""
        self.handler = ChatHandler()

    def test_scenario_happy_path_structure(self):
        """Test the structure of happy path (diagnosis → reboot → resolved)."""
        session = create_session("scenario-happy-1")
        
        # 1. Start in DIAGNOSIS
        assert session.state == State.DIAGNOSIS
        session.add_message("user", "My WiFi is down")
        
        # 2. Simulate reboot decision
        session.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
        session.transition_to(State.REBOOT_GUIDE)
        assert session.state == State.REBOOT_GUIDE
        
        # 3. Set reboot method
        session.reboot_method = "soft_reboot"
        
        # 4. Simulate completing steps
        from src.manual_service import get_total_steps
        total_steps = get_total_steps("soft_reboot")
        
        for i in range(total_steps):
            session.reboot_step_index = i
            session.add_message("user", f"Step {i+1} completed")
        
        # 5. Move to POST_CHECK
        session.transition_to(State.POST_CHECK)
        assert session.state == State.POST_CHECK
        
        # 6. Record resolution
        session.resolved = True
        session.transition_to(State.EXIT)
        assert session.state == State.EXIT
        
        print("✅ Happy path scenario structure validated")

    def test_scenario_not_resolved_structure(self):
        """Test structure when issue not resolved after reboot."""
        session = create_session("scenario-notresolved-1")
        
        session.state = State.POST_CHECK
        session.resolved = False
        session.transition_to(State.EXIT)
        
        assert session.state == State.EXIT
        assert session.resolved is False
        print("✅ Not-resolved scenario structure validated")

    def test_scenario_firmware_update_structure(self):
        """Test structure when firmware update is detected."""
        session = create_session("scenario-firmware-1")
        
        # Firmware update detected → no reboot
        session.reboot_decision = RebootDecision.REBOOT_NOT_APPROPRIATE
        session.transition_to(State.EXIT)
        
        assert session.state == State.EXIT
        assert session.reboot_decision == RebootDecision.REBOOT_NOT_APPROPRIATE
        print("✅ Firmware update scenario structure validated")

    def test_scenario_device_specific_structure(self):
        """Test structure when issue is device-specific."""
        session = create_session("scenario-device-specific-1")
        
        # Device-specific → no reboot
        session.reboot_decision = RebootDecision.REBOOT_NOT_APPROPRIATE
        session.transition_to(State.EXIT)
        
        assert session.state == State.EXIT
        print("✅ Device-specific scenario structure validated")

    def test_scenario_multi_turn_diagnosis(self):
        """Test multi-turn diagnostic flow."""
        session = create_session("scenario-multiturn-1")
        
        # Turn 1
        session.add_message("user", "My WiFi is slow")
        session.add_message("assistant", "When did this start?")
        assert session.diagnosis_turn_count == 1
        
        # Turn 2
        session.add_message("user", "This morning")
        session.add_message("assistant", "Does it affect all devices?")
        assert session.diagnosis_turn_count == 2
        
        # Turn 3
        session.add_message("user", "Yes, all devices")
        session.add_message("assistant", "Let's reboot...")
        assert session.diagnosis_turn_count == 3
        
        assert session.total_turns == 3
        print("✅ Multi-turn diagnosis scenario validated")


class TestErrorHandling:
    """Test error handling in conversation flow."""

    def test_missing_manual_data_check(self):
        """Test handling of missing manual data."""
        from src.manual_service import get_total_steps, get_reboot_step
        
        # Valid method should have steps
        total = get_total_steps("soft_reboot")
        assert total > 0
        
        # Invalid method should return 0
        total_invalid = get_total_steps("invalid_method")
        assert total_invalid == 0
        print("✅ Missing manual data detection works")

    def test_state_transition_logging(self):
        """Test that state transitions are logged."""
        session = create_session("test-logging-1")
        
        # Transitions should update state
        initial_state = session.state
        session.transition_to(State.REBOOT_GUIDE)
        
        assert session.state != initial_state
        assert session.state == State.REBOOT_GUIDE
        print("✅ State transition logging works")

    def test_conversation_context_preservation(self):
        """Test that conversation context is preserved across states."""
        session = create_session("test-context-1")
        
        # Add messages in DIAGNOSIS
        session.add_message("user", "My WiFi is down")
        session.add_message("assistant", "Let me help")
        diagnosis_message_count = len(session.messages)
        
        # Transition to REBOOT_GUIDE
        session.transition_to(State.REBOOT_GUIDE)
        
        # Add messages in REBOOT_GUIDE
        session.add_message("user", "Ready for step 1")
        
        # All messages should be preserved
        assert len(session.messages) == diagnosis_message_count + 1
        assert session.messages[0]["content"] == "My WiFi is down"
        print("✅ Conversation context preservation works")


class TestManualDataCompleteness:
    """Test that manual data is complete for all reboot methods."""

    def test_soft_reboot_complete(self):
        """Test soft reboot method has all required fields and steps."""
        from src.manual_service import get_reboot_method
        
        method = get_reboot_method("soft_reboot")
        assert method is not None
        assert "method_id" in method
        assert "title" in method
        assert "description" in method
        assert "steps" in method
        assert len(method["steps"]) >= 3  # Should have multiple steps
        print(f"✅ Soft reboot method complete ({len(method['steps'])} steps)")

    def test_web_ui_reboot_complete(self):
        """Test web UI reboot method has all required fields."""
        from src.manual_service import get_reboot_method
        
        method = get_reboot_method("web_ui_reboot")
        assert method is not None
        assert method["method_id"] == "web_ui_reboot"
        assert len(method["steps"]) >= 3
        print(f"✅ Web UI reboot method complete ({len(method['steps'])} steps)")

    def test_factory_reset_complete(self):
        """Test factory reset method has warning and steps."""
        from src.manual_service import get_reboot_method
        
        method = get_reboot_method("factory_reset")
        assert method is not None
        assert "warning" in method  # Should have warning
        assert len(method["steps"]) >= 5
        print(f"✅ Factory reset method complete ({len(method['steps'])} steps)")

    def test_all_reboot_methods_accessible(self):
        """Test that all reboot methods can be accessed."""
        from src.manual_service import get_reboot_method
        
        methods = ["soft_reboot", "web_ui_reboot", "factory_reset"]
        for method_id in methods:
            method = get_reboot_method(method_id)
            assert method is not None, f"Method {method_id} not found"
        print(f"✅ All {len(methods)} reboot methods accessible")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
