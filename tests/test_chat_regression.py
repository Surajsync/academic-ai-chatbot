import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app
from backend.database.database import SessionLocal
from backend.database.models import User
from backend.security.security import hash_password
from backend.services.auth_service import create_access_token
from backend.services.chatbot_service import _build_recent_history_context


class ChatHistoryRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.headers = cls._build_auth_headers()

    @staticmethod
    def _build_auth_headers() -> dict[str, str]:
        email = "regression_chat_user@example.com"
        password = "RegressionPass#123"

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    username="regression_chat_user",
                    email=email,
                    hashed_password=hash_password(password),
                    role="user",
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            token = create_access_token({"sub": user.email})

        return {"Authorization": f"Bearer {token}"}

    def test_build_recent_history_context_trims_and_filters_roles(self):
        history = [
            {"role": "user", "content": "  hello   there  "},
            {"role": "bot", "content": "  Hi!  How can I help?  "},
            {"role": "system", "content": "ignored"},
            {"role": "user", "content": "   "},
        ]

        context = _build_recent_history_context(history)

        self.assertIn("USER: hello there", context)
        self.assertIn("BOT: Hi! How can I help?", context)
        self.assertNotIn("SYSTEM", context)
        self.assertNotIn("ignored", context)

    def test_chat_second_turn_history_path_no_name_error(self):
        # Disable LLM branch so this test is deterministic and offline-safe.
        with (
            patch("backend.services.chatbot_service._is_llm_enabled", return_value=False),
            patch("backend.services.chatbot_service.semantic_faq_search", return_value=None),
        ):
            first = self.client.post(
                "/chat",
                json={"message": "Tell me fee structure for CSE"},
                headers=self.headers,
            )
            self.assertEqual(first.status_code, 200, first.text)

            conversation_id = first.json().get("conversation_id")
            self.assertIsNotNone(conversation_id)

            second = self.client.post(
                "/chat",
                json={
                    "message": "How to apply for admission?",
                    "conversation_id": int(conversation_id),
                },
                headers=self.headers,
            )

            self.assertEqual(second.status_code, 200, second.text)
            payload = second.json()
            self.assertIn("reply", payload)
            self.assertIn("suggestions", payload)
            self.assertIsInstance(payload.get("suggestions"), list)


if __name__ == "__main__":
    unittest.main()
