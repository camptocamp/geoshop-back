import os
import tempfile
import shutil

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from django.test import TestCase, override_settings
from django.urls import reverse

from api.models import Order, OrderItem, OrderType


ADMIN_ORDER_FILE_CONTENT = b"Order extract result"
ADMIN_ORDER_ITEM_FILE_CONTENT = b"Order item extract result"

@override_settings(LANGUAGE_CODE="en")
class AdminExtractResultDownloadTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override_media_root = override_settings(MEDIA_ROOT=self.media_root)
        self.override_media_root.enable()

        UserModel = get_user_model()

        self.superuser = UserModel.objects.get(username="admin")

        self.client_user = UserModel.objects.create_user(
            username="client",
            email="client@example.com",
            password="client-password",
        )

        self.order_type = OrderType.objects.create(name="Privé")

        self.order = Order.objects.create(
            title="Admin extract download test order",
            description="Test order",
            geom=Polygon(
                ((0, 0), (0, 1), (1, 1), (0, 0)),
                srid=4326,
            ),
            client=self.client_user,
            order_type=self.order_type,
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
        )

        self.order_file_name = "admin_order_result.zip"
        self.order_item_file_name = "admin_order_item_result.zip"

        with open(os.path.join(self.media_root, self.order_file_name), "wb") as file:
            file.write(ADMIN_ORDER_FILE_CONTENT)

        with open(os.path.join(self.media_root, self.order_item_file_name), "wb") as file:
            file.write(ADMIN_ORDER_ITEM_FILE_CONTENT)

        self.order.extract_result.name = self.order_file_name
        self.order.save()

        self.order_item.extract_result.name = self.order_item_file_name
        self.order_item.save()

    def tearDown(self):
        self.override_media_root.disable()
        shutil.rmtree(self.media_root)

    def _response_content(self, response):
        if getattr(response, "streaming", False):
            return b"".join(response.streaming_content)
        return response.content

    def test_admin_order_extract_download_requires_admin_login(self):
        url = reverse(
            "admin:order_download_extract_result",
            args=[self.order.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_order_extract_download_returns_file_for_superuser(self):
        self.client.force_login(self.superuser)

        url = reverse(
            "admin:order_download_extract_result",
            args=[self.order.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._response_content(response),
            ADMIN_ORDER_FILE_CONTENT,
        )
        self.assertIn(
            'attachment; filename="admin_order_result.zip"',
            response["Content-Disposition"],
        )

    def test_admin_order_extract_download_returns_404_when_file_is_missing(self):
        self.client.force_login(self.superuser)

        os.remove(os.path.join(self.media_root, self.order_file_name))

        url = reverse(
            "admin:order_download_extract_result",
            args=[self.order.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_admin_order_item_extract_download_requires_admin_login(self):
        url = reverse(
            "admin:order_item_download_extract_result",
            args=[self.order_item.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_admin_order_item_extract_download_returns_file_for_superuser(self):
        self.client.force_login(self.superuser)

        url = reverse(
            "admin:order_item_download_extract_result",
            args=[self.order_item.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self._response_content(response),
            ADMIN_ORDER_ITEM_FILE_CONTENT,
        )
        self.assertIn(
            'attachment; filename="admin_order_item_result.zip"',
            response["Content-Disposition"],
        )

    def test_admin_order_item_extract_download_returns_404_when_file_is_missing(self):
        self.client.force_login(self.superuser)

        os.remove(os.path.join(self.media_root, self.order_item_file_name))

        url = reverse(
            "admin:order_item_download_extract_result",
            args=[self.order_item.pk],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_order_admin_change_page_contains_order_download_link(self):
        self.client.force_login(self.superuser)

        change_url = reverse("admin:api_order_change", args=[self.order.pk])
        download_url = reverse(
            "admin:order_download_extract_result",
            args=[self.order.pk],
        )

        response = self.client.get(change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, download_url)
        self.assertContains(response, "Download extract result")

    def test_order_admin_change_page_contains_inline_order_item_download_link(self):
        self.client.force_login(self.superuser)

        change_url = reverse("admin:api_order_change", args=[self.order.pk])
        order_item_download_url = reverse(
            "admin:order_item_download_extract_result",
            args=[self.order_item.pk],
        )

        response = self.client.get(change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order_item_download_url)
        self.assertContains(response, "Download extract result")