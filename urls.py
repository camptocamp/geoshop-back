
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from mozilla_django_oidc.urls import OIDCCallbackClass,OIDCAuthenticateClass
from mozilla_django_oidc.views import OIDCLogoutView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from api.routers import GeoshopRouter
from api import views
import oidc

# Use ROOTURL from settings to prefix all urls
ROOTURL = getattr(settings, 'ROOTURL', '')

# Ensure ROOTURL is properly formatted
if ROOTURL.startswith('/'):
    ROOTURL = ROOTURL[1:]
if not ROOTURL.endswith('/') and not ROOTURL == '':
    ROOTURL += '/'


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
router.register_additional_route_to_root(f'{ROOTURL}extract/order/', 'extract_order')
router.register_additional_route_to_root(f'{ROOTURL}extract/order/fake', 'extract_order_fake')
router.register_additional_route_to_root(f'{ROOTURL}extract/orderitem/', 'extract_orderitem')
router.register_additional_route_to_root(f'{ROOTURL}token', 'token_obtain_pair')
router.register_additional_route_to_root(f'{ROOTURL}token/refresh', 'token_refresh')
router.register_additional_route_to_root(f'{ROOTURL}token/verify', 'token_verify')
router.register_additional_route_to_root(f'{ROOTURL}auth/change', 'auth_change_user')
router.register_additional_route_to_root(f'{ROOTURL}auth/current', 'auth_current_user')
router.register_additional_route_to_root(f'{ROOTURL}auth/password', 'auth_password')
router.register_additional_route_to_root(f'{ROOTURL}auth/password/confirm', 'auth_password_confirm')
router.register_additional_route_to_root(f'{ROOTURL}auth/register', 'auth_register')

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    # this url is used to generate email content
    #TODO FIXME: the favicon is not served correctly
    path('favicon.ico', RedirectView.as_view(url='{}api/favicon.ico'.format(settings.STATIC_URL))),
    re_path(rf'^{ROOTURL}auth/reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
            TemplateView.as_view(),
            name='password_reset_confirm'),
    path(f'{ROOTURL}auth/change/', views.UserChangeView.as_view(), name='auth_change_user'),
    path(f'{ROOTURL}auth/current/', views.CurrentUserView.as_view(), name='auth_current_user'),
    re_path(rf'^{ROOTURL}download/(?P<guid>\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)$',
            views.OrderByUUIDView.as_view(), name='order_uuid'),
    re_path(rf'^{ROOTURL}download/(?P<guid>\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)/get_link$',
            views.DownloadLinkView.as_view(), name='order_uuid_link'),
    path(f'{ROOTURL}auth/password/', views.PasswordResetView.as_view(),name='auth_password'),
    path(f'{ROOTURL}auth/password/confirm', views.PasswordResetConfirmView.as_view(), name='auth_password_confirm'),
    path(f'{ROOTURL}auth/verify-email/', views.VerifyEmailView.as_view(), name='auth_verify_email'),
    re_path(rf'^{ROOTURL}auth/account-confirm-email/(?P<key>[-:\w]+)/$', TemplateView.as_view(),
            name='account_confirm_email'),
    path(f'{ROOTURL}auth/register/', views.RegisterView.as_view(), name='auth_register'),
    path(f'{ROOTURL}extract/order/', views.ExtractOrderView.as_view(), name='extract_order'),
    path(f'{ROOTURL}extract/orderitem/', views.ExtractOrderItemView.as_view(), name='extract_orderitem'),
    re_path(rf'^{ROOTURL}extract/orderitem/(?P<pk>[0-9]+)$',
            views.ExtractOrderItemView.as_view(), name='extract_orderitem'),
    path(f'{ROOTURL}token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path(f'{ROOTURL}token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path(f'{ROOTURL}token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path(f'{ROOTURL}session-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(rf'^{ROOTURL}validate/orderitem/(?P<token>[a-zA-Z0-9_-]+)$',
            views.OrderItemByTokenView.as_view(), name='orderitem_validate'),
    path(f'{ROOTURL}admin/', admin.site.urls, name='admin'),
    path(f'{ROOTURL}', include(router.urls)),
    path(f'{ROOTURL}docs/schema', SpectacularAPIView.as_view(), name='schema'),
    path(f'{ROOTURL}docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path(f'{ROOTURL}health/', include('health_check.urls')),
] + static(settings.STATIC_URL,document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)

            # OIDC urls
if settings.OIDC_ENABLED:
    urlpatterns += [
        path(f'{ROOTURL}oidc/callback', OIDCCallbackClass.as_view(), name='oidc_authentication_callback'),
        path(f'{ROOTURL}oidc/authenticate/', OIDCAuthenticateClass.as_view(), name='oidc_authentication_init'),
        path(f'{ROOTURL}oidc/logout', OIDCLogoutView.as_view(), name='oidc_logout'),
    ]
