import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.adapters.openrouter_adapter import OpenRouterAdapter
from app.domain.ai_errors import AIProviderError, EMPTY_RESPONSE


class OpenRouterAdapterTests(unittest.IsolatedAsyncioTestCase):
    @patch("openai.AsyncOpenAI")
    async def test_empty_choices_raise_without_retrying(self, client_factory):
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(choices=[])))
            )
        )
        client_factory.return_value = client
        adapter = OpenRouterAdapter(api_key="test-key", model="test/model")

        with self.assertRaises(AIProviderError) as raised:
            await adapter.generate_text("hello", "system", stop=["Sandy:"])

        self.assertEqual(raised.exception.code, EMPTY_RESPONSE)
        self.assertEqual(client.chat.completions.create.await_count, 1)
