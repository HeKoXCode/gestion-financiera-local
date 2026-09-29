from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_advance_payment_flow"),
    ]

    operations = [
        migrations.CreateModel(
            name="Collector",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modificado")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="nombre")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
            ],
            options={
                "verbose_name": "cobrador",
                "verbose_name_plural": "cobradores",
                "ordering": ["name", "pk"],
            },
        ),
        migrations.CreateModel(
            name="CollectionRoute",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modificado")),
                ("collection_date", models.DateField(verbose_name="fecha del recorrido")),
                (
                    "collector",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="routes",
                        to="core.collector",
                        verbose_name="cobrador",
                    ),
                ),
            ],
            options={
                "verbose_name": "recorrido de cobranza",
                "verbose_name_plural": "recorridos de cobranza",
                "ordering": ["-collection_date", "collector__name", "pk"],
            },
        ),
        migrations.CreateModel(
            name="CollectionAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modificado")),
                ("assigned_date", models.DateField(verbose_name="fecha asignada")),
                (
                    "expected_amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                        verbose_name="importe esperado al asignar",
                    ),
                ),
                ("snapshot", models.JSONField(default=dict, verbose_name="detalle al asignar")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="collection_assignments",
                        to="core.customer",
                        verbose_name="cliente",
                    ),
                ),
                (
                    "route",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="core.collectionroute",
                        verbose_name="recorrido",
                    ),
                ),
            ],
            options={
                "verbose_name": "cliente asignado a cobranza",
                "verbose_name_plural": "clientes asignados a cobranza",
                "ordering": [
                    "assigned_date",
                    "customer__last_name",
                    "customer__first_name",
                    "pk",
                ],
            },
        ),
        migrations.AddField(
            model_name="payment",
            name="collector",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments_collected",
                to="core.collector",
                verbose_name="cobrador",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="collection_assignment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="core.collectionassignment",
                verbose_name="asignación de cobranza",
            ),
        ),
        migrations.AddField(
            model_name="collectionattempt",
            name="collector",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="collection_attempts",
                to="core.collector",
                verbose_name="cobrador",
            ),
        ),
        migrations.AddField(
            model_name="collectionattempt",
            name="collection_assignment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="attempts",
                to="core.collectionassignment",
                verbose_name="asignación de cobranza",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectionroute",
            constraint=models.UniqueConstraint(
                fields=("collection_date", "collector"),
                name="route_unique_date_collector",
            ),
        ),
        migrations.AddIndex(
            model_name="collectionroute",
            index=models.Index(fields=["collection_date"], name="collection_route_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="collectionassignment",
            constraint=models.UniqueConstraint(
                fields=("route", "customer"),
                name="assignment_unique_route_customer",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectionassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_date", "customer"),
                name="assignment_unique_date_customer",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectionassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(("expected_amount__gte", Decimal("0.00"))),
                name="assignment_expected_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="collectionassignment",
            index=models.Index(
                fields=["assigned_date", "customer"],
                name="assignment_date_customer_idx",
            ),
        ),
    ]
