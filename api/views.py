from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_post_parameters

from rest_framework import filters, generics, views, viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.parsers import MultiPartParser

from drf_spectacular.utils import extend_schema

from allauth.account.views import ConfirmEmailView

from .models import (
    Contact, Copyright, Document, DataFormat, Identity, Metadata, MetadataContact,
    Order, OrderItem, OrderType, Pricing, Product,
    ProductFormat, UserChange)

from .serializers import (
    ContactSerializer, CopyrightSerializer, DocumentSerializer, DataFormatSerializer,
    ExtractOrderSerializer,
    ExtractOrderItemSerializer, UserIdentitySerializer, MetadataIdentitySerializer,
    MetadataSerializer, MetadataContactSerializer, OrderDigestSerializer,
    OrderSerializer, OrderItemSerializer, OrderItemValidationSerializer, OrderTypeSerializer,
    PasswordResetSerializer, PasswordResetConfirmSerializer,
    PricingSerializer, ProductSerializer, ProductDigestSerializer, PublicOrderSerializer,
    ProductFormatSerializer, RegisterSerializer, UserChangeSerializer,
    VerifyEmailSerializer, ValidationSerializer)

from .helpers import send_geoshop_email

from .filters import FullTextSearchFilter

from .permissions import ExtractGroupPermission, InternalGroupObjectPermission

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters(
        'password', 'old_password', 'new_password1', 'new_password2'
    )
)

UserModel = get_user_model()


class CopyrightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Copyright to be viewed.
    """
    queryset = Copyright.objects.all()
    serializer_class = CopyrightSerializer


class ContactViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.DestroyModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    API endpoint that allows Contacts to be viewed, searched or edited.
    Only will retrieve is_active=True on search
    """
    search_fields = ['first_name', 'last_name', 'company_name']
    filter_backends = [filters.SearchFilter]
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        keywords = self.request.query_params.get('search')
        if keywords:
            return Contact.objects.filter(Q(belongs_to=user.id) & Q(is_active=True))
        return Contact.objects.filter(belongs_to=user.id)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

class CurrentUserView(views.APIView):
    """
    API endpoint that allows users to register.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=UserIdentitySerializer,
    )
    def get(self, request):
        user = request.user
        ser = UserIdentitySerializer(user, context={'request': request})
        return Response(ser.data)


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Document to be viewed.
    """
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer


class DataFormatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Format to be viewed.
    """
    queryset = DataFormat.objects.all()
    serializer_class = DataFormatSerializer


class IdentityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Identity to be viewed.
    Only retrieves the current user or "public" identities.
    Authentication is mandatory to access this ressource.

    You can search an identity with `?search=` param.
    Searchable properties are:
     - email
    """
    search_fields = ['email']
    filter_backends = [filters.SearchFilter]
    serializer_class = MetadataIdentitySerializer

    def get_queryset(self):
        user = self.request.user
        return Identity.objects.filter(Q(user_id=user.id) | Q(is_public=True))


class MetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Metadata to be viewed.
    `public` and `approval needed` metadatas can be viewed by everyone.
    All metadatas can be accessed only by users belonging to `intranet` group.
    """
    permission_classes = [InternalGroupObjectPermission]
    serializer_class = MetadataSerializer
    lookup_field = 'id_name'

    @action(detail=True, renderer_classes=[TemplateHTMLRenderer])
    def html(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data, template_name="metadata.html")
        response['Access-Control-Allow-Origin'] = '*'
        response['Content-Security-Policy'] = 'frame-ancestors *'
        return response

    @action(detail=True, renderer_classes=[TemplateHTMLRenderer])
    def html_simple(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data, template_name="metadata_simple.html")
        response['Access-Control-Allow-Origin'] = '*'
        response['Content-Security-Policy'] = 'frame-ancestors *'
        return response

    def get_queryset(self):
        user = self.request.user
        has_permision = user.has_perm('api.view_internal')
        if has_permision:
            return Metadata.objects.all()
        return Metadata.objects.filter(accessibility__in=settings.METADATA_PUBLIC_ACCESSIBILITIES)

    def get_serializer_context(self):
        context = super(MetadataViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context


class MetadataContactViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows MetadataContact to be viewed.
    """
    queryset = MetadataContact.objects.all()
    serializer_class = MetadataContactSerializer


