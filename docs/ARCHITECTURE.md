# System Architecture & Design

## Overview

The WiFi Troubleshooter is an enterprise-grade FastAPI chat service that demonstrates production-ready patterns for security, reliability, and observability. This document explains the system design, key decisions, and architectural patterns used.

---

## 1. Core Architecture

### Request Flow Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP Request                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │   CORS Mware │
                    └──────┬───────┘
                           │
                    ┌──────▼────────────────┐
                    │  Request Logging Mware│
                    │  (PII redaction)      │
                    └──────┬────────────────┘
                           │
                    ┌──────▼──────────────┐
                    │  APIKeyValidator    │
                    │  (Optional)         │
                    └──────┬──────────────┘
                           │
                    ┌──────▼────────────────┐
                    │  RateLimiter          │
                    │  (100 req/hour)       │
                    └──────┬────────────────┘
                           │
                    ┌──────▼───────────────────┐
                    │  InputValidator          │
                    │  (injection detection)   │
                    └──────┬───────────────────┘
                           │
                    ┌──────▼──────────────────┐
                    │  Message Sanitization   │
                    │  (normalize whitespace) │
                    └──────┬──────────────────┘
                           │
                    ┌──────▼─────────────────────┐
                    │  chat_handler.process()    │
                    │  ├─ State machine routing  │
                    │  ├─ DiagnosticDetector     │
                    │  └─ call_llm()             │
                    │      ├─ LLM API call       │
                    │      ├─ Token tracking     │
                    │      └─ Cost calculation   │
                    └──────┬─────────────────────┘
                           │
                    ┌──────▼──────────────────────┐
                    │  MetricsCollector           │
                    │  (record outcomes)          │
                    └──────┬──────────────────────┘
                           │
                    ┌──────▼──────────────────────┐
                    │  HTTP Response              │
                    │  (JSON)                     │
                    └─────────────────────────────┘
```

---

## 2. Module Organization

### Core Application Layer
```
main.py
  ├─ FastAPI app initialization
  ├─ Middleware setup (CORS, logging, security)
  ├─ Route handlers (/session, /chat, /health, /metrics)
  └─ Session storage (_sessions dict for in-memory store)

chat_handler.py
  ├─ Process user message
  ├─ Route based on session state
  ├─ Integration with llm_service
  └─ State transitions

llm_service.py
  ├─ LLM API integration (Azure AI Inference)
  ├─ Token tracking integration
  ├─ Multi-token failover strategy
  └─ Model configuration management

state_machine.py
  ├─ Session state enum (DIAGNOSIS, REBOOT, POST_CHECK, EXIT)
  ├─ State transitions
  ├─ Conversation history
  └─ Metrics recording on transitions

manual_service.py
  └─ Router manual data loading (JSON)
```

### Infrastructure / Utility Layer
```
Configuration
  └─ config.py
      ├─ ConfigManager class
      ├─ Environment variable loading
      └─ Type-safe config accessors

Security
  └─ api_security.py
      ├─ APIKeyValidator (optional auth)
      ├─ RateLimitTracker (per-session, rolling window)
      └─ RateLimiter wrapper

Validation
  └─ input_validator.py
      ├─ Pattern detection (SQL injection, command injection)
      ├─ Control character filtering
      ├─ Length validation
      └─ Whitespace normalization

Observability
  ├─ metrics.py
  │  ├─ Prometheus instrumentation
  │  ├─ 8 metric types
  │  └─ Lazy initialization (graceful degradation)
  ├─ request_logging.py
  │  ├─ RequestLoggingMiddleware
  │  ├─ Sensitive field redaction
  │  └─ Request/response timing
  └─ token_usage_tracker.py
      ├─ LLM token recording
      ├─ Cost calculation by model
      ├─ JSONL persistence
      └─ Spike detection

Session Management
  └─ session_store.py
      ├─ SessionStore ABC interface
      ├─ MemorySessionStore implementation
      └─ RedisSessionStore (optional, commented)

