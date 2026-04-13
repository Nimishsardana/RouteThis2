#!/usr/bin/env python3
"""
Demo script showing the retry mechanism for multi-token API failover.

This demonstrates:
1. Loading multiple token/model configurations
2. Attempting calls with retry logic
3. Switching to next token after 2 failures
4. Proper error handling when all tokens exhausted
"""

import os
import sys
import types
import logging

# Setup console encoding for emoji
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# ── Mock Azure modules before imports ──────────────────────────────────
_mock_azure = types.ModuleType("azure")
_mock_azure_ai = types.ModuleType("azure.ai")
_mock_azure_ai_inference = types.ModuleType("azure.ai.inference")
_mock_azure_ai_inference_models = types.ModuleType("azure.ai.inference.models")
_mock_azure_core = types.ModuleType("azure.core")
_mock_azure_core_credentials = types.ModuleType("azure.core.credentials")

class _MockMessage:
    def __init__(self, content=""):
        self.content = content

class _MockResponse:
    def __init__(self, content="Mock response"):
        self.choices = [types.SimpleNamespace(message=_MockMessage(content))]

class _MockClient:
    def __init__(self, endpoint=None, credential=None):
        self.endpoint = endpoint
        self.call_count = 0
        self.should_fail = False
    
    def complete(self, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Simulated API failure")
        return _MockResponse(f"Response from {kwargs.get('model', 'unknown')}")

class _MockCredential:
    def __init__(self, *args, **kw): pass

_mock_azure_ai_inference_models.SystemMessage = _MockMessage
_mock_azure_ai_inference_models.UserMessage = _MockMessage
_mock_azure_ai_inference_models.AssistantMessage = _MockMessage
_mock_azure_ai_inference.ChatCompletionsClient = _MockClient
_mock_azure_core_credentials.AzureKeyCredential = _MockCredential

sys.modules["azure"] = _mock_azure
sys.modules["azure.ai"] = _mock_azure_ai
sys.modules["azure.ai.inference"] = _mock_azure_ai_inference
sys.modules["azure.ai.inference.models"] = _mock_azure_ai_inference_models
sys.modules["azure.core"] = _mock_azure_core
sys.modules["azure.core.credentials"] = _mock_azure_core_credentials

# ── Setup environment with test tokens ──────────────────────────────────
os.environ["GITHUB_TOKEN_1"] = "token_1_gpt_4o_mini"
os.environ["MODEL_1"] = "openai/gpt-4o-mini"
os.environ["GITHUB_TOKEN_2"] = "token_2_gpt_4o"
os.environ["MODEL_2"] = "openai/gpt-4o"
os.environ["GITHUB_TOKEN_3"] = "token_3_gpt_4_turbo"
os.environ["MODEL_3"] = "openai/gpt-4-turbo"

# ── Now import our modules ──────────────────────────────────────────────
from src.llm_service import (
    _load_token_configs,
    _get_current_config,
    _advance_to_next_config,
    _record_attempt_failure,
    get_current_model,
    call_llm,
)

# ── Setup logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s | %(message)s"
)
logger = logging.getLogger(__name__)

def demo_load_configs():
    """Show tokens loaded from environment."""
    print("\n" + "="*70)
    print("DEMO 1: Loading Token Configurations")
    print("="*70)
    configs = _load_token_configs()
    print(f"✓ Loaded {len(configs)} token/model pairs:\n")
    for config in configs:
        print(f"  Token {config.index}: {config.model}")
    return configs

def demo_retry_mechanism():
    """Show retry logic in action."""
    print("\n" + "="*70)
    print("DEMO 2: Retry Mechanism (2 Attempts Per Token)")
    print("="*70)
    
    # Reset global state
    import src.llm_service as llm_service
    llm_service._current_config_index = 0
    llm_service._current_attempt_count = 0
    
    configs = _load_token_configs()
    print(f"Starting with Token 1 ({configs[0].model})\n")
    
    # Simulate 2 failures on token 1
    for attempt in range(1, 3):
        config = _get_current_config()
        print(f"  Attempt {attempt}/{llm_service.MAX_ATTEMPTS_PER_TOKEN} on Token {config.index}")
        _record_attempt_failure()
    
    # Should advance to token 2
    config = _get_current_config()
    print(f"\n  ✓ After {llm_service.MAX_ATTEMPTS_PER_TOKEN} failures, switched to Token {config.index}")
    print(f"    Now using model: {config.model}\n")
    
    # Simulate 1 failure on token 2 (shouldn't advance yet)
    print(f"  Attempt 1/{llm_service.MAX_ATTEMPTS_PER_TOKEN} on Token {config.index}")
    _record_attempt_failure()
    config_still = _get_current_config()
    print(f"  ✓ Still on Token {config_still.index} (1 < {llm_service.MAX_ATTEMPTS_PER_TOKEN})\n")

def demo_successful_call():
    """Show successful LLM call with current config."""
    print("="*70)
    print("DEMO 3: Successful LLM Call")
    print("="*70)
    
    # Reset global state for clean demo
    import src.llm_service as llm_service
    llm_service._current_config_index = 0
    llm_service._current_attempt_count = 0
    
    config = _get_current_config()
    print(f"Using Token {config.index}: {config.model}\n")
    
    messages = [{"role": "user", "content": "What is WiFi?"}]
    response = call_llm("You are helpful.", messages, max_tokens=100)
    print(f"Response: {response}\n")

if __name__ == "__main__":
    print("\n🔄 Multi-Token Retry Mechanism Demo\n")
    
    try:
        configs = demo_load_configs()
        demo_retry_mechanism()
        demo_successful_call()
        
        print("="*70)
        print("✅ All demos completed successfully!")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
