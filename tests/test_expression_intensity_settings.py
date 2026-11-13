import unittest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from app.models.client_settings_model import ClientSettingsModel
from app.services import client_settings

class ExpressionIntensitySettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_individual_intensities_are_persisted_with_the_owning_accounts_settings(self):
        intensities = {"vrm:catMouth": 0.25, "vrm:earsUp": 0.85, "live2d:blush": 0.4}
        payload = ClientSettingsModel(expression_intensities=intensities).model_dump(exclude_none=True)
        with (
            patch.object(client_settings, "load_effective_settings", new=AsyncMock(return_value={"expression_hotkeys": {"vrm:catMouth": "F8"}})),
            patch.object(client_settings, "upsert_user_settings", new=AsyncMock()) as store,
        ):
            await client_settings.save_effective_settings(payload, user_id="account-a")
        self.assertEqual(store.await_args.args[0], "account-a")
        self.assertEqual(store.await_args.args[1]["expression_intensities"], intensities)
        self.assertEqual(store.await_args.args[1]["expression_hotkeys"], {"vrm:catMouth": "F8"})

    def test_rejects_out_of_range_and_non_finite_values(self):
        for value in [-0.1, 1.1, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ClientSettingsModel(expression_intensities={"vrm:happy": value})
        self.assertEqual(ClientSettingsModel(expression_intensities={"vrm:happy": 0}).expression_intensities, {"vrm:happy": 0})
