"""
LLM service: wraps the Azure AI inference API (GitHub Models) with retry failover.

Responsibilities:
- Build system prompts grounded in manual data
- Call the inference API with full conversation history with automatic token/model failover
- Classify intents (reboot decision, post-check outcome)
- Enforce guardrails: reboot steps ONLY from manual
- Retry mechanism: 2 attempts per token, then switch to next token pair
- Track token usage for cost accounting
"""

import os
import json
import logging
import time
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
from azure.core.credentials import AzureKeyCredential

from src.manual_service import (
    get_all_reboot_methods_summary,
    get_router_lights_info,
    get_when_to_reboot_guidance,
)
from infra.token_usage_tracker import get_usage_tracker
from infra.config import ConfigManager, ModelConfig

logger = logging.getLogger(__name__)

# Retry configuration
MAX_ATTEMPTS_PER_TOKEN = 2
ENDPOINT = "https://models.github.ai/inference"

# Lazy-loaded configs
_token_configs: Optional[List[ModelConfig]] = None
_current_config_index = 0
_current_attempt_count = 0


def _get_token_configs() -> List[ModelConfig]:
    """Load all token/model pairs from configuration."""
    global _token_configs
    if _token_configs is None:
        _token_configs = ConfigManager.load_model_configs()
    return _token_configs


def _get_current_config() -> ModelConfig:
    """Get the current token/model config."""
    global _current_config_index
    configs = _get_token_configs()
    
    if _current_config_index >= len(configs):
        raise RuntimeError(f"All {len(configs)} token(s) exhausted after retries")
    
    return configs[_current_config_index]


def _advance_to_next_config() -> bool:
    """Move to the next token/model pair. Returns True if more configs available."""
    global _current_config_index, _current_attempt_count
    _current_config_index += 1
    _current_attempt_count = 0
    configs = _get_token_configs()
    return _current_config_index < len(configs)


def _record_attempt_failure() -> bool:
    """Record a failed attempt. Returns True if all tokens exhausted."""
    global _current_attempt_count
    _current_attempt_count += 1
    if _current_attempt_count >= MAX_ATTEMPTS_PER_TOKEN:
        config = _get_current_config()
        logger.warning(
            f"Token {config.index} ({config.model}) failed {MAX_ATTEMPTS_PER_TOKEN} times, "
            f"switching to next token..."
        )
        return not _advance_to_next_config()
    return False  # Retry with current token


def get_client_for_current_config() -> ChatCompletionsClient:
    """Create a client for the current token/model config."""
    config = _get_current_config()
    logger.debug(f"Creating client with token {config.index}, model: {config.model}")
    
    # Create client with custom transport and no retry policy
    from azure.core.pipeline.transport import RequestsTransport
    from azure.core.pipeline.policies import RetryPolicy
    
    transport = RequestsTransport(timeout=10)  # 10 second timeout for all requests
    
    # Disable automatic retries to prevent waiting on Retry-After header
    retry_policy = RetryPolicy(total_retries=0)
    
    return ChatCompletionsClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(config.token),
        transport=transport,
    )


def get_current_model() -> str:
    """Get the current model name."""
    config = _get_current_config()
    return config.model


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

def _build_diagnosis_system_prompt() -> str:
    guidance = get_when_to_reboot_guidance()
    lights_info = get_router_lights_info()

    when_to = "\n".join(f"- {item}" for item in guidance["when_to_reboot"])
    when_not = "\n".join(f"- {item}" for item in guidance["when_not_to_reboot"])

    return f"""You are a helpful WiFi troubleshooting assistant for a Linksys EA6350 router.

Your job is to ask clear, concise diagnostic questions to understand the user's WiFi problem.
Ask one question at a time. Be friendly and patient.

Key diagnostic questions to cover (not all required — use your judgment):
1. What is the exact problem? (no internet, can't connect, slow speeds, specific device issue?)
2. Does the problem affect all devices or just one?
3. What do the router lights look like?
4. Has anything changed recently? (new device, ISP outage, moved the router?)
5. How long has the problem been occurring?

{lights_info}

Signs a reboot IS appropriate:
{when_to}

Signs a reboot is NOT appropriate (exit without reboot):
{when_not}

When you have enough information (usually 2-4 exchanges), you MUST end your response with one of:
- [DECISION: reboot_appropriate] — if the evidence suggests a reboot will help
- [DECISION: reboot_not_appropriate] — if the problem is device-specific, ISP-side, or not router-related
- [DECISION: need_more_info] — if you still need more diagnostic information

Keep responses under 100 words. Be direct and helpful."""


