from urllib.parse import urljoin

from django.contrib.syndication.views import Feed
from django.http import HttpRequest
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import ProductUpdate

def absolute_reverse(feed_name, args=None, kwargs=None):
    """
    This method returns the absolute URL for a given feed name by joining the base URL from settings
    with the reverse URL generated from the feed name, arguments, and keyword arguments.
    """
    return urljoin(
        settings.FEED_BASE_URL,
        reverse(feed_name, args=args, kwargs=kwargs),
    )

class OverallProductUpdateFeed(Feed):
    """
    This class represents an RSS feed that provides information about the latest data set updates of
    all the available products registered for RSS feeds.

    The RSS feed is limited to the latest 15 overall product updates.
    """
    title = "Product updates"
    description = "Latest product update feed"

    def link(self):
        return absolute_reverse("overall-product-update-feed")

    def items(self):
        return ProductUpdate.objects.order_by("-created_at")[:15]

    def item_title(self, item: ProductUpdate):
        return item.title + ' - ' + item.product.label

    def item_description(self, item: ProductUpdate):
        return item.product.label + ": last data import at " + item.created_at.strftime("%d/%m/%Y %H:%M:%S")

    def item_link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])


class SingleProductUpdateFeed(Feed):
    """
    This class represents an RSS feed that provides information about the latest data set updates of
    a single product.

    The RSS feed is limited to the latest 15 updates.
    """

    def get_object(self, request: HttpRequest, *args, **kwargs):
        return get_object_or_404(ProductUpdate.objects.filter(product_id=kwargs["pk"]).order_by("-created_at")[:1])

    def title(self, item: ProductUpdate):
        return item.title + ' - ' + item.product.label

    def description(self, item: ProductUpdate):
        return "Latest updates/imports for product " + item.product.label

    def link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])

    def items(self, item: ProductUpdate):
        return ProductUpdate.objects.filter(product_id=item.product.id).order_by("-created_at")[:15]

    def item_title(self, item: ProductUpdate):
        return self.title(item)

    def item_description(self, item: ProductUpdate):
        return "Data set updated at " + item.created_at.strftime("%d/%m/%Y %H:%M:%S")

    def item_link(self, item: ProductUpdate):
        return absolute_reverse("single-product-update-feed", args=[item.product.id])