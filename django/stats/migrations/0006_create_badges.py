from django.db import migrations


def forwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).bulk_create(
        [
            MatchBadgeType(pk='surpass-yourself', name='Surpass-yourself Performance'),
            MatchBadgeType(pk='ace', name='Ace'),
            MatchBadgeType(pk='quad-kill', name='Quad-kill'),
        ]
    )


def backwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='surpass-yourself').delete()
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='ace').delete()
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='quad-kill').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0005_remove_matchparticipation_accuracy_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

