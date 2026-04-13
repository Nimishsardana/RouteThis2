"""
WiFi Troubleshooter — FastAPI Backend
=====================================
Endpoints:
  POST /chat        — Send a user message, get assistant reply
  POST /session     — Create a new session
  GET  /session/{id} — Get current session state
  GET  /health      — Health check
"""

import os
import uuid
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env before any other imports that need env vars
load_dotenv()

from utils.logger import setup_logging
setup_logging()

from src.state_machine import create_session, ConversationState, State
from src.chat_handler import chat_handler
from src.manual_service import load_manual
from infra.input_validator import InputValidator
from infra.metrics import MetricsCollector, get_metrics_endpoint
from infra.request_logging import RequestLoggingMiddleware
from infra.api_security import APIKeyValidator, get_rate_limiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WiFi Troubleshooter",
    description="LLM-powered WiFi troubleshooting chatbot using Linksys EA6350 manual",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request/response logging middleware
app.add_middleware(RequestLoggingMiddleware)

# In-memory session store (replace with Redis for production)
_sessions: dict[str, ConversationState] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: str
    turn: int
    is_complete: bool


class SessionResponse(BaseModel):
    session_id: str
    state: str
    turn: int
    reboot_method: Optional[str] = None
    reboot_step: Optional[int] = None


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Pre-load the manual data and verify API key on startup."""
    logger.info("Starting WiFi Troubleshooter API...")
    try:
        manual = load_manual()
        logger.info(f"Manual loaded: {manual['router_model']}")
    except Exception as e:
        logger.error(f"Failed to load manual: {e}")
        raise

    

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "wifi-troubleshooter"}


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return get_metrics_endpoint()


@app.post("/session", response_model=SessionResponse)
async def create_new_session():
    """Create a new troubleshooting session and return the opening message."""
    session_id = str(uuid.uuid4())[:8]
    session = create_session(session_id)

    # Prime the assistant with an opening message
    opening = (
        "Hi! I'm your WiFi troubleshooting assistant. I'm here to help you diagnose "
        "and fix your connectivity issues. Let's figure this out together!\n\n"
        "To start, can you describe what's happening with your WiFi? "
        "For example: are you unable to connect, experiencing slow speeds, or is the internet dropping out?"
    )
    session.add_message("assistant", opening)
    _sessions[session_id] = session

    logger.info(f"New session created: {session_id}")
    return SessionResponse(
        session_id=session_id,
        state=session.state.value,
        turn=session.total_turns,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, x_api_key: str = None):
    """
    Process a user message and return the assistant's reply.
    
    Optional header: X-API-Key (set API_KEY environment variable to require it)
    """
    # Validate API key
    if not APIKeyValidator.validate(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    # Check rate limit
    rate_limiter = get_rate_limiter()
    is_allowed, error_msg = rate_limiter.check(request.session_id)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=error_msg)
    
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Start a new session at POST /session")

    # Validate input
    is_valid, error_msg = InputValidator.validate(request.message, session.session_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Sanitize
    sanitized_message = InputValidator.sanitize(request.message)

    try:
        reply = chat_handler.process(session, sanitized_message)
    except Exception as e:
        logger.exception(f"[{request.session_id}] Error processing your message: {e}")
        raise HTTPException(status_code=500, detail="An error occurred processing your message")

    is_complete = session.state == State.EXIT
    
    # Record metrics
    MetricsCollector.record_chat_turn()
    MetricsCollector.set_active_sessions(len(_sessions))
    
    # If session is complete, record the outcome
    if is_complete and session.resolved is not None:
        MetricsCollector.record_session_resolved(session.resolved)

    return ChatResponse(
        session_id=session.session_id,
        reply=reply,
        state=session.state.value,
        turn=session.total_turns,
        is_complete=is_complete,
    )


@app.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get the current state of a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session_id,
        state=session.state.value,
        turn=session.total_turns,
        reboot_method=session.reboot_method,
        reboot_step=session.reboot_step_index,
    )


# ---------------------------------------------------------------------------
# Simple web UI (served at /)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the minimal web chat UI."""
    # Go up one level from src/ to project root, then into ui/
    html_path = os.path.join(os.path.dirname(__file__), "..", "ui", "index.html")
    html_path = os.path.normpath(html_path)  # Normalize the path
    if os.path.exists(html_path):
        with open(html_path, encoding='utf-8') as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>WiFi Troubleshooter API</h1><p>See /docs for API reference.</p>")
