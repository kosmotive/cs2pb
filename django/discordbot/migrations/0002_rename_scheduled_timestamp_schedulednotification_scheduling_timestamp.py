# Generated by Django 4.1.13 on 2024-09-10 23:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('discordbot', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='schedulednotification',
            old_name='scheduled_timestamp',
            new_name='scheduling_timestamp',
        ),
    ]