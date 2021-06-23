# Generated by Django 3.0.8 on 2020-12-09 07:07

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_contact_subscribed'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='extract_result',
            field=models.FileField(blank=True, null=True, upload_to='extract'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('DRAFT', 'Draft'), ('PENDING', 'Pending'), ('READY', 'Ready'), ('PARTIALLY_DELIVERED', 'Partially delivered'), ('PROCESSED', 'Processed'), ('ARCHIVED', 'Archived'), ('REJECTED', 'Rejected')], default='DRAFT', max_length=20, verbose_name='status'),
        ),
    ]