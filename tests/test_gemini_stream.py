import json
import unittest
from unittest.mock import patch

from app.controllers.http.gemini_router import gemini_stream
from app.core.security.clerk import ClerkUser
from app.models.message_model import MessageModel


class GeminiStreamReactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_done_event_contains_reaction_decision_and_clean_message(self):
        async def fake_stream(message, user_id, stream_result=None):
            if stream_result is not None:
                stream_result["reaction"] = True
                stream_result["emotion"] = "surprised"
            yield "Hola."

        with patch("app.controllers.http.gemini_router.stream_sandy_shandrew", fake_stream):
            response = await gemini_stream(
                MessageModel(message="hola"),
                ClerkUser(user_id="user-1", session_id=None, claims={}),
            )
            body = "".join([chunk async for chunk in response.body_iterator])

        done_frame = next(frame for frame in body.split("\n\n") if frame.startswith("event: done"))
        payload = json.loads(next(line[6:] for line in done_frame.splitlines() if line.startswith("data:")))

        self.assertEqual(payload["message"], "Hola.")
        self.assertIs(payload["reaction"], True)
        self.assertEqual(payload["emotion"], "surprised")


    async def test_reply_streamer_extracts_emotion_marker_without_speaking_it(self):
        from app.services.gemini import ReplyStreamer

        streamer = ReplyStreamer()
        streamer.feed("Me alegra verte. [[REACTION:surprised]]")
        streamer.close()

        self.assertEqual(streamer.full_text, "Me alegra verte.")
        self.assertIs(streamer.reaction, True)
        self.assertEqual(streamer.emotion, "surprised")

    async def test_reply_streamer_strips_a_none_marker_and_returns_no_emotion(self):
        from app.services.gemini import ReplyStreamer

        streamer = ReplyStreamer()
        streamer.feed("No hace falta reaccionar. [[REACTION:none]]")
        streamer.close()

        self.assertEqual(streamer.full_text, "No hace falta reaccionar.")
        self.assertIs(streamer.reaction, False)
        self.assertIsNone(streamer.emotion)


if __name__ == "__main__":
    unittest.main()
