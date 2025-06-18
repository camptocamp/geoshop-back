from django.urls import reverse
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import (
  Identity,
  OrderItem,
  Order,
  Product,
)
from api.tests.factories import BaseObjectsFactory

class EmailTranslationTest(APITestCase):

    def setUp(self):
        self.config = BaseObjectsFactory(self.client)
        self.order_data = {
            'order_type': 'Privé',
            'items': [{
                'product': {'label': 'Produit gratuit'},
                'status': OrderItem.OrderItemStatus.PROCESSED,
            }],
            'title': 'Test Translation',
            'description': 'Nice order',
            'order_status': Order.OrderStatus.READY,
            'geom': {
                'type': 'Polygon',
                'coordinates': [
                    [[2545488, 1203070],
                    [2557441, 1202601],
                    [2557089, 1210921],
                    [2545605, 1211390],
                    [2545488, 1203070]]
                ]
            },
        }
        fromDb = Product.objects.get(label='Produit gratuit')
        fromDb.max_order_area = 1000000000
        fromDb.save()

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.client.post(reverse('order-list'), self.order_data, format='json')

    def test_quote_email(self):
        order = Order.objects.get(title='Test Translation')

        order.client.identity.language = Identity.PreferredLanguage.ENGLISH
        order.client.identity.save()
        order.order_status = Order.OrderStatus.READY
        order.next_status_on_extract_input()
        self.assertEqual(mail.outbox[-1].subject, "Geoshop - Download ready", "English subject")

        order.client.identity.language = Identity.PreferredLanguage.GERMAN
        order.client.identity.save()
        order.order_status = Order.OrderStatus.READY
        order.next_status_on_extract_input()
        self.assertEqual(mail.outbox[-1].subject, "Geoshop - Ihre Bestellung steht zum Download bereit.", "German subject")
