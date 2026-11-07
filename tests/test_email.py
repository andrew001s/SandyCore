import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.config import config
from app.services.email import send_email


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"id": "email-test-001"}


class EmailTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_generic_sandy_studio_sender(self):
        with patch.multiple(
            config,
            RESEND_API_KEY="re_test",
            RESEND_FROM_EMAIL="hello@sandystudio.net",
            RESEND_FROM_NAME="Sandy Studio",
        ), patch(
            "app.services.email.get_http_client"
        ) as client:
            client.return_value.post = AsyncMock(return_value=FakeResponse())
            result = await send_email(
                ["user@example.com"], "Código de Sandy", "<p>Tu código</p>"
            )
        self.assertEqual(result, "email-test-001")
        payload = client.return_value.post.call_args.kwargs["json"]
        self.assertEqual(payload["from"], "Sandy Studio <hello@sandystudio.net>")

    async def test_requires_resend_configuration(self):
        with patch.object(config, "RESEND_API_KEY", ""):
            with self.assertRaises(HTTPException) as error:
                await send_email(["user@example.com"], "Asunto", "<p>Hola</p>")
        self.assertEqual(error.exception.status_code, 503)
