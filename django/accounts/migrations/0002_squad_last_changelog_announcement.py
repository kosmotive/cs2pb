# Generated by Django 4.1 on 2024-07-27 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='squad',
            name='last_changelog_announcement',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]