def _build_reboot_system_prompt() -> str:
    manual_content = get_all_reboot_methods_summary()
    return f"""You are a WiFi troubleshooting assistant guiding the user through a router reboot.

CRITICAL RULE: You MUST ONLY use reboot steps from the official Linksys EA6350 manual below.
Do NOT add, modify, or invent any steps. Quote steps exactly as written.

{manual_content}

You are currently guiding the user step-by-step. When given a step to deliver:
- Present it clearly and warmly
- Ask the user to confirm when they've completed it before moving on
- If user has a question, answer briefly and get back on track
- Keep responses under 80 words"""


def _build_post_check_system_prompt() -> str:
    return """You are a WiFi troubleshooting assistant checking if the reboot resolved the user's issue.

Ask the user if their WiFi issue is now resolved.

Based on their response, end your message with:
- [OUTCOME: resolved] — if they confirm it's working
- [OUTCOME: not_resolved] — if it's still broken or worse
- [OUTCOME: unclear] — if you need clarification

Keep responses under 60 words."""


def _build_exit_system_prompt() -> str:
    return """You are a friendly WiFi troubleshooting assistant closing the conversation.

If resolved: congratulate the user warmly and wish them well.
If not resolved: apologize sincerely, then suggest these next steps:
1. Check for ISP outages in their area
2. Contact Linksys support at 1-800-326-7114
3. Visit support.linksys.com for additional resources
4. Consider a factory reset (warn it erases all settings)

Keep responses under 100 words. End with a warm goodbye."""


def _build_no_reboot_exit_prompt() -> str:
    return """You are a WiFi troubleshooting assistant. Based on the diagnosis, a router reboot is NOT the right solution.

Explain briefly why a reboot won't help in this case, then provide targeted suggestions:
- If device-specific: check device WiFi settings, forget and rejoin network, restart the device
- If ISP outage: check ISP status page or call them
- If single website: the issue is likely with that website's servers
- If firmware updating: wait for it to complete

Keep response under 100 words. Be helpful and empathetic."""


# ---------------------------------------------------------------------------
# Core LLM call
# ---------------------------------------------------------------------------

def _convert_messages_to_azure(messages: list) -> list:
    """
    Convert generic role/content dicts to Azure SDk message objects.
    Azure expects SystemMessage, UserMessage, AssistantMessage objects.
    """
    azure_messages = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            azure_messages.append(UserMessage(content=content))
        elif role == "assistant":
            azure_messages.append(AssistantMessage(content=content))
        # system messages are passed separately, not in the messages list
    return azure_messages


