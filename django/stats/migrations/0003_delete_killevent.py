# Generated by Django 4.1 on 2024-07-22 15:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0002_remove_areaidentity_canonical_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='KillEvent',
        ),
    ]
