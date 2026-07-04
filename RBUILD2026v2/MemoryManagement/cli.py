import argparse
from .storage import (
    save_conversation,
    update_conversation,
    load_conversation,
    list_conversations,
    search_conversations,
    delete_conversation,
    prune_expired_conversations,
)
from .models import Conversation
import json


def main():
    parser = argparse.ArgumentParser(description="MemoryManagement CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="Add a conversation from JSON file")
    p_add.add_argument("file", help="Path to JSON file with fields: id, metadata, messages")

    p_edit = sub.add_parser("edit", help="Edit an existing conversation from JSON file")
    p_edit.add_argument("file", help="Path to JSON file with fields: id, metadata, messages")

    p_list = sub.add_parser("list", help="List conversations")

    p_search = sub.add_parser("search", help="Search conversations by text")
    p_search.add_argument("query", help="Text to search in conversation ids, titles, or messages")

    p_show = sub.add_parser("show", help="Show a conversation")
    p_show.add_argument("id", help="Conversation id")

    p_delete = sub.add_parser("delete", help="Delete a conversation")
    p_delete.add_argument("id", help="Conversation id")

    p_prune = sub.add_parser("prune", help="Delete expired conversations")

    args = parser.parse_args()
    if args.cmd in ("add", "edit"):
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        conv = Conversation(id=data["id"], metadata=data.get("metadata", {}), messages=data.get("messages", []))
        if args.cmd == "add":
            path = save_conversation(conv)
            print(f"Saved: {path}")
        else:
            try:
                path = update_conversation(conv)
                print(f"Updated: {path}")
            except FileNotFoundError:
                print("Not found")
                return
    elif args.cmd == "list":
        for item in list_conversations():
            print(item["id"], item.get("metadata", {}).get("title", ""), "[expired]" if item.get("expired") else "")
    elif args.cmd == "search":
        for item in search_conversations(args.query, include_expired=True):
            print(item["id"], item.get("metadata", {}).get("title", ""), "[expired]" if item.get("expired") else "")
    elif args.cmd == "show":
        conv = load_conversation(args.id)
        if not conv:
            print("Not found")
            return
        print("ID:", conv.id)
        print("Metadata:", conv.metadata)
        print("Messages:")
        for m in conv.messages:
            print(f"- {m.get('timestamp', '')} {m.get('role')}: {m.get('content')[:80].replace('\n',' ')}")
    elif args.cmd == "delete":
        success = delete_conversation(args.id)
        print("Deleted" if success else "Not found")
    elif args.cmd == "prune":
        removed = prune_expired_conversations()
        if removed:
            print("Removed expired:", ", ".join(removed))
        else:
            print("No expired conversations found.")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
