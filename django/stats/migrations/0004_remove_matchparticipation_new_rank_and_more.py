# Generated by Django 4.1 on 2024-07-22 15:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0003_delete_killevent'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='matchparticipation',
            name='new_rank',
        ),
        migrations.RemoveField(
            model_name='matchparticipation',
            name='old_rank',
        ),
    ]
