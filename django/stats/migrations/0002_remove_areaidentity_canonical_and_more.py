# Generated by Django 4.1 on 2024-07-22 06:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='killevent',
            name='killer_area',
        ),
        migrations.RemoveField(
            model_name='killevent',
            name='victim_area',
        ),
        migrations.DeleteModel(
            name='Area',
        ),
        migrations.DeleteModel(
            name='AreaIdentity',
        ),
    ]
