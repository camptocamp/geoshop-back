# Generated by Django 3.2.8 on 2022-01-04 08:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_auto_20220103_1630'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='validation_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='validation_date'),
        ),
    ]