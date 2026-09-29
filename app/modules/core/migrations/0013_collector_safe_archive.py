from django.db import migrations, models
from django.utils import timezone


LEGACY_REASON = "Archivado en una versión anterior."


def archive_legacy_inactive_collectors(apps, schema_editor):
    collector = apps.get_model("core", "Collector")
    collector.objects.filter(is_active=False, archived_at__isnull=True).update(
        archived_at=timezone.now(),
        archive_reason=LEGACY_REASON,
    )


def restore_legacy_inactive_collectors(apps, schema_editor):
    collector = apps.get_model("core", "Collector")
    collector.objects.filter(archive_reason=LEGACY_REASON).update(
        archived_at=None,
        archive_reason="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_collectors_and_collection_routes"),
    ]

    operations = [
        migrations.AddField(
            model_name="collector",
            name="archive_reason",
            field=models.TextField(blank=True, verbose_name="motivo del archivado"),
        ),
        migrations.AddField(
            model_name="collector",
            name="archived_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="enviado al archivo seguro",
            ),
        ),
        migrations.RunPython(
            archive_legacy_inactive_collectors,
            restore_legacy_inactive_collectors,
        ),
        migrations.AddIndex(
            model_name="collector",
            index=models.Index(
                fields=["archived_at"],
                name="collector_archived_idx",
            ),
        ),
    ]
