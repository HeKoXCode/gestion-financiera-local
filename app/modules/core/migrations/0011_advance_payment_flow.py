from django.db import migrations, models


def enable_advance_payments(apps, schema_editor):
    BusinessSettings = apps.get_model("core", "BusinessSettings")
    BusinessSettings.objects.update(allow_advance_payments=True)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_single_daily_late_fee_policy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesssettings",
            name="allow_advance_payments",
            field=models.BooleanField(
                default=True,
                verbose_name="permitir pagos adelantados",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="is_advance",
            field=models.BooleanField(
                default=False,
                verbose_name="pago adelantado",
            ),
        ),
        migrations.RunPython(enable_advance_payments, migrations.RunPython.noop),
    ]
