import unittest
from unittest.mock import AsyncMock, patch

from app.core.use_cases.chat_use_case import ChatUseCase


class RecordingWebsocket:
    def __init__(self):
        self.payload = None
        self.user_id = None

    async def broadcast_message(self, payload, user_id):
        self.payload = payload
        self.user_id = user_id


class ChatReactionEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = patch(
            "app.core.use_cases.chat_use_case.load_effective_settings",
            new=AsyncMock(return_value={}),
        )
        self.load_settings = self.settings.start()
        self.addCleanup(self.settings.stop)

    async def test_disabled_emotion_is_rejected_without_heuristic_fallback(self):
        self.load_settings.return_value = {
            "automatic_reaction_scope": "live2d",
            "automatic_reaction_mappings": {
                "live2d:angry": '{"expressions":["frown"],"enabled":false}'
            },
        }
        websocket = RecordingWebsocket()
        await ChatUseCase(websocket).process_chunk(
            "Estoy furiosa! [[REACTION:angry]]", messages=[], user_id="user-1"
        )
        self.assertFalse(websocket.payload["reaction"])
        self.assertIsNone(websocket.payload["emotion"])
        self.assertIsNone(websocket.payload["expression"])
        self.assertEqual(websocket.payload["text"], "Estoy furiosa!")

    async def test_twitch_chat_avatar_event_carries_decision_and_clean_speech(self):
        websocket = RecordingWebsocket()
        use_case = ChatUseCase(websocket)

        await use_case.process_chunk(
            "Hola, qué sorpresa. [[REACTION:surprised]]",
            messages=["viewer: hola"],
            user_id="user-1",
        )

        self.assertEqual(websocket.payload["text"], "Hola, qué sorpresa.")
        self.assertEqual(websocket.payload["emotion"], "surprised")
        self.assertIs(websocket.payload["reaction"], True)
        self.assertEqual(websocket.payload["metadata"]["response"], "Hola, qué sorpresa.")
        self.assertEqual(websocket.user_id, "user-1")

    async def test_missing_reaction_decision_is_sent_as_no_reaction(self):
        websocket = RecordingWebsocket()
        use_case = ChatUseCase(websocket)

        await use_case.process_chunk(
            "Hola, ¿cómo estás?",
            messages=["viewer: hola"],
            user_id="user-1",
        )

        self.assertIs(websocket.payload["reaction"], False)
        self.assertIsNone(websocket.payload["expression"])

    async def test_explicit_none_marker_remains_no_reaction_without_expression(self):
        websocket = RecordingWebsocket()
        use_case = ChatUseCase(websocket)

        await use_case.process_chunk(
            "Hola. [[REACTION:none]]",
            messages=["viewer: hola"],
            user_id="user-1",
        )

        self.assertIs(websocket.payload["reaction"], False)
        self.assertIsNone(websocket.payload["expression"])


if __name__ == "__main__":
    unittest.main()
