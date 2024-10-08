# Generated by Django 4.1 on 2024-07-22 20:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0006_create_badges'),
    ]

    operations = [
        migrations.CreateModel(
            name='KillEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('round', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('kill_type', models.PositiveSmallIntegerField()),
                ('bomb_planted', models.BooleanField()),
                ('killer_x', models.FloatField()),
                ('killer_y', models.FloatField()),
                ('killer_z', models.FloatField()),
                ('victim_x', models.FloatField()),
                ('victim_y', models.FloatField()),
                ('victim_z', models.FloatField()),
                ('killer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kill_events', to='stats.matchparticipation')),
                ('victim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='death_events', to='stats.matchparticipation')),
            ],
        ),
    ]
