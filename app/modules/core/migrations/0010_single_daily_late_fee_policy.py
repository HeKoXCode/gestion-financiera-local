from collections import defaultdict
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone


ZERO = Decimal("0.00")


def normalize_overlapping_late_fees(apps, schema_editor):
    """Keep one effective charge per sale and date without deleting old rows."""
    Sale = apps.get_model("core", "Sale")
    LateFee = apps.get_model("core", "LateFee")
    normalized_at = timezone.now()
    reason = (
        "Normalización v1.3: este cargo duplicaba el recargo diario de otra "
        "cuota de la misma venta; se conserva como registro histórico."
    )

    for sale in Sale.objects.filter(status="active").prefetch_related(
        "installments__late_fees"
    ):
        fees_by_date = defaultdict(list)
        for installment in sale.installments.all():
            for fee in installment.late_fees.all():
                fees_by_date[fee.fee_date].append(fee)

        changed = []
        for fees in fees_by_date.values():
            fees.sort(
                key=lambda fee: (
                    fee.installment.due_date,
                    fee.installment.number,
                    fee.pk,
                )
            )
            remaining = sale.daily_late_fee
            for fee in fees:
                effective = min(fee.amount, max(ZERO, remaining))
                waived = fee.amount - effective
                remaining -= effective
                if fee.waived_amount == waived:
                    continue
                fee.waived_amount = waived
                fee.waived_reason = reason if waived > ZERO else ""
                fee.waived_at = normalized_at if waived > ZERO else None
                changed.append(fee)
        if changed:
            LateFee.objects.bulk_update(
                changed,
                ["waived_amount", "waived_reason", "waived_at"],
                batch_size=500,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_businesssettings_allow_exceptional_sale_edits_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businesssettings",
            name="daily_late_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("5000.00"),
                max_digits=14,
                validators=[MinValueValidator(Decimal("0.00"))],
                verbose_name="recargo diario por atraso",
            ),
        ),
        migrations.AlterField(
            model_name="sale",
            name="daily_late_fee",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                validators=[MinValueValidator(Decimal("0.00"))],
                verbose_name="recargo diario congelado",
            ),
        ),
        migrations.AddField(
            model_name="latefee",
            name="waived_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                validators=[MinValueValidator(Decimal("0.00"))],
                verbose_name="importe dejado sin efecto",
            ),
        ),
        migrations.AddField(
            model_name="latefee",
            name="waived_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="dejado sin efecto el",
            ),
        ),
        migrations.AddField(
            model_name="latefee",
            name="waived_reason",
            field=models.TextField(
                blank=True,
                verbose_name="motivo del importe dejado sin efecto",
            ),
        ),
        migrations.RunPython(
            normalize_overlapping_late_fees,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="latefee",
            constraint=models.CheckConstraint(
                condition=Q(waived_amount__gte=ZERO)
                & Q(waived_amount__lte=F("amount")),
                name="late_fee_waived_amount_valid",
            ),
        ),
    ]
