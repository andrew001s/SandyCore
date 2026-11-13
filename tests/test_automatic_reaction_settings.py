import unittest
from unittest.mock import AsyncMock, patch

from app.models.client_settings_model import ClientSettingsModel
from app.services import client_settings


class AutomaticReactionSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_mappings_pass_from_request_model_to_persisted_settings(self):
        mappings = {"happy": "smile-expression"}
        payload = ClientSettingsModel(
            automatic_reaction_mappings=mappings
        ).model_dump(exclude_none=True)
        stored_settings = {}

        with (
            patch.object(
                client_settings, "load_effective_settings", new=AsyncMock(return_value={})
            ),
            patch.object(
                client_settings,
                "upsert_user_settings",
                new=AsyncMock(side_effect=lambda _user_id, settings: stored_settings.update(settings)),
            ),
        ):
            result = await client_settings.save_effective_settings(
                payload, user_id="account-a"
            )

        self.assertEqual(result["automatic_reaction_mappings"], mappings)
        self.assertEqual(stored_settings["automatic_reaction_mappings"], mappings)


if __name__ == "__main__":
    unittest.main()
