from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from django.conf import settings
from django.utils import timezone

from modules.core.models import Customer, Installment, Payment, Product, Sale
from modules.core.services.analytics import build_analytics
from modules.core.services.balances import (
    get_installment_balance,
    installment_balance_prefetches,
    sale_effective_filter,
)

EXPECTED_FILES = {
    "README.txt",
    "data_dictionary.csv",
    "dim_clientes.csv",
    "dim_productos.csv",
    "fact_cuotas.csv",
    "fact_operaciones.csv",
    "fact_pagos.csv",
    "manifest.json",
    "mart_aging.csv",
    "mart_cohortes.csv",
    "metricas.csv",
}


class ReportingExportError(RuntimeError):
    pass


def _value(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value)
    return f"'{text}" if text.lstrip().startswith(("=", "+", "-", "@")) else text


def _csv_bytes(headers: list[str], rows) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows([_value(value) for value in row] for row in rows)
    return output.getvalue().encode("utf-8-sig")


def _dictionary_rows(tables) -> list[tuple]:
    descriptions = {
        "dim_clientes.csv": "Dimensión seudonimizada sin identificadores directos.",
        "dim_productos.csv": "Catálogo de productos.",
        "fact_operaciones.csv": "Una fila por venta o préstamo.",
        "fact_cuotas.csv": "Snapshot de saldo por cuota a la fecha de corte.",
        "fact_pagos.csv": "Pagos registrados hasta la fecha de corte.",
        "mart_aging.csv": "Cartera agrupada por días de atraso.",
        "mart_cohortes.csv": "Desempeño por mes de originación.",
        "metricas.csv": "KPIs y residuos de reconciliación.",
    }
    return [
        (name, column, descriptions.get(name, ""))
        for name, (headers, _) in tables.items()
        for column in headers
    ]


def _tables(*, as_of: date) -> tuple[dict, dict]:
    analytics = build_analytics(as_of=as_of)
    installments = list(
        Installment.objects.filter(
            sale_effective_filter(as_of, "sale"),
            sale__delivery_date__lte=as_of,
        )
        .select_related("sale", "sale__customer")
        .prefetch_related(*installment_balance_prefetches())
        .order_by("pk")
    )
    tables = {
        "dim_clientes.csv": (
            ["cliente_id", "barrio", "activo"],
            [
                (item.pk, item.neighborhood, item.is_active)
                for item in Customer.objects.order_by("pk")
            ],
        ),
        "dim_productos.csv": (
            ["producto_id", "producto", "activo"],
            [(item.pk, item.name, item.is_active) for item in Product.objects.order_by("pk")],
        ),
        "fact_operaciones.csv": (
            [
                "operacion_id",
                "cliente_id",
                "producto_id",
                "tipo_operacion",
                "fecha_entrega",
                "capital_origen",
                "total_financiado",
                "frecuencia",
                "cantidad_cuotas",
                "estado",
            ],
            [
                (
                    item.pk,
                    item.customer_id,
                    item.product_id,
                    item.operation_type,
                    item.delivery_date,
                    item.cash_price,
                    item.financed_amount,
                    item.frequency,
                    item.installment_count,
                    item.status,
                )
                for item in Sale.objects.filter(
                    sale_effective_filter(as_of),
                    delivery_date__lte=as_of,
                ).order_by("pk")
            ],
        ),
        "fact_cuotas.csv": (
            [
                "cuota_id",
                "operacion_id",
                "cliente_id",
                "numero",
                "vencimiento",
                "capital_original",
                "capital_pagado",
                "capital_pendiente",
                "recargo_pendiente",
                "saldo_total",
                "dias_atraso",
                "fecha_corte",
            ],
            [
                (
                    item.pk,
                    item.sale_id,
                    item.sale.customer_id,
                    item.number,
                    item.due_date,
                    (balance := get_installment_balance(item, as_of=as_of)).principal_original,
                    balance.principal_paid,
                    balance.principal_due,
                    balance.late_fees_due,
                    balance.total_due,
                    balance.days_overdue,
                    as_of,
                )
                for item in installments
            ],
        ),
        "fact_pagos.csv": (
            ["pago_id", "operacion_id", "cliente_id", "fecha", "importe", "medio", "tipo"],
            [
                (
                    item.pk,
                    item.sale_id,
                    item.customer_id,
                    item.payment_date,
                    item.amount,
                    item.payment_method,
                    item.kind,
                )
                for item in Payment.objects.filter(
                    sale_effective_filter(as_of, "sale"),
                    status=Payment.Status.REGISTERED,
                    payment_date__lte=as_of,
                ).order_by("pk")
            ],
        ),
        "mart_aging.csv": (
            [
                "bucket",
                "clientes",
                "cuotas",
                "capital_pendiente",
                "recargos_pendientes",
                "saldo_total",
                "participacion_porcentaje",
                "fecha_corte",
            ],
            [
                (
                    row["label"],
                    row["customers"],
                    row["installments"],
                    row["principal_due"],
                    row["late_fees_due"],
                    row["total_due"],
                    row["share"],
                    as_of,
                )
                for row in analytics["aging_rows"]
            ],
        ),
        "mart_cohortes.csv": (
            [
                "cohorte_mes",
                "clientes",
                "operaciones",
                "monto_financiado_originado",
                "monto_cobrado_cuotas",
                "monto_pendiente_cuotas",
                "monto_vencido_cuotas",
                "recuperacion_porcentaje",
                "mora_porcentaje",
                "fecha_corte",
            ],
            [
                (
                    row["cohort_month"],
                    row["customers"],
                    row["sales"],
                    row["principal_originated"],
                    row["principal_collected"],
                    row["principal_outstanding"],
                    row["principal_overdue"],
                    row["recovery_rate"],
                    row["overdue_rate"],
                    as_of,
                )
                for row in analytics["cohort_rows"]
            ],
        ),
        "metricas.csv": (
            ["metrica", "valor", "fecha_corte"],
            [
                ("monto_financiado_originado", analytics["principal_originated"], as_of),
                ("monto_cobrado_cuotas", analytics["principal_collected"], as_of),
                ("cartera_total", analytics["portfolio_total"], as_of),
                ("cartera_vencida", analytics["overdue_total"], as_of),
                ("tasa_recuperacion", analytics["recovery_rate"], as_of),
                ("tasa_mora", analytics["overdue_rate"], as_of),
                ("residuo_aging", analytics["reconciliation"]["aging_vs_portfolio"], as_of),
                ("residuo_cohortes", analytics["reconciliation"]["cohorts_vs_principal"], as_of),
                (
                    "residuo_pagos_aplicaciones",
                    analytics["reconciliation"]["payments_vs_allocations"],
                    as_of,
                ),
            ],
        ),
    }
    return tables, analytics


