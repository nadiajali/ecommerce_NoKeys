# Generated by Django 2.2 on 2020-12-18 20:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_auto_20201218_1252'),
    ]

    operations = [
        migrations.AlterField(
            model_name='address',
            name='apartment_address',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]