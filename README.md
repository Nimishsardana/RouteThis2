# WiFi Troubleshooter - LLM-Powered Chatbot

An enterprise-grade FastAPI chatbot that diagnoses and resolves WiFi connectivity issues using AI reasoning and decision-making. Built with production-ready patterns for security, observability, and reliability.

**Status:** ✅ Production-Ready | **Version:** 1.0.0 | **Python:** 3.11+

---

## 🎯 Quick Start (5 minutes)

### 1. Clone & Setup
```bash
# Clone the repository
git clone <repo>
cd "Route This/Claude"

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure
```bash
# Copy environment template
copy .env.example .env

# Edit .env with your tokens
# Required:
# GITHUB_TOKEN_1=your_token_here
```

### 3. Run
```bash
# Start the server
uvicorn src.main:app --reload --port 8000

# Server is running at http://localhost:8000
```

### 4. Test
```bash
# Health check
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs

# Or use the web UI at http://localhost:8000/
```

---

## 📋 What's Implemented

### ✅ Production Features
| Feature | Details |
|---------|---------|
| **LLM Integration** | Azure AI Inference with multi-model/token failover |
| **Input Validation** | Regex-based injection detection, control char filtering |
| **API Security** | Optional API key auth, per-session rate limiting (100 req/hour) |
| **Token Tracking** | Automatic cost calculation & JSONL logging for billing |
| **Observability** | Prometheus metrics (8 types), structured request logging |
| **Error Recovery** | Firmware update detection, intelligent reboot escalation |
| **Session Management** | In-memory store with TTL support, extensible to Redis |
| **State Machine** | Diagnosis → Reboot → Verification → Exit workflow |

### ✅ Code Quality
- 100% type hints (Python 3.11+)
- Full docstrings on all classes/methods
- Comprehensive error handling
- Centralized configuration management
- Modular architecture with clean separation of concerns

---

## 🏗️ Repository Structure

```
.
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template (copy to .env before running)
├── Dockerfile                   # Docker deployment
│
├── src/                         # Core application modules
│   ├── chat_handler.py          # Conversation state machine logic
│   ├── llm_service.py           # LLM API integration & token tracking
│   ├── state_machine.py         # Conversation state definitions
│   ├── manual_service.py        # Router manual data loading
│   ├── logger.py                # Logging configuration
│   │
│   └── Utilities (production infrastructure)
│       ├── config.py                    # Centralized configuration
│       ├── input_validator.py           # Input validation & sanitization
│       ├── api_security.py              # Auth & rate limiting
│       ├── session_store.py             # Session persistence abstraction
│       ├── metrics.py                   # Prometheus metrics instrumentation
│       ├── token_usage_tracker.py       # Cost tracking & billing
│       ├── diagnostic_detector.py       # Pattern detection (firmware, ISP, etc.)
│       ├── request_logging.py           # Request/response logging middleware
│       └── conversation_context.py      # Rich context dataclass
│
├── ui/                          # Frontend
│   └── index.html               # Web chat interface
│
├── docs/                        # Documentation
│   ├── API_DOCUMENTATION.md     # REST API reference with examples
│   ├── DEPLOYMENT.md            # Operations & monitoring guide
│   ├── ARCHITECTURE.md          # System design & decisions
│   └── IMPROVEMENTS.md          # Production upgrades made
│
├── tests/                       # Test suite
│   ├── run_tests.py             # Test runner
│   ├── test_retry_mechanism.py  # Token retry logic tests
│   └── simulate_conversation.py # Conversation simulation
│
├── data/                        # Data files
│   └── ea6350_reboot_instructions.json
│
└── logs/                        # Application logs (auto-created)
    ├── app.log                  # Application logs
    └── token_usage.jsonl        # Token tracking for billing
