from django.urls import reverse
from rest_framework import status

from api.feed import absolute_reverse
from api.models import Product, ProductUpdate, Metadata, Pricing
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from api.routers import GeoshopRouter

UserModel = get_user_model()

class FeedTest(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = UserModel.objects.create_user(username='feed_provider', password='password')
        cls.metadata = Metadata.objects.create(id_name='feed-metadata', modified_user=cls.user)
        cls.pricing = Pricing.objects.create(name='Free', pricing_type='FREE')

        # Create test products
        cls.product_alpha = Product.objects.create(
            label="Product Alpha",
            pricing=cls.pricing,
            metadata=cls.metadata,
            provider=cls.user
        )
        cls.product_beta = Product.objects.create(
            label="Product Beta",
            pricing=cls.pricing,
            metadata=cls.metadata,
            provider=cls.user
        )

        # Create product updates
        cls.update_a1 = ProductUpdate.objects.create(product=cls.product_alpha, title="Alpha Update 1")
        cls.update_a2 = ProductUpdate.objects.create(product=cls.product_alpha, title="Alpha Update 2")
        cls.update_b1 = ProductUpdate.objects.create(product=cls.product_beta, title="Beta Update 1")

    def test_absolute_reverse(self):
        result = absolute_reverse("overall-product-update-feed")
        expected_path = reverse("overall-product-update-feed")

        self.assertEqual(result, f"http://localhost:8000{expected_path}")
        self.assertEqual(result, "http://localhost:8000/rss/all")

    def test_get_overall_product_update_feed(self):
        url = reverse('overall-product-update-feed')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/rss+xml; charset=utf-8')

        content = response.content.decode('utf-8')

        self.assertIn('<title>Product updates</title>', content)
        self.assertIn('<link>http://localhost:8000/rss/all</link>', content)
        self.assertIn('<description>Latest product update feed</description>', content)

        self.assertIn(f'<title>{self.product_alpha.label}</title>', content)
        self.assertIn(f'<link>http://localhost:8000/rss/product/{self.product_alpha.id}</link>', content)
        date_str = self.update_a2.created_at.strftime("%d/%m/%Y %H:%M:%S")
        self.assertIn(f'<description>{self.product_alpha.label}: last data import at {date_str}</description>', content)

        self.assertIn(f'<title>{self.product_beta.label}</title>', content)
        self.assertIn(f'<link>http://localhost:8000/rss/product/{self.product_beta.id}</link>', content)
        date_str = self.update_b1.created_at.strftime("%d/%m/%Y %H:%M:%S")
        self.assertIn(f'<description>{self.product_beta.label}: last data import at {date_str}</description>', content)

    def test_get_overall_product_update_feed_entries_limit(self):
        for i in range(16):
            ProductUpdate.objects.create(product=self.product_alpha, title=f"Alpha Update {i}")

        url = reverse('overall-product-update-feed')
        response = self.client.get(url)

        content = response.content.decode('utf-8')

        self.assertEqual(content.count('<item>'), 15)

    def test_get_single_product_update_feed(self):
        url = reverse('single-product-update-feed', args=[self.product_alpha.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/rss+xml; charset=utf-8')

        content = response.content.decode('utf-8')

        self.assertIn(f'<title>{self.product_alpha.label}</title>', content)
        self.assertIn(f'<description>Latest updates/imports for product {self.product_alpha.label}</description>', content)
        self.assertIn(f'<link>http://localhost:8000/rss/product/{self.product_alpha.id}</link>', content)

        date_str_update_a1 = self.update_a1.created_at.strftime("%d/%m/%Y %H:%M:%S")
        self.assertIn(f'<description>Data set updated at {date_str_update_a1}</description>', content)

        date_str_update_a2 = self.update_a2.created_at.strftime("%d/%m/%Y %H:%M:%S")
        self.assertIn(f'<description>Data set updated at {date_str_update_a2}</description>', content)

        self.assertEqual(content.count('<item>'), 2)

    def test_get_single_product_update_feed_entries_limit(self):
        for i in range(16):
            ProductUpdate.objects.create(product=self.product_alpha, title=f"Alpha Update {i}")

        url = reverse('single-product-update-feed', args=[self.product_alpha.id])
        response = self.client.get(url)

        content = response.content.decode('utf-8')

        self.assertEqual(content.count('<item>'), 15)

    def test_get_single_product_update_feed_not_found(self):
        # Product does not exist
        url = reverse('single-product-update-feed', args=[99999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Product exists but has no updates
        product_gamma = Product.objects.create(
            label="Product Gamma",
            pricing=self.pricing,
            metadata=self.metadata,
            provider=self.user
        )
        url = reverse('single-product-update-feed', args=[product_gamma.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_product_update_feed_view_set(self):
        url = absolute_reverse('feeds-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        feeds: list[dict] = response.data
        print(feeds)
        self.assertTrue(isinstance(feeds, list))
        self.assertEqual(len(feeds), 3)
        names = [feed['name'] for feed in feeds]
        urls = [feed['url'] for feed in feeds]
        self.assertIn(f'http://localhost:8000/rss/product/{self.product_alpha.id}', urls)
        self.assertIn(f'http://localhost:8000/rss/product/{self.product_beta.id}', urls)
        self.assertIn(f'http://localhost:8000/rss/all', urls)
        self.assertIn(f'Product Alpha', names)
        self.assertIn(f'Product Beta', names)
        self.assertIn(f'All Product Updates', names)


