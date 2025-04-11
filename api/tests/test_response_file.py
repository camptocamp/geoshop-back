import os
import json
from django.conf import settings
import tempfile
from uuid import uuid4
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import Order, OrderItem
from api.tests.factories import BaseObjectsFactory

# Order
ORDER_EXISTS_UUID = str(uuid4())
ORDER_FILE_NOTFOUND_UUID = str(uuid4())
ORDER_NOTFOUND_UUID = str(uuid4())

# Order item
ITEM_EXISTS_UUID = str(uuid4())
ITEM_FILE_NOTFOUND_UUID = str(uuid4())
ITEM_NOTFOUND_UUID = str(uuid4())

TMP_CONTENT="Hello world"


class TestResponseFile(APITestCase):
    """
    Test sending extract result files
    """
    order_data = {
            "order_type": "Privé",
            "items": [
                {"product": {"label": "Maquette 3D"}},
                {"product": {"label": "Maquette 3D"}},
                {"product": {"label": "Maquette 3D"}},
            ],
            "title": "Test file exists",
            "description": "Nice order",
            "geom": {"type": "Polygon", "coordinates": [[[0,0], [0, 1], [1, 1], [0, 0]]]},
        }

    def addOrder(self, updates) -> Order:
        data = self.order_data.copy()
        data.update(updates)
        id = json.loads(self.client.post(reverse("order-list"), data, format="json").content)["id"]
        return Order.objects.get(id=id)

    def setUp(self):
        self.config = BaseObjectsFactory(self.client)
        settings.MEDIA_ROOT = tempfile.mkdtemp()
        with open(os.path.join(settings.MEDIA_ROOT, "demo_file"), "w") as tmpfile:
            tmpfile.write(TMP_CONTENT)
        with open(os.path.join(settings.MEDIA_ROOT, "another_demo_file"), "w") as tmpfile:
            tmpfile.write(TMP_CONTENT[::-1])
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.config.client_token)

        obj = self.addOrder({"title": "Test file exists"})
        obj.download_guid = ORDER_EXISTS_UUID
        obj.extract_result.name = "demo_file"
        obj.save()

        obj = self.addOrder({"title": "Test file not found"})
        obj.download_guid = ORDER_FILE_NOTFOUND_UUID
        obj.extract_result.name = "missing_demo_file"
        obj.save()

        obj = self.addOrder({"title": "Order with tokened items"})
        items = obj.items.all()
        item = OrderItem.objects.get(id=items[0].id)
        item.download_guid = ITEM_EXISTS_UUID
        item.extract_result.name = "another_demo_file"
        item.save()

        item = OrderItem.objects.get(id=items[1].id)
        item.download_guid = ITEM_FILE_NOTFOUND_UUID
        item.extract_result.name = "missing_another_demo_file"
        item.save()

    def testSendOrderFileSuccess(self):
        url = reverse("download_by_uuid", kwargs={"guid": ORDER_EXISTS_UUID})
        resp = self.client.get(url)
        self.assertEqual(TMP_CONTENT, str(resp.content, "utf8"))

    def testSendOrderNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": ORDER_NOTFOUND_UUID})
        resp = self.client.get(url)
        self.assertTrue("No object matches" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def testSendFileNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": ORDER_FILE_NOTFOUND_UUID})
        resp = self.client.get(url)
        self.assertTrue("file not found" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def testSendItemFileSuccess(self):
        url = reverse("download_by_uuid", kwargs={"guid": ITEM_EXISTS_UUID})
        resp = self.client.get(url)
        self.assertEqual(TMP_CONTENT[::-1], str(resp.content, "utf8"))

    def testSendItemNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": ITEM_NOTFOUND_UUID})
        resp = self.client.get(url)
        self.assertTrue("No object matches" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def testSendItemFileNotFound(self):
        url = reverse("download_by_uuid", kwargs={"guid": ITEM_FILE_NOTFOUND_UUID})
        resp = self.client.get(url)
        self.assertTrue("file not found" in str(resp.content))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