class MultiSerializerMixin():
    serializers = {
        'default': None,
    }

    def get_serializer_class(self):
        return self.serializers.get(self.action,
                                    self.serializers['default'])


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows OrderItem to be viewed.
    """
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return OrderItem.objects.filter(order__client_id=user.id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        order = instance.order
        if order.order_status not in [Order.OrderStatus.DRAFT, Order.OrderStatus.PENDING]:
            return Response(
                {"detail": _("This orderitem cannot be deleted anymore.")},
                status=status.HTTP_403_FORBIDDEN
            )
        response = super(OrderItemViewSet, self).destroy(request, *args, **kwargs)
        order.set_price()
        return response

    @action(detail=True, methods=['get'])
    def download_link(self, request, pk=None):
        """
        Returns the download link
        """
        instance = self.get_object()
        if instance.extract_result:
            instance.last_download = timezone.now()
            instance.save()
            if Path(settings.MEDIA_ROOT, instance.extract_result.name).is_file():
                return Response({
                    'download_link' : instance.extract_result.url})
            return Response(
                {"detail": _("Zip does not exist")},
                status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)


class OrderTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows OrderType to be viewed.
    """
    queryset = OrderType.objects.all()
    serializer_class = OrderTypeSerializer


class OrderViewSet(MultiSerializerMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows Orders to be viewed or edited.
    Only orders that belong to current authenticated user are shown.

    You can search an order with `?search=` param.
    Searchable properties are:
     - title
     - description

    `PUT` or `PATCH` on the items property will behave the same.
    The route will check for each product name if is is already present in existing items list.
    If yes, no action is taken, if no, product is added.
    If an existing product is present in the list of items but the
    `PUT` or `PATCH` data doesn't mention it, then the existing item is deleted.

    To modify or delete an existing item, please use `/orderitem/` endpoint.
    """
    search_fields = ['title', 'description', 'id']
    ordering_fields = ['id']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    serializers = {
        'default':  OrderSerializer,
        'list':    OrderDigestSerializer,
    }
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(client_id=user.id)

    def update(self, request, pk=None, *args, **kwargs):
        queryset = self.get_queryset()
        order = get_object_or_404(queryset, pk=pk)
        if order.order_status == Order.OrderStatus.DRAFT:
            return super(OrderViewSet, self).update(request, pk, *args, **kwargs)
        raise PermissionDenied(detail='Order status is not DRAFT.')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.order_status == Order.OrderStatus.DRAFT:
            response = super(OrderViewSet, self).destroy(request, *args, **kwargs)
            return response

        if instance.order_status == Order.OrderStatus.QUOTE_DONE:
            instance.order_status = Order.OrderStatus.REJECTED
            instance.save()
            return Response(
                status=status.HTTP_204_NO_CONTENT
            )

        return Response(
            {"detail": _("This order cannot be deleted anymore.")},
            status=status.HTTP_403_FORBIDDEN
        )

    @action(detail=False, methods=['get'])
    def last_draft(self, request):
        """
        Returns the last saved order having a "DRAFT" status. If there's no DRAFT, returns a 204.
        """
        user = self.request.user
        last_draft = Order.objects.filter(client_id=user.id, order_status=Order.OrderStatus.DRAFT).first()
        if last_draft:
            serializer = OrderSerializer(last_draft, context={'request': request}, partial=True)
            return Response(serializer.data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def confirm(self, request, pk=None):
        """
        Confirms order meaning it can not be edited anymore by user.
        """
        order = self.get_object()
        if order.order_status not in [Order.OrderStatus.DRAFT, Order.OrderStatus.QUOTE_DONE]:
            raise PermissionDenied(detail='Order status is not DRAFT or QUOTE_DONE')
        items = order.items.all()
        if not items:
            raise ValidationError(detail="This order has no item")
        for item in items:
            if not item.data_format:
                raise ValidationError(detail="One or more items don't have data_format")
        order.confirm()
        order.save()
        return Response(status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'])
    def download_link(self, request, pk=None):
        """
        Returns the download link
        """
        instance = self.get_object()
        if instance.extract_result:
            instance.date_downloaded = timezone.now()
            instance.save()
            if Path(settings.MEDIA_ROOT, instance.extract_result.name).is_file():
                return Response({
                    'download_link' : instance.extract_result.url})
            return Response(
                {"detail": _("Full zip is not ready")},
                status=status.HTTP_200_OK)
        return Response(status=status.HTTP_404_NOT_FOUND)


class ExtractOrderView(views.APIView):
    """
    API endpoint that allows Orders to be fetched by Extract.
    This endpoint searches for orderitems belonging to current Extract user and
    rebuilds Order context around the order item for each matched order item.
    """
    permission_classes = [ExtractGroupPermission]

    @extend_schema(
            responses=ExtractOrderSerializer
    )
    def get(self, request, *args, **kwargs):
        # Start by getting orderitems that are PENDING and that will be extracted by current user
        order_items = OrderItem.objects.filter(
            (
                Q(order__order_status=Order.OrderStatus.READY) |
                Q(order__order_status=Order.OrderStatus.PARTIALLY_DELIVERED)
            ) &
            Q(product__provider=request.user) &
            Q(status=OrderItem.OrderItemStatus.PENDING)
        ).order_by('order_id').all()
        response_data = []
        order_data = { 'id': None }
        for item in order_items:
            if order_data['id'] != item.order_id:
                # Serialize order to get order informations
                order_serializer = ExtractOrderSerializer(item.order)
                order_data = order_serializer.data
                order_data['items'] = []
                response_data.append(order_data)

            # Serialize order item
            item_serializer = ExtractOrderItemSerializer(item)
            item_data = item_serializer.data
            # Replace items in the order by the only concerned item
            order_data['items'].append(item_data)
            # Once fetched by extract, status of item changes
            item.status = OrderItem.OrderItemStatus.IN_EXTRACT
            item.save()
        if len(response_data) == 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(response_data)


class ExtractOrderItemView(generics.UpdateAPIView):
    """
    API endpoint that allows Orders to be fetched by Extract
    """
    parser_classes = [MultiPartParser]
    serializer_class = ExtractOrderItemSerializer
    permission_classes = [ExtractGroupPermission]
    queryset = OrderItem.objects.all()
    http_method_names = ['put']

    def put(self, request, *args, **kwargs):
        """Allows to upload a file and destroys existing one or cancel orderitem"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = self.get_object()
            serializer.update(instance, serializer.validated_data)
            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Copy from dj-rest-auth
class PasswordResetView(generics.GenericAPIView):
    """
    <b>SMTP Server needs to be configured before using this route</b>

    Returns the success/fail message.
    """
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        # Create a serializer with request.data
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()
        # Return the success message with OK HTTP status
        return Response(
            {"detail": _("Password reset e-mail has been sent.")},
            status=status.HTTP_200_OK
        )


# Copy from dj-rest-auth
class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Password reset e-mail link is confirmed, therefore
    this resets the user's password.
    Accepts the following POST parameters: token, uid,
        new_password1, new_password2
    Returns the success/fail message.
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super(PasswordResetConfirmView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": _("Password has been reset with the new password.")}
        )


class ProductFormatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows ProductFormat to be viewed.
    """
    queryset = ProductFormat.objects.all()
    serializer_class = ProductFormatSerializer


class ProductViewSet(MultiSerializerMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Product to be viewed.

    You can search a product with `?search=` param.
    Searchable properties are:
     - label
    """
    querysets = {
        'default': Product.objects.all(),
        'list': Product.objects.filter(product_status=Product.ProductStatus.PUBLISHED)
    }
    filter_backends = (FullTextSearchFilter,)
    serializers = {
        'default': ProductSerializer,
        'list': ProductDigestSerializer,
    }
    ts_field = 'ts'

    def get_queryset(self):
        return self.querysets.get(self.action, self.querysets['default'])


class PricingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Pricing to be viewed.
    """
    queryset = Pricing.objects.all()
    serializer_class = PricingSerializer


class RegisterView(generics.CreateAPIView):
    """
    API endpoint that allows users to register.
    """
    queryset = UserModel.objects.all().order_by('-date_joined')
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        response = super(RegisterView, self).post(request, *args, **kwargs)
        user = UserModel.objects.get(pk=response.data['id'])
        user.is_active = False
        user.save()
        send_geoshop_email(
            _('Geoshop - New user request'),
            template_name='email_admin',
            template_data={
                'messages': [_('A new user account needs to be validated:')],
                'admin_url': 'admin:auth_user_change',
                'admin_url_params': user.id,
                'current_site':request.get_host(),
                'protocol': request.scheme
            }
        )
        send_geoshop_email(
            _('Geoshop - New account pending'),
            recipient=user.identity,
            template_name='email_welcome_user',
            template_data=UserIdentitySerializer(user).data
        )

        return Response({'detail': _('Your data was successfully submitted')}, status=status.HTTP_200_OK)


class OrderByUUIDView(generics.RetrieveAPIView):
    """
    Returns an order based on in its UUID
    """
    queryset = Order.objects.all()
    serializer_class = PublicOrderSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, guid):
        queryset = self.get_queryset()
        order = get_object_or_404(queryset, download_guid=guid)
        serializer = PublicOrderSerializer(order, context={'request': request})
        return Response(serializer.data)


class OrderItemByTokenView(generics.RetrieveAPIView):
    """
    Returns an orderitem based on its token.
    PATCH allows to validate the order item:
      * `{'is_validated': true}` will validate
      * `{'is_validated': false}` will reject the order item but order will proceed
    """
    queryset = OrderItem.objects.filter(status=OrderItem.OrderItemStatus.VALIDATION_PENDING)
    serializer_class = OrderItemValidationSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        queryset = self.get_queryset()
        item = get_object_or_404(queryset, token=token)
        serializer = OrderItemValidationSerializer(item, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, token):
        queryset = self.get_queryset()
        item = get_object_or_404(queryset, token=token)

        validation_serializer = ValidationSerializer(data=request.data)
        validation_serializer.is_valid()
        is_validated = validation_serializer.validated_data['is_validated']
        item.validation_date = timezone.now()

        if is_validated:
            item.status = OrderItem.OrderItemStatus.PENDING
            item.save()
        else:
            item.status = OrderItem.OrderItemStatus.REJECTED
            item.save()
            item.order.next_status_on_extract_input()
            item.order.save()
        return Response(status=status.HTTP_202_ACCEPTED)

class DownloadView(generics.RetrieveAPIView):
    """
    Returns the download link based on order UUID
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, guid):
        queryset = self.get_queryset()
        instance = get_object_or_404(queryset, download_guid=guid)
        if instance.extract_result:
            file = Path(settings.MEDIA_ROOT, instance.extract_result.name)
            if file.is_file():
                with open(file, 'rb') as result:
                    response = Response(
                        headers={'Content-Disposition': 'attachment; filename="report.zip"'},
                        content_type='application/zip'
                    )
                    response.content = result.read()
                    return response
            else:
                return Response(
                    {"detail": _("Zip does not exist")},
                    status=status.HTTP_200_OK)
            instance.date_downloaded = timezone.now()
            instance.save()
        return Response(status=status.HTTP_404_NOT_FOUND)

