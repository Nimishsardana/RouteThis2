# WiFi Troubleshooter API Documentation

Comprehensive REST API for LLM-powered WiFi troubleshooting with router reboot guidance.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Environment Setup](#environment-setup)
3. [API Endpoints](#api-endpoints)
4. [Authentication](#authentication)
5. [Rate Limiting](#rate-limiting)
6. [Error Handling](#error-handling)
7. [Example Workflows](#example-workflows)
8. [Monitoring & Metrics](#monitoring--metrics)
9. [Deployment](#deployment)

---

## Quick Start

### Prerequisites
- Python 3.11+
- GitHub API token (from https://github.com/settings/tokens)

### Local Development

```bash
# 1. Clone and setup
git clone <repo>
cd wifi-troubleshooter
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add:
#   GITHUB_TOKEN=your_token_here
#   LOG_LEVEL=INFO

# 4. Run server
uvicorn main:app --reload --port 8000

# 5. Open API docs
# Visit http://localhost:8000/docs
```

---

## Environment Setup

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub API token for LLM inference | `ghp_xxxx...` |
| `GITHUB_TOKEN_1`, `GITHUB_TOKEN_2` | Multiple tokens for failover (optional) | `ghp_xxxx...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SESSION_TTL_HOURS` | `24` | Session expiration time in hours |
| `SESSION_STORE` | `memory` | Session storage: `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_DIAGNOSIS_TURNS` | `6` | Max diagnostic questions before recommending reboot |
| `MAX_MESSAGE_LENGTH` | `2000` | Max length of user messages |
| `RATE_LIMIT_PER_HOUR` | `100` | Max requests per session per hour |
| `API_KEY` | (none) | If set, requires `X-API-Key` header on `/chat` endpoint |
| `ENABLE_PROMETHEUS` | `false` | Enable Prometheus metrics at `/metrics` |

### .env Example

```bash
# API Configuration
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN_1=ghp_primary_token_xxxx
GITHUB_TOKEN_2=ghp_backup_token_yyyy

# Logging
LOG_LEVEL=INFO

# Session Management
SESSION_TTL_HOURS=24
SESSION_STORE=memory
# REDIS_URL=redis://localhost:6379/0  # Uncomment for Redis

# Troubleshooting Behavior
MAX_DIAGNOSIS_TURNS=6

# Security
MAX_MESSAGE_LENGTH=2000
RATE_LIMIT_PER_HOUR=100
API_KEY=your_secret_api_key_here  # Optional

# Monitoring
ENABLE_PROMETHEUS=true
```

---

## API Endpoints

### 1. Create New Session (`POST /session`)

Start a new troubleshooting session.

**Request:**
```bash
curl -X POST http://localhost:8000/session
```

**Response (200):**
```json
{
  "session_id": "a1b2c3d4",
  "state": "DIAGNOSIS",
  "turn": 0
}
```

**Example with cURL:**
```bash
SESSION_ID=$(curl -s -X POST http://localhost:8000/session | jq -r '.session_id')
echo "Session ID: $SESSION_ID"
```

---

### 2. Send Chat Message (`POST /chat`)

Send a user message and receive assistant reply.

**Headers:**
- `X-API-Key` (optional, required if `API_KEY` env var is set)
- `Content-Type: application/json`

**Request Body:**
```json
{
  "session_id": "a1b2c3d4",
  "message": "My internet is super slow right now"
}
```

**Response (200):**
```json
{
  "session_id": "a1b2c3d4",
  "reply": "I understand how frustrating slow internet can be! Let me help you diagnose and fix this.\n\nFirst, I have a few quick questions:\n1. Do you think the slowness is affecting all your devices, or just one specific device?",
  "state": "DIAGNOSIS",
  "turn": 1,
  "is_complete": false
}
```

**Example with cURL:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{
    "session_id": "a1b2c3d4",
    "message": "My WiFi is not working at all"
  }'
```

**Error Responses:**

- **400 Bad Request:** Invalid message (too long, contains control chars, etc.)
  ```json
  {"detail": "Message exceeds maximum length of 2000 characters."}
  ```

- **401 Unauthorized:** Invalid/missing API key
  ```json
  {"detail": "Invalid or missing API key"}
  ```

- **404 Not Found:** Session doesn't exist
  ```json
  {"detail": "Session not found. Start a new session at POST /session"}
  ```

- **429 Too Many Requests:** Rate limit exceeded
  ```json
  {"detail": "Rate limit exceeded. Max 100 requests per hour. Try again in 3245 seconds."}
  ```

- **500 Internal Server Error:** LLM call failed or other error
  ```json
  {"detail": "An error occurred processing your message"}
  ```

---

### 3. Get Session State (`GET /session/{session_id}`)

Retrieve current state of a session.

**Request:**
```bash
curl http://localhost:8000/session/a1b2c3d4
```

**Response (200):**
```json
{
  "session_id": "a1b2c3d4",
  "state": "REBOOT_GUIDE",
  "turn": 5,
  "reboot_method": "soft_reboot",
  "reboot_step": 2
}
```

---

### 4. Health Check (`GET /health`)

Simple health check endpoint.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response (200):**
```json
{
  "status": "ok",
  "service": "wifi-troubleshooter"
}
```

---

### 5. Prometheus Metrics (`GET /metrics`)

Expose metrics for Prometheus scraping (requires `ENABLE_PROMETHEUS=true`).

**Request:**
```bash
curl http://localhost:8000/metrics
```

**Response (200):**
```
# HELP llm_call_duration_seconds Duration of LLM API calls in seconds
# TYPE llm_call_duration_seconds histogram
llm_call_duration_seconds_bucket{le="0.1",model="openai/gpt-4o-mini",state="DIAGNOSIS"} 5.0
llm_call_duration_seconds_bucket{le="0.5",model="openai/gpt-4o-mini",state="DIAGNOSIS"} 12.0
...
```

---

## Authentication

### API Key (Optional)

If `API_KEY` environment variable is set, all `/chat` requests require validation.

**With API Key:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "a1b2c3d4", "message": "..."}'
```

**Without API Key (development mode):**
```bash
# If API_KEY is not set in environment, any/no header is accepted
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "a1b2c3d4", "message": "..."}'
```

---

## Rate Limiting

### Per-Session Limits

- **Default:** 100 requests/hour per session
- **Configurable:** Set `RATE_LIMIT_PER_HOUR` environment variable

**Behavior:**
- Requests are tracked per `session_id`
- Rate window is rolling 1-hour
- Exceeding limit returns `429 Too Many Requests`

**Example:**
```bash
# First 100 requests succeed
for i in {1..100}; do
  curl -X POST http://localhost:8000/chat \
    -d '{"session_id": "s1", "message": "message $i"}'
done

# 101st request fails
curl -X POST http://localhost:8000/chat \
  -d '{"session_id": "s1", "message": "message 101"}'
# Response: 429 Too Many Requests
# Detail: "Rate limit exceeded. Max 100 requests per hour."
```

---

## Error Handling

### Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | Success | Chat response received |
| 400 | Bad Request | Invalid message format |
| 401 | Unauthorized | Missing/invalid API key |
| 404 | Not Found | Session doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | LLM API failure |

### Retry Strategy

**Recommended Client Behavior:**

```python
import requests
import time

MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5

for attempt in range(MAX_RETRIES):
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"session_id": "s1", "message": "..."},
            headers={"X-API-Key": "key"},
            timeout=30
        )
        
        if response.status_code == 200:
            print(response.json())
            break
        elif response.status_code == 429:
            # Rate limited - wait and retry
            wait_time = BACKOFF_FACTOR * (2 ** attempt)
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"Error: {response.status_code} {response.text}")
            break
    except requests.exceptions.Timeout:
        print("Timeout - retrying...")
        time.sleep(BACKOFF_FACTOR * (2 ** attempt))
```

---

## Example Workflows

### Scenario 1: Successful Resolution

```bash
# Step 1: Create session
SESSION=$(curl -s -X POST http://localhost:8000/session | jq -r '.session_id')
echo "Session: $SESSION"

# Step 2: Diagnostic questions
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"My WiFi isn't working at all\"
  }" | jq '.reply'

# Step 3: User responses
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"All my devices lost connection\"
  }" | jq '.reply'

# Step 4: Reboot steps
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"OK, I've done that\"
  }" | jq '.reply'

# Step 5: Check resolution
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"Yes! WiFi is working again\"
  }" | jq '.{reply, state, is_complete}'
```

### Scenario 2: Reboot Not Appropriate

```bash
# Device-specific issue
SESSION=$(curl -s -X POST http://localhost:8000/session | jq -r '.session_id')

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"Only my phone can't connect\"
  }" | jq '.reply'

# Response suggests checking device settings instead of rebooting router
```

### Scenario 3: Firmware Update

```bash
SESSION=$(curl -s -X POST http://localhost:8000/session | jq -r '.session_id')

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION\",
    \"message\": \"The power light is blinking slowly\"
  }" | jq '.reply'

# Response: "I see you may be in the middle of a firmware update..."
```

---

## Monitoring & Metrics

### Prometheus Metrics Available

Enable with `ENABLE_PROMETHEUS=true`:

```
llm_call_duration_seconds       # LLM API call latency
llm_call_errors_total           # LLM API error count
chat_turns_total                # Total chat turns
session_resolved_total          # Sessions with resolved issues
session_not_resolved_total      # Sessions without resolution
active_sessions                 # Current active sessions (gauge)
tokens_used_total               # Total tokens consumed
state_transitions_total         # State transition counts
```

### Token Usage Tracking

Token usage is logged to `logs/token_usage.jsonl` (one JSON per line):

```json
{"timestamp": "2026-04-12T10:30:45.123456", "session_id": "a1b2c3d4", "model": "openai/gpt-4o-mini", "prompt_tokens": 450, "completion_tokens": 120, "total_tokens": 570, "estimated_cost_usd": 0.00123, "state": "DIAGNOSIS"}
```

### Application Logs

Located in `logs/app.log` with rotation (5MB max, 3 backups):

```
2026-04-12 10:30:45 | INFO     | llm_service          | LLM call | token=1 | model=openai/gpt-4o-mini | attempt=1/2 | messages=4 | max_tokens=400
2026-04-12 10:30:46 | INFO     | chat_handler         | [a1b2c3d4] State transition: DIAGNOSIS → REBOOT_GUIDE
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV LOG_LEVEL=INFO
ENV SESSION_STORE=redis

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Run:**
```bash
docker build -t wifi-troubleshooter .
docker run -p 8000:8000 \
  -e GITHUB_TOKEN=your_token \
  -e REDIS_URL=redis://redis:6379/0 \
  wifi-troubleshooter
```

### Production Checklist

- [ ] Set `API_KEY` environment variable
- [ ] Use `SESSION_STORE=redis` with Redis backend
- [ ] Configure `MAX_DIAGNOSIS_TURNS`, `MAX_MESSAGE_LENGTH` appropriately
- [ ] Enable Prometheus metrics (`ENABLE_PROMETHEUS=true`)
- [ ] Configure rate limiting (`RATE_LIMIT_PER_HOUR`)
- [ ] Use proper HTTPS (via reverse proxy like Nginx)
- [ ] Harden CORS (set `allow_origins` to specific domains)
- [ ] Monitor logs and metrics
- [ ] Set up log aggregation (ELK, Splunk, DataDog)
- [ ] Configure alerting on error rates and latency

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wifi-troubleshooter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: wifi-troubleshooter
  template:
    metadata:
      labels:
        app: wifi-troubleshooter
    spec:
      containers:
      - name: app
        image: wifi-troubleshooter:latest
        ports:
        - containerPort: 8000
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: github-token
        - name: SESSION_STORE
          value: "redis"
        - name: REDIS_URL
          value: "redis://redis:6379/0"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## Support

- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Alternative Docs:** http://localhost:8000/redoc (ReDoc)
- **GitHub:** [repository URL]
- **Issues:** [GitHub Issues]
