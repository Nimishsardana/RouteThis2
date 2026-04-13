# SETUP GUIDE - For Project Evaluators

**Time to First Run:** ~5 minutes  
**Difficulty:** Beginner-friendly

This guide walks you through getting the WiFi Troubleshooter running on your machine.

---

## ✅ Prerequisites

Before starting, ensure you have:
- Python 3.11+ installed
  ```bash
  python --version  # Should show 3.11.0 or higher
  ```
- Git (to clone this repo)
- A terminal/command prompt
- ~500MB disk space for dependencies

---

## 🚀 Step-by-Step Setup

### Step 1: Clone the Repository
```bash
git clone <repository-url>
cd "Route This/Claude"
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` at the start of your terminal line.

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- Uvicorn (server)
- Azure AI Inference (LLM)
- Prometheus Client (metrics)
- And more...

### Step 4: Create Environment File
```bash
# Copy the example
copy .env.example .env    # Windows
cp .env.example .env      # macOS/Linux

# Edit in your favorite editor and add:
# GITHUB_TOKEN_1=your_token_here
```

⚠️ **Important:** You need a GitHub personal access token. Get one at:
https://github.com/settings/tokens

The token needs `repo:read` scope (for GitHub Models API).

### Step 5: Run the Server
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

✅ Server is running!

### Step 6: Test It

**In a new terminal:**

```bash
# Health check
curl http://localhost:8000/health

# View API docs (open in browser)
http://localhost:8000/docs

# Create a session
curl -X POST http://localhost:8000/session

# Or open web UI
http://localhost:8000/
```

---

## 🌐 Web Interface

Open your browser to **http://localhost:8000/**

You should see:
1. Text box: "Describe your WiFi issue"
2. Chat conversation area
3. Reboot instructions when provided

Try typing: "My WiFi is not connecting"

---

## 🔍 What to Look At

### 1. Main Application Code
- **main.py** - FastAPI routes and middleware setup
- **chat_handler.py** - Conversation logic
- **state_machine.py** - Conversation states

### 2. Production Features (in `src/` conceptually, currently at root)
- **input_validator.py** - Input validation
- **api_security.py** - Rate limiting
- **metrics.py** - Prometheus metrics
- **token_usage_tracker.py** - Cost tracking
- **diagnostic_detector.py** - Smart detection

### 3. Documentation
- **docs/API_DOCUMENTATION.md** - API reference
- **docs/DEPLOYMENT.md** - Production guide
- **docs/ARCHITECTURE.md** - System design
- **docs/IMPROVEMENTS.md** - What's new

### 4. Testing
- **tests/run_tests.py** - Run the test suite
- **tests/simulate_conversation.py** - Test conversations

---

## 📋 Viewing API Documentation

### Interactive Swagger UI
```
http://localhost:8000/docs
```

Features:
- Try it out button (send real requests)
- Request/response examples
- Parameter documentation

### Endpoints

**POST /session**
- Create a new troubleshooting session
- Returns: session_id, opening message

**POST /chat**
- Send a user message
- Body: { "session_id": "...", "message": "..." }
- Returns: reply, state, turn, is_complete

**GET /session/{session_id}**
- Get current session state
- Returns: state, turn, reboot_method

**GET /health**
- Health check
- Returns: { "status": "ok" }

**GET /metrics**
- Prometheus metrics
- For monitoring systems

---

## 🔧 Configuration

All settings in `.env`:

```bash
# Required: Your LLM token
GITHUB_TOKEN_1=your_token_here

# Optional: Different model
MODEL_1=openai/gpt-4o-mini

# Optional: Debug logging
LOG_LEVEL=DEBUG

# Optional: API key authentication
API_KEY=my_secret_key

# Optional: Rate limiting
RATE_LIMIT_PER_HOUR=100
```

No restart needed - changes take effect on next request.

---

## 🧪 Testing the System

### Run Basic Tests
```bash
python run_tests.py
```

### Simulate a Full Conversation
```bash
python simulate_conversation.py
```

Expected output:
- Series of user messages
- AI responses
- State transitions
- Final resolution status

### Test API with curl

```bash
# 1. Create session
SESSION_ID=$(curl -s -X POST http://localhost:8000/session | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)

# 2. Send message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\", \"message\":\"My WiFi stopped working\"}"

# 3. Check metrics
curl http://localhost:8000/metrics | head -20
```

---

## 📊 Monitoring

### View Metrics
```bash
curl http://localhost:8000/metrics
```