```

---

## 🚀 API Endpoints

### Create Session
```bash
POST http://localhost:8000/session
# Response: { session_id, state, turn, ... }
```

### Send Message
```bash
POST http://localhost:8000/chat
Header: X-API-Key: optional_key
Body: { session_id, message }
# Response: { session_id, reply, state, turn, is_complete }
```

### Get Session State
```bash
GET http://localhost:8000/session/{session_id}
# Response: { session_id, state, turn, reboot_method, reboot_step }
```

### Health Check
```bash
GET http://localhost:8000/health
```

### Prometheus Metrics
```bash
GET http://localhost:8000/metrics
```

**Full API documentation:** See [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

---

## 🔧 Configuration

### Environment Variables
```bash
# LLM API Configuration (required)
GITHUB_TOKEN_1=your_token_here
MODEL_1=openai/gpt-4o-mini  # Optional, defaults to gpt-4o-mini

# Logging
LOG_LEVEL=INFO              # DEBUG|INFO|WARNING|ERROR

# Rate Limiting
RATE_LIMIT_PER_HOUR=100     # Per-session, rolling window

# Session Management  
SESSION_TTL_HOURS=24        # Session expiration
SESSION_STORE=memory        # memory|redis (Redis requires redis:// URL)

# API Security (optional)
API_KEY=                    # Leave empty for dev mode (no auth required)

# Diagnosis Configuration
MAX_DIAGNOSIS_TURNS=6       # Max questions before forcing reboot decision
```

See `.env.example` for all options.

---

## 💡 How It Works

### Conversation Flow
```
1. User describes WiFi issue
   ↓
