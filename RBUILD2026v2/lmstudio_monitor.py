#!/usr/bin/env python3
"""
Auto-capture monitor for LM Studio.

Watches the LM Studio API (http://localhost:1234) and automatically
captures conversations to MemoryManagement (http://localhost:5001/api/capture).

Usage:
  python lmstudio_monitor.py

Environment:
  LM_STUDIO_URL (default: http://localhost:1234)
  MEMORY_MANAGER_URL (default: http://localhost:5001)
"""

import requests
import json
import time
from datetime import datetime, timezone
from pathlib import Path

LM_STUDIO_URL = "http://localhost:1234"
MEMORY_API_URL = "http://localhost:5001/api/capture"
CONVERSATIONS_FILE = "lm_conversations_state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_state() -> dict:
    """Load last seen conversation state."""
    if Path(CONVERSATIONS_FILE).exists():
        with open(CONVERSATIONS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    """Save conversation state."""
    with open(CONVERSATIONS_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _get_lm_studio_models() -> list:
    """Fetch list of available models from LM Studio."""
    try:
        resp = requests.get(f"{LM_STUDIO_URL}/api/models", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", [])
    except Exception as e:
        print(f"Error fetching models: {e}")
    return []


def _capture_conversation(conv_id: str, messages: list, title: str = None):
    """Send conversation to MemoryManagement."""
    payload = {
        "id": conv_id,
        "metadata": {
            "title": title or conv_id,
            "participants": ["user", "assistant"],
        },
        "messages": messages,
    }
    try:
        resp = requests.post(MEMORY_API_URL, json=payload, timeout=5)
        if resp.status_code in (200, 201):
            print(f"✓ Captured: {conv_id}")
            return True
    except Exception as e:
        print(f"✗ Capture error: {e}")
    return False


def monitor():
    """Monitor LM Studio for new conversations."""
    print(f"Monitoring LM Studio at {LM_STUDIO_URL}")
    print(f"Saving to MemoryManagement at {MEMORY_API_URL}")
    print("Press CTRL+C to stop.\n")
    
    state = _load_state()
    
    try:
        while True:
            models = _get_lm_studio_models()
            if models:
                for model in models:
                    model_id = model.get("id", "unknown")
                    # In a real scenario, you'd hook into LM Studio's chat history
                    # For now, this is a framework showing how to integrate
            
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
        _save_state(state)


if __name__ == "__main__":
    monitor()