Shows real-time:
- Chat turns processed
- Active sessions
- Token usage
- Error counts
- Latency

### View Logs
```bash
# Application logs
tail -f logs/app.log

# Token tracking (for billing)
tail -f logs/token_usage.jsonl
```

---

## ❌ Troubleshooting

### "Module not found"
```bash
# Solution: Reinstall dependencies
pip install -r requirements.txt
```

### "GITHUB_TOKEN not configured"
```bash
# Solution: Set in .env
GITHUB_TOKEN_1=your_token_here

# Or as environment variable
export GITHUB_TOKEN_1=your_token_here
```

### "Port 8000 already in use"
```bash
# Solution: Use different port
uvicorn main:app --reload --port 8001
```

### "Connection refused"
```bash
# Make sure server is running:
uvicorn main:app --reload
# Should show "Uvicorn running on http://127.0.0.1:8000"
```

### LLM API Errors
```bash
# Check token is valid
# Check Azure AI Inference is accessible
# Check network connection
# Check .env has GITHUB_TOKEN_1 set
```

See [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md#troubleshooting) for more.

---

## 🎯 What to Evaluate

### Code Quality
- ✅ Type hints (Python 3.11+)
- ✅ Docstrings on all classes
- ✅ Error handling, logging
- ✅ Clean architecture, modularity

### Production Features
- ✅ Input validation (security)
- ✅ Rate limiting
- ✅ Token tracking (billing)
- ✅ Prometheus metrics (observability)
- ✅ Request logging with PII redaction

### Architecture
- ✅ State machine design
- ✅ Middleware pattern
- ✅ Dependency injection
- ✅ Abstract interfaces
- ✅ Graceful degradation

### Documentation
- ✅ README with quick start
- ✅ API documentation
- ✅ Architecture design doc
- ✅ Deployment guide
- ✅ Setup instructions

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| README.md | Project overview & quick start |
| docs/API_DOCUMENTATION.md | REST API reference |
| docs/DEPLOYMENT.md | Production deployment guide |
| docs/ARCHITECTURE.md | System design & patterns |
| docs/IMPROVEMENTS.md | Production features added |
| SETUP_GUIDE.md | This file - getting started |

---

## ⏱️ Expected Timeline

| Time | Activity |
|------|----------|
| 0-1 min | Read this file |
| 1-2 min | Clone repo, setup venv |
| 2-4 min | Install dependencies, configure .env |
| 4-5 min | Run server, test web interface |
| 5+ min | Explore code, read documentation |

---

## 🚀 Next Steps

### To Understand the Code
1. Read [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) (10 min)
2. Look at `main.py` (entry point)
3. Look at `chat_handler.py` (core logic)
4. Look at `state_machine.py` (conversation flow)

### To See Production Features
1. Read [docs/IMPROVEMENTS.md](../docs/IMPROVEMENTS.md) (15 min)
2. Look at `token_usage_tracker.py` (cost tracking)
3. Look at `input_validator.py` (security)
4. Look at `metrics.py` (observability)

### To Deploy Elsewhere
1. Read [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md) (20 min)
2. Try Docker: `docker build -t wifi-troubleshooter . && docker run -p 8000:8000 wifi-troubleshooter`
3. Try Kubernetes using manifests in docs/

### To Extend
1. Add validation: `input_validator.py`
2. Add metrics: `metrics.py`
3. Add patterns: `diagnostic_detector.py`
4. Add states: `state_machine.py`

---

## ✅ Verification Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed (`pip install` completes)
- [ ] .env file created with GITHUB_TOKEN_1
- [ ] Server starts (`uvicorn main:app` runs)
- [ ] Health check passes (`curl /health` returns ok)
- [ ] Web UI loads (`localhost:8000/` displays chat)
- [ ] Chat works (can type messages, get responses)
- [ ] Metrics available (`curl /metrics` shows data)
- [ ] All documentation readable

---

## 🎓 Learning Resources

- **FastAPI:** https://fastapi.tiangolo.com/
- **Azure AI Inference:** https://github.com/Azure/azure-sdk-for-python
- **Prometheus:** https://prometheus.io/docs/
- **Python Type Hints:** https://docs.python.org/3/library/typing.html

---

## 📞 Questions?

1. Check documentation in `/docs`
2. Look at relevant Python file (well-commented)
3. Check error message in logs
4. Try troubleshooting guide above

---

**You're ready to evaluate!**

Start with the web interface, then explore the codebase.

Have fun! 🎉
