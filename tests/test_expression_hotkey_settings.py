import unittest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from app.models.client_settings_model import ClientSettingsModel
from app.services import client_settings


class ExpressionHotkeySettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_hotkeys_are_saved_in_the_owning_accounts_settings_json(self):
        bindings = {"vrm:catMouth": "Shift+KeyC", "live2d:smile": "F8"}
        payload = ClientSettingsModel(expression_hotkeys=bindings).model_dump(exclude_none=True)
        with (
            patch.object(client_settings, "load_effective_settings", new=AsyncMock(return_value={})),
            patch.object(client_settings, "upsert_user_settings", new=AsyncMock()) as store,
        ):
            result = await client_settings.save_effective_settings(payload, user_id="account-a")
        self.assertEqual(result["expression_hotkeys"], bindings)
        self.assertEqual(store.await_args.args[0], "account-a")
        self.assertEqual(store.await_args.args[1]["expression_hotkeys"], bindings)

    async def test_empty_dictionary_removes_all_bindings(self):
        with (
            patch.object(client_settings, "load_effective_settings", new=AsyncMock(return_value={"expression_hotkeys": {"vrm:happy": "F8"}})),
            patch.object(client_settings, "upsert_user_settings", new=AsyncMock()) as store,
        ):
            await client_settings.save_effective_settings({"expression_hotkeys": {}}, user_id="account-a")
        self.assertEqual(store.await_args.args[1]["expression_hotkeys"], {})

    def test_rejects_oversized_bindings(self):
        with self.assertRaises(ValidationError):
            ClientSettingsModel(expression_hotkeys={"vrm:happy": "x" * 81})
        with self.assertRaises(ValidationError):
            ClientSettingsModel(expression_hotkeys={str(i): "F8" for i in range(257)})
