from django.db import migrations


def create_default_settings(apps, schema_editor):
    business_settings = apps.get_model("core", "BusinessSettings")
    business_settings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_settings, migrations.RunPython.noop),
    ]

