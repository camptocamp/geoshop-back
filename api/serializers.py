import json
import copy
from shapely.geometry.polygon import Polygon

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import Polygon, MultiPolygon, GEOSException, GEOSGeometry, WKTWriter
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from djmoney.contrib.django_rest_framework import MoneyField

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from allauth.account.adapter import get_adapter

from .helpers import send_geoshop_email, zip_all_orderitems
from .models import (
    Copyright, Contact, Document, DataFormat, Group, Identity,
    Metadata, MetadataCategoryEch, MetadataContact, Order, OrderItem, OrderType,
    Pricing, Product, ProductFormat, ProductOwnership, UserChange)

from typing import List, Dict

# Get the UserModel
UserModel = get_user_model()
import logging

logger = logging.getLogger(__name__)

class WKTPolygonField(serializers.Field):
    """
    Polygons are serialized to POLYGON((Long, Lat)) notation
    """

    def to_representation(self, value) -> str:
        if isinstance(value, dict) or value is None:
            return value
        new_value = copy.copy(value)
        wkt_w = WKTWriter()

        # Use buffer and Douglas-Peucker to simplify geom (one vertex 0.2m) for large polygons
        # The smallest Cadastre has 156 vertices
        # TODO is this generally true or only for NE?
        if new_value.num_coords > 156:
            new_value = new_value.buffer(0.5)
            new_value = new_value.simplify(0.2, preserve_topology=False)
            wkt_w.precision = 6
        new_value.transform(4326)

        # number of decimals

        if new_value.area > 0:
            return wkt_w.write(new_value).decode()
        return 'POLYGON EMPTY'

    def to_internal_value(self, value):
        if value == '' or value is None:
            return value
        if isinstance(value, GEOSGeometry):
            # value already has the correct representation
            return value
        if isinstance(value, dict):
            value = json.dumps(value)
        try:
            return GEOSGeometry(value)
        except (GEOSException):
            raise ValidationError(
                _(
                    'Invalid format: string or unicode input unrecognized as GeoJSON, WKT EWKT or HEXEWKB.'
                )
            )
        except (ValueError, TypeError, GDALException) as error:
            raise ValidationError(
                _('Unable to convert to python object: {}'.format(str(error)))
            )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = [
            'username', 'id', 'identity'
        ]


class IdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Identity
        exclude = ['sap_id', 'contract_accepted', 'is_public', 'user']


class CopyrightSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Copyright
        fields = '__all__'


