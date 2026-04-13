# Deployment & Operations Guide

## Table of Contents
1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [Production Setup](#production-setup)
4. [Monitoring Setup](#monitoring-setup)
5. [Troubleshooting](#troubleshooting)
6. [Performance Tuning](#performance-tuning)

---

## Local Development

### Setup

```bash
# 1. Clone repository
git clone https://github.com/yourorg/wifi-troubleshooter.git
cd wifi-troubleshooter

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Run development server
uvicorn main:app --reload --port 8000

# 6. Test endpoints
curl -X POST http://localhost:8000/session
curl http://localhost:8000/docs  # Swagger UI
```

### Development Features

- Auto-reload on code changes (--reload flag)
- Structured logging to console + file
- In-memory session store (no Redis needed)
- Token usage tracking to CSV

---

## Docker Deployment

### Build Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and Run

```bash
# Build image
docker build -t wifi-troubleshooter:latest .

# Run container
docker run -d \
  --name wifi-troubleshooter \
  -p 8000:8000 \
  -e GITHUB_TOKEN=your_token_here \
  -e LOG_LEVEL=INFO \
  -v ./logs:/app/logs \
  wifi-troubleshooter:latest

# View logs
docker logs -f wifi-troubleshooter

# Stop container
docker stop wifi-troubleshooter
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
      SESSION_STORE: redis
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: INFO
      ENABLE_PROMETHEUS: "true"
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    depends_on:
      - prometheus
```

**Run:**
```bash
docker-compose up -d
# Access:
# - App: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

---

## Production Setup

### Environment Configuration

```bash
# .env.production
# API Configuration
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN_1=ghp_primary_token_xxxx
GITHUB_TOKEN_2=ghp_backup_token_yyyy

# Logging
LOG_LEVEL=WARNING  # Be less verbose in production

# Session Management
SESSION_STORE=redis
REDIS_URL=redis://redis-primary:6379/0

# Troubleshooting
MAX_DIAGNOSIS_TURNS=6
MAX_MESSAGE_LENGTH=2000

# Security
API_KEY=your_long_random_secret_key_here
RATE_LIMIT_PER_HOUR=150

# Monitoring
ENABLE_PROMETHEUS=true
```

### Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/wifi-troubleshooter
upstream wifi_upstream {
    server app:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    # SSL certificates (use certbot + Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req zone=general burst=20 nodelay;
    
    # Logging
    access_log /var/log/nginx/wifi-troubleshooter-access.log combined;
    error_log /var/log/nginx/wifi-troubleshooter-error.log warn;
    
    # Proxy settings
    location / {
        proxy_pass http://wifi_upstream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Metrics endpoint (restrict to monitoring network)
    location /metrics {
        proxy_pass http://wifi_upstream;
        allow 10.0.0.0/8;  # Internal network only
        deny all;
    }
}
```

### Kubernetes Deployment

```bash
# 1. Create namespace
kubectl create namespace wifi-troubleshooter

# 2. Create secrets
kubectl create secret generic api-keys \
  --from-literal=github-token=your_token \
  --from-literal=api-key=your_secret_key \
  -n wifi-troubleshooter

# 3. Apply ConfigMap
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=INFO \
  --from-literal=SESSION_STORE=redis \
  -n wifi-troubleshooter

# 4. Deploy Redis
helm install redis bitnami/redis \
  -n wifi-troubleshooter \
  --set auth.enabled=false

# 5. Deploy application
kubectl apply -f k8s-deployment.yaml -n wifi-troubleshooter

# 6. Check status
kubectl get pods -n wifi-troubleshooter
kubectl logs -f deployment/wifi-troubleshooter -n wifi-troubleshooter
```

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'wifi-troubleshooter'

scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
    scrape_timeout: 10s
```

### Grafana Dashboard

**Panel 1: Active Sessions**
```promql
active_sessions
```

**Panel 2: LLM Call Latency (p95)**
```promql
histogram_quantile(0.95, rate(llm_call_duration_seconds_bucket[5m]))
```

**Panel 3: Error Rate**
```promql
rate(llm_call_errors_total[5m])
```

**Panel 4: Session Resolution Rate**
```promql
rate(session_resolved_total[1h]) / (rate(session_resolved_total[1h]) + rate(session_not_resolved_total[1h]))
```

### Alerting Rules

```yaml
# alert-rules.yml
groups:
  - name: wifi-troubleshooter
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: rate(llm_call_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High LLM error rate"
          description: "Error rate > 10% in last 5 minutes"
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(llm_call_duration_seconds_bucket[5m])) > 5
        for: 5m
        annotations:
          summary: "High LLM latency"
          description: "p95 latency > 5 seconds"
      
      - alert: TokensExhausted
        expr: llm_call_errors_total{error_type="RuntimeError"} > 5
        for: 2m
        annotations:
          summary: "All API tokens exhausted"
          description: "All backup tokens have been exhausted"
```

### Log Aggregation (ELK Stack)

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /app/logs/app.log
  fields:
    service: wifi-troubleshooter
    environment: production

processors:
  - add_kubernetes_metadata: ~
  - add_docker_metadata: ~

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "wifi-troubleshooter-%{+yyyy.MM.dd}"

logging.level: info
```

---

## Troubleshooting

### Issue: Token Exhaustion

**Symptom:** `RuntimeError: All X token(s) exhausted after retries`

**Solution:**
```bash
# 1. Check token status
curl -X POST http://localhost:8000/chat ...  # See error message

# 2. Add more tokens
# Set GITHUB_TOKEN_2, GITHUB_TOKEN_3, etc. in .env

# 3. Monitor token usage
tail -f logs/app.log | grep "token"
tail -f logs/token_usage.jsonl | jq '.estimated_cost_usd'
```

### Issue: Rate Limiting Too Strict

**Symptom:** `429 Too Many Requests`

**Solution:**
```bash
# Increase rate limit
RATE_LIMIT_PER_HOUR=500  # In .env

# Or track per session more granularly
# Check logs/app.log for [RATE_LIMIT] messages
```

### Issue: Redis Connection Failed

**Symptom:** Errors in logs about Redis connection

**Solution:**
```bash
# Check Redis health
redis-cli -h redis ping
# Expected: PONG

# Check REDIS_URL format
echo $REDIS_URL
# Expected: redis://host:port/db

# For Docker compose:
docker-compose logs redis
docker exec -it wifi-troubleshooter_redis_1 redis-cli ping
```

### Issue: High Memory Usage

**Symptom:** Process memory grows over time

**Solution:**
```bash
# Enable session TTL cleanup
SESSION_TTL_HOURS=24  # Sessions expire after 24h

# Check active sessions
curl http://localhost:8000/metrics | grep active_sessions

# Restart to clear in-memory store
docker restart wifi-troubleshooter
```

---

## Performance Tuning

### Optimize LLM Calls

```bash
# Reduce max tokens for faster responses
# In chat_handler.py:
response = call_llm(system, messages, max_tokens=250)  # Reduce from 400

# Reduce conversation history size
# In llm_service.py:
messages = messages[-8:]  # Keep only last 8 messages
```

### Redis Optimization

```bash
# Configure Redis performance
redis-cli CONFIG SET maxmemory 1gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET timeout 300
```

### Nginx Caching

```nginx
# Cache health checks
location /health {
    proxy_pass http://wifi_upstream;
    proxy_cache_valid 200 60s;
    add_header X-Cache-Status $upstream_cache_status;
}
```

### Load Testing

```bash
# Install Apache Bench
apt-get install apache2-utils

# Test with 100 concurrent users, 1000 requests
ab -n 1000 -c 100 \
  -H "X-API-Key: your_key" \
  -T "application/json" \
  -p /tmp/chat_payload.json \
  http://localhost:8000/chat
```

---

## Backup & Recovery

### Backup Strategy

```bash
# 1. Backup token usage logs
tar -czf backup-tokens-$(date +%s).tar.gz logs/token_usage.jsonl

# 2. Backup Redis data
docker exec wifi_redis redis-cli BGSAVE
docker cp wifi_redis:/data/dump.rdb ./redis-backup-$(date +%s).rdb

# 3. Backup configuration
tar -czf backup-config-$(date +%s).tar.gz .env

# Automated daily backup
0 2 * * * /opt/wifi-troubleshooter/backup.sh
```

### Recovery

```bash
# Restore Redis backup
docker cp redis-backup.rdb wifi_redis:/data/
docker exec wifi_redis redis-cli SHUTDOWN

# Restore and verify
docker start wifi_redis
docker exec wifi_redis redis-cli DBSIZE
```

