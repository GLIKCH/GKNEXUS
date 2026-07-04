#!/usr/bin/env python3
"""
LM Studio action to capture conversations into MemoryManagement.

Usage:
  python lmstudio_capture.py --id <conv-id> --user-msg "message" --ai-msg "response"
  
Or import directly:
  from lmstudio_capture import capture_lm_conversation
"""

import argparse
import json
from datetime import datetime, timezone
from MemoryManagement.storage import capture_conversation


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_lm_conversation(
    conv_id: str,
    user_message: str = None,
    ai_message: str = None,
    title: str = None,
    append: bool = False,
) -> dict:
    """
    Simple wrapper to capture LM Studio conversations.
    
    Args:
        conv_id: Unique conversation identifier
        user_message: User message to add
        ai_message: AI/assistant message to add
        title: Conversation title (optional)
        append: If True, append to existing conversation; else create new
        
    Returns:
        Dict with status and conversation id
    """
    from MemoryManagement.storage import load_conversation
    
    messages = []
    if append:
        existing = load_conversation(conv_id)
        if existing:
            messages = list(existing.get("messages", []))
    
    if user_message:
        messages.append({"role": "user", "content": user_message, "timestamp": _now_iso()})
    if ai_message:
        messages.append({"role": "assistant", "content": ai_message, "timestamp": _now_iso()})
    
    metadata = {
        "title": title or conv_id,
        "participants": ["user", "assistant"],
    }
    
    conv = capture_conversation({"id": conv_id, "metadata": metadata, "messages": messages})
    
    return {"status": "saved", "id": conv.id}


def main():
    parser = argparse.ArgumentParser(description="LM Studio conversation capture")
    parser.add_argument("--id", required=True, help="Conversation ID")
    parser.add_argument("--user-msg", help="User message")
    parser.add_argument("--ai-msg", help="AI message")
    parser.add_argument("--title", help="Conversation title")
    parser.add_argument("--append", action="store_true", help="Append to existing conversation")
    
    args = parser.parse_args()
    
    result = capture_lm_conversation(
        conv_id=args.id,
        user_message=args.user_msg,
        ai_message=args.ai_msg,
        title=args.title,
        append=args.append,
    )
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
