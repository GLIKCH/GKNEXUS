#!/usr/bin/env python3
"""
LM Studio Auto-Capture Wrapper

Instead of using LM Studio's API directly, use this wrapper to auto-capture all responses.
It acts as a proxy between your code and LM Studio, logging everything to MemoryManagement.

Usage:
    Instead of: requests.post('http://localhost:1234/api/v1/chat', json=payload)
    Use:        from lmstudio_auto_capture import chat_with_capture
                response = chat_with_capture(prompt, model="gemma-4-cdb")
"""

import requests
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

LM_STUDIO_URL = "http://localhost:1234"
MEMORY_API_URL = "http://localhost:5001/api/capture"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def chat_with_capture(
    prompt: str,
    model: str = "google/gemma-4-e4b",
    conversation_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Send a chat message to LM Studio and automatically capture it.
    
    Args:
        prompt: User's message
        model: Model name (default: google/gemma-4-e4b - Gemma 4 E4B loaded model)
        conversation_id: ID for grouping messages (auto-generated if None)
        system_prompt: Optional system instructions to prepend to the prompt
        **kwargs: Additional LM Studio API parameters
        
    Returns:
        {'content': response_text, 'model': model, 'captured': True/False}
    """
    
    if not conversation_id:
        conversation_id = f"lmstudio-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Build LM Studio request
    user_message = prompt
    if system_prompt:
        user_message = f"{system_prompt}\n\n{prompt}"
    
    payload = {
        "model": model,
        "input": user_message,
        **kwargs
    }
    
    try:
        # Call LM Studio API
        response = requests.post(
            f"{LM_STUDIO_URL}/api/v1/chat",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract response from LM Studio format (output is an array)
        ai_response = ""
        if "output" in result and len(result["output"]) > 0:
            ai_response = result["output"][0].get("content", "")
        
        # Auto-capture to MemoryManagement
        capture_payload = {
            "id": conversation_id,
            "metadata": {
                "title": f"Chat with {model}",
                "model": model,
                "participants": ["user", "assistant"],
                "system_prompt": system_prompt or None
            },
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "timestamp": _now_iso()
                },
                {
                    "role": "assistant",
                    "content": ai_response,
                    "timestamp": _now_iso()
                }
            ]
        }
        
        capture_response = requests.post(
            MEMORY_API_URL,
            json=capture_payload,
            timeout=10
        )
        
        return {
            "content": ai_response,
            "model": model,
            "captured": capture_response.status_code == 200,
            "conversation_id": conversation_id
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "error": str(e),
            "content": None,
            "captured": False,
            "conversation_id": conversation_id
        }


def get_lmstudio_models() -> list:
    """Get list of available models from LM Studio."""
    try:
        response = requests.get(
            f"{LM_STUDIO_URL}/api/v1/models",
            timeout=10
        )
        response.raise_for_status()
        models = response.json().get("models", [])
        return [m.get("display_name", m.get("key", "unknown")) for m in models]
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("LM Studio Auto-Capture Wrapper")
    print("=" * 60)
    
    print("\nAvailable models:")
    models = get_lmstudio_models()
    for model in models:
        print(f"  ✓ {model}")
    
    print("\n" + "=" * 60)
    print("Testing auto-capture...")
    print("=" * 60)
    
    result = chat_with_capture(
        "What is the capital of France?",
        model="google/gemma-4-e4b"
    )
    
    if result.get("content"):
        print(f"\n✅ Response received ({len(result['content'])} chars)")
        print(f"✅ Captured: {result['captured']}")
        print(f"✅ Conversation ID: {result['conversation_id']}")
        print(f"\nFirst 200 chars of response:")
        print(result['content'][:200] + "...")
    else:
        print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
