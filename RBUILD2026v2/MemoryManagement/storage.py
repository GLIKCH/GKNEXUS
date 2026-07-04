import os
import json
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Optional
from .models import Conversation

BASE_DIR = os.path.dirname(__file__)
DOCS_DIR = os.path.join(BASE_DIR, "docs")
CONV_DIR = os.path.join(DOCS_DIR, "conversations")
INDEX_FILE = os.path.join(DOCS_DIR, "index.json")

os.makedirs(CONV_DIR, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_index() -> Dict:
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(idx: Dict):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)


def _conversation_path(conv_id: str) -> str:
    return os.path.join(CONV_DIR, f"{conv_id}.md")


def _is_expired(metadata: Dict) -> bool:
    expires_at = metadata.get("expires_at")
    if not expires_at:
        return False
    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires_dt


def _normalize_metadata(metadata: Dict) -> Dict:
    normalized = dict(metadata or {})
    if not normalized.get("created"):
        normalized["created"] = _now_iso()
    if normalized.get("participants") is None:
        normalized["participants"] = []
    return normalized


def _normalize_messages(messages: List[Dict]) -> List[Dict]:
    normalized: List[Dict] = []
    default_ts = _now_iso()
    for message in messages:
        if not isinstance(message, dict):
            continue
        item = dict(message)
        if not item.get("timestamp"):
            item["timestamp"] = default_ts
        normalized.append(item)
    return normalized


def _write_markdown(path: str, conv: Conversation):
    markdown_metadata = dict(conv.metadata)
    markdown_metadata["messages"] = conv.messages
    front = yaml.safe_dump(markdown_metadata, sort_keys=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(front)
        f.write("---\n\n")
        f.write("# Messages\n\n")
        for m in conv.messages:
            role = m.get("role", "unknown")
            timestamp = m.get("timestamp")
            content = m.get("content", "")
            if timestamp:
                f.write(f"**{timestamp}**\n\n")
            f.write(f"## {role}\n\n")
            f.write(content.rstrip() + "\n\n")


def save_conversation(conv: Conversation) -> str:
    if not conv.id:
        raise ValueError("Conversation must have an id")
    conv.metadata = _normalize_metadata(conv.metadata)
    conv.messages = _normalize_messages(conv.messages)
    path = _conversation_path(conv.id)
    _write_markdown(path, conv)

    idx = _load_index()
    idx[conv.id] = {
        "file": os.path.relpath(path, BASE_DIR).replace("\\", "/"),
        "metadata": conv.metadata,
    }
    _save_index(idx)
    return path


def update_conversation(conv: Conversation) -> str:
    idx = _load_index()
    if conv.id not in idx:
        raise FileNotFoundError(f"Conversation '{conv.id}' not found")
    return save_conversation(conv)


def delete_conversation(conv_id: str) -> bool:
    idx = _load_index()
    entry = idx.pop(conv_id, None)
    if not entry:
        return False
    path = os.path.join(BASE_DIR, entry["file"]) if not os.path.isabs(entry["file"]) else entry["file"]
    if os.path.exists(path):
        os.remove(path)
    _save_index(idx)
    return True


def _load_conversation_file(path: str) -> Optional[Conversation]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    metadata: Dict = {}
    messages: List[Dict] = []
    md_text = text
    if text.startswith("---"):
        parts = text.split("---")
        if len(parts) >= 3:
            meta_text = parts[1]
            md_text = "---".join(parts[2:])
            metadata = yaml.safe_load(meta_text) or {}
            if isinstance(metadata.get("messages"), list):
                messages = _normalize_messages(metadata.get("messages", []))

    if not messages:
        lines = md_text.splitlines()
        role = None
        buffer: List[str] = []
        for line in lines:
            if line.startswith('## '):
                if role is not None:
                    messages.append({"role": role, "content": "\n".join(buffer).strip()})
                role = line[3:].strip()
                buffer = []
            else:
                buffer.append(line)
        if role is not None:
            messages.append({"role": role, "content": "\n".join(buffer).strip()})
        messages = _normalize_messages(messages)

    return Conversation(id=os.path.splitext(os.path.basename(path))[0], metadata=metadata, messages=messages)


def load_conversation(conv_id: str) -> Optional[Conversation]:
    idx = _load_index()
    entry = idx.get(conv_id)
    if not entry:
        return None
    path = os.path.join(BASE_DIR, entry["file"]) if not os.path.isabs(entry["file"]) else entry["file"]
    if not os.path.exists(path):
        return None
    return _load_conversation_file(path)


def list_conversations(query: Optional[str] = None, include_expired: bool = False) -> List[Dict]:
    idx = _load_index()
    items: List[Dict] = []
    for k, v in idx.items():
        metadata = v.get("metadata", {}) or {}
        expired = _is_expired(metadata)
        if expired and not include_expired:
            continue
        item = {"id": k, "file": v.get("file"), "metadata": metadata, "expired": expired}
        items.append(item)

    if query:
        query_lower = query.lower()
        results: List[Dict] = []
        for item in items:
            if query_lower in item["id"].lower() or query_lower in item["metadata"].get("title", "").lower():
                results.append(item)
                continue
            conv = load_conversation(item["id"])
            if conv and any(query_lower in str(m.get("content", "")).lower() or query_lower in str(m.get("role", "")).lower() for m in conv.messages):
                results.append(item)
        return results
    return items


def search_conversations(query: str, include_expired: bool = False) -> List[Dict]:
    return list_conversations(query=query, include_expired=include_expired)


def prune_expired_conversations() -> List[str]:
    idx = _load_index()
    expired_ids: List[str] = []
    for conv_id, entry in list(idx.items()):
        metadata = entry.get("metadata", {}) or {}
        if _is_expired(metadata):
            delete_conversation(conv_id)
            expired_ids.append(conv_id)
    return expired_ids


def capture_conversation(data: Dict) -> Conversation:
    conversation_id = data.get("id") or f"capture-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    metadata = _normalize_metadata(data.get("metadata", {}))
    messages = _normalize_messages(data.get("messages", []))
    conv = Conversation(id=conversation_id, metadata=metadata, messages=messages)
    idx = _load_index()
    if conversation_id in idx:
        update_conversation(conv)
    else:
        save_conversation(conv)
    return conv
