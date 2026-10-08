from urllib.parse import urljoin

from django.contrib.syndication.views import Feed
from django.http import HttpRequest
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import ProductUpdate

def absolute_reverse(feed_name, args=None, kwargs=None):
    """
    Return the absolute URL for a given feed name by joining
    the base URL from settings with the reversed URL.
    """
    return urljoin(
        settings.FEED_BASE_URL,
        reverse(feed_name, args=args, kwargs=kwargs),
    )

class OverallProductUpdateFeed(Feed):
    """
    RSS feed providing the latest dataset updates for all products.

    The feed is limited to the latest 200 updates.
    """
    title = "Product updates"
    description = "Latest product update feed"

    def link(self):
        return absolute_reverse("overall-product-update-feed")

    def feed_url(self):
        return self.link()

    def items(self):
        return ProductUpdate.objects.order_by(
            "-created_at", "-id"
        )[:200]

    def item_title(self, item: ProductUpdate):
        return item.title + " - " + item.product.label

    def item_description(self, item: ProductUpdate):
        return (
            item.product.label
            + ": last data import at "
            + item.created_at.strftime("%d/%m/%Y %H:%M:%S")
        )

    def item_link(self, item: ProductUpdate):
        return absolute_reverse(
            "single-product-update-feed",
            args=[item.product_id],
        )

    def item_guid(self, item: ProductUpdate):
        return f"geoshop:product-update:{item.id}"

    item_guid_is_permalink = False

    def item_pubdate(self, item: ProductUpdate):
        return item.created_at


class SingleProductUpdateFeed(Feed):
    """
    RSS feed providing the latest dataset updates for a single product.

    The feed is limited to the latest 200 updates.
    """

    def get_object(self, request: HttpRequest, *args, **kwargs):
        return get_object_or_404(
            ProductUpdate.objects.filter(
                product_id=kwargs["pk"]
            ).order_by("-created_at", "-id")[:1]
        )

    def title(self, item: ProductUpdate):
        return item.product.label + " - Datenaktualisierungen"

    def description(self, item: ProductUpdate):
        return "Latest updates/imports for product " + item.product.label

    def link(self, item: ProductUpdate):
        return absolute_reverse(
            "single-product-update-feed",
            args=[item.product_id],
        )

    def feed_url(self, item: ProductUpdate):
        return self.link(item)

    def items(self, item: ProductUpdate):
        return ProductUpdate.objects.filter(
            product_id=item.product_id
        ).order_by("-created_at", "-id")[:200]

    def item_title(self, item: ProductUpdate):
        return item.title + " - " + item.product.label

    def item_description(self, item: ProductUpdate):
        return (
            "Data set updated at "
            + item.created_at.strftime("%d/%m/%Y %H:%M:%S")
        )

    def item_link(self, item: ProductUpdate):
        return absolute_reverse(
            "single-product-update-feed",
            args=[item.product_id],
        )

    def item_guid(self, item: ProductUpdate):
        return f"geoshop:product-update:{item.id}"

    item_guid_is_permalink = False

    def item_pubdate(self, item: ProductUpdate):
        return item.created_at
