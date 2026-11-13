import json
import unittest
from unittest.mock import AsyncMock, patch

from app.domain.automatic_reactions import (
    REACTION_EMOTIONS, allowed_reaction_emotions, filter_reaction_decision, reaction_instruction,
)
from app.domain.prompts import build_prompt_bundle
from app.services.gemini import ReplyStreamer
from app.models.client_settings_model import ClientSettingsModel
from app.services import client_settings


class AutomaticReactionPolicyTests(unittest.TestCase):
    def test_disabled_emotions_are_excluded_only_in_the_active_format(self):
        for scope in ("pngtuber", "live2d", "vrm"):
            with self.subTest(scope=scope):
                settings = {
                    "automatic_reaction_scope": scope,
                    "automatic_reaction_mappings": {
                        f"{scope}:angry": json.dumps({"enabled": False, "expressions": ["frown"]}),
                    },
                }
                self.assertNotIn("angry", allowed_reaction_emotions(settings))
                self.assertIn("happy", allowed_reaction_emotions(settings))
                other = "live2d" if scope == "pngtuber" else "pngtuber"
                self.assertIn("angry", allowed_reaction_emotions({**settings, "automatic_reaction_scope": other}))

    def test_legacy_and_empty_mappings_remain_enabled(self):
        self.assertEqual(allowed_reaction_emotions({}), REACTION_EMOTIONS)
        self.assertIn("happy", allowed_reaction_emotions({"automatic_reaction_mappings": {"happy": "smile"}}))

    def test_both_chat_prompts_offer_only_enabled_emotions(self):
        settings = {"automatic_reaction_mappings": {"pngtuber:angry": '{"enabled":false}'}}
        for key in ("vtuber", "vtuber_shandrew"):
            prompt = build_prompt_bundle(settings)[key]
            allowed = prompt.split("Emociones permitidas: ")[1].split(".")[0].split(", ")
            self.assertNotIn("angry", allowed)
            self.assertIn("happy", allowed)
            self.assertIn("No analices, infieras ni selecciones", prompt)

    def test_disabling_every_emotion_forces_none(self):
        settings = {"automatic_reaction_mappings": {f"pngtuber:{emotion}": '{"enabled":false}' for emotion in REACTION_EMOTIONS}}
        self.assertEqual(allowed_reaction_emotions(settings), ())
        self.assertIn("Termina siempre con [[REACTION:none]]", reaction_instruction(settings))
        self.assertEqual(filter_reaction_decision(True, "happy", settings), (False, None))

    def test_streaming_rejects_disabled_emotions_even_across_chunks(self):
        streamer = ReplyStreamer(allowed_emotions=("happy",))
        for part in ("Hola. [[REA", "CTION:an", "gry]]"):
            streamer.feed(part)
        streamer.close()
        self.assertFalse(streamer.reaction)
        self.assertIsNone(streamer.emotion)
        self.assertEqual(streamer.full_text, "Hola.")

    def test_streaming_still_accepts_enabled_emotions(self):
        streamer = ReplyStreamer(allowed_emotions=("happy",))
        streamer.feed("Hola. [[REACTION:happy]]")
        streamer.close()
        self.assertTrue(streamer.reaction)
        self.assertEqual(streamer.emotion, "happy")

    def test_final_validation_rejects_an_emotion_disabled_during_generation(self):
        self.assertEqual(filter_reaction_decision(True, "happy", {}), (True, "happy"))
        settings = {"automatic_reaction_mappings": {"pngtuber:happy": '{"enabled":false}'}}
        self.assertEqual(filter_reaction_decision(True, "happy", settings), (False, None))


class AutomaticReactionPolicyPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_saves_active_format_and_disabled_emotion_with_its_expressions(self):
        mappings = {"vrm:angry": json.dumps({"expressions": ["frown"], "intensity": .6, "enabled": False})}
        payload = ClientSettingsModel(automatic_reaction_scope="vrm", automatic_reaction_mappings=mappings).model_dump(exclude_none=True)
        saved = {}
        with (
            patch.object(client_settings, "load_effective_settings", new=AsyncMock(return_value={})),
            patch.object(client_settings, "upsert_user_settings", new=AsyncMock(side_effect=lambda _user, settings: saved.update(settings))),
        ):
            await client_settings.save_effective_settings(payload, user_id="account-a")
        self.assertEqual(saved["automatic_reaction_scope"], "vrm")
        self.assertEqual(saved["automatic_reaction_mappings"], mappings)
