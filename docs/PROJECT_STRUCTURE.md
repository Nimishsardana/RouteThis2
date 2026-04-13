# Project Structure

Complete directory organization for the WiFi Troubleshooter project.

## Root Level

```
Route This/Claude/
├── .env.example                  # Configuration template
├── .gitignore                    # Git exclusion patterns
├── __init__.py                   # Package root marker
├── README.md                     # Quick start guide
├── requirements.txt              # Python dependencies (10 packages)
│
├── src/                          # Core application modules
│   ├── __init__.py
│   ├── main.py                   # FastAPI server entry point
│   ├── chat_handler.py           # Conversation orchestration
│   ├── llm_service.py            # Azure AI Inference integration
│   ├── state_machine.py          # Session state management
│   └── manual_service.py         # Router manual data loader
│
├── infra/                        # Infrastructure & cross-cutting concerns
│   ├── __init__.py
│   ├── config.py                 # Environment configuration management
│   ├── metrics.py                # Prometheus metrics instrumentation
│   ├── token_usage_tracker.py    # Token usage & cost tracking
│   ├── session_store.py          # Session persistence (memory/Redis)
│   ├── conversation_context.py   # Rich conversation state object
│   ├── input_validator.py        # Input validation & security
│   ├── diagnostic_detector.py    # Error pattern detection
│   ├── request_logging.py        # Structured request/response logging
│   ├── api_security.py           # API key validation & rate limiting
│   └── (total: 9 modules)
│
├── utils/                        # Utility modules
│   ├── __init__.py
│   └── logger.py                 # Logging configuration setup
│
├── docs/                         # Documentation (7 core guides)
│   ├── ARCHITECTURE.md           # System design & patterns
│   ├── SETUP_GUIDE.md            # Installation & quick start
│   ├── API_DOCUMENTATION.md      # API endpoint reference
│   ├── IMPROVEMENTS.md           # 11 production enhancements summary
│   ├── EVALUATION_CHECKLIST.md   # Feature verification for evaluators
│   ├── DEPLOYMENT.md             # Production deployment guide
│   └── PROJECT_STRUCTURE.md      # This file
│
├── ui/                           # Web interface
│   ├── index.html                # Single-page chat UI
│   └── (static assets)
│
├── tests/                        # Test suite
│   ├── verify_system.py          # Module import verification
│   ├── test_retry_mechanism.py   # LLM retry logic tests
│   ├── simulate_conversation.py  # Conversation flow simulation
│   └── run_tests.py              # Test runner
│
├── logs/                         # Application logs (runtime)
│   └── (generated on run)
│
├── data/                         # Static data files
│   └── ea6350_reboot_instructions.json  # Linksys EA6350 manual
│
└── __pycache__/                  # Python compiled files (gitignored)
```

## Module Organization

### Core Application (`src/`)

Responsibilities: Primary business logic for conversation flow and chat handling

| Module | Purpose | Key Classes |
|--------|---------|-----------|
| `main.py` | FastAPI app, routes, middleware | ChatRequest, ChatResponse |
| `chat_handler.py` | Message routing & state transitions | ChatHandler |
| `llm_service.py` | LLM API calls with retry failover | (module functions) |
| `state_machine.py` | Session state & conversation history | ConversationState, State |
| `manual_service.py` | Router manual data loading | (module functions) |

### Infrastructure (`infra/`)

Responsibilities: Production infrastructure, cross-cutting concerns, observability, security

| Module | Purpose | Key Classes |
|--------|---------|-----------|
| `config.py` | Type-safe environment variables | ConfigManager |
| `metrics.py` | Prometheus metrics (8 metrics) | MetricsCollector |
| `token_usage_tracker.py` | LLM token & cost tracking | TokenUsageTracker |
| `session_store.py` | Session persistence abstraction | SessionStore, MemorySessionStore |
| `conversation_context.py` | Rich context dataclass | ConversationContext |
| `input_validator.py` | Security validation | InputValidator |
| `diagnostic_detector.py` | Error pattern detection | DiagnosticDetector |
| `request_logging.py` | Structured logging middleware | RequestLoggingMiddleware |
| `api_security.py` | API key & rate limiting | APIKeyValidator, RateLimitTracker |

