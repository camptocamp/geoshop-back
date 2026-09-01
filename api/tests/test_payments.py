from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Order, OrderItem, Payment, Product, ProductFormat
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
    def test_creates_payment_and_moves_order_to_awaiting_payment(self, mock_create):
        payment, redirect_url = start_payment(self.order, RETURN_URLS, self.order.total_with_vat)

        mock_create.assert_called_once()
        self.assertEqual(redirect_url, FAKE_SESSION.redirect_url)

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.provider_transaction_id, "txn-123")
        self.assertEqual(payment.provider, "postfinance")
        self.assertEqual(payment.amount, self.order.total_with_vat)
        self.assertEqual(self.order.order_status, Order.OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(self.order.payments.count(), 1)

    @mock.patch("api.payments._payment_page_url", return_value="https://pf/pay/txn-123")
    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_dedups_an_in_flight_payment(self, mock_create, mock_url):
        start_payment(self.order, RETURN_URLS, self.order.total_with_vat)
        # Second attempt must reuse the open payment, not charge again.
        _, redirect_url = start_payment(self.order, RETURN_URLS, self.order.total_with_vat)

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
            start_payment(unpriced, RETURN_URLS, unpriced.total_with_vat)


@override_settings(LANGUAGE_CODE="en")
class _OrderApiTestBase(APITestCase):
    """Shared setup for the order payment/checkout endpoint tests."""

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
        return order


class PayEndpointTests(_OrderApiTestBase):
    """The POST /order/{id}/pay/ action."""

    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_autopriced_order_starts_payment(self, mock_create):
        order = self._draft_order("single")
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["payment_required"])
        self.assertEqual(resp.data["redirect_url"], FAKE_SESSION.redirect_url)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(order.payments.count(), 1)

    def test_quote_needed_order_is_rejected(self):
        order = self._draft_order("manual")  # MANUAL pricing -> PENDING, needs a quote
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)  # rolled back, untouched
        self.assertEqual(order.payments.count(), 0)

    def test_non_draft_order_is_forbidden(self):
        order = self._draft_order("single")
        order.order_status = Order.OrderStatus.READY
        order.save()
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(order.payments.count(), 0)

    def test_free_order_skips_payment(self):
        # A "Communal" order is priced to zero -> free, so no card payment is needed.
        order = self._draft_order("single", order_type="public")
        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["payment_required"])
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.READY)
        self.assertEqual(order.payments.count(), 0)

    @mock.patch("api.payments.create_session", return_value=FAKE_SESSION)
    def test_previously_failed_order_can_pay_again(self, mock_create):
        # A failed payment releases the order back to DRAFT, leaving a FAILED payment behind.
        # The buyer must be able to start a fresh payment -- not get a 403.
        order = self._draft_order("single")
        Payment.objects.create(
            order=order,
            amount=Money(150, "CHF"),
            provider="postfinance",
            status=Payment.PaymentStatus.FAILED,
        )

        resp = self.client.post(reverse("order-pay", kwargs={"pk": order.id}), format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["payment_required"])
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.AWAITING_PAYMENT)
        # A new payment is started; the old FAILED one is not reused.
        self.assertEqual(order.payments.count(), 2)
        self.assertEqual(order.payments.filter(status=Payment.PaymentStatus.PENDING).count(), 1)


class PrepareEndpointTests(_OrderApiTestBase):
    """The POST /order/{id}/prepare/ action (finalize at checkout)."""

    def _prepare(self, order):
        return self.client.post(reverse("order-prepare", kwargs={"pk": order.id}), format="json")

    def test_autopriced_order_reports_card(self):
        order = self._draft_order("single")
        resp = self._prepare(order)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_option"], "card")
        self.assertIsNotNone(resp.data["total"])
        self.assertEqual(resp.data["currency"], "CHF")
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)  # not committed
        self.assertEqual(order.payments.count(), 0)
        self.assertEqual(order.items.count(), 1)  # read-only: cart untouched

    def test_quote_needed_order_reports_quote(self):
        order = self._draft_order("manual")  # MANUAL pricing -> PENDING
        resp = self._prepare(order)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_option"], "quote")
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)

    def test_free_order_reports_free(self):
        order = self._draft_order("single", order_type="public")  # Communal -> priced to 0
        resp = self._prepare(order)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["payment_option"], "free")
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)

    def test_non_draft_order_is_forbidden(self):
        order = self._draft_order("single")
        order.order_status = Order.OrderStatus.READY
        order.save()
        resp = self._prepare(order)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_is_idempotent(self):
        order = self._draft_order("single")
        first = self._prepare(order)
        second = self._prepare(order)

        self.assertEqual(first.data["payment_option"], second.data["payment_option"])
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)


