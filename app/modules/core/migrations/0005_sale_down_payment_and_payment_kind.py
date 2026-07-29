from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_add_monthly_frequency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sale",
            name="cash_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01"))
                ],
                verbose_name="precio del producto",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="down_payment",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.00"))
                ],
                verbose_name="entrega inicial",
            ),
        ),
        migrations.AlterField(
            model_name="sale",
            name="financed_amount",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01"))
                ],
                verbose_name="total en cuotas",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="kind",
            field=models.CharField(
                choices=[
                    ("installment", "Pago de cuota"),
                    ("initial", "Entrega inicial"),
                ],
                default="installment",
                max_length=16,
                verbose_name="tipo de movimiento",
            ),
        ),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.CheckConstraint(
                condition=models.Q(down_payment__gte=Decimal("0.00")),
                name="sale_down_payment_non_negative",
            ),
        ),
    ]
