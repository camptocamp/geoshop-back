# Generated by Django 3.0.8 on 2021-07-21 07:01

import django.contrib.gis.db.models.fields
import django.contrib.gis.geos.polygon
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_auto_20210707_1357'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='geom',
            field=django.contrib.gis.db.models.fields.PolygonField(default=django.contrib.gis.geos.polygon.Polygon(((2479000, 1076000), (2479000, 1305000), (2853000, 1305000), (2853000, 1076000), (2479000, 1076000))), srid=2056, verbose_name='geom'),
        ),
    ]