import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from api.models import Order

UserModel = get_user_model()

class Command(BaseCommand):
    """
    Needs to be called once after database is reset.
    Sets .env ADMIN_PASSWORD
    Creates extract user and group
    Creates internal group
    """
    def handle(self, *args, **options):
        admin_user = UserModel.objects.get(username=os.environ.get('ADMIN_USERNAME', 'admin'))
        admin_user.set_password(os.environ['ADMIN_PASSWORD'])
        admin_user.save()

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
