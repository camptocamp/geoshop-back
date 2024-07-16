
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from api.routers import GeoshopRouter
from api import views

admin.site.site_header = _("GeoShop Administration")
admin.site.site_title = _("GeoShop Admin")

router = GeoshopRouter()
router.register(r'contact', views.ContactViewSet, basename='contact')
router.register(r'copyright', views.CopyrightViewSet)
router.register(r'document', views.DocumentViewSet)
router.register(r'dataformat', views.DataFormatViewSet)
router.register(r'identity', views.IdentityViewSet, basename='identity')
router.register(r'metadata', views.MetadataViewSet, basename='metadata')
router.register(r'order', views.OrderViewSet, basename='order')
router.register(r'orderitem', views.OrderItemViewSet, basename='orderitem')
router.register(r'ordertype', views.OrderTypeViewSet)
router.register(r'product', views.ProductViewSet, basename='product')
router.register(r'productformat', views.ProductFormatViewSet)
router.register(r'pricing', views.PricingViewSet)
router.register_additional_route_to_root('extract/order/', 'extract_order')
router.register_additional_route_to_root('extract/order/fake', 'extract_order_fake')
router.register_additional_route_to_root('extract/orderitem/', 'extract_orderitem')
router.register_additional_route_to_root('token', 'token_obtain_pair')
router.register_additional_route_to_root('token/refresh', 'token_refresh')
router.register_additional_route_to_root('token/verify', 'token_verify')
router.register_additional_route_to_root('auth/change', 'auth_change_user')
router.register_additional_route_to_root('auth/current', 'auth_current_user')
router.register_additional_route_to_root('auth/password', 'auth_password')
router.register_additional_route_to_root('auth/password/confirm', 'auth_password_confirm')
router.register_additional_route_to_root('auth/register', 'auth_register')

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    # this url is used to generate email content
    path('favicon.ico', RedirectView.as_view(url='{}api/favicon.ico'.format(settings.STATIC_URL))),
    re_path(r'^auth/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
            TemplateView.as_view(),
            name='password_reset_confirm'),
    path('auth/change/', views.UserChangeView.as_view(), name='auth_change_user'),
    path('auth/current/', views.CurrentUserView.as_view(), name='auth_current_user'),
    re_path(r'^download/(?P<guid>\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)$',
            views.OrderByUUIDView.as_view(), name='order_uuid'),
    re_path(r'^download/(?P<guid>\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)/get_link',
            views.DownloadLinkView.as_view(), name='order_uuid_link'),
    path('auth/password/', views.PasswordResetView.as_view(), name='auth_password'),
    path('auth/password/confirm', views.PasswordResetConfirmView.as_view(), name='auth_password_confirm'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='auth_verify_email'),
    re_path(r'^auth/account-confirm-email/(?P<key>[-:\w]+)/$', TemplateView.as_view(),
            name='account_confirm_email'),
    path('auth/register/', views.RegisterView.as_view(), name='auth_register'),
    path('extract/order/', views.ExtractOrderView.as_view(), name='extract_order'),
    path('extract/orderitem/', views.ExtractOrderItemView.as_view(), name='extract_orderitem'),
    re_path(r'^extract/orderitem/(?P<pk>[0-9]+)',
            views.ExtractOrderItemView.as_view(), name='extract_orderitem'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('session-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^validate/orderitem/(?P<token>[a-zA-Z0-9_-]+)$',
            views.OrderItemByTokenView.as_view(), name='orderitem_validate'),
    path('admin/', admin.site.urls, name='admin'),
    path('', include(router.urls)),
    path('api/docs/schema', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('health/', include('health_check.urls')),
] + static(settings.STATIC_URL,document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)