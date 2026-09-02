from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Order, OrderItem, Payment
from api.payments import (
    PaymentError,
    ReturnUrls,
    Session,
    WebhookEvent,
    WebhookVerificationError,
    get_status,
    start_payment,
)
from api.tests.factories import BaseObjectsFactory

RETURN_URLS = ReturnUrls(
    success="https://front/payment/ok",
    failure="https://front/payment/ko",
    cancel="https://front/payment/cancel",
)
FAKE_SESSION = Session(provider_transaction_id="txn-123", redirect_url="https://pf/pay/txn-123")


class StartPaymentTests(TestCase):
    """The start_payment orchestrator (provider call mocked)."""

    def setUp(self):
        self.config = BaseObjectsFactory()
        self.order = self.config.order
        # A single auto-priced item makes the order fully priced (total_with_vat set).
        OrderItem.objects.create(
            order=self.order,
            product=self.config.products["single"],
            data_format=self.config.formats["dxf"],
        )
        for item in self.order.items.all():
            item.set_price()
            item.save()
        self.order.set_price()
        self.order.save()
        self.assertIsNotNone(self.order.total_with_vat)  # sanity: fully priced

    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_creates_a_pending_payment_without_touching_the_order(self, mock_create):
        status_before = self.order.order_status
        payment, redirect_url = start_payment(self.order, RETURN_URLS)

        mock_create.assert_called_once()
        self.assertEqual(redirect_url, FAKE_SESSION.redirect_url)

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.provider_transaction_id, "txn-123")
        self.assertEqual(payment.provider, "postfinance")
        self.assertEqual(payment.amount, self.order.total_with_vat)  # charges the confirmed total
        # Card is a side-record: the order's status is left exactly as it was.
        self.assertEqual(self.order.order_status, status_before)
        self.assertEqual(self.order.payments.count(), 1)

    @mock.patch("api.payments._payment_page_url", return_value="https://pf/pay/txn-123")
    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_dedups_an_in_flight_payment(self, mock_create, mock_url):
        start_payment(self.order, RETURN_URLS)
        # Second attempt must reuse the open payment, not charge again.
        _, redirect_url = start_payment(self.order, RETURN_URLS)

        self.assertEqual(self.order.payments.count(), 1)
        self.assertEqual(mock_create.call_count, 1)  # provider not hit again
        mock_url.assert_called_once()  # reuse re-fetches the existing page URL
        self.assertEqual(redirect_url, "https://pf/pay/txn-123")

    def test_refuses_an_unpriced_order(self):
        unpriced = Order.objects.create(
            client=self.config.user_private,
            order_type=self.config.order_types["private"],
            title="unpriced order",
            geom=self.order.geom,
        )
        with self.assertRaises(PaymentError):
            start_payment(unpriced, RETURN_URLS)


@override_settings(LANGUAGE_CODE="en")
class _OrderApiTestBase(APITestCase):
    """Shared setup for the order payment endpoint tests."""

    def setUp(self):
        self.config = BaseObjectsFactory(webclient=self.client)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.config.client_token)

    def _draft_order(self, product_key, order_type="private"):
        order = Order.objects.create(
            client=self.config.user_private,
            order_type=self.config.order_types[order_type],
            title="pay test",
            geom=self.config.order.geom,
        )
        OrderItem.objects.create(
            order=order,
            product=self.config.products[product_key],
            data_format=self.config.formats["dxf"],
        )
        # The serializer prices items as they're added to a cart; mirror that here.
        for item in order.items.all():
            item.set_price()
            item.save()
        order.set_price()
        order.save()
        return order

    def _ready_order(self, product_key, order_type="private"):
        """A confirmed order, as it exists when card payment is offered (post-confirm)."""
        order = self._draft_order(product_key, order_type)
        order.confirm()
        order.save()
        return order


class PayEndpointTests(_OrderApiTestBase):
    """The POST /order/{id}/pay/ action (card payment on a confirmed order)."""

    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_confirmed_order_starts_payment_and_keeps_its_status(self, mock_create):
        order = self._ready_order("single")
        self.assertEqual(order.order_status, Order.OrderStatus.READY)

        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["redirect_url"], FAKE_SESSION.redirect_url)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.READY)  # untouched
        self.assertEqual(order.payments.count(), 1)

    def test_unconfirmed_order_is_forbidden(self):
        order = self._draft_order("single")  # still DRAFT, not confirmed
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(order.payments.count(), 0)

    def test_free_order_has_nothing_to_pay(self):
        # A "Communal" order is priced to zero -> nothing to charge by card.
        order = self._ready_order("single", order_type="public")
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(order.payments.count(), 0)

    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_a_new_payment_can_follow_a_failed_one(self, mock_create):
        # A failed card attempt leaves a FAILED payment behind; the order is still READY, so
        # the buyer can just try again (a new payment is created, the old one is not reused).
        order = self._ready_order("single")
        Payment.objects.create(
            order=order,
            amount=Money(150, "CHF"),
            provider="postfinance",
            status=Payment.PaymentStatus.FAILED,
        )

        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.READY)
        self.assertEqual(order.payments.count(), 2)
        self.assertEqual(order.payments.filter(status=Payment.PaymentStatus.PENDING).count(), 1)