Context
  ├─ conversation_context.py
  │  ├─ Rich context dataclass
  │  ├─ 9 enums for metadata
  │  └─ Intelligent escalation logic
  └─ diagnostic_detector.py
      ├─ Pattern matching (firmware, ISP, device)
      ├─ Keyword-based detection
      └─ Reboot attempt counting

Utilities
  └─ logger.py
      ├─ Logging configuration
      └─ Log format standardization
```

---

## 3. Design Patterns

### A. State Machine Pattern
**Purpose:** Clear conversation lifecycle management

**Implementation:**
```
State Enum: DIAGNOSIS → REBOOT → POST_CHECK → EXIT

Transitions:
  DIAGNOSIS  --[turn_limit reached]--> REBOOT
  REBOOT     --[user confirms]--> POST_CHECK
  POST_CHECK --[online?]--> EXIT (resolved) or DIAGNOSIS (not resolved)
  EXIT       --[end]--> (session expires)
```

**Benefits:**
- Clear state visibility
- Prevents invalid transitions
- Easy to test and debug
- Extensible for new states

---

### B. Middleware Pattern
**Purpose:** Cross-cutting concerns without cluttering business logic

**Implementation:**
```python
# Security middleware
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RequestLoggingMiddleware)

# Each middleware:
# 1. Processes request
# 2. Calls next middleware/handler
# 3. Processes response
```

**Benefits:**
- Clean separation of concerns
- Reusable across routes
- Testable in isolation
- Standard FastAPI pattern

---

### C. Dependency Injection Pattern
**Purpose:** Testable, mockable LLM service

**Implementation:**
```python
# llm_service provides call_llm() function
# chat_handler calls llm_service.call_llm()
# Can easily mock for testing

# Real LLM call:
response = call_llm(messages, model, session_id)

# Test mock:
response = Mock(
    choices=[Mock(message=Mock(content="mocked_response"))],
    usage=Mock(prompt_tokens=10, completion_tokens=5)
)
```

**Benefits:**
- Easy unit testing
- No real API calls in tests
- Can swap implementations

---

### D. Abstract Base Class Pattern
**Purpose:** Pluggable implementations (memory vs Redis)

**Implementation:**
```python
class SessionStore(ABC):
    @abstractmethod
    async def save(self, session): pass
    
    @abstractmethod
    async def load(self, session_id): pass
    
    @abstractmethod
    async def cleanup_expired(self, ttl_hours): pass

# Implementations:
# - MemorySessionStore (active, in-memory)
# - RedisSessionStore (optional, commented)
```

**Benefits:**
- Interface consistency
- Easy backend swapping
- Single responsibility
- Test with mock implementations

---

### E. Singleton Pattern
**Purpose:** Global instances for metrics and rate limiting

**Implementation:**
```python
# Global rate limiter (initialized once)
_rate_limiter = RateLimiter(rate_limit_per_hour=100)

def get_rate_limiter() -> RateLimiter:
    return _rate_limiter

# Usage:
rate_limiter = get_rate_limiter()
is_allowed, msg = rate_limiter.check(session_id)
```

**Benefits:**
- Single state across requests
- Thread-safe (dict operations in Python are atomic for simple ops)
- Easy cleanup/reset

---

### F. Context Object Pattern
**Purpose:** Rich metadata to avoid re-parsing

**Implementation:**
```python
@dataclass
class ConversationContext:
    session_id: str
    issue_severity: IssueSeverity
    affected_devices: list[UserDeviceType]
    reboot_attempts_count: int
    prior_actions: list[PriorAction]
    
    @property
    def should_recommend_factory_reset(self) -> bool:
        return self.reboot_attempts_count >= 2
    
    def get_safe_reboot_method(self) -> RebootMethod:
        # Escalate based on attempts
        if self.reboot_attempts_count == 0:
            return RebootMethod.SOFT_REBOOT
        elif self.reboot_attempts_count == 1:
            return RebootMethod.WEB_UI_REBOOT
        else:
            return RebootMethod.FACTORY_RESET
```

**Benefits:**
- Prevents scattered state
- Type-safe metadata
- Easy to add rich properties
- Reduces function parameters

---

### G. Graceful Degradation Pattern
**Purpose:** Features work independently

**Implementation:**
```python
# Metrics are optional
_prometheus_available = False
try:
    from prometheus_client import Counter, Histogram
    _prometheus_available = True