2. AI asks diagnostic questions (up to 6 turns)
   → Detects if firmware updating (early exit - don't reboot!)
   → Detects if ISP outage
   → Detects device-specific issues
   ↓
3. AI recommends reboot method based on diagnosis
   → Soft reboot (power cord)
   → Web UI reboot
   → Factory reset (if multiple reboot attempts)
   ↓
4. AI guides through reboot steps
   ↓
5. Post-verification: "Are you back online?"
   ↓
6. Session resolved or retry
```

### Production Addition: Token Tracking
Each LLM call automatically:
- Records tokens used (prompt + completion)
- Calculates cost by model pricing
- Logs to `logs/token_usage.jsonl` for billing
- Alerts on spike (>$1 per call, >$5 per session)

### Production Addition: Metrics
Track via Prometheus:
- LLM call latency (p50, p95, p99)
- Error rates by type
- Chat turns per session
- Resolution success rate
- Active sessions in real-time
- Token usage over time

---

## 🔐 Security Features

### Input Protection
- ✅ SQL injection detection (3 regex patterns)
- ✅ Command injection prevention
- ✅ Control character filtering
- ✅ Message length validation
- ✅ Whitespace normalization

### API Security
- ✅ Optional API key authentication (dev mode if not configured)
- ✅ Per-session rate limiting (rolling 1-hour window)
- ✅ 429 responses with retry timing

### Data Protection
- ✅ Sensitive field redaction in logs (tokens, passwords, keys)
- ✅ Structured logging for audit trails
- ✅ No PII in metrics

---

## 📊 Monitoring

### View Metrics
```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics

# Metrics include:
# - llm_call_duration_seconds (histogram)
# - llm_call_errors_total (counter)
# - chat_turns_total (counter)
# - session_resolved_total (counter)
# - active_sessions (gauge)
# - tokens_used_total (counter)
# - state_transitions_total (counter)
```

### View Token Costs
```bash
# Check token_usage.jsonl for billing records
tail -f logs/token_usage.jsonl

# Example entry:
# {
#   "timestamp": "2024-04-12T10:30:45",
#   "session_id": "abc12345",
#   "model": "openai/gpt-4o-mini",
#   "prompt_tokens": 150,
#   "completion_tokens": 45,
#   "total_tokens": 195,
#   "cost_usd": 0.00385,
#   "state": "DIAGNOSIS"
# }
```

### Deployment with Monitoring
See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for:
- Docker setup with Prometheus/Grafana
- Kubernetes deployment with health probes
- Nginx reverse proxy configuration
- Alert rules for production

---

## 🧪 Testing

### Run Test Suite
```bash
python run_tests.py
```

### Simulate Conversation
```bash
python simulate_conversation.py
```

### Unit Tests
```bash
pytest tests/
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Complete REST API reference with curl examples |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment, monitoring, troubleshooting |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, decision rationale, patterns used |
| [IMPROVEMENTS.md](docs/IMPROVEMENTS.md) | What's new: 11 production-ready features added |

---

## 🎓 Architecture & Design

### Request Pipeline
```
HTTP Request
  ├→ CORSMiddleware
  ├→ RequestLoggingMiddleware (logs with sensitive field redaction)
  ├→ Authorization (API key validation)
  ├→ Rate Limiting (per-session, 100/hour)
  ├→ Input Validation (injection detection, length check)
  ├→ Input Sanitization (normalize whitespace)
  ├→ chat_handler.process()
  │   ├→ State machine routing
  │   ├→ DiagnosticDetector (firmware, ISP, device checks)
  │   └→ llm_service.call_llm()
  │       ├→ LLM API call
  │       ├→ TokenUsageTracker.record() [billing]
  │       └→ MetricsCollector.record_llm_tokens()
  ├→ Metrics Recording (turns, sessions, outcomes)
  └→ HTTPResponse
```

### Key Design Patterns
1. **State Machine** - Clear session lifecycle (DIAGNOSIS → REBOOT → POST_CHECK → EXIT)
2. **Dependency Injection** - Testable, mockable LLM calls
3. **Middleware** - Cross-cutting concerns (logging, validation, security)
4. **ABC Interfaces** - SessionStore abstraction for memory/Redis backends
5. **Context Objects** - ConversationContext reduces re-parsing
6. **Graceful Degradation** - Metrics/logging optional if dependencies missing

---

## 🚀 What's New (Production Upgrades)

### 11 Major Improvements
1. ✅ **Token Usage Tracking** - Cost calculation by model, JSONL logging
2. ✅ **ConversationContext** - Rich metadata, intelligent escalation
3. ✅ **Session Persistence** - In-memory store, extensible to Redis
4. ✅ **Centralized Config** - ConfigManager for env var management
5. ✅ **Input Validation** - Injection detection, control char filtering
6. ✅ **Error Recovery** - Firmware detection, reboot escalation
7. ✅ **Prometheus Metrics** - 8 metrics for observability
8. ✅ **Request Logging** - Structured logs with PII redaction
9. ✅ **API Authentication** - Optional API key + rate limiting
10. ✅ **API Documentation** - 1200+ line comprehensive reference
11. ✅ **Deployment Guide** - Production setup, monitoring, troubleshooting

See [IMPROVEMENTS.md](docs/IMPROVEMENTS.md) for details.

---

## 🛠️ Troubleshooting

### "GITHUB_TOKEN not configured"
```bash
# Solution: Set environment variable
set GITHUB_TOKEN_1=your_token_here
# or add to .env file
```

### "Module not found"
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

### Rate limit exceeded (429)
```
# Per-session limit is 100 requests per hour by default
# Check RATE_LIMIT_PER_HOUR in .env
# Or adjust via environment variable
```

### Prometheus metrics not showing
```bash
# Verify prometheus-client installed:
pip list | grep prometheus

# Check metrics endpoint:
curl http://localhost:8000/metrics
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md#troubleshooting) for more.

---

## 💻 Development

### Installing in Development Mode
```bash
# Install with dev dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio

# Run tests
pytest tests/

# Run with auto-reload
uvicorn main:app --reload
```

### Adding Custom Features
The modular architecture makes it easy:
- Add validators to `input_validator.py`
- Add metrics to `metrics.py`
- Add patterns to `diagnostic_detector.py`
- Add state transitions to `state_machine.py`

---

## 📝 License

This project is part of an interviewer evaluation task.

---

## 📧 Questions?

**For API usage:** See [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)  
**For deployment:** See [DEPLOYMENT.md](docs/DEPLOYMENT.md)  
**For architecture:** See [ARCHITECTURE.md](docs/ARCHITECTURE.md)  

---

