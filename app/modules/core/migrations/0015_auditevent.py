# Merge the historical GitHub audit branch with the local product branch.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_v16_collection_workflow"),
        ("core", "0008_auditevent"),
    ]

    operations = []