except ImportError:
    logger.warning("prometheus-client not installed")

# Code uses _prometheus_available to skip if not installed
if _prometheus_available:
    # Record metrics
    _llm_call_duration_seconds.observe(duration)
```

**Benefits:**
- No hard dependency failures
- Easier deployment
- Optional features don't crash app
- Clean error handling

---

## 4. Data Flow

### Conversation Data Flow
```
User Message (JSON)
    │
    ├─→ Validation (InputValidator)
    ├─→ Load Session (from memory dict)
    ├─→ Add to conversation history
    │
    ├─→ LLM Service
    │   ├─ Prepare messages with context
    │   ├─ Call Azure AI API
    │   ├─ Parse decision tags from response
    │   ├─ Track tokens used
    │   └─ Log cost to JSON
    │
    ├─→ State Machine
    │   ├─ Based on decision, transition state
    │   ├─ Record state transition metrics
    │   └─ Return appropriate guidance text
    │
    ├─→ Metrics
    │   ├─ Record chat turn
    │   ├─ Update active sessions gauge
    │   └─ If complete, record resolution
    │
    └─→ Response (JSON)
        ├─ session_id
        ├─ reply (assistant message)
        ├─ state (current state name)
        ├─ turn (which turn in conversation)
        └─ is_complete (has session ended?)
```

### Token Tracking Data Flow
```
LLM Call
    │
    ├─→ Azure AI API returns response
    │   └─ response.usage.prompt_tokens = 150
    │   └─ response.usage.completion_tokens = 45
    │
    ├─→ TokenUsageTracker.record()
    │   ├─ Calculate cost: (150 * 0.15 + 45 * 0.60) / 1M = 0.00385
    │   ├─ Log to JSONL: { timestamp, session_id, model, tokens, cost, state }
    │   ├─ Check if spike: cost > $1.00? Yes → ALERT
    │   └─ Aggregate per session
    │
    └─→ logs/token_usage.jsonl
        (for billing and cost analysis)
```

---

## 5. Security Architecture

### Input Security
```
User Input → Validation → Sanitization → Chat Processing

Validation (InputValidator):
  1. Check for null/control characters → REJECT
  2. Check length (max 2000) → REJECT if too long
  3. Match against injection patterns → REJECT if suspicious
  4. Allow if passes all checks → SANITIZE

Sanitization (InputValidator):
  1. Strip leading/trailing whitespace
  2. Collapse 3+ consecutive newlines to 2
  3. Return cleaned message

Result: Safe input enters chat processing
```

### API Security
```
Request → Authentication → Rate Limiting → Processing

Authentication (APIKeyValidator):
  1. Check if API_KEY configured
  2. If not, skip (dev mode)
  3. If yes, validate header against env var
  4. Return 401 if invalid

Rate Limiting (RateLimitTracker):
  1. Track per session_id
  2. Maintain rolling 1-hour window
  3. Count requests in window
  4. Return 429 if limit exceeded with retry timing
```

### Data Protection
```
Logging → Redaction → Persistence

Request Logging (RequestLoggingMiddleware):
  1. Log [REQUEST] method, path, client IP
  2. Log body keys (not values) to avoid PII
  3. Log [RESPONSE] status, duration

Response Logging:
  1. Log errors as [ERROR_RESPONSE]
  2. Redact sensitive fields:
     - session_id → REDACTED
     - token → REDACTED
     - password → REDACTED
     - api_key → [MASKED][len:N]
     - authorization → REDACTED
     - x-api-key → REDACTED

