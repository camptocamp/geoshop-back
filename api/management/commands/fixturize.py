import io
import os
import logging
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from api.models import Order

UserModel = get_user_model()
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Needs to be called once after database is reset.
    Sets .env ADMIN_PASSWORD
    Creates extract user and group
    Creates internal group
    """
    def configureAdmin(self):
        admin_user = UserModel.objects.get(username=os.environ.get('ADMIN_USERNAME', 'admin'))
        admin_user.set_password(os.environ['ADMIN_PASSWORD'])
        admin_user.save()

    def configureExtract(self):
        content_type = ContentType.objects.get_for_model(Order)
        Group.objects.update_or_create(name='internal')
        extract_permission = Permission.objects.update_or_create(
            codename='is_extract',
            name='Is extract service',
            content_type=content_type)
        extract_permission[0].save()

        extract_group = Group.objects.update_or_create(name='extract')
        extract_group[0].permissions.add(extract_permission[0])
        extract_group[0].save()

        if not UserModel.objects.filter(username='external_provider').exists():
            extract_user = UserModel.objects.create_user(
                username='external_provider',
                password=os.environ['EXTRACT_USER_PASSWORD']
            )
            extract_user.groups.add(extract_group[0])
            extract_user.identity.company_name = 'ACME'
            extract_user.save()

    def configureCounters(self):
        output = io.StringIO()
        call_command("sqlsequencereset", "api", stdout=output, no_color=True)
        sql = output.getvalue()

        with connection.cursor() as cursor:
            cursor.execute(sql)

        output.close()

    def handle(self, *args, **options):
        logger.info("Configuring admin user")
        self.configureAdmin()
        logger.info("Configuring extract user")
        self.configureExtract()
        logger.info("Configuring autoincrement counters")
        self.configureCounters()