# Generated by Django 5.1.5 on 2025-01-31 10:12

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0050_order_excludedgeom_alter_orderitem_download_guid_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='excludedGeom',
            field=django.contrib.gis.db.models.fields.PolygonField(blank=True, null=True, srid=2056, verbose_name='excludedGeom'),
        ),
    ]
