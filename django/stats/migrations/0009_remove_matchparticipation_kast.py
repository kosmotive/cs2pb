# Generated by Django 4.1 on 2024-07-24 15:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0008_matchparticipation_hltv_matchparticipation_kast'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='matchparticipation',
            name='kast',
        ),
    ]
