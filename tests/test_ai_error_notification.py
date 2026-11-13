import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.controllers.websocket.websocket_server import manager
from app.domain.ai_errors import AIProviderError, INSUFFICIENT_CREDITS
from app.services.gemini import response_gemini_events, response_gemini_rewards, response_sandy


class AiErrorNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_broadcast_still_delivers_to_websocket_then_stream(self):
        owner = await manager.connect_stream("user-1")

        async def send(message):
            self.assertTrue(owner.empty())
            self.assertEqual(message["type"], "speech")

        socket = SimpleNamespace(accept=AsyncMock(), send_json=AsyncMock(side_effect=send))
        await manager.connect(socket, "user-1")
        try:
            await manager.broadcast({"type": "speech"}, "user-1")
            socket.send_json.assert_awaited_once_with({"type": "speech"})
            self.assertEqual((await owner.get())["type"], "speech")
        finally:
            await manager.disconnect_stream(owner, "user-1")
            await manager.disconnect(socket, "user-1")

    async def test_stalled_websocket_does_not_block_the_users_sse_notification(self):
        class StalledSocket:
            async def accept(self):
                return None

            async def send_json(self, _message):
                await asyncio.Event().wait()

        owner = await manager.connect_stream("user-1")
        socket = StalledSocket()
        await manager.connect(socket, "user-1")
        failure = AIProviderError(INSUFFICIENT_CREDITS, provider="openrouter")
        task = None
        try:
            with (
                patch("app.services.gemini.load_effective_settings", new=AsyncMock(return_value={})),
                patch("app.services.gemini.build_prompt_bundle", return_value={"vtuber": "prompt"}),
                patch("app.services.gemini.persona_name", return_value="Sandy"),
                patch("app.services.gemini.client_gemini", new=AsyncMock(side_effect=failure)),
            ):
                task = asyncio.create_task(response_sandy("hello", "user-1"))
                event = await asyncio.wait_for(owner.get(), timeout=0.2)
                self.assertEqual(event["metadata"]["error"]["code"], INSUFFICIENT_CREDITS)
                with self.assertRaises(AIProviderError) as caught:
                    await task
                self.assertIs(caught.exception, failure)
        finally:
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await manager.disconnect_stream(owner, "user-1")
            await manager.disconnect(socket, "user-1")

    async def test_provider_error_is_sent_only_to_the_affected_user(self):
        owner = await manager.connect_stream("user-1")
        other = await manager.connect_stream("user-2")
        failure = AIProviderError(
            INSUFFICIENT_CREDITS,
            provider="openrouter",
            detail="private provider detail",
        )
        try:
            with (
                patch("app.services.gemini.load_effective_settings", new=AsyncMock(return_value={})),
                patch(
                    "app.services.gemini.build_prompt_bundle",
                    return_value={"vtuber": "prompt", "events": "prompt", "rewards": "prompt"},
                ),
                patch("app.services.gemini.persona_name", return_value="Sandy"),
                patch("app.services.gemini.client_gemini", new=AsyncMock(side_effect=failure)),
            ):
                for generate in (response_sandy, response_gemini_events, response_gemini_rewards):
                    with self.subTest(generate=generate.__name__):
                        with self.assertRaises(AIProviderError) as caught:
                            await generate("hello", "user-1")

                        self.assertIs(caught.exception, failure)
                        event = await asyncio.wait_for(owner.get(), timeout=0.2)
                        self.assertEqual(event["type"], "system")
                        self.assertEqual(event["metadata"]["source"], "ai_error")
                        self.assertEqual(
                            event["metadata"]["error"],
                            {"code": INSUFFICIENT_CREDITS, "provider": "openrouter"},
                        )
                        self.assertNotIn("private provider detail", str(event))
                        self.assertTrue(other.empty())
        finally:
            await manager.disconnect_stream(owner, "user-1")
            await manager.disconnect_stream(other, "user-2")

    async def test_notification_failure_does_not_replace_the_provider_error(self):
        failure = AIProviderError(INSUFFICIENT_CREDITS, provider="openrouter")
        with (
            patch("app.services.gemini.load_effective_settings", new=AsyncMock(return_value={})),
            patch("app.services.gemini.build_prompt_bundle", return_value={"vtuber": "prompt"}),
            patch("app.services.gemini.persona_name", return_value="Sandy"),
            patch("app.services.gemini.client_gemini", new=AsyncMock(side_effect=failure)),
            patch(
                "app.services.gemini.WebsocketAdapter.broadcast_message",
                new=AsyncMock(side_effect=RuntimeError("stream unavailable")),
            ),
        ):
            with self.assertRaises(AIProviderError) as caught:
                await response_sandy("hello", "user-1")
        self.assertIs(caught.exception, failure)

    async def test_missing_user_never_broadcasts_to_an_inferred_recipient(self):
        failure = AIProviderError(INSUFFICIENT_CREDITS, provider="openrouter")
        with (
            patch("app.services.gemini.get_active_user_id", return_value="another-user"),
            patch("app.services.gemini.load_effective_settings", new=AsyncMock(return_value={})),
            patch("app.services.gemini.build_prompt_bundle", return_value={"vtuber": "prompt"}),
            patch("app.services.gemini.persona_name", return_value="Sandy"),
            patch("app.services.gemini.client_gemini", new=AsyncMock(side_effect=failure)),
            patch("app.services.gemini.WebsocketAdapter.broadcast_message", new=AsyncMock()) as send,
        ):
            with self.assertRaises(AIProviderError):
                await response_sandy("hello")
        send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
