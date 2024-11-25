import os
import datetime
from pathlib import Path
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from api.models import Contact, Order, OrderItem, OrderType, Product, DataFormat, Identity, Metadata, Pricing, Money
from django.contrib.gis.geos import Polygon
from api.helpers import _zip_them_all
from typing import TypeVar, Generic, Type
from collections.abc import MutableMapping

T = TypeVar('T', bound=models.Model)
UserModel = get_user_model()


class Command(BaseCommand):
    help = "seed database for testing and development."

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...\n")
        self.seed()
        self.stdout.write("Done.\n")

    def notice(self, msg: str):
        self.stdout.write(self.style.NOTICE(msg))

    def success(self, msg: str):
        self.stdout.write(self.style.SUCCESS(msg))

    def error(self, msg: str):
        self.stdout.write(self.style.ERROR(msg))

    def getOrCreate(self, model: Type[T], defaults: MutableMapping[str, any] | None = ..., **kwargs) -> T:
        (value, created) = model.objects.get_or_create(defaults, **kwargs)
        typeName = model.__name__
        if created:
            self.success(f"Created {typeName} \"{value}\"")
        else:
            self.notice(f"Not creating {typeName}: \"{value}\" - already exists")
        return value

    def addUser(self, username: str, email: str, password: str) -> User:
        return self.getOrCreate(UserModel, username=username, defaults={"email": email, "password": password})

    def setIdentity(self, user: User, params: dict[str, any]) -> Identity:
        for k, v in params.items():
            setattr(user.identity, k, v)
        user.identity.save()
        self.success(f"Updated identity for user '{user.username}'")
        return user.identity

    def addProduct(self, user: User, label: str) -> OrderType:
        return self.getOrCreate(Product, label=label, defaults={
            "metadata": self.getOrCreate(Metadata, id_name="metadata", name="metadata", defaults={"modified_user_id": user.id}),
            "pricing": self.getOrCreate(Pricing, name="Free", defaults={"pricing_type": Pricing.PricingType.FREE}),
            "provider": user
        })

    def seed(self):
        # Create users
        rincevent = self.addUser('rincevent', 'rincevent@mail.com', 'rincevent')
        self.setIdentity(rincevent, {
            "email": os.environ.get('EMAIL_TEST_TO', 'admin@admin.com'),
            "first_name": 'Jean',
            "last_name": 'Michoud',
            "street": 'Rue de Tivoli 22',
            "postcode": '2000',
            "city": 'Neuchâtel',
            "country": 'Suisse',
            "company_name": 'Service du Registre Foncier et de la Géomatique - SITN',
            "phone": '+41 32 000 00 00'})

        mmi = self.addUser("mmi", "mmi@mmi.com", "mmi")
        self.setIdentity(mmi, {
            "email": os.environ.get('EMAIL_TEST_TO_ARXIT', 'admin@admin.com'),
            "first_name": 'Jeanne',
            "last_name": 'Paschoud',
            "street": 'Rue de Tivoli 22',
            "postcode": '2000',
            "city": 'Neuchâtel',
            "country": 'Suisse',
            "company_name": 'Service du Registre Foncier et de la Géomatique - SITN',
            "phone": '+41 32 000 00 00'})

        mma = self.addUser("mma", "mma@mma.com", "mma")
        self.setIdentity(mma, {
            "email": 'mma-email@admin.com',
            "first_name": 'Jean-René',
            "last_name": 'Humbert-Droz L\'Authentique',
            "street": 'Rue de Tivoli 22',
            "postcode": '2000',
            "city": 'Neuchâtel',
            "country": 'Suisse',
            "company_name": 'Service du Registre Foncier et de la Géomatique - SITN',
            "phone": '+41 32 000 00 00'})

        mka2 = self.addUser("mka", "mka@mka.com", "mka")
        self.setIdentity(mka2, {
            "email": 'mka2-email@ne.ch',
            "first_name": 'Michaël',
            "last_name": 'Kalbermatten',
            "street": 'Rue de Tivoli 22',
            "postcode": '2000',
            "city": 'Neuchâtel',
            "country": 'Suisse',
            "company_name": 'Service du Registre Foncier et de la Géomatique - SITN',
            "phone": '+41 32 000 00 00',
            "subscribed": True})

        # contacts
        contact1 = Contact.objects.create(
            first_name='Marc',
            last_name='Riedo',
            email='test@admin.com',
            postcode=2000,
            city='Neuchâtel',
            country='Suisse',
            company_name='SITN',
            phone='+41 00 787 45 15',
            belongs_to=mmi
        )
        contact1.save()
        contact2 = Contact.objects.create(
            first_name='Marcelle',
            last_name='Rieda',
            email='test2@admin.com',
            postcode=2000,
            city='Neuchâtel',
            country='Suisse',
            company_name='SITN',
            phone='+41 00 787 45 16',
            belongs_to=mmi
        )
        contact2.save()
        contact3 = Contact.objects.create(
            first_name='Jean',
            last_name='Doe',
            email='test3@admin.com',
            postcode=2000,
            city='Lausanne',
            country='Suisse',
            company_name='Marine de Colombier',
            phone='+41 00 787 29 16',
            belongs_to=mmi
        )
        contact3.save()
        contact_mka2 = Contact.objects.create(
            first_name='Jean',
            last_name='Doe',
            email='test3@admin.com',
            postcode=2000,
            city='Lausanne',
            country='Suisse',
            company_name='Marine de Colombier',
            phone='+41 00 787 29 16',
            belongs_to=mka2
        )
        contact_mka2.save()

        order_geom = Polygon((
            (
                2528577.8382161376,
                1193422.4003930448
            ),
            (
                2542482.6542869355,
                1193422.4329014618
            ),
            (
                2542482.568523701,
                1199018.36469272
            ),
            (
                2528577.807487005,
                1199018.324372703
            ),
            (
                2528577.8382161376,
                1193422.4003930448
            )
        ))

        order_type_prive = self.getOrCreate(OrderType, name='Privé', defaults={})
        public = self.getOrCreate(OrderType, name='Public', defaults={})

        # Create orders
        order1 = Order.objects.create(
            title='Plan de situation pour enquête',
            description='C\'est un test',
            order_type=order_type_prive,
            client=rincevent,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order1.save()

        order2 = Order.objects.create(
            title='Plan de situation pour enquête',
            description='C\'est un test',
            order_type=order_type_prive,
            client=rincevent,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order2.save()

        order3 = Order.objects.create(
            title='Plan de situation pour enquête',
            description='C\'est un test',
            order_type=order_type_prive,
            client=rincevent,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order3.save()

        order4 = Order.objects.create(
            title='Plan de situation pour enquête',
            description='C\'est un test',
            order_type=order_type_prive,
            client=mma,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order4.save()

        order_mka2 = Order.objects.create(
            title='Plan de situation pour enquête',
            description='C\'est un test',
            order_type=order_type_prive,
            client=mka2,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order_mka2.save()

        order_download = Order.objects.create(
            title='Commande prête à être téléchargée',
            description='C\'est un test',
            order_type=order_type_prive,
            client=mmi,
            geom=order_geom,
            invoice_reference='Dossier 8',
            date_ordered=timezone.now())
        order_download.save()

        order_quoted = Order.objects.create(
            title='Commande devisée pour test',
            description='C\'est un test',
            order_type=order_type_prive,
            client=mmi,
            geom=order_geom,
            invoice_reference='Dossier n°545454',
            date_ordered=timezone.now())
        order_quoted.save()

        # Products
        product1 = self.addProduct(mma, 'MO - Cadastre complet')
        product2 = self.addProduct(mma, 'Maquette 3D')
        product_deprecated = self.addProduct(mma,
                                             'MO07 - Objets divers et éléments linéaires - linéaires')

        data_format = self.getOrCreate(DataFormat, name='Geobat NE complet (DXF)', defaults={})
        data_format_maquette = self.getOrCreate(DataFormat, name='3dm (Fichier Rhino)', defaults={})

        for order_item in [
            OrderItem.objects.create(order=order1, product=product1),
            OrderItem.objects.create(order=order1, product=product2),
            OrderItem.objects.create(order=order_download, product=product1),
            OrderItem.objects.create(order=order2, product=product1),
            OrderItem.objects.create(
                order=order3, product=product1, data_format=data_format),
            OrderItem.objects.create(order=order4, product=product2),
            OrderItem.objects.create(
                order=order_mka2, product=product1, data_format=data_format)
        ]:
            order_item.set_price()
            order_item.save()
        order_item_deprecated = OrderItem.objects.create(
            order=order_mka2, product=product_deprecated, data_format=data_format)
        order_item_deprecated.set_price(price=Money(
            400, 'CHF'), base_fee=Money(150, 'CHF'))
        order_item_deprecated.price_status = OrderItem.PricingStatus.CALCULATED
        order_item_deprecated.save()

        order_item_download = OrderItem.objects.create(
            order=order_download, product=product2, data_format=data_format_maquette)
        order_item_download.set_price(price=Money(
            400, 'CHF'), base_fee=Money(150, 'CHF'))
        order_item_download.price_status = OrderItem.PricingStatus.CALCULATED
        order_item_download.save()

        order_item_quoted = OrderItem.objects.create(
            order=order_quoted, product=product2, data_format=data_format_maquette)
        order_item_quoted.set_price(price=Money(
            400, 'CHF'), base_fee=Money(150, 'CHF'))
        order_item_quoted.price_status = OrderItem.PricingStatus.CALCULATED
        order_item_quoted.save()

        order2.set_price()
        order2.save()

        order3.set_price()
        order3.confirm()
        order3.invoice_contact = contact1
        order3.save()

        order4.save()

        order_mka2.invoice_contact = contact_mka2
        order_mka2.set_price()
        order_mka2.date_ordered = datetime.datetime(
            2018, 12, 1, 8, 20, 3, 0, tzinfo=datetime.timezone.utc)
        order_mka2.order_status = Order.OrderStatus.ARCHIVED
        order_mka2.save()

        order_download.set_price()
        empty_zip_data = b'PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        extract_file = SimpleUploadedFile(
            "result.zip", empty_zip_data, content_type="multipart/form-data")
        for order_item in order_download.items.all():
            order_item.extract_result = extract_file
            order_item.status = OrderItem.OrderItemStatus.PROCESSED
            order_item.save()
        order_download.order_status = Order.OrderStatus.PROCESSED

        # Creating zip with all zips without background process unsupported by manage.py
        zip_list_path = list(order_download.items.all(
        ).values_list('extract_result', flat=True))
        today = timezone.now()
        zip_path = Path(
            'extract',
            str(today.year), str(today.month),
            "{}{}.zip".format('0a2ebb0a-', str(order_download.id)))
        order_download.extract_result.name = zip_path.as_posix()
        full_zip_path = Path(settings.MEDIA_ROOT, zip_path)
        _zip_them_all(full_zip_path, zip_list_path)
        order_download.save()

        order_quoted.set_price()
        order_quoted.quote_done()
        order_quoted.save()