class PostFinanceWebhookTests(TestCase):
    """The POST /payment/webhook/postfinance/ settlement webhook (verification mocked)."""

    def setUp(self):
        self.config = BaseObjectsFactory()
        self.url = reverse("postfinance_webhook")

    def _paid_order(self, tx_id="tx-1"):
        """A confirmed (READY) order with an in-flight card payment."""
        order = Order.objects.create(
            client=self.config.user_private,
            order_type=self.config.order_types["private"],
            title="paid order",
            geom=self.config.order.geom,
            order_status=Order.OrderStatus.READY,
        )
        item = OrderItem.objects.create(
            order=order, product=self.config.products["single"],
            data_format=self.config.formats["dxf"],
        )
        item.set_price()
        item.save()
        order.set_price()
        order.save()
        payment = Payment.objects.create(
            order=order, amount=order.total_with_vat, provider="postfinance",
            provider_transaction_id=tx_id, status=Payment.PaymentStatus.PENDING,
        )
        return order, payment

    def _event(self, tx_id, new_status, event_id="evt-1"):
        return WebhookEvent(
            provider_event_id=event_id, provider_transaction_id=tx_id,
            new_status=new_status, raw_payload={"eventId": event_id, "entityId": tx_id},
        )

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_settled_payment_marks_the_payment_and_order_is_card_paid(self, mock_parse):
        order, payment = self._paid_order()
        mock_parse.return_value = self._event("tx-1", Payment.PaymentStatus.SETTLED)

        resp = self.client.post(self.url)

        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.SETTLED)
        # Order flow is untouched; the settlement is surfaced via is_card_paid.
        self.assertEqual(order.order_status, Order.OrderStatus.READY)
        self.assertTrue(order.is_card_paid)
        self.assertEqual(payment.events.count(), 1)

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_failed_payment_leaves_the_order_untouched(self, mock_parse):
        order, payment = self._paid_order()
        mock_parse.return_value = self._event("tx-1", Payment.PaymentStatus.FAILED)

        resp = self.client.post(self.url)

        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.FAILED)
        self.assertEqual(order.order_status, Order.OrderStatus.READY)  # untouched
        self.assertFalse(order.is_card_paid)

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_duplicate_event_takes_effect_once(self, mock_parse):
        order, payment = self._paid_order()
        mock_parse.return_value = self._event("tx-1", Payment.PaymentStatus.SETTLED, event_id="evt-dup")

        self.client.post(self.url)
        self.client.post(self.url)  # same eventId again

        self.assertEqual(payment.events.count(), 1)

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_unknown_transaction_is_acknowledged(self, mock_parse):
        mock_parse.return_value = self._event("no-such-tx", Payment.PaymentStatus.SETTLED)

        resp = self.client.post(self.url)

        self.assertEqual(resp.status_code, 200)

    @mock.patch("api.payments.parse_and_verify_webhook", side_effect=WebhookVerificationError("bad signature"))
    def test_invalid_signature_returns_400(self, mock_parse):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 400)


@override_settings(POSTFINANCE_SPACE_ID="1")
class GetStatusMappingTests(TestCase):
    """get_status maps PostFinance transaction states to our PaymentStatus values."""

    @mock.patch("api.payments.TransactionsService")
    def _status_for(self, state, mock_svc):
        mock_svc.return_value.get_payment_transactions_id.return_value = mock.Mock(state=state)
        return get_status("123")

    def test_state_mapping(self):
        self.assertEqual(self._status_for("FULFILL"), "SETTLED")
        self.assertEqual(self._status_for("COMPLETED"), "AUTHORIZED")
        self.assertEqual(self._status_for("FAILED"), "FAILED")
        self.assertEqual(self._status_for("VOIDED"), "CANCELED")
        self.assertEqual(self._status_for("PROCESSING"), "PENDING")
        self.assertEqual(self._status_for("SOMETHING_NEW"), "PENDING")  # unknown -> safe default