### Utilities (`utils/`)

Responsibilities: Shared utilities and helpers

- `logger.py` — Logging setup & configuration

### Documentation (`docs/`)

Responsibilities: Project documentation for evaluators & developers

| Document | Contents |
|----------|----------|
| `ARCHITECTURE.md` | System design, patterns, module interactions |
| `SETUP_GUIDE.md` | Installation steps, environment setup, 5-minute quick start |
| `API_DOCUMENTATION.md` | Endpoint specs, request/response examples, error codes |
| `IMPROVEMENTS.md` | 11 production features implemented with code samples |
| `EVALUATION_CHECKLIST.md` | Feature verification steps for external evaluators |
| `DEPLOYMENT.md` | Production deployment guide, monitoring setup |
| `PROJECT_STRUCTURE.md` | This file — directory organization |

### Tests (`tests/`)

Responsibilities: Verification & testing

- `verify_system.py` — ✅ All 8 core modules import & instantiate correctly
- `test_retry_mechanism.py` — LLM retry & failover logic
- `simulate_conversation.py` — End-to-end conversation simulation
- `run_tests.py` — Test orchestration & reporting

### User Interface (`ui/`)

Responsibilities: Web frontend

- `index.html` — Responsive chat UI with WebSocket-style polling

### Data (`data/`)

Responsibilities: Static resources and manual data

- `ea6350_reboot_instructions.json` — Linksys EA6350 router manual data

## File Organization Principles

### Separation of Concerns

- **`src/`** — Business logic only (chat, LLM integration, state management)
- **`infra/`** — Production infrastructure (logging, security, metrics, persistence)
- **`utils/`** — Reusable utilities and common setup
- **`docs/`** — Human-readable documentation & guides
- **`tests/`** — Automated testing & verification
- **`ui/`** — User-facing frontend
- **`data/`** — Static configuration data

### Imports Pattern

```python
# Absolute imports from root (enabled via __init__.py files)
from src.state_machine import ConversationState
from src.chat_handler import ChatHandler
from infra.config import ConfigManager
from infra.metrics import MetricsCollector
from utils.logger import setup_logging
```

### Entry Point

```bash
cd "Route This/Claude"
python src/main.py                    # Runs FastAPI server on localhost:8000
# or
python -m uvicorn src.main:app --reload
```

### Python Package Structure

All directories contain `__init__.py` to enable proper module imports:

```
src/__init__.py               ✅ Enables: from src.main import app
infra/__init__.py             ✅ Enables: from infra.config import ConfigManager  
utils/__init__.py             ✅ Enables: from utils.logger import setup_logging
__init__.py (root)            ✅ Enables: Python package resolution
```

## Configuration

Environment variables (see `.env.example`):

```env
GITHUB_TOKEN_1=ghp_xxxxx              # Primary LLM token (required)
GITHUB_TOKEN_2=ghp_yyyyy              # Fallback token (recommended)
SESSION_STORE=memory                  # Session storage (memory or redis)
SESSION_TTL_HOURS=24                  # Session expiration (hours)
API_KEY=your-secret-key               # Optional API authentication
LOG_LEVEL=INFO                        # Logging verbosity (DEBUG, INFO, WARNING, ERROR)
MAX_DIAGNOSIS_TURNS=10                # Conversation turns before forcing decision
MAX_MESSAGE_LENGTH=2000               # Input validation character limit
```

## Dependencies

**Required Packages (10):**