def call_llm(system_prompt: str, messages: list, max_tokens: int = 400, session_id: str = "unknown", state: str = "unknown") -> str:
    """
    Call the Azure AI inference API with retry failover mechanism.
    - Tries each token/model pair up to MAX_ATTEMPTS_PER_TOKEN times
    - On failure, automatically switches to the next token/model pair
    - Raises RuntimeError after all tokens are exhausted
    - Tracks token usage for cost accounting
    
    Args:
        system_prompt: System instruction for the LLM
        messages: Conversation history
        max_tokens: Max output tokens
        session_id: Session ID for tracking (optional)
        state: Current conversation state for logging (optional)
    
    Returns the assistant text response.
    """
    global _current_config_index, _current_attempt_count
    
    # Convert messages to Azure format once (reused across retries)
    azure_messages = _convert_messages_to_azure(messages)
    
    while True:
        try:
            config = _get_current_config()
            logger.info(
                f"LLM call | token={config.index} | model={config.model} | "
                f"attempt={_current_attempt_count + 1}/{MAX_ATTEMPTS_PER_TOKEN} | "
                f"messages={len(messages)} | max_tokens={max_tokens}"
            )
            
            client = get_client_for_current_config()
            
            # Wrap the API call with a timeout using ThreadPoolExecutor
            # This prevents Azure SDK's retry logic from blocking indefinitely
            t_start = time.time()
            
            def make_api_call():
                return client.complete(
                    model=config.model,
                    messages=[SystemMessage(content=system_prompt)] + azure_messages,
                    temperature=1.0,
                    top_p=1.0,
                    max_tokens=max_tokens,
                )
            
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(make_api_call)
                    response = future.result(timeout=15)  # 15 second timeout
            except FuturesTimeoutError:
                logger.warning(f"LLM call timed out after 15s on token {config.index}, trying next token")
                if not _advance_to_next_config():
                    raise RuntimeError("All tokens exhausted or rate-limited (timeout)")
                continue
            
            t_elapsed = time.time() - t_start
            
            content = response.choices[0].message.content
            logger.info(f"LLM response received in {t_elapsed:.2f}s | length={len(content)}")
            logger.debug(f"Response: {content[:200]}...")
            
            # Track token usage
            try:
                prompt_tokens = getattr(response, 'usage', None)
                if prompt_tokens:
                    prompt_tokens = getattr(prompt_tokens, 'prompt_tokens', 0)
                    completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                    
                    tracker = get_usage_tracker()
                    tracker.record(
                        session_id=session_id,
                        model=config.model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        state=state,
                    )
            except Exception as e:
                logger.warning(f"Failed to track token usage: {e}")
            
            # Reset attempt counter on success
            _current_attempt_count = 0
            return content
            
        except Exception as e:
            logger.error(f"LLM call failed: {type(e).__name__}: {e}")
            
            # Check if this is a rate limit error (429)
            error_str = str(e).lower()
            if ("429" in error_str or "ratelimit" in error_str or "rate_limit" in error_str or 
                "quotaexceed" in error_str or "ratelimitreached" in error_str):
                config = _get_current_config()
                logger.warning(f"🔄 Rate limit on token {config.index} ({config.model}), switching to next token")
                if not _advance_to_next_config():
                    raise RuntimeError(
                        f"All {len(_token_configs)} token(s) are rate-limited. "
                        f"Quota exceeded on all tokens. Please wait for quota to reset or add new tokens to .env"
                    )
                # Continue to next iteration (retry with next token)
                continue
            
            # Check if we should switch to next token for other errors
            all_exhausted = _record_attempt_failure()
            if all_exhausted:
                raise RuntimeError(
                    f"All {len(_token_configs)} token(s) exhausted after {MAX_ATTEMPTS_PER_TOKEN} "
                    f"attempts each. Last error: {type(e).__name__}: {e}"
                )
            # Loop will retry with either same token or next token



# ---------------------------------------------------------------------------
# State-specific handlers
# ---------------------------------------------------------------------------

def handle_diagnosis(messages: list, session_id: str = "unknown") -> tuple[str, Optional[str]]:
    """
    Run one diagnosis turn.
    Returns: (response_text, decision_tag or None)
    decision_tag: 'reboot_appropriate' | 'reboot_not_appropriate' | 'need_more_info' | None
    """
    system = _build_diagnosis_system_prompt()
    response = call_llm(system, messages, session_id=session_id, state="DIAGNOSIS")

    decision = None
    if "[DECISION: reboot_appropriate]" in response:
        decision = "reboot_appropriate"
        response = response.replace("[DECISION: reboot_appropriate]", "").strip()
    elif "[DECISION: reboot_not_appropriate]" in response:
        decision = "reboot_not_appropriate"
        response = response.replace("[DECISION: reboot_not_appropriate]", "").strip()
    elif "[DECISION: need_more_info]" in response:
        decision = "need_more_info"
        response = response.replace("[DECISION: need_more_info]", "").strip()

    return response, decision


