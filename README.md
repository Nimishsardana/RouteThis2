# WiFi Troubleshooter - Enterprise-Grade LLM Chatbot

> A production-ready FastAPI chatbot that diagnoses and resolves WiFi issues using AI, with enterprise security, observability, and reliability features.

**⏱️ Time to First Run:** 5 minutes | **📝 Language:** Python 3.11+ | **✅ Status:** Production-Ready

---

## 🎯 Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd "Route This/Claude"
python -m venv .venv
.venv\Scripts\activate                    # Windows
# source .venv/bin/activate              # macOS/Linux

# 2. Install and configure
pip install -r requirements.txt
copy .env.example .env                    # Add GITHUB_TOKEN_1=your_token

# 3. Run
uvicorn main:app --reload

# 4. Open browser
# http://localhost:8000/
```

✅ That's it! Chat interface is ready.

See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for detailed setup instructions.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  User Interface                  │
│         CLI (cli.py) │ Web UI (ui/index.html)    │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│              FastAPI Server (main.py)            │
│         POST /chat │ POST /session │ GET /health  │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│            Chat Handler (flows/chat_handler.py)  │
│                 State Machine Router             │
└──────┬──────────────────┬──────────────────┬────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼──────┐  ┌───────▼──────┐
│ State Machine│  │  LLM Service  │  │Manual Service │
│(state_machine│  │(llm_service.py│  │(manual_service│
│    .py)      │  │)              │  │    .py)       │
└─────────────┘  └───────┬───────┘  └───────┬───────┘
                         │                  │
                   Claude API        data/ea6350_
                                     reboot_instructions
                                          .json
```

### State Machine

```
DIAGNOSIS ──[reboot_appropriate]──► REBOOT_GUIDE ──[all steps done]──► POST_CHECK
    │                                                                        │
    │[reboot_not_appropriate]                            [resolved/not]      │
    ▼                                                                        ▼
  EXIT ◄───────────────────────────────────────────────────────────────── EXIT
```

---

## Directory Structure

```
wifi-troubleshooter/
├── main.py                          # FastAPI server
├── cli.py                           # CLI interface
├── run_tests.py                     # Standalone test runner (no pytest needed)
├── requirements.txt
├── Dockerfile
├── .env.example
│
├── src/
│   ├── flows/
│   │   ├── state_machine.py         # State enum + ConversationState dataclass
│   │   └── chat_handler.py          # Main orchestration logic
│   ├── services/
│   │   ├── llm_service.py           # Claude API calls + prompt construction
│   │   └── manual_service.py        # PDF data loader + retrieval
│   └── utils/
│       └── logger.py                # Rotating file + console logging
│
├── data/
│   └── ea6350_reboot_instructions.json   # Extracted from official PDF
│
├── ui/
│   └── index.html                   # Single-file web chat UI
│
├── tests/
│   └── test_wifi_troubleshooter.py  # pytest-compatible tests
│
└── logs/
    └── app.log                      # Runtime logs (auto-created)
```

---

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### 2. Clone / Set up the project
```bash
git clone <your-repo-url>
cd wifi-troubleshooter
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

### 5. Run the tests (no API key needed)
```bash
python run_tests.py
# Expected: 46/46 passed
```

### 6a. Start the web server
```bash
uvicorn main:app --reload --port 8000
# Open http://localhost:8000 in your browser
# API docs at http://localhost:8000/docs
```

### 6b. Use the CLI instead
```bash
python cli.py
```

### 7. Docker (optional)
```bash
docker build -t wifi-troubleshooter .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your_key wifi-troubleshooter
```

---

## Example `.env`

```env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
MAX_CONVERSATION_TURNS=30
```

---

## How PDF Grounding is Enforced

**The core guarantee:** The LLM can never fabricate reboot steps.

1. **Pre-extraction**: Reboot steps from the Linksys EA6350 PDF are stored in `data/ea6350_reboot_instructions.json` as a structured knowledge base.

2. **Step injection**: In `_deliver_reboot_step()`, the chat handler fetches each step directly from `manual_service.get_reboot_step()` and *injects the exact text* into the LLM prompt. The LLM's job is only to present this text warmly — not to recall or generate steps.

3. **Prompt guardrails**: The reboot system prompt includes:
   > *"CRITICAL RULE: You MUST ONLY use reboot steps from the official Linksys EA6350 manual below. Do NOT add, modify, or invent any steps."*

4. **Validated by tests**: `ch11` asserts that the `step_text` argument passed to the LLM mock equals `get_reboot_step("soft_reboot", 0)` exactly — catching any drift between the data source and what the LLM receives.

5. **No LLM path to step generation**: There is no code path where the LLM is asked "what are the steps to reboot a router?" — the question is never asked.

---

## Sample Conversation Transcript

```
🤖 Hi! I'm your WiFi troubleshooting assistant.
   To start, can you describe what's happening with your WiFi?

👤 My internet keeps dropping every few minutes on all my devices.

🤖 I'm sorry to hear that! To help diagnose this — how long has
   this been happening, and do you notice the router's power light
   changing when it drops?

👤 Started yesterday. The power light looks solid white but the
   internet light sometimes turns amber.

🤖 Got it. That amber internet light suggests the router is losing
   its upstream connection. This is a classic sign that a router
   reboot may help restore a clean connection with your ISP.

   Let's go through the reboot process using the official Linksys
   EA6350 guide. There are 5 steps — I'll walk you through each one.

   Step 1 of 5: Unplug the router's power cord from the electrical
   outlet or power strip.

   Please let me know when you've done that!

👤 Done.

🤖 Step 2 of 5: Wait 10 seconds before plugging the power cord
   back in.

   Take your time!

👤 OK waited.

🤖 Step 3 of 5: Plug the power cord back into the electrical outlet.

👤 Plugged in.

🤖 Step 4 of 5: Wait for the router to fully restart. The power
   light will be solid when the router is ready (approximately
   1-2 minutes).

👤 Power light is solid white now.

🤖 Step 5 of 5: Check if your devices can connect to WiFi and if
   internet access has been restored.

   Let me know what you find!

👤 Yes! Everything is working now. Internet light is white too.

🤖 That's wonderful news! The power cycle cleared whatever was
   causing the connection to drop.

   You're all set! If the drops happen again in the future, a
   quick power cycle is a great first step. Have a great day! 🎉
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web chat UI |
| `/health` | GET | Health check |
| `/session` | POST | Start a new session |
| `/chat` | POST | Send a message |
| `/session/{id}` | GET | Get session state |
| `/docs` | GET | Interactive API docs |

### POST /chat
```json
// Request
{ "session_id": "abc12345", "message": "My internet is down" }

// Response
{
  "session_id": "abc12345",
  "reply": "I'm sorry to hear that...",
  "state": "DIAGNOSIS",
  "turn": 1,
  "is_complete": false
}
```

---

## Logging

Logs are written to both console and `logs/app.log` (rotating, 5MB max).

Each log line includes timestamp, level, module, and message:
```
2025-01-15 14:23:01 | INFO     | src.flows.state_machine       | [abc123] State transition: DIAGNOSIS → REBOOT_GUIDE
2025-01-15 14:23:01 | INFO     | src.services.manual_service   | Loaded router manual: Linksys EA6350
2025-01-15 14:23:01 | DEBUG    | src.services.llm_service      | LLM call | model=claude-sonnet-4 | messages=6
```