class PrepareFinalizeConsistencyTests(TestCase):
    """
    The read path (_prepare_order_items / prepare_checkout) must resolve to the same
    concrete products and total as the write path (_finalize_order_items). This pins the
    two parallel implementations together so they cannot drift.
    """

    def setUp(self):
        self.config = BaseObjectsFactory()

    def _group_order(self):
        """A DRAFT order holding one use_largest_area group whose winning child is Child B."""
        srid = settings.DEFAULT_SRID
        child_a = Product.objects.create(
            label="Child A", pricing=self.config.pricings["single"],
            metadata=self.config.public_metadata, product_status=Product.ProductStatus.PUBLISHED,
            provider=self.config.provider,
            geom=MultiPolygon(Polygon.from_bbox((0, 0, 10, 10)), srid=srid),
            use_largest_area_validation=True,
        )
        child_b = Product.objects.create(
            label="Child B", pricing=self.config.pricings["single"],
            metadata=self.config.public_metadata, product_status=Product.ProductStatus.PUBLISHED,
            provider=self.config.provider,
            geom=MultiPolygon(Polygon.from_bbox((20, 0, 30, 10)), srid=srid),
            use_largest_area_validation=True,
        )
        parent = Product.objects.create(
            label="Parent Group", pricing=self.config.pricings["single"],
            metadata=self.config.public_metadata, product_status=Product.ProductStatus.PUBLISHED,
            provider=self.config.provider, use_largest_area_validation=True,
        )
        for child in (child_a, child_b):
            child.group = parent
            child.save()
        ProductFormat.objects.bulk_create([
            ProductFormat(product=child_a, data_format=self.config.formats["dxf"]),
            ProductFormat(product=child_b, data_format=self.config.formats["dxf"]),
        ])
        order_geom = Polygon.from_bbox((8, 0, 28, 10))  # overlaps Child B far more
        order_geom.srid = srid
        order = Order.objects.create(
            client=self.config.user_private, order_type=self.config.order_types["private"],
            title="group order", geom=order_geom,
        )
        item = OrderItem.objects.create(
            order=order, product=parent, data_format=self.config.formats["dxf"]
        )
        item.set_price()
        item.save()
        return order, child_b

    def test_read_path_matches_write_path(self):
        order, expected_winner = self._group_order()

        # READ path (must not persist anything).
        read_products = sorted(i.product_id for i in order._prepare_order_items())
        read_option, read_total = order.prepare_checkout()
        self.assertEqual(order.items.count(), 1)  # still just the group item

        # WRITE path on the same order.
        order._finalize_order_items()
        write_priced = order.set_price()
        write_products = sorted(i.product_id for i in order.items.all())

        self.assertEqual(read_products, write_products)
        self.assertEqual(read_products, [expected_winner.id])  # largest-overlap child
        self.assertTrue(write_priced)
        self.assertEqual(read_total, order.total_with_vat)
        self.assertEqual(read_option, "card")


class PostFinanceWebhookTests(TestCase):
    """The POST /payment/webhook/postfinance/ settlement webhook (verification mocked)."""

    def setUp(self):
        self.config = BaseObjectsFactory()
        self.url = reverse("postfinance_webhook")

    def _awaiting_payment_order(self, tx_id="tx-1"):
        order = Order.objects.create(
            client=self.config.user_private,
            order_type=self.config.order_types["private"],
            title="paid order",
            geom=self.config.order.geom,
            order_status=Order.OrderStatus.AWAITING_PAYMENT,
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
    def test_settled_payment_moves_order_to_ready(self, mock_parse):
        order, payment = self._awaiting_payment_order()
        mock_parse.return_value = self._event("tx-1", Payment.PaymentStatus.SETTLED)

        resp = self.client.post(self.url)

        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.SETTLED)
        self.assertEqual(order.order_status, Order.OrderStatus.READY)
        self.assertEqual(payment.events.count(), 1)

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_failed_payment_releases_order_to_draft(self, mock_parse):
        order, payment = self._awaiting_payment_order()
        mock_parse.return_value = self._event("tx-1", Payment.PaymentStatus.FAILED)

        resp = self.client.post(self.url)

        self.assertEqual(resp.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.FAILED)
        # Order returns to DRAFT so the buyer can edit or retry.
        self.assertEqual(order.order_status, Order.OrderStatus.DRAFT)

    @mock.patch("api.payments.parse_and_verify_webhook")
    def test_duplicate_event_takes_effect_once(self, mock_parse):
        order, payment = self._awaiting_payment_order()
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
