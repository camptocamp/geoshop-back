import json

from django.urls import reverse
from django.core import mail
from django.test import override_settings

from math import isclose
from django.contrib.gis.geos import Polygon

from djmoney.money import Money
from rest_framework import status
from rest_framework.test import APITestCase
from api.models import (
  Contact,
  OrderItem,
  Order,
  Metadata,
  Product,
  ProductFormat,
)
from api.tests.factories import BaseObjectsFactory

def updateMaxOrderArea(product, area):
    fromDb = Product.objects.get(label=product)
    fromDb.max_order_area = area
    fromDb.save()

def areasEqual(geomA, geomB, srid: int = 2056) -> bool:
    """We can consider polygons equal if """
    polyA = Polygon(geomA['coordinates'][0], srid=srid)
    polyB = Polygon(geomB['coordinates'][0], srid=srid)
    intAB = polyA.intersection(polyB).area
    uniAB = polyA.union(polyB).area
    return (isclose(intAB, polyA.area) and isclose(intAB, polyB.area) and
            isclose(uniAB, polyA.area) and isclose(uniAB, polyB.area) and
            isclose(polyA.difference(polyB).area, 0))


@override_settings(LANGUAGE_CODE='en')
class OrderTests(APITestCase):
    """
    Test Orders
    """

    def setUp(self):
        self.config = BaseObjectsFactory(self.client)
        self.order_data = {
            'order_type': 'Privé',
            'items': [],
            'title': 'Test 1734',
            'description': 'Nice order',
            'geom': {
                'type': 'Polygon',
                'coordinates': [
                    [
                        [
                            2528577.8382161376,
                            1193422.4003930448
                        ],
                        [
                            2542482.6542869355,
                            1193422.4329014618
                        ],
                        [
                            2542482.568523701,
                            1199018.36469272
                        ],
                        [
                            2528577.807487005,
                            1199018.324372703
                        ],
                        [
                            2528577.8382161376,
                            1193422.4003930448
                        ]
                    ]
                ]
            },
        }

    def get_order_item(self):
        url = reverse('orderitem-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_order_auto_price(self):
        """
        Tests POST of an order
        """
        url = reverse('order-list')
        response = self.client.post(url, self.order_data, format='json')
        # Forbidden if not logged in
        self.assertIn(response.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN], response.content)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        # Last draft view
        url = reverse('order-last-draft')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue('id' in response.data)
        order_id = response.data['id']
        contact_id = Contact.objects.filter(email='test3@admin.com').first().id

        # Update
        data = {
            "invoice_contact": contact_id
        }

        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['invoice_contact'], contact_id, 'Check contact is updated')

        # Update
        data = {
            "items": [{
                "product": {"label": "Produit gratuit"}
        }]
        }

        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['items'][0]['product']['label'], data['items'][0]['product']['label'], 'Check product')
        self.assertEqual(
            response.data['items'][0]['price_status'], OrderItem.PricingStatus.CALCULATED, 'Check price is calculated')
        self.assertIsNotNone(response.data['items'][0]['available_formats'], 'Check available formats are present')

        order_item_id = response.data['items'][0]['id']
        # Confirm order without format should not work
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

        # Choose format
        data = {
            "data_format": "Geobat NE complet (DXF)"
        }
        url = reverse('orderitem-detail', kwargs={'pk':order_item_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['status'], OrderItem.OrderItemStatus.PENDING, 'status is PENDING')


        # Confirm order with format should work
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        # Confirm order that's already confirmed, should not work
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)
        # Edit order that's already confirmed, should not work
        data = {
            "items": [{
                "product": {"label": "Produit forfaitaire"}}]
        }
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)


    def test_post_order_quote(self):
        # POST an order
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        order_id = response.data['id']
        # PATCH order with a product needing quote
        data = {
            "items": [
                {
                    "product": {"label": "Maquette 3D"},
                    "data_format": "Rhino 3DM"
                }
            ]
        }
        # Check price is PENDIND and no price is given
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        ordered_item = response.data['items'][0]
        self.assertEqual(ordered_item['product']['label'], data['items'][0]['product']['label'], 'Check product')
        self.assertEqual(ordered_item['product_provider'], self.config.provider.identity.company_name, 'Check provider is present')
        self.assertEqual(ordered_item['price_status'], OrderItem.PricingStatus.PENDING, 'Check quote is needed')
        self.assertIsNone(response.data['processing_fee'], 'Check quote is needed')
        self.assertIsNone(response.data['total_without_vat'], 'Check quote is needed')
        self.assertIsNone(response.data['part_vat'], 'Check quote is needed')
        self.assertIsNone(response.data['total_with_vat'], 'Check quote is needed')

        # Ask for a quote
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        self.assertEqual(len(mail.outbox), 1, 'An email has been sent to admins')

        # Admin sets the quote
        quoted_order = Order.objects.get(pk=order_id)
        quoted_orderitem = OrderItem.objects.get(pk=ordered_item['id'])
        quoted_orderitem.set_price(price=Money(400, 'CHF'), base_fee=Money(150, 'CHF'))
        quoted_orderitem.save()
        is_quote_ok = quoted_order.quote_done()
        self.assertTrue(is_quote_ok, 'Quote done successfully')

        # Client sees the quote
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['order_status'], Order.OrderStatus.QUOTE_DONE, 'Check quote has been done')
        self.assertEqual(response.data['processing_fee'], '150.00', 'Check price is ok')
        self.assertEqual(response.data['total_without_vat'], '550.00', 'Check price is ok')
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)

    def test_post_order_subscribed(self):
        self.config.user_private.identity.subscribed = True
        self.config.user_private.identity.save()
        self.order_data['order_type'] = 'Utilisateur permanent'

        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        order_id = response.data['id']

        data = {
            "items": [
                {
                    "product": {"label": "MO"},
                    "data_format": "Geobat NE complet (DXF)"
                }
            ]
        }
        # Check price is 0
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['processing_fee'], '0.00', 'Check price is 0')
        self.assertEqual(response.data['total_without_vat'], '0.00', 'Check price is 0')
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        order = Order.objects.get(pk=order_id)
        self.assertIsNotNone(order.download_guid, "Check order has a GUID")
        self.assertIsNotNone(order.date_ordered, "Check order has a date")

    def test_post_order_contact_subscribed(self):
        self.config.contact.subscribed = True
        self.config.contact.save()
        self.order_data['invoice_contact'] = self.config.contact.id
        self.order_data['order_type'] = 'Utilisateur permanent'

        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        order_id = response.data['id']

        data = {
            "items": [
                {
                    "product": {"label": "MO"},
                    "data_format": "Geobat NE complet (DXF)"
                }
            ]
        }
        # Check price is 0
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['processing_fee'], '0.00', 'Check price is 0')
        self.assertEqual(response.data['total_without_vat'], '0.00', 'Check price is 0')
        url = reverse('order-confirm', kwargs={'pk':order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        order = Order.objects.get(pk=order_id)
        self.assertIsNotNone(order.download_guid, "Check order has a GUID")
        self.assertIsNotNone(order.date_ordered, "Check order has a date")


    def test_patch_put_order_items(self):
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(response.data['order_status'], Order.OrderStatus.DRAFT, 'status is DRAFT')
        order_id = response.data['id']
        # PATCH order with a product
        data1 = {
            "items": [
                {
                    "product": {"label": "Produit forfaitaire"}
                }
            ]
        }
        url = reverse('order-detail', kwargs={'pk':order_id})
        response = self.client.patch(url, data1, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['order_status'], Order.OrderStatus.DRAFT, 'status is DRAFT')
        self.assertEqual(len(response.data['items']), 1, 'One product is present')
        data2 = {
            "items": [
                {
                    "product": {"label": "Produit forfaitaire"}
                },{
                    "product": {"label": "Produit gratuit"}
                }
            ]
        }
        response = self.client.patch(url, data2, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(len(response.data['items']), 2, 'Two products are present')
        response = self.client.patch(url, data1, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(len(response.data['items']), 2, 'Two products are still present')
        response = self.client.put(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(len(response.data['items']), 0, 'No product is present')


    def test_delete_order(self):
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        response = self.client.post(url, self.order_data, format='json')
        order = Order.objects.get(pk=response.data['id'])
        oi1 = OrderItem.objects.create(order=order, product=self.config.products['free'], data_format=self.config.formats['geobat'])
        oi2 = OrderItem.objects.create(order=order, product=self.config.products['single'], data_format=self.config.formats['rhino'])
        oi1.set_price()
        oi1.save()
        oi2.set_price(price=Money(400, 'CHF'), base_fee=Money(150, 'CHF'))
        oi2.price_status = OrderItem.PricingStatus.CALCULATED
        oi2.save()
        url = reverse('order-detail', kwargs={'pk':order.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.content)


    def test_order_geom_is_valid(self):
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2545488, 1203070],
                 [2545605, 1211390],
                 [2557441, 1202601],
                 [2557089, 1210921],
                 [2545488, 1203070]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(len(mail.outbox), 1, 'An email has been sent to admins')


    def order_item_validation(self, grouped=True):
        """
        Helper for tests of validation
        """
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['order_type'] = 'Utilisateur permanent'
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        order_id = response.data['id']

        approval_needed_metadata = Metadata.objects.create(
            id_name='01_approval_generic',
            modified_user=self.config.user_private,
            accessibility=Metadata.MetadataAccessibility.APPROVAL_NEEDED
        )
        approval_needed_metadata.contact_persons.set([
            self.config.user_private.identity
        ])
        approval_needed_metadata.save()

        product_name_to_order = "Données sensibles"
        sensitive_product = Product.objects.create(
            label=product_name_to_order,
            pricing=self.config.pricings['free'],
            metadata=approval_needed_metadata,
            product_status=Product.ProductStatus.PUBLISHED,
            provider=self.config.provider
        )


        if grouped:
            product_name_to_order = "Cadastre souterrain"
            group = Product.objects.create(
                label=product_name_to_order,
                pricing=self.config.pricings['free'],
                provider=self.config.provider,
                metadata=self.config.public_metadata,
                product_status=Product.ProductStatus.PUBLISHED
            )
            ProductFormat.objects.bulk_create([
                ProductFormat(product=sensitive_product, data_format=self.config.formats['dxf']),
                ProductFormat(product=group, data_format=self.config.formats['dxf']),
            ])
            sensitive_product.group = group
            sensitive_product.save()


        data = {
            "items": [
                {
                    "product": {"label": product_name_to_order},
                    "data_format": "DXF"
                },
                {
                    "product": {"label": "MO"},
                    "data_format": "Geobat NE complet (DXF)"
                }
            ]
        }
        url = reverse('order-detail', kwargs={'pk': order_id})
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        url = reverse('order-confirm', kwargs={'pk': order_id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        self.assertEqual(len(mail.outbox), 2, 'An email has been sent to the validator and one to admin')
        order = Order.objects.get(pk=order_id)
        items = order.items.all()
        item = None
        # Get the item needing a validation
        for i in items:
            if i.status == OrderItem.OrderItemStatus.VALIDATION_PENDING:
                item = i
        self.assertIsNotNone(item, 'Item is waiting for validation')
        self.assertGreater(len(item.token), 0, 'item has token')
        self.assertIsNotNone(order.download_guid, "Check order has a GUID")
        self.assertIsNotNone(order.date_ordered, "Check order has a date")

        url = reverse('orderitem_validate', kwargs={'token': item.token})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = {
            "is_validated": True
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.content)
        order = Order.objects.get(pk=order_id)
        item = order.items.first()
        self.assertEqual(OrderItem.OrderItemStatus.PENDING, item.status, 'Item is ready for extraction')

    def test_order_item_validation(self):
        """
        Tests email is sent when a product needs validation
        """
        self.order_item_validation(False)


    def test_group_with_validation(self):
        """
        Tests email is sent when a product inside a group needs validation
        """
        self.order_item_validation(True)

    def test_order_geom_is_too_big(self):
        updateMaxOrderArea('Produit gratuit', 1000)
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{ 'product': {'label': 'Produit gratuit'} }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                # 2545488 1203070, 2557441 1202601, 2557089 1210921, 2545605 1211390, 2545488 1203070
                [[2545488, 1203070],
                 [2557441, 1202601],
                 [2557089, 1210921],
                 [2545605, 1211390],
                 [2545488, 1203070]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        errorDetails = json.loads(response.content)
        self.assertEqual(errorDetails['message'], ['Order area is too large'])
        self.assertTrue(errorDetails['expected'][0].startswith('34558655.8'))
        self.assertTrue(errorDetails['actual'][0].startswith('97442812.5'))

    def test_order_geom_is_fine(self):
        updateMaxOrderArea('Produit gratuit', 1000000000)
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{ 'product': {'label': 'Produit gratuit'} }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2545488, 1203070],
                 [2557441, 1202601],
                 [2557089, 1210921],
                 [2545605, 1211390],
                 [2545488, 1203070]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

    def test_order_owned_noExcluded(self):
        updateMaxOrderArea('Produit gratuit', 100)
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{
                'product': {'label': 'Produit gratuit'},
        }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2682192.2803059844, 1246970.4157564922],
                 [2682178.2106039342, 1247984.965345809],
                 [2683720.8073948864, 1248006.558970477],
                 [2683735.1414241255, 1246992.0130589735],
                 [2682192.2803059844, 1246970.4157564922]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        order = json.loads(response.content)

        self.assertEqual(len(order["excludedGeom"]["coordinates"]), 0)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

    def test_order_owned_intersects_toobig(self):
        updateMaxOrderArea('Produit gratuit', 1001)
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{
                'product': {'label': 'Produit gratuit'},
        }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2651783.430446268, 1248297.3690953483],
                 [2651756.3479182185, 1251397.9173197772],
                 [2717461.37168784, 1252336.6990602014],
                 [2717522.8814288364, 1249236.639547884],
                 [2651783.430446268, 1248297.3690953483]]
            ]}
        response = self.client.post(url, self.order_data, format='json')

        errorDetails = json.loads(response.content)
        self.assertEqual(errorDetails['message'], ['Order area is too large'])
        self.assertTrue(errorDetails['expected'][0].startswith('34558656.85'))
        self.assertTrue(errorDetails['actual'][0].startswith('203800502.0'))

    def test_order_unowned_limited(self):
        updateMaxOrderArea('Produit gratuit', 10000)
        url = reverse('order-list')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{
                'product': {'label': 'Produit gratuit'},
        }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2682058.9416315095, 1246529.024343783],
                 [2682052.9914918, 1246958.8119991398],
                 [2682208.5772218467, 1246960.9680303528],
                 [2682214.538653401, 1246531.1805305541],
                 [2682058.9416315095, 1246529.024343783]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        order = json.loads(response.content)

        self.assertEqual(len(order["excludedGeom"]["coordinates"]), 1)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)


