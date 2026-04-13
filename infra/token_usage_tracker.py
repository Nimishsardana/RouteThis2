"""
Token Usage Tracker: logs token consumption and estimated costs from LLM API calls.

Responsibilities:
- Track prompt tokens, completion tokens, and total per request
- Calculate estimated costs based on model pricing
- Persist usage logs for billing and analytics
- Warn if usage spikes unexpectedly
"""

import logging
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import threading

logger = logging.getLogger(__name__)

# Pricing (per 1M tokens) — GitHub Models pricing as of 2024
MODEL_PRICING = {
    "openai/gpt-4o-mini": {
        "input": 0.15,      # $0.15 per 1M input tokens
        "output": 0.60,     # $0.60 per 1M output tokens
    },
    "openai/gpt-4o": {
        "input": 2.50,
        "output": 10.00,
    },
    "mistral/large": {
        "input": 2.00,
        "output": 6.00,
    },
}


@dataclass
class TokenUsageRecord:
    """Single API call token record."""
    timestamp: str
    session_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    state: str  # e.g., "DIAGNOSIS", "REBOOT_GUIDE"
    
    def to_dict(self) -> dict:
        return asdict(self)


class TokenUsageTracker:
    """Tracks and logs token usage for cost accounting."""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or (Path(__file__).parent / "logs" / "token_usage.jsonl")
        self.log_file.parent.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self._session_total = {}  # session_id -> total_cost
        logger.info(f"TokenUsageTracker initialized, logging to {self.log_file}")
    
    def record(
        self,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        state: str,
    ) -> TokenUsageRecord:
        """
        Record a token usage event. Returns the record created.
        Optionally warns if cost spike detected.
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        record = TokenUsageRecord(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            state=state,
        )
        
        # Persist to JSONL
        with self.lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
            
            # Track session total
            session_total = self._session_total.get(session_id, 0)
            self._session_total[session_id] = session_total + cost
            
            # Warn if single call exceeds $1 (suspicious)
            if cost > 1.00:
                logger.warning(
                    f"[{session_id}] Expensive API call: {model} | "
                    f"{total_tokens} tokens | ${cost:.4f}"
                )
            
            # Warn if session total exceeds $5 (potential runaway)
            if self._session_total[session_id] > 5.00:
                logger.warning(
                    f"[{session_id}] Session cost spike: ${self._session_total[session_id]:.2f} spent"
                )
        
        logger.info(
            f"[{session_id}] Tokens: {prompt_tokens}→{completion_tokens} | "
            f"Model: {model} | Cost: ${cost:.4f}"
        )
        return record
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on model pricing."""
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            logger.warning(f"Unknown model {model}, assuming gpt-4o-mini pricing")
            pricing = MODEL_PRICING["openai/gpt-4o-mini"]
        
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def get_session_total(self, session_id: str) -> float:
        """Get cumulative cost for a session."""
        with self.lock:
            return self._session_total.get(session_id, 0.0)
    
    def get_all_totals(self) -> dict[str, float]:
        """Get cost breakdown by session."""
        with self.lock:
            return dict(self._session_total)
    
    def get_daily_summary(self) -> dict:
        """Summarize today's usage (for reporting)."""
        today = datetime.utcnow().date().isoformat()
        total_tokens = 0
        total_cost = 0.0
        call_count = 0
        
        try:
            if self.log_file.exists():
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        record_dict = json.loads(line)
                        if record_dict["timestamp"].startswith(today):
                            total_tokens += record_dict["total_tokens"]
                            total_cost += record_dict["estimated_cost_usd"]
                            call_count += 1
        except Exception as e:
            logger.error(f"Error reading usage log: {e}")
        
        return {
            "date": today,
            "api_calls": call_count,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_cost,
        }


# Singleton instance
_tracker: Optional[TokenUsageTracker] = None


def get_usage_tracker() -> TokenUsageTracker:
    """Get or create the singleton tracker."""
    global _tracker
    if _tracker is None:
        _tracker = TokenUsageTracker()
    return _tracker
