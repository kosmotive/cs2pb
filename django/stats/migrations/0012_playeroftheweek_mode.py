# Generated by Django 4.1 on 2024-07-29 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0011_alter_matchparticipation_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='playeroftheweek',
            name='mode',
            field=models.CharField(default='k/d', max_length=20),
            preserve_default=False,
        ),
    ]