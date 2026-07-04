import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from MemoryManagement import cli, storage
from MemoryManagement.models import Conversation


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        storage.BASE_DIR = self.tempdir.name
        storage.DOCS_DIR = os.path.join(self.tempdir.name, "docs")
        storage.CONV_DIR = os.path.join(storage.DOCS_DIR, "conversations")
        storage.INDEX_FILE = os.path.join(storage.DOCS_DIR, "index.json")
        os.makedirs(storage.CONV_DIR, exist_ok=True)

    def run_cli(self, argv):
        with patch.object(sys, "argv", argv):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                cli.main()
                return fake_out.getvalue()

    def test_add_command(self):
        data = {
            "id": "cli-add",
            "metadata": {"title": "CLI Add", "created": "2026-07-02"},
            "messages": [{"role": "user", "content": "Hello CLI"}],
        }
        data_path = os.path.join(self.tempdir.name, "conv.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        output = self.run_cli(["cli.py", "add", data_path])
        self.assertIn("Saved:", output)
        self.assertTrue(os.path.exists(os.path.join(storage.CONV_DIR, "cli-add.md")))

    def test_edit_command(self):
        conv = Conversation(
            id="cli-edit",
            metadata={"title": "Before", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Hello"}],
        )
        storage.save_conversation(conv)

        data = {
            "id": "cli-edit",
            "metadata": {"title": "After", "created": "2026-07-02"},
            "messages": [{"role": "assistant", "content": "Updated"}],
        }
        data_path = os.path.join(self.tempdir.name, "update.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        output = self.run_cli(["cli.py", "edit", data_path])
        self.assertIn("Updated:", output)

        loaded = storage.load_conversation("cli-edit")
        self.assertEqual(loaded.metadata["title"], "After")
        self.assertEqual(loaded.messages[0]["role"], "assistant")

    def test_show_command(self):
        conv = Conversation(
            id="cli-show",
            metadata={"title": "Show", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Show me"}],
        )
        storage.save_conversation(conv)
        output = self.run_cli(["cli.py", "show", "cli-show"])
        self.assertIn("ID: cli-show", output)
        self.assertIn("Show", output)

    def test_delete_command(self):
        conv = Conversation(
            id="cli-delete",
            metadata={"title": "Delete", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Delete me"}],
        )
        storage.save_conversation(conv)
        output = self.run_cli(["cli.py", "delete", "cli-delete"])
        self.assertIn("Deleted", output)
        self.assertIsNone(storage.load_conversation("cli-delete"))

    def test_search_command(self):
        conv = Conversation(
            id="cli-search",
            metadata={"title": "Searchable", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Find this item"}],
        )
        storage.save_conversation(conv)
        output = self.run_cli(["cli.py", "search", "find"])
        self.assertIn("cli-search", output)

    def test_prune_command(self):
        conv = Conversation(
            id="cli-prune",
            metadata={"title": "Prune", "created": "2026-07-02", "expires_at": "2000-01-01T00:00:00+00:00"},
            messages=[{"role": "user", "content": "Expired"}],
        )
        storage.save_conversation(conv)
        output = self.run_cli(["cli.py", "prune"])
        self.assertIn("Removed expired", output)
        self.assertIsNone(storage.load_conversation("cli-prune"))


if __name__ == "__main__":
    unittest.main()
