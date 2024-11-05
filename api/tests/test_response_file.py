import os
from django.conf import settings
import tempfile
from uuid import uuid4
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import Order
from api.tests.factories import BaseObjectsFactory

UUID_EXISTS = str(uuid4())
UUID_FILE_NOTFOUND = str(uuid4())
UUID_ORDER_NOTFOUND = str(uuid4())
TMP_CONTENT="Hello world"

class TestResponseFile(APITestCase):
    """
    Test sending extract result files
    """

    def setUp(self):
        self.config = BaseObjectsFactory(self.client)
        settings.MEDIA_ROOT = tempfile.mkdtemp()
        with open(os.path.join(settings.MEDIA_ROOT, "demo_file"), "w") as tmpfile:
            tmpfile.write(TMP_CONTENT)
        order_data = {
            "order_type": "Privé",
            "items": [],
            "title": "Test file exists",
            "description": "Nice order",
            "geom": {"type": "Polygon", "coordinates": [[[0,0], [0, 1], [1, 1], [0, 0]]]},
        }
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.config.client_token)
        self.client.post(reverse("order-list"), order_data, format="json").content
        order_data["title"] = "Test file not found"
        self.client.post(reverse("order-list"), order_data, format="json").content

        obj = Order.objects.filter(title="Test file exists")[0]
        obj.download_guid = UUID_EXISTS
        obj.extract_result.name = "demo_file"
        obj.save()

        obj = Order.objects.filter(title="Test file not found")[0]
        obj.download_guid = UUID_FILE_NOTFOUND
        obj.extract_result.name = "missing_demo_file"
        obj.save()

    def testSendFileSuccess(self):
        url = reverse("download_by_uuid", kwargs={"guid": UUID_EXISTS})
        resp = self.client.get(url)
        self.assertEqual(TMP_CONTENT, str(resp.content, "utf8"))

    def testSendOrderNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": UUID_ORDER_NOTFOUND})
        resp = self.client.get(url)
        self.assertTrue("No Order matches" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def testSendFileNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": UUID_FILE_NOTFOUND})
        resp = self.client.get(url)
        self.assertTrue("file not found" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