def handle_reboot_step(messages: list, step_text: str, step_num: int, total_steps: int, session_id: str = "unknown") -> str:
    """
    Deliver a specific reboot step to the user.
    The step_text comes ONLY from the manual — we inject it to prevent hallucination.
    """
    system = _build_reboot_system_prompt()

    # Inject the exact step so Claude presents it (not invents it)
    step_instruction = (
        f"Please present this exact step ({step_num} of {total_steps}) to the user "
        f"in a friendly way and ask them to confirm when done:\n\n\"{step_text}\""
    )

    # Add the step instruction as a temporary system guidance appended to last user message
    augmented_messages = messages + [
        {"role": "user", "content": f"[SYSTEM: {step_instruction}]"}
    ]

    return call_llm(system, augmented_messages, session_id=session_id, state="REBOOT_GUIDE")


def handle_post_check(messages: list, session_id: str = "unknown") -> tuple[str, Optional[str]]:
    """
    Ask if the issue is resolved after reboot.
    Returns: (response_text, outcome or None)
    outcome: 'resolved' | 'not_resolved' | 'unclear'
    """
    system = _build_post_check_system_prompt()
    response = call_llm(system, messages, session_id=session_id, state="POST_CHECK")

    outcome = None
    if "[OUTCOME: resolved]" in response:
        outcome = "resolved"
        response = response.replace("[OUTCOME: resolved]", "").strip()
    elif "[OUTCOME: not_resolved]" in response:
        outcome = "not_resolved"
        response = response.replace("[OUTCOME: not_resolved]", "").strip()
    elif "[OUTCOME: unclear]" in response:
        outcome = "unclear"
        response = response.replace("[OUTCOME: unclear]", "").strip()

    return response, outcome


def handle_exit(messages: list, resolved: Optional[bool], session_id: str = "unknown") -> str:
    """Generate a closing message."""
    system = _build_exit_system_prompt()
    context = "resolved" if resolved else "not resolved"
    augmented = messages + [
        {"role": "user", "content": f"[SYSTEM: The issue was {context}. Generate closing message.]"}
    ]
    return call_llm(system, augmented, session_id=session_id, state="EXIT")


def handle_no_reboot_exit(messages: list, session_id: str = "unknown") -> str:
    """Generate a closing message when reboot is not appropriate."""
    system = _build_no_reboot_exit_prompt()
    return call_llm(system, messages, session_id=session_id, state="EXIT")


def handle_general_question(messages: list, current_state: str) -> str:
    """
    Handle an off-topic or general question during any state.
    Answers briefly, then steers back to the troubleshooting flow.
    """
    system = f"""You are a WiFi troubleshooting assistant.
The user has asked a question during the troubleshooting process (current state: {current_state}).
Answer their question briefly (under 60 words), then politely redirect them back to the troubleshooting.
Do NOT provide any router reboot steps unless they come from your context.
Be friendly and helpful."""
    return call_llm(system, messages)


def classify_reboot_method(diagnosis_summary: str, session_id: str = "unknown") -> str:
    """
    Given a diagnosis summary, decide which reboot method to use.
    Returns: 'soft_reboot' | 'web_ui_reboot' | 'factory_reset'
    Default to soft_reboot for safety.
    """
    system = """You are a router support assistant. Based on the diagnosis summary, 
decide which reboot method is most appropriate:
- soft_reboot: standard first step, works for most issues
- web_ui_reboot: if user is comfortable with web browsers and the router is accessible
- factory_reset: ONLY if soft_reboot has already been tried and failed, and issue persists

Respond with ONLY one of: soft_reboot, web_ui_reboot, factory_reset"""

    try:
        messages = [{"role": "user", "content": diagnosis_summary}]
        response = call_llm(system, messages, max_tokens=20, session_id=session_id, state="DECISION")
        response = response.strip().lower()
        if response in ("soft_reboot", "web_ui_reboot", "factory_reset"):
            return response
    except Exception as e:
        logger.warning(f"Reboot method classification failed: {e}")

    return "soft_reboot"  # safe default
