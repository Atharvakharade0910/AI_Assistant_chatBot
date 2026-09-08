import tempfile
import unittest
from pathlib import Path

from backend.database import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = db.DATABASE_PATH
        db.DATABASE_PATH = Path(self.temp_dir.name) / "chatbot.db"
        db.initialize_database()

    def tearDown(self):
        db.DATABASE_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_conversation_and_message_lifecycle(self):
        user = db.create_user("test@example.com", "hash")
        conversation = db.create_conversation(user["id"], "  Test chat  ")
        db.save_message(conversation["id"], user["id"], "user", "Hello")
        db.save_message(conversation["id"], user["id"], "assistant", "Hi", "complete")

        messages = db.get_messages(conversation["id"], user["id"])
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[1]["status"], "complete")

        db.delete_conversation(conversation["id"], user["id"])
        self.assertFalse(db.conversation_exists(conversation["id"], user["id"]))

    def test_targeted_assistant_deletion(self):
        user = db.create_user("target@example.com", "hash")
        conversation = db.create_conversation(user["id"])
        db.save_message(conversation["id"], user["id"], "user", "Question one")
        db.save_message(conversation["id"], user["id"], "assistant", "Answer one")
        db.save_message(conversation["id"], user["id"], "user", "Question two")
        db.save_message(conversation["id"], user["id"], "assistant", "Answer two")

        messages = db.get_messages(conversation["id"], user["id"])
        assistant_id = messages[1]["id"]
        self.assertTrue(db.delete_assistant_message(conversation["id"], user["id"], assistant_id))
        remaining = db.get_messages(conversation["id"], user["id"])
        self.assertEqual([message["content"] for message in remaining], [
            "Question one", "Question two", "Answer two"
        ])


if __name__ == "__main__":
    unittest.main()