Result: Logs safe for storage/audit without exposing secrets
```

---

## 6. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API** | FastAPI 0.115.0 | Modern async web framework |
| **LLM** | Azure AI Inference | Cloud LLM API with failover support |
| **Auth** | Python stdlib | Optional API key validation |
| **Validation** | regex (stdlib) | Injection pattern detection |
| **Metrics** | Prometheus 0.19.0 | Industry-standard observability |
| **Logging** | Python logging | Structured application logs |
| **Running** | Uvicorn 0.30.0 | ASGI server |
| **Config** | python-dotenv 1.0.0 | Environment variable management |
| **Types** | Python 3.11 type hints | Static type checking |

---

## 7. Scalability Considerations

### Current State (Single-Process)
- **Session Store:** MemorySessionStore (in-memory dict)
- **Rate Limiter:** In-memory dict per session
- **Suitable for:** Development, testing, single-process deployment

### Production State (Multi-Process)
To scale to multiple processes:

1. **Session Store Upgrade**
   - Changes: Uncomment RedisSessionStore in session_store.py
   - Add: `pip install redis`
   - Config: `SESSION_STORE=redis`, `REDIS_URL=redis://localhost:6379`

2. **Rate Limiter Upgrade**
   - Changes: Add Redis backend to RateLimitTracker
   - Benefit: Consistent rate limits across processes

3. **Metrics Aggregation**
   - Current: Prometheus scrapes /metrics endpoint
   - Upgrade: Use Prometheus Pushgateway for multi-instance

---

## 8. Error Handling Strategy

### Levels of Error Handling

**Level 1: Input Validation**
```python
# Reject bad input early
if not InputValidator.validate(message):
    raise HTTPException(400, "Invalid input")
```

**Level 2: LLM API Errors**
```python
try:
    response = call_llm(...)
except Exception as e:
    # Record metric
    MetricsCollector.record_llm_error(type(e).__name__)
    # Return user-friendly message
    raise HTTPException(500, "Failed to process request")
```

**Level 3: Session Errors**
```python
if not session:
    raise HTTPException(404, "Session not found")
```

**Level 4: Optional Feature Degradation**
```python
try:
    MetricsCollector.record_chat_turn()
except Exception as e:
    logger.warning(f"Metrics recording failed: {e}")
    # Continue anyway, don't crash
```

---

## 9. Testing Strategy

### Unit Tests
- Test InputValidator patterns independently
- Mock LLM responses, test state transitions
- Test RateLimiter with concurrent requests
- Test token tracking cost calculations

### Integration Tests
- Test full request flow through middleware
- Verify metrics recording works end-to-end
- Test state machine transitions with real LLM

### Test Example
```python
def test_input_validation_rejects_sql_injection():
    message = "test'; DROP TABLE sessions; --"
    is_valid, msg = InputValidator.validate(message, "test-session")
    assert not is_valid
    assert "injection" in msg.lower()

def test_rate_limiter_rejects_after_limit():
    limiter = RateLimitTracker(rate_limit_per_hour=3)
    
    # Allow 3 requests
    for i in range(3):
        allowed, msg = limiter.is_allowed("session-1")
        assert allowed
    
    # Reject 4th
    allowed, msg = limiter.is_allowed("session-1")
    assert not allowed
    assert "exceeded" in msg.lower()
```

---

## 10. Configuration Management

### Environment-Driven Design
```
Application Code
    ↓
ConfigManager (single source of truth)
    ↓
Environment Variables
    ↓
.env file or OS environment
```

### All Configuration
```bash
# LLM
GITHUB_TOKEN_1=xyz
MODEL_1=openai/gpt-4o-mini

# Logging
LOG_LEVEL=INFO

# Security
API_KEY=optional
RATE_LIMIT_PER_HOUR=100

# Sessions
SESSION_TTL_HOURS=24
SESSION_STORE=memory

# Diagnosis
MAX_DIAGNOSIS_TURNS=6
```

**Benefits:**
- Easy docker/k8s deployment with env vars
- No hardcoded secrets
- Runtime configuration changes
- Dev/staging/prod can use same code

---

## Summary

This architecture demonstrates:
- ✅ **Security**: Multi-layer validation, optional auth, rate limiting
- ✅ **Observability**: Logging, metrics, cost tracking
- ✅ **Reliability**: Error handling, graceful degradation
- ✅ **Maintainability**: Modular design, type hints, clear patterns
- ✅ **Scalability**: Abstracted session store, external metrics
- ✅ **Testability**: Dependency injection, mockable components

The system is production-ready and demonstrates enterprise software engineering practices.