@override_settings(LANGUAGE_CODE='en')
class OrderValidationTests(APITestCase):

    def setUp(self):
        self.config = BaseObjectsFactory(self.client)
        self.order_data = {
            'order_type': 'Privé',
            'items': [],
            'title': 'Test 1734',
            'description': 'Nice order',
            'geom': {
                'type': 'Polygon',
                'coordinates': [
                    [
                        [
                            2528577.8382161376,
                            1193422.4003930448
                        ],
                        [
                            2542482.6542869355,
                            1193422.4329014618
                        ],
                        [
                            2542482.568523701,
                            1199018.36469272
                        ],
                        [
                            2528577.807487005,
                            1199018.324372703
                        ],
                        [
                            2528577.8382161376,
                            1193422.4003930448
                        ]
                    ]
                ]
            },
        }

    def test_order_toolarge(self):
        updateMaxOrderArea('Produit gratuit', 1000)
        url = reverse('validate-order')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        del self.order_data['order_type']
        self.order_data['items'] = [{ 'product': {'label': 'Produit gratuit'} }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                # 2545488 1203070, 2557441 1202601, 2557089 1210921, 2545605 1211390, 2545488 1203070
                [[2545488, 1203070],
                 [2557441, 1202601],
                 [2557089, 1210921],
                 [2545605, 1211390],
                 [2545488, 1203070]]
            ]}
        response = self.client.post(url, self.order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        errorDetails = json.loads(response.content)["error"]
        self.assertEqual(errorDetails['message'], ['Order area is too large'])
        self.assertTrue(errorDetails['expected'][0].startswith('34558655.8'))
        self.assertTrue(errorDetails['actual'][0].startswith('97442812.5'))

    def test_order_fine(self):
        updateMaxOrderArea('Produit gratuit', 1000000000)
        url = reverse('validate-order')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.config.client_token)
        self.order_data['items'] = [{ 'product': {'label': 'Produit gratuit'} }]
        self.order_data['geom'] = {
            'type': 'Polygon',
            'coordinates': [
                [[2545488, 1203070],
                 [2557441, 1202601],
                 [2557089, 1210921],
                 [2545605, 1211390],
                 [2545488, 1203070]]
            ]}
        del self.order_data['order_type']
        response = self.client.post(url, self.order_data, format='json')
        responseData = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(responseData['geom'], 'SRID=4326;POLYGON ((2545488 1203070, 2557441 1202601, 2557089 1210921, 2545605 1211390, 2545488 1203070))')
        self.assertEqual(responseData['excludedGeom'], 'SRID=2056;POLYGON ((2545605 1211390, 2557089 1210921, 2557441 1202601, 2545488 1203070, 2545605 1211390))')
