import unittest

from app.domain.prompts import build_prompt_bundle


class PromptReactionTests(unittest.TestCase):
    def test_primary_vtuber_prompt_requests_supported_emotion_or_none(self):
        prompt = build_prompt_bundle({})["vtuber_shandrew"]

        self.assertIn("[[REACTION:none]]", prompt)
        self.assertIn("happy, sad, angry, surprised, excited, sleepy, thinking, confused, shy", prompt)
        self.assertIn("[[REACTION:none]] es la opción habitual", prompt)
        self.assertIn("No añadas una emoción por defecto", prompt)

    def test_chat_vtuber_prompt_requests_supported_emotion_or_none(self):
        prompt = build_prompt_bundle({})["vtuber"]

        self.assertIn("[[REACTION:none]]", prompt)
        self.assertIn("happy, sad, angry, surprised, excited, sleepy, thinking, confused, shy", prompt)
        self.assertIn("[[REACTION:none]] es la opción habitual", prompt)
        self.assertIn("No añadas una emoción por defecto", prompt)


if __name__ == "__main__":
    unittest.main()
