# Generated by Django 4.1 on 2024-07-22 06:20

import discordbot.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_timestamp', models.PositiveBigIntegerField(default=discordbot.models.timestamp_now, verbose_name='Scheduled')),
                ('text', models.TextField()),
                ('squad', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='accounts.squad')),
            ],
        ),
        migrations.CreateModel(
            name='InvitationDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discord_name', models.CharField(blank=True, max_length=30, unique=True)),
                ('steam_profile', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='accounts.steamprofile')),
            ],
        ),
    ]
