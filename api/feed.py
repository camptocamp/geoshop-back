from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import ProductUpdate

# check for naming (DatasetUpdateFeed) is a Dataset = Product?
class OverallProductUpdateFeed(Feed):

    def items(self):
        return ProductUpdate.objects.order_by("-created_at")[:15]

    def item_title(self, item: ProductUpdate):
        return item.product.metadata.name

    def item_description(self, item: ProductUpdate):
        return item.product.metadata.name + ": last data import at " + item.created_at.strftime("%d/%m/%Y %H:%M:%S")

    # item_link is only needed if item has no get_absolute_url method.
    def item_link(self, item: ProductUpdate):
        return reverse("product-update", args=[item.pk])


class SingleProductUpdateFeed(OverallProductUpdateFeed):

    def items(self):
        return ProductUpdate.objects.filter(product__metadata_id=self.kwargs["pk"]).order_by("-created_at").first()