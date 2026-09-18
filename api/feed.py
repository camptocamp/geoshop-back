from urllib.parse import urljoin

from django.contrib.syndication.views import Feed
from django.http import HttpRequest
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import ProductUpdate

def absolute_reverse(feed_name, args=None, kwargs=None):
    return urljoin(
        settings.FEED_BASE_URL,
        reverse(feed_name, args=args, kwargs=kwargs),
    )

class OverallProductUpdateFeed(Feed):
    title = "Product updates"
    description = "Latest product update feed"

    def link(self):
        return absolute_reverse("product-update-feed")

    def items(self):
        return ProductUpdate.objects.order_by("-created_at")[:15]

    def item_title(self, item: ProductUpdate):
        return item.product.label

    def item_description(self, item: ProductUpdate):
        return item.product.label + ": last data import at " + item.created_at.strftime("%d/%m/%Y %H:%M:%S")

    def item_link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])


class SingleProductUpdateFeed(Feed):

    def get_object(self, request: HttpRequest, *args, **kwargs):
        return get_object_or_404(ProductUpdate.objects.filter(product_id=kwargs["pk"]).order_by("-created_at")[:1])

    def title(self, item: ProductUpdate):
        return item.product.label

    def description(self, item: ProductUpdate):
        return "Latest updates/imports for product " + item.product.label

    def link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])

    def items(self, item: ProductUpdate):
        return ProductUpdate.objects.filter(product_id=item.product.id).order_by("-created_at")[:15]

    def item_title(self, item: ProductUpdate):
        return item.product.label

    def item_description(self, item: ProductUpdate):
        return "Data set updated at " + item.created_at.strftime("%d/%m/%Y %H:%M:%S")

    def item_link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])