class ContactSerializer(serializers.HyperlinkedModelSerializer):
    belongs_to = serializers.HiddenField(
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = Contact
        fields = '__all__'


class DocumentSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'


class DataFormatSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = DataFormat
        fields = '__all__'


class OrderTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderType
        fields = '__all__'


class UserIdentitySerializer(UserSerializer):
    """
    Flattens User and Identity.
    """
    identity = IdentitySerializer(many=False)

    def to_representation(self, instance):
        """Move fields from user to identity representation."""
        representation = super().to_representation(instance)
        identity_representation = representation.pop('identity')
        for identity_key in identity_representation:
            new_key = identity_key
            if new_key in representation:
                new_key = 'identity_' + identity_key
            representation[new_key] = identity_representation[identity_key]
        return representation


class MetadataIdentitySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Identity
        fields = [
            'url',
            'first_name', 'last_name', 'email',
            'phone', 'street', 'street2',
            'company_name',
            'postcode', 'city', 'country']


class PublicUserIdentitySerializer(UserIdentitySerializer):
    """
    User serializer that is safe to use on token protected routes.
    """
    identity = MetadataIdentitySerializer(many=False)


class MetadataContactSerializer(serializers.HyperlinkedModelSerializer):
    contact_person = MetadataIdentitySerializer(read_only=True)

    class Meta:
        model = MetadataContact
        fields = [
            'contact_person',
            'metadata_role']


class MetadataDigestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metadata
        fields = ['geoportal_link']


class MetadataSerializer(serializers.HyperlinkedModelSerializer):
    contact_persons = serializers.SerializerMethodField()
    modified_user = serializers.StringRelatedField(read_only=True)
    documents = DocumentSerializer(many=True)
    copyright = CopyrightSerializer(many=False)
    legend_tag = serializers.StringRelatedField()
    image_tag = serializers.StringRelatedField()
    legend_link = serializers.SerializerMethodField()
    ech_category = serializers.SlugRelatedField(
        required=False,
        queryset=MetadataCategoryEch.objects.all(),
        slug_field='description_fr'
    )
    data_last_update_date = serializers.DateField(format=settings.DATE_FORMAT)

    class Meta:
        model = Metadata
        exclude = ['datasource']
        lookup_field = 'id_name'
        extra_kwargs = {
            'url': {'lookup_field': 'id_name'}
        }

    def get_contact_persons(self, obj) -> List[Dict[str, str]]:
        """obj is a Metadata instance. Returns list of dicts"""
        qset = MetadataContact.objects.filter(metadata=obj)
        return [
            MetadataContactSerializer(m, context={
                'request': self.context['request']
            }).data for m in qset]

    def get_legend_link(self, obj) -> str:
        return obj.get_legend_link()


class OrderDigestSerializer(serializers.HyperlinkedModelSerializer):
    """
    Serializer showing a summary of an Order.
    Always exclude geom here as it is used in lists of
    orders and performance can be impacted.
    """
    order_type = serializers.StringRelatedField()

    class Meta:
        model = Order
        exclude = [
            'geom', 'date_downloaded', 'client',
            'processing_fee_currency', 'processing_fee',
            'part_vat_currency', 'part_vat', 'extract_result',
            'invoice_contact']


class OrderItemSerializer(serializers.ModelSerializer):
    """
    A Basic serializer for order items
    """
    price = MoneyField(max_digits=14, decimal_places=2,
                       required=False, allow_null=True, read_only=True)
    data_format = serializers.SlugRelatedField(
        required=False,
        queryset=DataFormat.objects.all(),
        slug_field='name'
    )
    product = serializers.SlugRelatedField(
        queryset=Product.objects.all(),
        slug_field='label')
    product_id = serializers.PrimaryKeyRelatedField(read_only=True)
    product_provider = serializers.SerializerMethodField()
    available_formats = serializers.ListField(read_only=True)

    def get_product_provider(self, obj):
        return obj.product.provider.identity.company_name

    class Meta:
        model = OrderItem
        exclude = ['_price_currency', '_price', '_base_fee_currency',
                   '_base_fee', 'last_download', 'extract_result',
                   'validation_date', 'token']
        read_only_fields = ['price_status', 'order']


class OrderItemValidationSerializer(OrderItemSerializer):
    """
    Extends OrderItemSerializer with the order_guid.
    CAUTION: order_guid allows to acces to order without authentication
    """
    order_guid = serializers.SerializerMethodField()

    def get_order_guid(self, obj) -> str:
        return obj.order.download_guid


class OrderItemTextualSerializer(OrderItemSerializer):
    """
    Same as OrderItem, without Order
    """

    class Meta(OrderItemSerializer.Meta):
        exclude = OrderItemSerializer.Meta.exclude + ['order']


class OrderSerializer(serializers.ModelSerializer):
    """
    A complete Order serializer.
    """
    order_type = serializers.SlugRelatedField(
        queryset=OrderType.objects.all(),
        slug_field='name',
        help_text='Input the translated string value, for example "Privé"')
    items = OrderItemTextualSerializer(many=True)
    client = serializers.HiddenField(
        default=serializers.CurrentUserDefault(),
    )

    def validate(self, attrs):
        super().validate(attrs)
        self._errors = {}
        if ('geom' not in attrs) or (settings.MAX_ORDER_AREA == 0):
            return attrs
        requestedGeom = Polygon(
            [xy[0:2] for xy in list(attrs['geom'].coords[0])],
            srid=settings.DEFAULT_SRID
        )
        relevantOwnedAreas = ProductOwnership.objects.filter(
            product__in=[ item['product'] for item in attrs['items']],
            user_group__in=Group.objects.filter(user=self.context.get('request').user)
        ).all()

        ownedAreas = MultiPolygon(srid=settings.DEFAULT_SRID)
        for area in relevantOwnedAreas:
            ownedAreas = ownedAreas.union(area.geom)
        unownedAreas = requestedGeom.difference(ownedAreas)
        attrs['excludedGeom'] = unownedAreas
        if (unownedAreas.area > settings.MAX_ORDER_AREA):
            raise ValidationError({
                'message': _(f'Order area is too large'),
                'expected': settings.MAX_ORDER_AREA,
                'actual': requestedGeom.area,
                'excluded': unownedAreas.area
            })

        return attrs

    class Meta:
        model = Order
        exclude = ['date_downloaded', 'extract_result', 'download_guid']
        read_only_fields = [
            'date_ordered', 'date_processed',
            'processing_fee_currency', 'processing_fee',
            'total_cost_currency', 'total_cost',
            'part_vat_currency', 'part_vat',
            'order_status']

    def create(self, validated_data):
        items_data = validated_data.pop('items', None)
        geom = validated_data.pop('geom', None)
        order = Order(**validated_data)
        order.geom = Polygon(
            [xy[0:2] for xy in list(geom.coords[0])],
            srid=settings.DEFAULT_SRID
        )
        order.save()
        if not order.geom.valid:
            send_geoshop_email(
                _('Geoshop - Invalid geometry'),
                template_name='email_admin',
                template_data={
                    'messages': [_('A new order has been submitted and its geometry is invalid:')],
                    'details': {
                        _('order'): order.id,
                    }
                }
            )
        for item_data in items_data:
            item = OrderItem.objects.create(order=order, **item_data)
            item.set_price()
            item.save()

        if order.order_type and items_data:
            order.set_price()
            order.save()
        return order

    def update(self, instance, validated_data):
        if instance.order_status != Order.OrderStatus.DRAFT:
            raise serializers.ValidationError()

        items_data = validated_data.pop('items', None)
        geom = validated_data.pop('geom', None)

        if geom is not None:
            instance.geom = Polygon(
                [xy[0:2] for xy in list(geom.coords[0])],
                srid=settings.DEFAULT_SRID
            )

        instance.title = validated_data.get('title', instance.title)
        instance.description = validated_data.get(
            'description', instance.description)
        instance.invoice_contact = validated_data.get(
            'invoice_contact', instance.invoice_contact)
        instance.invoice_reference = validated_data.get(
            'invoice_reference', instance.invoice_reference)
        instance.email_deliver = validated_data.get(
            'email_deliver', instance.email_deliver)
        instance.order_type = validated_data.get(
            'order_type', instance.order_type)
        instance.save()

        update_products = []
        if items_data is not None:
            for item in items_data:
                update_products.append(item.get('product').label)

        # create / update / delete order_items on PUT (self.partial=False)
        # update order_items on PATCH (self.partial=True)
        order_items = list((instance.items).all())
        if not self.partial:
            for existing_item in order_items:
                if existing_item.product.label not in update_products:
                    existing_item.delete()

        if items_data:
            for item_data in items_data:
                oi_instance, created = OrderItem.objects.get_or_create(
                    order=instance,
                    product=item_data.get('product')
                )
                oi_instance.data_format = item_data.get(
                    'data_format', oi_instance.data_format)
                oi_instance.product = item_data.get(
                    'product', oi_instance.product)
                oi_instance.set_price()
                oi_instance.save()

        instance.set_price()
        instance.save()

        if instance.order_type:
            if items_data or geom or 'order_type' in validated_data:
                instance.set_price()
                instance.save()
        return instance


class PublicOrderSerializer(OrderSerializer):
    """
    Meant to be accessed by token
    """
    client = PublicUserIdentitySerializer(read_only=True)
    class Meta(OrderSerializer.Meta):
        exclude = [
            'date_downloaded', 'extract_result', 'download_guid'
        ]

class PricingSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Pricing
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    """
    Product serializer
    """

    metadata = serializers.HyperlinkedRelatedField(
        many=False,
        read_only=True,
        view_name='metadata-detail',
        lookup_field='id_name'
    )

    pricing = PricingSerializer(read_only=True)

    provider = serializers.CharField(
        source='provider.identity.company_name',
        read_only=True)

    metadata_summary = MetadataDigestSerializer(
        source='metadata',
        read_only=True
    )

    class Meta:
        model = Product
        read_only_fields = ['pricing', 'label', 'group', 'metadata_summary']
        exclude = ['order', 'ts', 'geom']


class ProductExtractSerializer(ProductSerializer):
    """
    Product serializer without geom
    """
    metadata = None

    class Meta:
        model = Product
        read_only_fields = ['pricing', 'label', 'group']
        exclude = ['order', 'thumbnail_link', 'ts', 'metadata', 'geom']


class ExtractOrderItemSerializer(OrderItemSerializer):
    """
    Orderitem serializer for extract. Allows to upload file of orderitem.
    """
    extract_result = serializers.FileField(required=False)
    product = ProductExtractSerializer(read_only=True)
    data_format = serializers.StringRelatedField(read_only=True)
    is_rejected = serializers.BooleanField(required=False)
    price = None
    available_formats = None

    class Meta(OrderItemSerializer.Meta):
        exclude = ['_price_currency', '_base_fee_currency',
                   '_price', '_base_fee', 'order', 'status',
                   'last_download', 'price_status']
        read_only_fields = [
            'id', 'data_format', 'product', 'srid']

    def update(self, instance, validated_data):
        if instance.extract_result:
            # deletes previous file in filesystem
            instance.extract_result.delete()
        instance.comment = validated_data.pop('comment', None)
        is_rejected = validated_data.pop('is_rejected')
        instance.extract_result = validated_data.pop('extract_result', '')
        if is_rejected:
            instance.status = OrderItem.OrderItemStatus.REJECTED
        if instance.extract_result.name != '':
            instance.status = OrderItem.OrderItemStatus.PROCESSED
        instance.save()
        status = instance.order.next_status_on_extract_input()
        if status == Order.OrderStatus.PROCESSED:
            zip_all_orderitems(instance.order)
        instance.order.save()
        return instance


class ExtractOrderSerializer(serializers.ModelSerializer):
    """
    Order serializer for Extract.
    """
    order_type = serializers.SlugRelatedField(
        queryset=OrderType.objects.all(),
        slug_field='name',
        help_text='Input the translated string value, for example "Privé"')
    client = UserIdentitySerializer()
    invoice_contact = IdentitySerializer()
    geom = WKTPolygonField()
    geom_srid = serializers.IntegerField()
    geom_area = serializers.FloatField()

    class Meta:
        model = Order
        exclude = [
            'date_downloaded', 'processing_fee_currency',
            'total_without_vat_currency', 'part_vat_currency', 'total_with_vat_currency']
        read_only_fields = [
            'date_ordered', 'date_processed',
            'processing_fee_currency', 'processing_fee',
            'total_cost_currency', 'total_cost',
            'part_vat_currency', 'part_vat',
            'status', 'geom_area']


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer for requesting a password reset e-mail.
    """
    email = serializers.EmailField()

    password_reset_form_class = PasswordResetForm

    def validate_email(self, value):
        # Create PasswordResetForm with the serializer
        self.reset_form = self.password_reset_form_class(
            data=self.initial_data)
        if not self.reset_form.is_valid():
            raise serializers.ValidationError(self.reset_form.errors)

        return value

    def save(self):
        request = self.context.get('request')
        # Set some values to trigger the send_email method.
        opts = {
            'domain_override': getattr(settings, 'FRONT_URL') + getattr(settings, 'FRONT_HREF'),
            'use_https': request.is_secure(),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL'),
            'request': request,
            'email_template_name': 'email_password_reset.html',
            'html_email_template_name': 'email_password_reset.html'
        }

        self.reset_form.save(**opts)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for setting a new user password.
    """
    new_password1 = serializers.CharField(max_length=128)
    new_password2 = serializers.CharField(max_length=128)
    uid = serializers.CharField()
    token = serializers.CharField()

    set_password_form_class = SetPasswordForm

    def validate(self, attrs):
        self._errors = {}

        # Decode the uidb64 to uid to get User object
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            self.user = UserModel._default_manager.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
            raise ValidationError({'uid': ['Invalid value']})

        # Construct SetPasswordForm instance
        self.set_password_form = self.set_password_form_class(
            user=self.user, data=attrs
        )
        if not self.set_password_form.is_valid():
            raise serializers.ValidationError(self.set_password_form.errors)
        if not default_token_generator.check_token(self.user, attrs['token']):
            raise ValidationError({'token': ['Invalid value']})

        return attrs

    def save(self):
        return self.set_password_form.save()


class ProductFormatSerializer(serializers.ModelSerializer):
    product = serializers.SlugRelatedField(
        queryset=Product.objects.all(),
        slug_field='label')
    data_format = serializers.SlugRelatedField(
        required=False,
        queryset=DataFormat.objects.all(),
        slug_field='name',
        label='format')

    class Meta:
        model = ProductFormat
        fields = '__all__'


class DataFormatListSerializer(ProductFormatSerializer):
    product = None

    class Meta:
        model = ProductFormat
        exclude = ['product']


class ProductDigestSerializer(ProductSerializer):
    pricing = serializers.SlugRelatedField(
        required=False,
        queryset=DataFormat.objects.all(),
        slug_field='name'
    )
    provider = serializers.CharField(
        source='provider.identity.company_name',
        read_only=True)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_username(self, username):
        username = get_adapter().clean_username(username)
        return username

    def validate_email(self, email):
        email = get_adapter().clean_email(email)
        return email

    def validate_password1(self, password):
        return get_adapter().clean_password(password)

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(
                _("The two password fields didn't match."))
        return data

    def create(self, validated_data):
        password = validated_data.pop('password1')
        validated_data.pop('password2')
        user = UserModel(username=validated_data.pop('username'))
        user.set_password(password)
        identity_data = self.initial_data.copy()
        for key in ['password1', 'password2', 'username']:
            identity_data.pop(key)
        identity_serializer = IdentitySerializer(data=identity_data)
        identity_serializer.is_valid(raise_exception=True)
        user.save()
        identity_serializer.instance = user.identity
        identity_serializer.save()
        return user

    class Meta:
        model = UserModel
        exclude = [
            'password', 'last_login', 'date_joined',
            'groups', 'user_permissions', 'is_staff',
            'is_active', 'is_superuser']


class UserChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserChange
        fields = '__all__'


class ValidationSerializer(serializers.Serializer):
    is_validated = serializers.BooleanField()


class VerifyEmailSerializer(serializers.Serializer):
    key = serializers.CharField()
