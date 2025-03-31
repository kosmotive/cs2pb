from django.db import migrations


def forwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).bulk_create(
        [
            MatchBadgeType(pk='john-wick-award', name='John Wick Award'),
        ]
    )


def backwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    MatchBadgeType.objects.using(schema_editor.connection.alias).filter(pk='john-wick-award').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0020_rename_completed_timestamp_updatetask_completion_timestamp'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
