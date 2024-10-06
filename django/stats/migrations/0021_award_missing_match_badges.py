from django.db import migrations


def forwards(apps, schema_editor):
    Match = apps.get_model('stats', 'Match')
    for pmatch in Match.objects.using(schema_editor.connection.alias).all():
        pmatch.award_badges()


class Migration(migrations.Migration):
    dependencies = [
        ('stats', '0020_rename_completed_timestamp_updatetask_completion_timestamp'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]

