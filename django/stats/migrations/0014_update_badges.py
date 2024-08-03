from django.db import migrations


def forwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    for badge_type in ['ace', 'quad-kill']:
        obj = MatchBadgeType.objects.using(schema_editor.connection.alias).get(pk = badge_type)
        obj.is_minor = True
        obj.save()


def backwards(apps, schema_editor):
    MatchBadgeType = apps.get_model('stats', 'MatchBadgeType')
    for badge_type in ['ace', 'quad-kill']:
        obj = MatchBadgeType.objects.using(schema_editor.connection.alias).get(pk = badge_type)
        obj.is_minor = False
        obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0013_create_badges'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

