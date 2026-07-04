# LM Studio Integration Guide

The MemoryManagement system is now running and ready to capture conversations from LM Studio.

## Setup

### Prerequisites
- MemoryManagement web app running: `python -m MemoryManagement.webapp` (port 5001)
- LM Studio with API enabled (default: http://localhost:1234)

---

## Integration Methods

### Method 1: Simple Capture (After Each Response)

After LM Studio generates a response, capture it:

```powershell
python lmstudio_chat_capture.py
# Then in LM Studio or externally call:
# from lmstudio_chat_capture import capture_from_lm_studio_api
# capture_from_lm_studio_api("What is AI?", "AI is...", "chat-001")
```

### Method 2: Capture Single Interaction

```python
from lmstudio_chat_capture import capture_chat_interaction

result = capture_chat_interaction(
    conversation_id="my-chat-001",
    user_input="Hello, how are you?",
    model_response="I'm doing great, thanks for asking!",
    model_name="neural-chat-7b",
)
print(result)  # {"status": "saved", "id": "my-chat-001"}
```

### Method 3: Capture Full Conversation

```python
from lmstudio_chat_capture import capture_full_conversation

messages = [
    {"role": "user", "content": "What is ML?"},
    {"role": "assistant", "content": "Machine learning is..."},
    {"role": "user", "content": "Give me an example"},
    {"role": "assistant", "content": "A common example is..."},
]

capture_full_conversation(
    conversation_id="chat-001",
    messages=messages,
    model_name="neural-chat-7b",
    title="ML Discussion"
)
```

### Method 4: HTTP POST (For External/Webhook Integration)

```bash
curl -X POST http://localhost:5001/api/capture \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-chat-001",
    "metadata": {
      "title": "LM Studio Chat",
      "model": "neural-chat-7b",
      "participants": ["user", "assistant"]
    },
    "messages": [
      {"role":"user","content":"Hello","timestamp":"2026-07-02T12:00:00+00:00"},
      {"role":"assistant","content":"Hi there!","timestamp":"2026-07-02T12:00:05+00:00"}
    ]
  }'
```

---

## Quick Reference Commands

```powershell
# List all captured conversations
python -m MemoryManagement.cli list

# Search conversations
python -m MemoryManagement.cli search "machine learning"

# View a specific conversation
python -m MemoryManagement.cli show chat-001

# Delete a conversation
python -m MemoryManagement.cli delete chat-001

# Remove expired conversations
python -m MemoryManagement.cli prune
```

---

## Web Interface
- **URL**: `http://localhost:5001/`
- **Features**:
  - Browse all captured conversations
  - Search by text, title, or model
  - View message history with timestamps
  - Edit metadata (title, participants, expiry)
  - Set conversation expiry date (auto-prune old chats)
  - Delete conversations

---

## LM Studio Script Hook

If LM Studio supports custom JavaScript/Python actions, use:

```python
# In LM Studio custom action/hook
from lmstudio_chat_capture import capture_from_lm_studio_api

capture_from_lm_studio_api(
    user_message=input_text,
    model_response=output_text,
    conv_id="session-123"
)
```

---

## Status

✅ Web app: http://localhost:5001/  
✅ Package installed and callable  
✅ LM Studio API available: http://localhost:1234  
✅ Auto-capture ready via Python or HTTP

---

## Next Steps

1. **Test a capture** with Python:
   ```python
   from lmstudio_chat_capture import capture_from_lm_studio_api
   capture_from_lm_studio_api("Test prompt", "Test response")
   ```

2. **Open web UI** and verify the conversation appears

3. **Hook into LM Studio** via custom actions or external script

---

**Questions?** All conversation data is stored in `MemoryManagement/docs/conversations/` as editable Markdown files.

