# Generated by Django 3.0.8 on 2020-08-03 15:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_auto_20200731_1339'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='link',
            field=models.URLField(default='default_product_thumbnail.png', help_text='Please complete the above URL', verbose_name='link'),
        ),
        migrations.AlterField(
            model_name='metadata',
            name='image_link',
            field=models.CharField(default='default_metadata_image.png', max_length=250, verbose_name='image_link'),
        ),
        migrations.AlterField(
            model_name='metadatacontact',
            name='contact_person',
            field=models.ForeignKey(limit_choices_to={'is_public': True}, on_delete=django.db.models.deletion.DO_NOTHING, to='api.Identity', verbose_name='contact_person'),
        ),
        migrations.AlterField(
            model_name='product',
            name='thumbnail_link',
            field=models.CharField(default='default_product_thumbnail.png', max_length=250, verbose_name='thumbnail_link'),
        ),
    ]
