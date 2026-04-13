"""
Chat handler: orchestrates the conversation state machine.

This is the main entry point for processing a user message.
It:
  1. Receives user input + current ConversationState
  2. Routes to the correct state handler
  3. Applies state transitions
  4. Returns the assistant response + updated state
"""

import logging
import time
from typing import Optional

from src.state_machine import (
    ConversationState,
    State,
    RebootDecision,
    PostCheckOutcome,
)
import src.llm_service as llm_service
import src.manual_service as manual_service
from infra.diagnostic_detector import DiagnosticDetector
from infra.config import ConfigManager

logger = logging.getLogger(__name__)

# After this many diagnosis turns without a decision, force a decision
MAX_DIAGNOSIS_TURNS = ConfigManager.get_max_diagnosis_turns()


class ChatHandler:
    """Processes one user message and returns an assistant reply."""

    def process(self, session: ConversationState, user_message: str) -> str:
        """
        Main dispatch method.
        Mutates `session` in place (state transitions, message history).
        Returns the assistant reply string.
        """
        t_start = time.time()
        
        # Record user message
        session.add_message("user", user_message)

        try:
            # Route to appropriate handler
            if session.state == State.DIAGNOSIS:
                reply = self._handle_diagnosis(session)

            elif session.state == State.DECISION:
                # DECISION is transient — we re-enter from DIAGNOSIS
                # This state is set internally, user messages land back in diagnosis flow
                reply = self._handle_diagnosis(session)

            elif session.state == State.REBOOT_GUIDE:
                reply = self._handle_reboot_guide(session)

            elif session.state == State.POST_CHECK:
                reply = self._handle_post_check(session)

            elif session.state == State.EXIT:
                reply = "Our troubleshooting session has ended. If you need further help, feel free to start a new session!"

            else:
                reply = "I'm sorry, something went wrong. Please start a new session."
                logger.error(f"[{session.session_id}] Unknown state: {session.state}")
        
        except RuntimeError as e:
            # Handle LLM service errors gracefully with specific error classification
            error_msg_lower = str(e).lower()
            
            # Classify error type and provide appropriate user-facing message
            if "rate" in error_msg_lower or "quotaexceed" in error_msg_lower or "ratelimitreached" in error_msg_lower:
                reply = (
                    "I'm currently experiencing high demand on the AI service. "
                    "Please try again in a few moments. If this persists, please start a new session."
                )
                logger.warning(f"[{session.session_id}] Rate limit error: {str(e)}")
            elif "timeout" in error_msg_lower:
                reply = (
                    "The AI service is responding slowly right now. "
                    "Please try again. If the issue continues, start a new session."
                )
                logger.warning(f"[{session.session_id}] Timeout error: {str(e)}")
            elif "token" in error_msg_lower and "exhausted" in error_msg_lower:
                reply = (
                    "I'm unable to connect to the AI service at the moment. "
                    "This is a temporary issue. Please try again in a few moments."
                )
                logger.error(f"[{session.session_id}] All tokens exhausted: {str(e)}")
            else:
                reply = (
                    "An unexpected error occurred while processing your message. "
                    "Please try again or start a new session."
                )
                logger.error(f"[{session.session_id}] Unexpected error: {str(e)}")
            
            session.transition_to(State.EXIT)

        # Record assistant reply
        session.add_message("assistant", reply)
        
        t_elapsed = time.time() - t_start
        logger.info(f"[{session.session_id}] Turn {session.total_turns} completed in {t_elapsed:.2f}s | State={session.state.value}")
        
        return reply

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_diagnosis(self, session: ConversationState) -> str:
        """Ask diagnostic questions and detect when a decision can be made."""

        # Early exit: detect firmware update in progress
        if DiagnosticDetector.detect_firmware_update("\n".join(m.get("content", "") for m in session.messages if m.get("role") == "user")):
            logger.info(f"[{session.session_id}] Firmware update detected, exiting without reboot")
            session.reboot_decision = RebootDecision.REBOOT_NOT_APPROPRIATE
            session.transition_to(State.EXIT)
            return (
                "I see you may be in the middle of a firmware update. **Don't reboot during firmware updates!** "
                "Please let the update complete first, then restart your router if needed. Once it finishes, try connecting again.\n\n"
                "Feel free to start a new session if you still have issues after the update completes."
            )

        # Safety: if stuck in diagnosis too long, force a reboot recommendation
        if session.diagnosis_turn_count >= MAX_DIAGNOSIS_TURNS:
            logger.warning(f"[{session.session_id}] Max diagnosis turns reached, forcing decision")
            return self._transition_to_reboot(session)

        response, decision = llm_service.handle_diagnosis(session.messages, session_id=session.session_id)

        if decision == "reboot_appropriate":
            session.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
            # Determine which reboot method to use (improved logic)
            diagnosis_summary = self._build_diagnosis_summary(session)
            diagnostics = DiagnosticDetector.analyze_conversation(session.messages)
            
            # Choose reboot method based on context
            if diagnostics["reboot_attempts"] >= 2:
                # Already rebooted, try web UI or factory reset
                session.reboot_method = "web_ui_reboot" if diagnostics["all_devices_affected"] else "factory_reset"
            else:
                # First time, always start with soft reboot
                session.reboot_method = llm_service.classify_reboot_method(diagnosis_summary, session_id=session.session_id)
            
            logger.info(f"[{session.session_id}] Reboot method selected: {session.reboot_method} (attempts: {diagnostics['reboot_attempts']})")

            session.transition_to(State.REBOOT_GUIDE)
            session.reboot_step_index = 0

            # Deliver the first reboot step immediately
            return self._deliver_reboot_step(session, preamble=response)

        elif decision == "reboot_not_appropriate":
            session.reboot_decision = RebootDecision.REBOOT_NOT_APPROPRIATE
            session.transition_to(State.EXIT)
            return llm_service.handle_no_reboot_exit(session.messages, session_id=session.session_id)

        else:
            # Still gathering info — stay in DIAGNOSIS
            return response

    def _handle_reboot_guide(self, session: ConversationState) -> str:
        """
        Deliver reboot steps one at a time.
        Each user reply advances to the next step.
        """
        # Advance step when user acknowledges
        session.reboot_step_index += 1
        total_steps = manual_service.get_total_steps(session.reboot_method)

        if session.reboot_step_index >= total_steps:
            # All steps done — move to post-check
            session.transition_to(State.POST_CHECK)
            response, outcome = llm_service.handle_post_check(session.messages, session_id=session.session_id)
            return self._apply_post_check_outcome(session, response, outcome)

        return self._deliver_reboot_step(session)

    def _handle_post_check(self, session: ConversationState) -> str:
        """Check if the reboot resolved the issue."""
        response, outcome = llm_service.handle_post_check(session.messages, session_id=session.session_id)
        return self._apply_post_check_outcome(session, response, outcome)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _deliver_reboot_step(self, session: ConversationState, preamble: str = "") -> str:
        """
        Fetch the current step from the manual and have LLM present it.
        The step text is always sourced from the manual — never hallucinated.
        """
        if not session.reboot_method:
            # Safety check: reboot method not set
            logger.error(f"[{session.session_id}] Reboot method not set before delivering steps")
            session.transition_to(State.EXIT)
            return (
                "I encountered an issue retrieving the reboot instructions. "
                "Please start a new session and we'll try again."
            )
        
        step_index = session.reboot_step_index
        total_steps = manual_service.get_total_steps(session.reboot_method)
        
        if total_steps == 0:
            # Manual data missing or corrupted
            logger.error(f"[{session.session_id}] Manual data missing for method: {session.reboot_method}")
            session.transition_to(State.EXIT)
            return (
                "I'm unable to retrieve the reboot instructions from the manual. "
                "Please contact Linksys support directly at 1-800-326-7114 for assistance."
            )
        
        step_text = manual_service.get_reboot_step(session.reboot_method, step_index)

        if not step_text:
            # Step index out of range (shouldn't happen if total_steps is correct)
            logger.error(f"[{session.session_id}] No step found at index {step_index}/{total_steps} for method {session.reboot_method}")
            session.transition_to(State.POST_CHECK)
            response, outcome = llm_service.handle_post_check(session.messages, session_id=session.session_id)
            return self._apply_post_check_outcome(session, response, outcome)

        try:
            step_response = llm_service.handle_reboot_step(
                session.messages,
                step_text=step_text,
                step_num=step_index + 1,
                total_steps=total_steps,
                session_id=session.session_id,
            )
        except Exception as e:
            # LLM call failed during step delivery
            logger.error(f"[{session.session_id}] Failed to present reboot step: {e}")
            session.transition_to(State.EXIT)
            return (
                "I encountered an issue while presenting the next instruction. "
                "Please try starting a new session."
            )

        if preamble:
            return f"{preamble}\n\n{step_response}"
        return step_response

    def _transition_to_reboot(self, session: ConversationState) -> str:
        """Force transition to reboot when max diagnosis turns exceeded."""
        session.reboot_decision = RebootDecision.REBOOT_APPROPRIATE
        session.reboot_method = "soft_reboot"
        session.transition_to(State.REBOOT_GUIDE)
        session.reboot_step_index = 0
        return self._deliver_reboot_step(session)

    def _apply_post_check_outcome(
        self,
        session: ConversationState,
        response: str,
        outcome: Optional[str],
    ) -> str:
        """Apply the post-check outcome and transition to EXIT."""
        if outcome == "resolved":
            session.resolved = True
            session.transition_to(State.EXIT)
            exit_msg = llm_service.handle_exit(session.messages, resolved=True, session_id=session.session_id)
            return f"{response}\n\n{exit_msg}"

        elif outcome == "not_resolved":
            session.resolved = False
            session.transition_to(State.EXIT)
            exit_msg = llm_service.handle_exit(session.messages, resolved=False, session_id=session.session_id)
            return f"{response}\n\n{exit_msg}"

        # Unclear — stay in POST_CHECK and ask again
        return response

    def _build_diagnosis_summary(self, session: ConversationState) -> str:
        """Summarize the diagnosis conversation for method classification."""
        lines = []
        for msg in session.messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines[-10:])  # Last 10 messages


# Singleton instance
chat_handler = ChatHandler()
