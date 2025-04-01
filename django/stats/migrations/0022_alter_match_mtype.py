# Generated by Django 4.1.13 on 2025-04-01 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0021_match_mtype_matchparticipation_new_rank_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='match',
            name='mtype',
            field=models.CharField(blank=True, choices=[('', 'Unknown'), ('Competitive', 'Competitive'), ('Wingman', 'Wingman'), ('Danger Zone', 'Danger Zone'), ('Premier', 'Premier')], max_length=20, verbose_name='Match type'),
        ),
    ]