class UserChangeView(generics.CreateAPIView):
    """
    API endpoint that allows users to submit profile changes.
    The changes are stored in a DB table and an email is
    sent to the admins.
    """
    queryset = UserChange.objects.all()
    serializer_class = UserChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):

        request.data['client'] = request.user.id

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        base_user = UserModel.objects.get(pk=request.user.id)

        changes = {}

        for key in serializer.data:
            if hasattr(base_user.identity, key):
                request_value = serializer.data[key]
                if request_value != getattr(base_user.identity, key):
                    changes[_(key)] = request_value

        send_geoshop_email(
            _('Geoshop - User change request'),
            template_name='email_admin',
            template_data={
                'messages': [_(
                    'The user {} has requested some changes for his user profile.'
                    ).format(base_user.username)],
                'details': changes
            }
        )
        send_geoshop_email(
            _('Geoshop - Your changes request'),
            recipient=base_user.identity,
            template_name='email_user_change',
            template_data=UserIdentitySerializer(base_user).data
        )

        return Response({'detail': _('Your data was successfully submitted')}, status=status.HTTP_200_OK)


class VerifyEmailView(views.APIView, ConfirmEmailView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = []
    allowed_methods = ('POST', 'OPTIONS', 'HEAD')

    def get_serializer(self, *args, **kwargs):
        return VerifyEmailSerializer(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.kwargs['key'] = serializer.validated_data['key']
        confirmation = self.get_object()
        confirmation.confirm(self.request)
        return Response({'detail': _('ok')}, status=status.HTTP_200_OK)