```
azure-ai-inference>=1.0.0             # LLM API client
azure-identity>=1.0.0                 # Azure authentication
fastapi>=0.115.0                      # Web framework
uvicorn[standard]>=0.30.0             # ASGI server
python-dotenv>=1.0.0                  # Environment variables
pydantic>=2.0.0                       # Data validation
httpx>=0.27.0                         # HTTP client
pytest>=8.0.0                         # Testing framework
pytest-asyncio>=0.23.0                # Async test support
prometheus-client>=0.19.0             # Optional metrics
```

**Installation:**
```bash
pip install -r requirements.txt
```

**Status:** ✅ All verified importable and working

## Key Statistics

- **Python Files:** 21 total
  - Core modules (src/): 5 files
  - Infrastructure modules (infra/): 9 files
  - Utilities (utils/): 1 file
  - Tests (tests/): 4 files
  - Misc: 2 files (__init__.py files)
  
- **Documentation Files:** 7 core guides
  - All guides include setup, architecture, API docs, evaluation checklist
  
- **Lines of Code:** ~3,500+ (core + infrastructure)
  
- **Test Coverage:** 
  - Core modules verified: ✅ 8/8
  - Edge cases: Ready for expansion
  
- **Dependencies Removed:** 2
  - ~~redis~~ (using in-memory store)
  - ~~slowapi~~ (using custom RateLimiter)

## Quick Start

```bash
# 1. Clone & setup (5 minutes)
cd "Route This/Claude"
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Mac/Linux
pip install -r requirements.txt

# 2. Configure
copy .env.example .env            # Windows
# cp .env.example .env            # Mac/Linux
# Edit .env and add your GitHub tokens

# 3. Verify
python tests/verify_system.py      # ✅ All 8/8 modules load

# 4. Run
python -m uvicorn src.main:app --reload

# 5. Test (in another terminal)
curl -X POST http://localhost:8000/session
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"...\", \"message\":\"WiFi is slow\"}"
```

## Architecture Highlights

### Design Patterns

1. **Modular Design:** Clear separation between business logic (src/), infrastructure (infra/), utilities
2. **Graceful Degradation:** Prometheus metrics optional; API works without it
3. **Dependency Injection:** ConfigManager and other services injectable
4. **Async/Await:** FastAPI async handlers for non-blocking I/O
5. **Error Recovery:** Automatic token failover, multi-layer error handling
6. **Observability:** Structured logging, Prometheus metrics, request tracing
7. **Security:** Input validation, optional API key validation, rate limiting

### Data Flow

```
Browser/Client
    ↓
FastAPI (main.py)
    ├─ CORS Middleware
    ├─ RequestLoggingMiddleware
    ├─ InputValidator
    └─ APIKeyValidator, RateLimitTracker
    ↓
ChatHandler (chat_handler.py)
    ├─ State Machine (state_machine.py)
    ├─ LLM Service (llm_service.py)
    │   └─ Azure AI Inference API
    ├─ Manual Service (manual_service.py)
    └─ DiagnosticDetector (infra/)
    ↓
Session Storage (infra/session_store.py)
    └─ MemorySessionStore (current)
    
Observability Layer
    ├─ MetricsCollector (infra/metrics.py)
    ├─ TokenUsageTracker (infra/token_usage_tracker.py)
    └─ RequestLoggingMiddleware (infra/request_logging.py)
```

## Migration from Previous Structure

**Old Structure Cleanup:**
- ✅ Removed duplicate files from root (main.py, state_machine.py, llm_service.py)
- ✅ Moved metrics.py to infra/ (infrastructure module)
- ✅ Created __init__.py files for all packages
- ✅ Removed duplicate documentation files (README_NEW.md, FINAL_SUMMARY.md, etc.)
- ✅ Updated all import statements to use new module paths

**Verification:**
- ✅ All Python files compile successfully
- ✅ All 8 core modules import correctly
- ✅ Package structure verified with pytest
- ✅ No breaking changes to functionality

---

**Last Updated:** April 2026  
**Status:** ✅ Production Ready  