# Generated by Django 4.1.13 on 2024-09-10 22:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0018_alter_matchbadge_badge_type'),
    ]

    operations = [
        migrations.RenameField(
            model_name='updatetask',
            old_name='scheduled_timestamp',
            new_name='scheduling_timestamp',
        ),
    ]