def create_reporting_export(*, as_of: date, export_directory: Path | None = None) -> Path:
    directory = Path(export_directory or settings.EXPORT_DIR).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"analytics_{as_of:%Y-%m-%d}.zip"
    temporary = destination.with_suffix(".zip.tmp")
    tables, analytics = _tables(as_of=as_of)
    dictionary = _dictionary_rows(tables)
    manifest = {
        "schema_version": "1.0.0",
        "generated_at": timezone.now().isoformat(),
        "as_of": as_of.isoformat(),
        "delimiter": ";",
        "encoding": "utf-8-sig",
        "files": {name: len(rows) for name, (_, rows) in tables.items()},
        "reconciliation": {
            key: _value(value) for key, value in analytics["reconciliation"].items()
        },
    }
    readme = (
        "GESTIÓN FINANCIERA — DATA MART ANALÍTICO\n\n"
        f"Fecha de corte: {as_of:%Y-%m-%d}\n"
        "Modelo: dimensiones + hechos + marts de aging y cohortes.\n"
        "Importá cada CSV en Power BI usando UTF-8 y punto y coma.\n"
        "Las métricas se reconcilian contra las mismas reglas financieras de la aplicación.\n"
        "No se incluyen nombres, DNI, teléfonos, domicilios, notas ni credenciales.\n"
    )
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name, (headers, rows) in tables.items():
                archive.writestr(name, _csv_bytes(headers, rows))
            archive.writestr(
                "data_dictionary.csv",
                _csv_bytes(["archivo", "columna", "descripcion"], dictionary),
            )
            archive.writestr("manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
            archive.writestr("README.txt", readme.encode("utf-8-sig"))
        with ZipFile(temporary) as archive:
            if set(archive.namelist()) != EXPECTED_FILES or archive.testzip() is not None:
                raise ReportingExportError("El data mart quedó incompleto.")
        temporary.replace(destination)
    except (OSError, BadZipFile, ReportingExportError) as exc:
        temporary.unlink(missing_ok=True)
        raise ReportingExportError("No se pudo crear el data mart analítico.") from exc
    return destination
