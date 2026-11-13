import json
import unittest
from unittest.mock import AsyncMock, patch

from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.domain.automatic_reactions import REACTION_EMOTIONS


class EventSubReactionPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.websocket = AsyncMock()
        self.use_case = EventSubUseCase(self.websocket)
        self.settings_patch = patch(
            "app.core.use_cases.eventsub_use_case.load_effective_settings",
            new=AsyncMock(return_value={}),
        )
        self.load_settings = self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    async def test_subscription_events_reject_disabled_emotions_in_every_format(self):
        for scope in ("pngtuber", "live2d", "vrm"):
            for event_kind in ("reaction", "speech"):
                with self.subTest(scope=scope, event_kind=event_kind):
                    self.load_settings.return_value = {
                        "automatic_reaction_scope": scope,
                        "automatic_reaction_mappings": {
                            f"{scope}:happy": json.dumps({"enabled": False, "expressions": ["smile"]})
                        },
                    }
                    await self.use_case.handle_events(event_kind, "subscription", "Gracias por suscribirte.", user_id="account-a")
                    payload, user_id = self.websocket.broadcast_message.call_args.args
                    self.assertIs(payload["reaction"], False)
                    self.assertIsNone(payload["emotion"])
                    self.assertIsNone(payload["expression"])
                    self.assertIsNone(payload["gesture"])
                    self.assertEqual(payload["mouth"]["smile"], 0)
                    self.assertEqual(payload["text"], "Gracias por suscribirte.")
                    self.assertEqual(payload["metadata"]["source"], "eventsub")
                    self.assertEqual(user_id, "account-a")
                    self.load_settings.assert_awaited_with("account-a")

    async def test_enabled_subscription_emotions_keep_existing_behavior(self):
        await self.use_case.handle_events("reaction", "subscription", "Gracias por suscribirte.", user_id="account-a")
        payload = self.websocket.broadcast_message.call_args.args[0]
        self.assertEqual(payload["emotion"], "happy")
        self.assertEqual(payload["expression"], "happy")
        self.assertNotIn("reaction", payload)

    async def test_disabling_all_emotions_also_blocks_the_default_reaction(self):
        self.load_settings.return_value = {"automatic_reaction_mappings": {
            f"pngtuber:{emotion}": '{"expressions":[],"enabled":false}'
            for emotion in REACTION_EMOTIONS
        }}
        await self.use_case.handle_events("reaction", "subscription", "Un nuevo evento.", user_id="account-a")
        payload = self.websocket.broadcast_message.call_args.args[0]
        self.assertFalse(payload["reaction"])
        self.assertIsNone(payload["emotion"])
        self.assertIsNone(payload["expression"])

    async def test_disabled_emotion_in_another_format_does_not_block_active_format(self):
        self.load_settings.return_value = {
            "automatic_reaction_scope": "pngtuber",
            "automatic_reaction_mappings": {"vrm:happy": '{"enabled":false}'},
        }
        await self.use_case.handle_events("reaction", "subscription", "Gracias.", user_id="account-a")
        self.assertEqual(self.websocket.broadcast_message.call_args.args[0]["emotion"], "happy")

    async def test_trigger_graph_events_are_forwarded_without_emotion_filtering(self):
        await self.use_case.publish_avatar_trigger("subscribe", {"viewer": "someone"}, user_id="account-a")
        payload, user_id = self.websocket.broadcast_message.call_args.args
        self.assertEqual(payload["type"], "avatar_trigger")
        self.assertEqual(payload["trigger"], "subscribe")
        self.assertEqual(user_id, "account-a")
        self.load_settings.assert_not_awaited()
