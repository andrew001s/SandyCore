import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.services import support_billing as billing
from app.controllers.http.support_router import router
from app.core.security.clerk import ClerkUser, verify_clerk_session

SETTINGS = dict(
    KOFI_WATERMARK_ENABLED=True,
    KOFI_WATERMARK_PRODUCT_CODE="product001",
    KOFI_VERIFICATION_TOKEN="test-verification-token-123",
    SUPPORT_BILLING_SECRET="test-billing-key-not-a-real-secret-12345",
    SUPPORT_OVERLAY_SECRET="test-overlay-key-not-a-real-secret-12345",
    CLERK_SECRET_KEY="test-clerk-key",
    KOFI_TEST_ENDPOINT_ENABLED=True,
    KOFI_TEST_EMAIL="tester@sandystudio.net",
    SUPPORT_TEST_REDEEM_ENABLED=False,
    SUPPORT_TEST_REDEEM_CODE="",
    SANDY_ENVIRONMENT="staging",
    RESEND_API_KEY="test-resend-api-key",
    RESEND_FROM_EMAIL="hello@sandystudio.net",
    RESEND_FROM_NAME="Sandy Studio",
)
USER = ClerkUser("account-a", "session-a", {})
FREE = {"watermark_free": False, "state": "free"}


def kofi_shop_test_payload(**changes):
    data = dict(
        verification_token=SETTINGS["KOFI_VERIFICATION_TOKEN"],
        message_id="d568b5fe-0cdb-4327-8c74-8a180def0426",
        timestamp="2026-11-07T20:48:19Z",
        type="Shop Order",
        is_public=True,
        from_name="Jo Example",
        message=None,
        amount="27.95",
        url="https://ko-fi.com/Home/CoffeeShop?txid=00000000-1111-2222-3333-444444444444",
        email="jo.example@example.com",
        currency="USD",
        is_subscription_payment=False,
        is_first_subscription_payment=False,
        kofi_transaction_id="00000000-1111-2222-3333-444444444444",
        shop_items=[
            {"direct_link_code": "1a2b3c4d5e", "variation_name": "Blue", "quantity": 1},
            {
                "direct_link_code": "a1b2c3d4e5",
                "variation_name": "Large",
                "quantity": 5,
            },
        ],
        tier_name=None,
        shipping={"full_name": "Ko-fi Mail Room"},
        discord_username="Jo#4105",
        discord_userid="012345678901234567",
    )
    return {**data, **changes}


def payment(**changes):
    data = dict(
        verification_token=SETTINGS["KOFI_VERIFICATION_TOKEN"],
        type="Shop Order",
        shop_items=[{"direct_link_code": "product001", "quantity": 1}],
        kofi_transaction_id="payment-001",
        message_id="message-001",
        email="andresroman45678@gmail.com",
        amount="3.00",
        currency="USD",
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_subscription_payment=False,
    )
    return {**data, **changes}


class BillingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = patch.multiple(billing.config, **SETTINGS)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        billing._REQUEST_WINDOWS.clear()

    def test_confirmed_payload_minimizes_stored_personal_data(self):
        record = billing.validate_webhook(payment())
        self.assertEqual(record["state"], "confirmed")
        self.assertEqual(record["amount_cents"], 300)
        self.assertNotIn("email", record)
        self.assertNotIn("verification_token", record)
        self.assertEqual(
            record["email_hash"], billing.private_hash("andresroman45678@gmail.com")
        )

    def test_unrelated_payments_do_not_grant_a_purchase(self):
        self.assertIsNone(billing.validate_webhook(payment(type="Donation")))
        self.assertIsNone(
            billing.validate_webhook(
                payment(shop_items=[{"direct_link_code": "different"}])
            )
        )

    def test_shared_secret_checked_before_payment_fields(self):
        with self.assertRaises(HTTPException) as error:
            billing.validate_webhook({"verification_token": "incorrect"})
        self.assertEqual(error.exception.status_code, 401)

    def test_unexpected_currency_amount_quantity_and_subscription_require_review(self):
        for changes in [
            {"currency": "EUR"},
            {"amount": "2.99"},
            {"shop_items": [{"direct_link_code": "product001", "quantity": 2}]},
            {"shop_items": [{"direct_link_code": "product001", "quantity": True}]},
            {"is_subscription_payment": True},
        ]:
            with self.subTest(changes=changes):
                self.assertEqual(
                    billing.validate_webhook(payment(**changes))["state"], "review"
                )

    def test_invalid_values_are_rejected(self):
        for changes in [
            {"amount": "NaN"},
            {"amount": "Infinity"},
            {"amount": "3.001"},
            {"email": "invalid"},
            {"timestamp": "tomorrow"},
            {"timestamp": "2999-01-01T00:00:00Z"},
            {"message_id": "<script>"},
        ]:
            with self.subTest(changes=changes):
                with self.assertRaises(HTTPException) as error:
                    billing.validate_webhook(payment(**changes))
                self.assertEqual(error.exception.status_code, 400)

    async def test_disabled_feature_never_queries_payments(self):
        with patch.object(
            billing.config, "KOFI_WATERMARK_ENABLED", False
        ), patch.object(billing, "rpc", new_callable=AsyncMock) as rpc:
            result = await billing.status(USER)
        self.assertFalse(result["available"])
        self.assertFalse(result["watermark_free"])
        rpc.assert_not_awaited()

    async def test_checkout_uses_verified_email_when_available(self):
        with patch.object(
            billing, "rpc", new_callable=AsyncMock, return_value=FREE
        ) as rpc, patch.object(
            billing,
            "verified_emails",
            new_callable=AsyncMock,
            return_value=["verified@example.com"],
        ):
            result = await billing.checkout(USER)
        self.assertEqual(result["checkout_url"], "https://ko-fi.com/s/product001")
        rpc.assert_any_await(
            "support_start_checkout",
            p_user_id="account-a",
            p_email_hash=billing.private_hash("verified@example.com"),
        )

    async def test_webhook_issues_and_emails_code_only_for_new_confirmed_payment(self):
        responses = [{"recorded": True}, {"send_required": True}, {"marked": True}]
        with patch.object(
            billing, "rpc", new_callable=AsyncMock, side_effect=responses
        ) as rpc, patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            result = await billing.webhook(payment())
        self.assertEqual(result, {"accepted": True})
        self.assertEqual(rpc.await_args_list[1].args, ("support_issue_license_code",))
        self.assertEqual(send.await_count, 1)
        self.assertEqual(send.await_args.args[0], ["andresroman45678@gmail.com"])
        self.assertRegex(send.await_args.args[1], "Sandy Studio Plus")
        self.assertRegex(
            send.await_args.kwargs["text"], r"SANDY-[A-Z2-9]{4}(?:-[A-Z2-9]{4}){3}"
        )

    async def test_kofi_shop_order_test_creates_marked_test_payment_and_sends_to_fixed_staging_email(
        self,
    ):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            side_effect=[{"recorded": True}, {"send_required": True}, {"marked": True}],
        ) as rpc, patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            result = await billing.test_webhook(kofi_shop_test_payload())
        self.assertEqual(
            result,
            {"accepted": True, "test": True, "email_submitted": True},
        )
        recorded = rpc.await_args_list[0].kwargs["p_payment"]
        self.assertTrue(recorded["is_test"])
        self.assertEqual(recorded["amount_cents"], 300)
        self.assertEqual(recorded["product_code"], "product001")
        self.assertNotIn("jo.example@example.com", str(recorded))
        self.assertEqual(send.await_args.args[0], ["tester@sandystudio.net"])
        self.assertRegex(
            send.await_args.kwargs["text"], r"SANDY-[A-Z2-9]{4}(?:-[A-Z2-9]{4}){3}"
        )

    async def test_license_email_flow_rejects_database_rpc_without_send_status(self):
        with patch.object(
            billing, "rpc", new_callable=AsyncMock, return_value={"created": True}
        ), patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            with self.assertRaises(HTTPException) as error:
                await billing.issue_and_send_license("test-transaction", "test@example.com")
        self.assertEqual(error.exception.status_code, 503)
        send.assert_not_awaited()

    async def test_staging_test_code_creates_test_payment_and_uses_normal_status(self):
        test_code = "SANDY-TEST-CODE-ONLY-1234"
        with (
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_ENABLED", True),
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_CODE", test_code),
            patch.object(billing, "verified_emails", new_callable=AsyncMock, return_value=["tester@example.com"]),
            patch.object(billing, "status", new_callable=AsyncMock, side_effect=[FREE, {"watermark_free": True, "state": "active"}]) as status,
            patch.object(billing, "rpc", new_callable=AsyncMock, return_value={"recorded": True}) as rpc,
        ):
            result = await billing.redeem_license_code(USER, test_code)

        self.assertTrue(result["watermark_free"])
        self.assertTrue(rpc.await_args.kwargs["p_payment"]["is_test"])
        self.assertEqual(rpc.await_args.kwargs["p_payment"]["amount_cents"], 300)
        self.assertEqual(rpc.await_args.kwargs["p_payment"]["email_hash"], billing.private_hash("tester@example.com"))
        self.assertEqual(status.await_args.args[1], rpc.await_args.kwargs["p_payment"]["transaction_id"])

    async def test_test_code_is_not_enabled_in_production(self):
        with (
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_ENABLED", True),
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_CODE", "SANDY-TEST-CODE-ONLY-1234"),
            patch.object(billing.config, "SANDY_ENVIRONMENT", "production"),
            patch.object(billing, "rpc", new_callable=AsyncMock, return_value={"redeemed": False}) as rpc,
        ):
            with self.assertRaises(HTTPException) as error:
                await billing.redeem_license_code(USER, "SANDY-TEST-CODE-ONLY-1234")

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(rpc.await_args.args, ("support_redeem_license_code",))

    async def test_test_code_requires_a_verified_email_even_for_an_active_account(self):
        with (
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_ENABLED", True),
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_CODE", "SANDY-TEST-CODE-ONLY-1234"),
            patch.object(billing, "verified_emails", new_callable=AsyncMock, return_value=[]),
            patch.object(billing, "rpc", new_callable=AsyncMock) as rpc,
        ):
            with self.assertRaises(HTTPException) as error:
                await billing.redeem_license_code(USER, "SANDY-TEST-CODE-ONLY-1234")
        self.assertEqual(error.exception.status_code, 409)
        rpc.assert_not_awaited()

    async def test_test_code_requires_a_session(self):
        with patch.object(billing, "rpc", new_callable=AsyncMock) as rpc:
            with self.assertRaises(HTTPException) as error:
                await billing.redeem_license_code(ClerkUser("account-a", None, {}), "SANDY-TEST-CODE-ONLY-1234")
        self.assertEqual(error.exception.status_code, 401)
        rpc.assert_not_awaited()

    def test_test_code_requires_explicit_enablement_and_an_allowed_environment(self):
        for environment in ("development", "test", "staging", "production", "", "preview"):
            for enabled in (False, True):
                with self.subTest(environment=environment, enabled=enabled), patch.multiple(
                    billing.config, SANDY_ENVIRONMENT=environment,
                    SUPPORT_TEST_REDEEM_ENABLED=enabled,
                    SUPPORT_TEST_REDEEM_CODE="SANDY-TEST-CODE-ONLY-1234",
                ):
                    self.assertEqual(billing.support_test_code_enabled(), enabled and environment in {"development", "test", "staging"})
        with patch.multiple(billing.config, SUPPORT_TEST_REDEEM_ENABLED=True, SUPPORT_TEST_REDEEM_CODE=""):
            self.assertFalse(billing.support_test_code_enabled())

    async def test_disabled_test_code_uses_normal_redemption_without_synthetic_payment(self):
        with (
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_CODE", "SANDY-TEST-CODE-ONLY-1234"),
            patch.object(billing, "rpc", new_callable=AsyncMock, return_value={"redeemed": False}) as rpc,
        ):
            with self.assertRaises(HTTPException) as error:
                await billing.redeem_license_code(USER, "SANDY-TEST-CODE-ONLY-1234")
        self.assertEqual(error.exception.status_code, 409)
        rpc.assert_awaited_once()
        self.assertEqual(rpc.await_args.args, ("support_redeem_license_code",))

    async def test_test_redemption_helper_refuses_production(self):
        with patch.object(billing.config, "SANDY_ENVIRONMENT", "production"), patch.object(billing, "rpc", new_callable=AsyncMock) as rpc:
            with self.assertRaises(HTTPException) as error:
                await billing.redeem_test_code(USER)
        self.assertEqual(error.exception.status_code, 404)
        rpc.assert_not_awaited()

    async def test_test_payment_links_to_authenticated_account_through_normal_status(self):
        async def store(name, **params):
            if name == "support_status":
                return {"watermark_free": bool(params.get("p_receipt_id")), "state": "active" if params.get("p_receipt_id") else "free"}
            return {"recorded": True}

        with (
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_ENABLED", True),
            patch.object(billing.config, "SUPPORT_TEST_REDEEM_CODE", "SANDY-TEST-CODE-ONLY-1234"),
            patch.object(billing, "verified_emails", new_callable=AsyncMock, return_value=["tester@example.com"]),
            patch.object(billing, "rpc", new_callable=AsyncMock, side_effect=store) as rpc,
            patch.object(billing, "send_email", new_callable=AsyncMock) as send,
        ):
            result = await billing.redeem_license_code(USER, " sandy-test-code-only-1234 ")
        self.assertTrue(result["watermark_free"])
        records = [c.kwargs["p_payment"] for c in rpc.await_args_list if c.args == ("support_record_payment",)]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["is_test"])
        rpc.assert_any_await("support_status", p_user_id="account-a", p_email_hashes=[billing.private_hash("tester@example.com")], p_receipt_id=records[0]["transaction_id"])
        send.assert_not_awaited()

    async def test_kofi_test_retries_same_fixture_without_resending_issued_code(self):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            side_effect=[
                {"recorded": True},
                {"send_required": True},
                {"marked": True},
                {"recorded": False},
                {"send_required": False},
            ],
        ) as rpc, patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            await billing.test_webhook(kofi_shop_test_payload())
            await billing.test_webhook(kofi_shop_test_payload())
        send.assert_awaited_once()
        first = rpc.await_args_list[0].kwargs["p_payment"]
        retry = rpc.await_args_list[3].kwargs["p_payment"]
        self.assertEqual(first["transaction_id"], retry["transaction_id"])
        self.assertEqual(first["message_id"], retry["message_id"])

    async def test_kofi_test_rejects_nonfixture_and_production_environment(self):
        payload = kofi_shop_test_payload(from_name="A real customer")
        with self.assertRaises(HTTPException) as error:
            await billing.test_webhook(payload)
        self.assertEqual(error.exception.status_code, 400)
        with patch.object(billing.config, "SANDY_ENVIRONMENT", "production"):
            with self.assertRaises(HTTPException) as error:
                await billing.test_webhook(kofi_shop_test_payload())
        self.assertEqual(error.exception.status_code, 404)

    async def test_webhook_replay_does_not_send_another_code(self):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            side_effect=[
                {"recorded": False},
                {"send_required": True},
                {"marked": True},
            ],
        ), patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            await billing.webhook(payment())
        send.assert_awaited_once()

    def test_license_email_contains_code_and_plain_text_fallback(self):
        html_body, text_body = billing.license_email("SANDY-ABCD-EFGH-IJKL-MNOP")
        self.assertIn("SANDY-ABCD-EFGH-IJKL-MNOP", html_body)
        self.assertIn("Código de activación", html_body)
        self.assertIn("SANDY-ABCD-EFGH-IJKL-MNOP", text_body)
        self.assertIn("Solo puede utilizarse una vez", text_body)

    async def test_owned_purchase_does_not_start_another_checkout(self):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            return_value={"watermark_free": True, "state": "active"},
        ) as rpc:
            self.assertTrue((await billing.checkout(USER))["already_owned"])
            self.assertEqual(rpc.await_count, 1)

    async def test_api_keys_cannot_purchase(self):
        with self.assertRaises(HTTPException) as error:
            await billing.status(ClerkUser("account-a", None, {}))
        self.assertEqual(error.exception.status_code, 401)

    async def test_restore_requires_both_receipt_and_current_verified_email(self):
        with patch.object(
            billing, "rpc", new_callable=AsyncMock, return_value=FREE
        ) as rpc, patch.object(
            billing,
            "verified_emails",
            new_callable=AsyncMock,
            return_value=["verified@example.com"],
        ):
            with self.assertRaises(HTTPException) as error:
                await billing.status(USER, "private-receipt-001")
        self.assertEqual(error.exception.status_code, 409)
        rpc.assert_awaited_with(
            "support_status",
            p_user_id="account-a",
            p_email_hashes=[billing.private_hash("verified@example.com")],
            p_receipt_id="private-receipt-001",
        )

    async def test_unverified_account_can_prepare_payment_for_code_flow(self):
        with patch.object(
            billing, "rpc", new_callable=AsyncMock, return_value=FREE
        ), patch.object(
            billing, "verified_emails", new_callable=AsyncMock, return_value=[]
        ):
            result = await billing.checkout(USER)
        self.assertEqual(result["checkout_url"], "https://ko-fi.com/s/product001")

    async def test_overlay_credential_is_read_only_and_tampering_never_queries_database(
        self,
    ):
        viewer = "12345678-1234-1234-1234-123456789abc"
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            return_value={"viewer_id": viewer, "revision": 1},
        ) as rpc:
            token = (await billing.overlay_key(USER))["token"]
            self.assertNotIn(USER.user_id, token)
            rpc.return_value = {"watermark_free": True}
            self.assertTrue((await billing.overlay_status(token))["watermark_free"])
            rpc.reset_mock()
            with self.assertRaises(HTTPException):
                await billing.overlay_status(
                    token[:-1] + ("A" if token[-1] != "A" else "B")
                )
            rpc.assert_not_awaited()

    async def test_verified_email_fetch_rejects_mismatched_clerk_account(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"id": "other-user", "email_addresses": []},
        )
        with patch.object(
            billing,
            "get_http_client",
            return_value=SimpleNamespace(get=AsyncMock(return_value=response)),
        ):
            with self.assertRaises(HTTPException):
                await billing.verified_emails(USER.user_id)

    def test_sensitive_actions_are_rate_limited(self):
        for _ in range(6):
            billing.limit_requests("restore:test", 6)
        with self.assertRaises(HTTPException) as error:
            billing.limit_requests("restore:test", 6)
        self.assertEqual(error.exception.status_code, 429)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.multiple(billing.config, **SETTINGS)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        billing._REQUEST_WINDOWS.clear()
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_checkout_requires_authentication(self):
        self.assertEqual(
            self.client.post("/support/checkout", json={}).status_code, 401
        )

    def test_redeem_requires_authentication(self):
        self.assertEqual(self.client.post("/support/redeem", json={"code": "SANDY-TEST-CODE-ONLY-1234"}).status_code, 401)

    def test_redeem_cannot_override_account_or_mark_itself_as_test(self):
        self.app.dependency_overrides[verify_clerk_session] = lambda: USER
        with patch.object(billing, "redeem_license_code", new_callable=AsyncMock) as redeem:
            response = self.client.post("/support/redeem", json={"code": "SANDY-TEST-CODE-ONLY-1234", "user_id": "other", "is_test": True})
        self.assertEqual(response.status_code, 422)
        redeem.assert_not_awaited()

    def test_caller_cannot_override_price_or_account(self):
        self.app.dependency_overrides[verify_clerk_session] = lambda: USER
        with patch.object(billing, "checkout", new_callable=AsyncMock) as checkout:
            response = self.client.post(
                "/support/checkout", json={"user_id": "other", "amount_cents": 1}
            )
        self.assertEqual(response.status_code, 422)
        checkout.assert_not_awaited()

    def test_authenticated_status_is_not_cached(self):
        self.app.dependency_overrides[verify_clerk_session] = lambda: USER
        with patch.object(billing, "status", new_callable=AsyncMock, return_value=FREE):
            response = self.client.get("/support/status")
        self.assertEqual(response.headers["cache-control"], "no-store, private")

    def test_form_webhook_works_without_user_session(self):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            side_effect=[{"recorded": True}, {"send_required": False}],
        ):
            response = self.client.post(
                "/support/ko-fi/webhook",
                content=urlencode({"data": json.dumps(payment())}),
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        self.assertEqual(response.status_code, 200)

    def test_kofi_test_endpoint_rejects_an_invalid_shared_token(self):
        payload = kofi_shop_test_payload(verification_token="wrong-test-token")
        with patch.object(billing, "rpc", new_callable=AsyncMock) as rpc:
            response = self.client.post(
                "/support/test/ko-fi-webhook",
                content=urlencode({"data": json.dumps(payload)}),
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        self.assertEqual(response.status_code, 401)
        rpc.assert_not_awaited()

    def test_kofi_test_endpoint_is_hidden_until_explicitly_enabled(self):
        with patch.object(billing.config, "KOFI_TEST_ENDPOINT_ENABLED", False):
            response = self.client.post(
                "/support/test/ko-fi-webhook",
                content=urlencode({"data": json.dumps(kofi_shop_test_payload())}),
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        self.assertEqual(response.status_code, 404)

    def test_swagger_documents_only_the_staging_test_webhook(self):
        paths = self.app.openapi()["paths"]
        operation = paths["/support/test/ko-fi-webhook"]["post"]
        self.assertIn("Envía el código", operation["description"])
        self.assertIn(
            "application/x-www-form-urlencoded",
            operation["requestBody"]["content"],
        )
        self.assertNotIn("/support/ko-fi/webhook", paths)

    def test_kofi_test_endpoint_runs_the_license_email_flow(self):
        with patch.object(
            billing,
            "rpc",
            new_callable=AsyncMock,
            side_effect=[{"recorded": True}, {"send_required": True}, {"marked": True}],
        ), patch.object(billing, "send_email", new_callable=AsyncMock) as send:
            response = self.client.post(
                "/support/test/ko-fi-webhook",
                content=urlencode({"data": json.dumps(kofi_shop_test_payload())}),
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"accepted": True, "test": True, "email_submitted": True},
        )
        self.assertEqual(send.await_args.args[0], ["tester@sandystudio.net"])

    def test_webhook_rejects_wrong_encoding_oversized_or_malformed_payload(self):
        self.assertEqual(
            self.client.post("/support/ko-fi/webhook", json=payment()).status_code, 415
        )
        self.assertEqual(
            self.client.post("/support/ko-fi/webhook", content="x" * 65537).status_code,
            413,
        )
        self.assertEqual(
            self.client.post(
                "/support/ko-fi/webhook",
                content="data=not-json",
                headers={"content-type": "application/x-www-form-urlencoded"},
            ).status_code,
            400,
        )

    def test_overlay_cannot_send_account_id_instead_of_limited_credential(self):
        self.assertEqual(
            self.client.post(
                "/support/overlay-status", json={"user_id": "account-a"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/support/overlay-status", content="x" * 2049).status_code,
            413,
        )


class PrivateErrorReportingTests(unittest.TestCase):
    def test_support_request_details_are_not_forwarded_to_error_monitor(self):
        from app.core.rollbar import exclude_support_payload

        self.assertIs(
            exclude_support_payload(
                {
                    "data": {
                        "request": {
                            "url": "https://api.example/support/ko-fi/webhook",
                            "body": "secret-payment",
                        }
                    }
                }
            ),
            False,
        )
        ordinary = {"data": {"request": {"url": "https://api.example/health"}}}
        self.assertIs(exclude_support_payload(ordinary), ordinary)


if __name__ == "__main__":
    unittest.main()
