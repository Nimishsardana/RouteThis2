#!/usr/bin/env python3
"""
WiFi Troubleshooter — CLI Interface
====================================
Run with: python cli.py

A simple command-line chat interface for local development and testing.
No server required — talks to Claude directly.
"""

import os
import sys
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add the project root to sys.path so sibling packages like utils and src can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import setup_logging
setup_logging(console=False)  # Suppress logs to keep CLI clean

from src.state_machine import create_session, State
from src.chat_handler import chat_handler

logger = logging.getLogger(__name__)


BANNER = """
╔══════════════════════════════════════════════════════════╗
║         WiFi Troubleshooter — Linksys EA6350             ║
║  Powered by Claude AI + Official Router Manual           ║
╚══════════════════════════════════════════════════════════╝
Type 'quit' or 'exit' to end the session.
"""

OPENING = (
    "Hi! I'm your WiFi troubleshooting assistant. I'm here to help you diagnose "
    "and fix your connectivity issues.\n\n"
    "To start, can you describe what's happening with your WiFi? "
    "For example: are you unable to connect, experiencing slow speeds, "
    "or is the internet dropping out?"
)


def run_cli():
    if not os.getenv("GITHUB_TOKEN"):
        print("ERROR: GITHUB_TOKEN environment variable not set.")
        print("Copy .env.example to .env and add your GitHub token.")
        sys.exit(1)

    session_id = str(uuid.uuid4())[:8]
    session = create_session(session_id)
    session.add_message("assistant", OPENING)

    print(BANNER)
    print(f"[Session: {session_id}]\n")
    print(f"🤖 Assistant: {OPENING}\n")

    while session.state != State.EXIT:
        try:
            user_input = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended by user.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\n🤖 Assistant: Goodbye! Feel free to start a new session if you need more help.")
            break

        try:
            reply = chat_handler.process(session, user_input)
            print(f"\n🤖 Assistant: {reply}\n")
            print(f"   [State: {session.state.value} | Turn: {session.total_turns}]\n")
        except Exception as e:
            logger.exception("Error processing message")
            print(f"\n❌ Error: {e}\nPlease try again.\n")

    print("\n--- Session Complete ---")
    if session.resolved is True:
        print("✅ Issue resolved!")
    elif session.resolved is False:
        print("❌ Issue not resolved — further support needed.")


if __name__ == "__main__":
    run_cli()
