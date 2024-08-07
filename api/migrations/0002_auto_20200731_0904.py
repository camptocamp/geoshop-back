# Generated by Django 3.0.8 on 2020-07-22 06:41
import os
from django.db import migrations
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    def generate_superuser(apps, schema_editor):
        from django.contrib.auth.models import User
        superuser = User.objects.create_superuser(
            username=os.environ.get('ADMIN_USERNAME', 'admin'),
            password=os.environ['ADMIN_PASSWORD'])

        superuser.save()


    operations = [
        migrations.RunPython(generate_superuser),
    ]
