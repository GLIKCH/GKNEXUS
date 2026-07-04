#!/usr/bin/env python3
"""Test RAG capture for Joel's LM Studio integration"""

from lmstudio_auto_capture import chat_with_capture
from MemoryManagement.storage import list_conversations

print("="*70)
print("TESTING RAG CAPTURE FOR LMSTUDIO INTEGRATION")
print("="*70)

# Capture the RAG test message
result = chat_with_capture(
    'My name is Joel J. De Alba and this is the initial test results of the custom RAG development for LM Studio integration.'
)

print("\nCapture Result:")
print(f"  Captured to MemoryManagement: {result.get('captured')}")
print(f"  Conversation ID: {result.get('conversation_id')}")
print(f"  Response length: {len(result.get('content', ''))} characters")

if result.get('error'):
    print(f"  Error: {result.get('error')}")

# List all conversations
print("\n" + "="*70)
print("STORED CONVERSATIONS")
print("="*70)

convs = list_conversations()
print(f"\nTotal conversations: {len(convs)}")
for conv in convs:
    title = conv.get('metadata', {}).get('title', 'Untitled')
    print(f"  ✓ {conv['id']}: {title}")

# Show the latest conversation (RAG test)
if convs:
    latest_id = convs[-1]['id']
    print(f"\n✅ Latest conversation: {latest_id}")
    print(f"   Access at: http://localhost:5001/conversation/{latest_id}")
