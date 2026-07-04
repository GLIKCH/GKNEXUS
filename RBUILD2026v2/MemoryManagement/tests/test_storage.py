import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from MemoryManagement import storage
from MemoryManagement.models import Conversation


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        storage.BASE_DIR = self.tempdir.name
        storage.DOCS_DIR = os.path.join(self.tempdir.name, "docs")
        storage.CONV_DIR = os.path.join(storage.DOCS_DIR, "conversations")
        storage.INDEX_FILE = os.path.join(storage.DOCS_DIR, "index.json")
        os.makedirs(storage.CONV_DIR, exist_ok=True)

    def test_save_and_load_conversation(self):
        conv = Conversation(
            id="test-conv",
            metadata={"title": "Test", "created": "2026-07-02", "participants": ["user", "assistant"]},
            messages=[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}],
        )
        path = storage.save_conversation(conv)
        self.assertTrue(os.path.exists(path))

        loaded = storage.load_conversation("test-conv")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, conv.id)
        self.assertEqual(loaded.metadata["title"], "Test")
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[0]["role"], "user")

    def test_update_conversation(self):
        conv = Conversation(
            id="update-conv",
            metadata={"title": "Before", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Hello"}],
        )
        storage.save_conversation(conv)

        updated = Conversation(
            id="update-conv",
            metadata={"title": "After", "created": "2026-07-02", "participants": ["user", "assistant"]},
            messages=[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Updated"}],
        )
        storage.update_conversation(updated)

        loaded = storage.load_conversation("update-conv")
        self.assertEqual(loaded.metadata["title"], "After")
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[1]["content"], "Updated")

    def test_list_conversations(self):
        conv = Conversation(
            id="list-conv",
            metadata={"title": "List Me", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "One"}],
        )
        storage.save_conversation(conv)
        results = storage.list_conversations()
        self.assertTrue(any(item["id"] == "list-conv" for item in results))

    def test_delete_conversation(self):
        conv = Conversation(
            id="delete-conv",
            metadata={"title": "Delete Me", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Goodbye"}],
        )
        storage.save_conversation(conv)
        deleted = storage.delete_conversation("delete-conv")
        self.assertTrue(deleted)
        self.assertIsNone(storage.load_conversation("delete-conv"))

    def test_search_conversations(self):
        conv = Conversation(
            id="search-conv",
            metadata={"title": "Search Test", "created": "2026-07-02"},
            messages=[{"role": "user", "content": "Find this text"}],
        )
        storage.save_conversation(conv)
        results = storage.search_conversations("find")
        self.assertTrue(any(item["id"] == "search-conv" for item in results))

    def test_prune_expired_conversations(self):
        conv = Conversation(
            id="expire-conv",
            metadata={"title": "Expiring", "created": "2026-07-02", "expires_at": "2000-01-01T00:00:00+00:00"},
            messages=[{"role": "user", "content": "Expired"}],
        )
        storage.save_conversation(conv)
        removed = storage.prune_expired_conversations()
        self.assertIn("expire-conv", removed)
        self.assertIsNone(storage.load_conversation("expire-conv"))

    def test_capture_conversation(self):
        data = {
            "id": "capture-conv",
            "metadata": {"title": "Capture Test"},
            "messages": [{"role": "assistant", "content": "Captured automatically"}],
        }
        conv = storage.capture_conversation(data)
        self.assertEqual(conv.id, "capture-conv")
        loaded = storage.load_conversation("capture-conv")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.metadata["title"], "Capture Test")


if __name__ == "__main__":
    unittest.main()
