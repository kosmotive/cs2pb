from django.db import migrations


def forwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).bulk_create(
        [
            MatchBadgeType(pk='carrier', name='Carrier Credential'),
            MatchBadgeType(pk='peach', name='Peach Price'),
        ]
    )


def backwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='carrier').delete()
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='peach').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0012_playeroftheweek_mode'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

