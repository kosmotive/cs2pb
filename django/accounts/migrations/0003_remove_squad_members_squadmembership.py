from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    Squad = apps.get_model('accounts', 'Squad')
    SquadMembership = apps.get_model('accounts', 'SquadMembership')
    for squad in Squad.objects.using(schema_editor.connection.alias).all():
        for player in squad.members.using(schema_editor.connection.alias).all():
            SquadMembership.objects.using(schema_editor.connection.alias).create(squad = squad, player = player)


def backwards(apps, schema_editor):
    SquadMembership = apps.get_model('accounts', 'SquadMembership')
    for m in SquadMembership.objects.using(schema_editor.connection.alias).create().all():
        m.squad.members.using(schema_editor.connection.alias).add(m.player)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_squad_last_changelog_announcement'),
    ]

    operations = [
        migrations.CreateModel(
            name='SquadMembership',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created = True,
                        primary_key = True,
                        serialize = False,
                        verbose_name = 'ID',
                    ),
                ),
                (
                    'position',
                    models.PositiveSmallIntegerField(
                        default = None,
                        null = True,
                    ),
                ),
                (
                    'player',
                    models.ForeignKey(
                        on_delete = django.db.models.deletion.CASCADE,
                        related_name = 'squad_memberships',
                        to = 'accounts.steamprofile',
                    ),
                ),
                (
                    'squad',
                    models.ForeignKey(
                        on_delete = django.db.models.deletion.CASCADE,
                        related_name = 'memberships',
                        to = 'accounts.squad',
                    ),
                ),
            ],
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name = 'squad',
            name = 'members',
        ),
    ]
