#!/usr/bin/env python3
"""
LM Studio Chat Integration - Middleware approach.

This script acts as a proxy that intercepts LM Studio chat completions
and automatically captures them to MemoryManagement.

Usage:
  1. Start MemoryManagement: python -m MemoryManagement.webapp
  2. Start this script: python lmstudio_chat_capture.py
  3. In LM Studio: Configure to send chat data after each completion

Or use directly in LM Studio custom actions:
  from lmstudio_chat_capture import capture_chat_interaction
"""

import requests
import json
from datetime import datetime, timezone
from typing import Optional

LM_STUDIO_URL = "http://localhost:1234"
MEMORY_API_URL = "http://localhost:5001/api/capture"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_chat_interaction(
    conversation_id: str,
    user_input: str,
    model_response: str,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> dict:
    """
    Capture a single chat interaction (user message + model response).
    
    Args:
        conversation_id: Unique ID for this conversation
        user_input: The user's message
        model_response: The model's response
        model_name: Name of the model used (optional)
        system_prompt: System prompt used (optional)
        
    Returns:
        Dict with capture status
    """
    timestamp = _now_iso()
    
    messages = [
        {
            "role": "user",
            "content": user_input,
            "timestamp": timestamp,
        },
        {
            "role": "assistant",
            "content": model_response,
            "timestamp": timestamp,
        },
    ]
    
    metadata = {
        "title": f"LM Studio Chat - {model_name or 'unknown model'}",
        "participants": ["user", "assistant"],
        "model": model_name,
        "system_prompt": system_prompt,
    }
    
    payload = {
        "id": conversation_id,
        "metadata": metadata,
        "messages": messages,
    }
    
    try:
        resp = requests.post(MEMORY_API_URL, json=payload, timeout=5)
        if resp.status_code in (200, 201):
            result = resp.json()
            return {"status": "saved", "id": conversation_id}
        else:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def capture_full_conversation(
    conversation_id: str,
    messages: list,
    model_name: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """
    Capture an entire conversation (multiple messages).
    
    Args:
        conversation_id: Unique conversation ID
        messages: List of message dicts with 'role' and 'content'
        model_name: Name of the model
        title: Conversation title
        
    Returns:
        Dict with capture status
    """
    # Timestamp any messages that don't have one
    for msg in messages:
        if "timestamp" not in msg:
            msg["timestamp"] = _now_iso()
    
    payload = {
        "id": conversation_id,
        "metadata": {
            "title": title or f"LM Studio - {model_name or 'chat'}",
            "participants": ["user", "assistant"],
            "model": model_name,
        },
        "messages": messages,
    }
    
    try:
        resp = requests.post(MEMORY_API_URL, json=payload, timeout=5)
        if resp.status_code in (200, 201):
            return {"status": "saved", "id": conversation_id}
        else:
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def capture_from_lm_studio_api(
    user_message: str,
    model_response: str,
    conv_id: str = None,
) -> dict:
    """Simple helper for quick LM Studio captures."""
    if not conv_id:
        conv_id = f"lm-studio-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return capture_chat_interaction(
        conversation_id=conv_id,
        user_input=user_message,
        model_response=model_response,
    )


if __name__ == "__main__":
    # Example usage
    result = capture_from_lm_studio_api(
        user_message="What is machine learning?",
        model_response="Machine learning is a subset of artificial intelligence...",
        conv_id="example-001",
    )
    print(json.dumps(result, indent=2))
