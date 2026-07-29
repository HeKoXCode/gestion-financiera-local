from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from django.conf import settings
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    CollectionAttempt,
    Customer,
    Installment,
    LateFee,
    Payment,
    PaymentAllocation,
    Product,
    Sale,
)


class ExportError(RuntimeError):
    """The relational CSV export could not be created or validated."""


@dataclass(frozen=True)
class ExportInfo:
    path: Path
    name: str
    created_at: datetime
    size: int


EXPECTED_FILES = {
    "clientes.csv",
    "productos.csv",
    "ventas.csv",
    "cuotas.csv",
    "recargos.csv",
    "pagos.csv",
    "aplicaciones_pago.csv",
    "intentos_cobranza.csv",
    "configuracion.csv",
    "resumen.txt",
}


def _safe_text(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(
        ("\t", "\r", "\n")
    ):
        return f"'{value}"
    return value


def _value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return _safe_text(str(value))


def _csv_bytes(headers: list[str], rows) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_value(value) for value in row])
    return output.getvalue().encode("utf-8-sig")


def _export_tables() -> dict[str, tuple[list[str], list[tuple]]]:
    business = BusinessSettings.get_solo()
    return {
        "clientes.csv": (
            [
                "id",
                "nombre",
                "apellido",
                "dni",
                "telefono",
                "direccion",
                "barrio",
                "referencia_domicilio",
                "observaciones",
                "activo",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.first_name,
                    item.last_name,
                    item.dni,
                    item.phone,
                    item.address,
                    item.neighborhood,
                    item.address_reference,
                    item.notes,
                    item.is_active,
                    item.created_at,
                    item.updated_at,
                )
                for item in Customer.objects.order_by("pk")
            ],
        ),
        "productos.csv": (
            ["id", "nombre", "descripcion", "activo", "creado", "modificado"],
            [
                (
                    item.pk,
                    item.name,
                    item.description,
                    item.is_active,
                    item.created_at,
                    item.updated_at,
                )
                for item in Product.objects.order_by("pk")
            ],
        ),
        "ventas.csv": (
            [
                "id",
                "cliente_id",
                "producto_id",
                "descripcion_producto",
                "fecha_entrega",
                "precio_producto",
                "entrega_inicial",
                "total_en_cuotas",
                "frecuencia",
                "cantidad_cuotas",
                "recargo_diario",
                "primer_vencimiento",
                "estado",
                "fecha_cancelacion",
                "motivo_cancelacion",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.customer_id,
                    item.product_id,
                    item.product_description,
                    item.delivery_date,
                    item.cash_price,
                    item.down_payment,
                    item.financed_amount,
                    item.frequency,
                    item.installment_count,
                    item.daily_late_fee,
                    item.first_due_date,
                    item.status,
                    item.cancelled_on,
                    item.cancellation_reason,
                    item.created_at,
                    item.updated_at,
                )
                for item in Sale.objects.order_by("pk")
            ],
        ),
        "cuotas.csv": (
            [
                "id",
                "venta_id",
                "numero",
                "vencimiento",
                "importe_original",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.sale_id,
                    item.number,
                    item.due_date,
                    item.original_amount,
                    item.created_at,
                    item.updated_at,
                )
                for item in Installment.objects.order_by("pk")
            ],
        ),
        "recargos.csv": (
            ["id", "cuota_id", "fecha", "importe", "creado", "modificado"],
            [
                (
                    item.pk,
                    item.installment_id,
                    item.fee_date,
                    item.amount,
                    item.created_at,
                    item.updated_at,
                )
                for item in LateFee.objects.order_by("pk")
            ],
        ),
        "pagos.csv": (
            [
                "id",
                "clave_operacion",
                "cliente_id",
                "venta_id",
                "fecha",
                "importe",
                "metodo",
                "tipo",
                "observaciones",
                "estado",
                "anulado_el",
                "motivo_anulacion",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.idempotency_key,
                    item.customer_id,
                    item.sale_id,
                    item.payment_date,
                    item.amount,
                    item.payment_method,
                    item.kind,
                    item.notes,
                    item.status,
                    item.voided_at,
                    item.void_reason,
                    item.created_at,
                    item.updated_at,
                )
                for item in Payment.objects.order_by("pk")
            ],
        ),
        "aplicaciones_pago.csv": (
            [
                "id",
                "pago_id",
                "cuota_id",
                "componente",
                "importe",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.payment_id,
                    item.installment_id,
                    item.component,
                    item.amount,
                    item.created_at,
                    item.updated_at,
                )
                for item in PaymentAllocation.objects.order_by("pk")
            ],
        ),
        "intentos_cobranza.csv": (
            [
                "id",
                "cliente_id",
                "venta_id",
                "fecha",
                "resultado",
                "observaciones",
                "creado",
                "modificado",
            ],
            [
                (
                    item.pk,
                    item.customer_id,
                    item.sale_id,
                    item.attempt_date,
                    item.result,
                    item.notes,
                    item.created_at,
                    item.updated_at,
                )
                for item in CollectionAttempt.objects.order_by("pk")
            ],
        ),
        "configuracion.csv": (
            [
                "nombre_negocio",
                "logo",
                "recargo_diario",
                "dias_cobranza",
                "metodos_pago",
                "frecuencias",
                "maximo_cuotas",
                "recargo_domingos",
                "recargo_tras_pago_parcial",
                "pagos_adelantados",
                "mensaje_whatsapp",
                "modificado",
            ],
            [
                (
                    business.business_name,
                    business.logo.name,
                    business.daily_late_fee,
                    "|".join(str(day) for day in business.collection_days),
                    "|".join(business.payment_methods),
                    "|".join(business.available_frequencies),
                    business.max_installments,
                    business.charge_sundays,
                    business.late_fee_after_partial_payment,
                    business.allow_advance_payments,
                    business.whatsapp_message,
                    business.updated_at,
                )
            ],
        ),
    }


def _validate_export(path: Path) -> None:
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            corrupted = archive.testzip()
    except (OSError, BadZipFile) as exc:
        raise ExportError("No se pudo validar la exportación.") from exc
    if corrupted or names != EXPECTED_FILES:
        raise ExportError("La exportación quedó incompleta o dañada.")


def create_data_export(export_directory: Path | None = None) -> Path:
    export_directory = Path(export_directory or settings.EXPORT_DIR).resolve()
    export_directory.mkdir(parents=True, exist_ok=True)
    generated_at = timezone.localtime()
    timestamp = generated_at.strftime("%Y-%m-%d_%H%M%S_%f")
    destination = export_directory / f"export_{timestamp}.zip"
    temporary = destination.with_suffix(".zip.tmp")
    tables = _export_tables()

    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name, (headers, rows) in tables.items():
                archive.writestr(name, _csv_bytes(headers, rows))
            counts = {name: len(rows) for name, (_, rows) in tables.items()}
            summary = "\n".join(
                [
                    "GESTIÓN FINANCIERA - EXPORTACIÓN RELACIONAL",
                    f"Generada: {generated_at.isoformat(timespec='seconds')}",
                    f"Negocio: {BusinessSettings.get_solo().business_name}",
                    "",
                    "Formato: CSV UTF-8 con BOM, delimitado por punto y coma.",
                    "Importes: decimal con punto y sin símbolo monetario.",
                    "Las columnas *_id conservan las relaciones entre archivos.",
                    "Los textos que podrían ejecutarse como fórmula están protegidos.",
                    (
                        "Este ZIP es para consulta; el backup .sqlite3.zip "
                        "es la copia restaurable."
                    ),
                    "",
                    *[
                        f"{name}: {count} registros"
                        for name, count in counts.items()
                    ],
                ]
            )
            archive.writestr("resumen.txt", summary.encode("utf-8-sig"))
        _validate_export(temporary)
        temporary.replace(destination)
    except (OSError, ExportError, BadZipFile) as exc:
        if temporary.exists():
            temporary.unlink()
        raise ExportError("No se pudo crear la exportación de datos.") from exc

    return destination


def list_exports(export_directory: Path) -> list[ExportInfo]:
    export_directory = export_directory.resolve()
    if not export_directory.is_dir():
        return []
    exports = []
    for path in export_directory.glob("export_*.zip"):
        if not path.is_file():
            continue
        stat = path.stat()
        exports.append(
            ExportInfo(
                path=path,
                name=path.name,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size,
            )
        )
    return sorted(exports, key=lambda item: item.created_at, reverse=True)


def resolve_export_path(export_directory: Path, name: str) -> Path:
    export_directory = export_directory.resolve()
    if Path(name).name != name or not name.startswith("export_"):
        raise ExportError("El nombre de la exportación no es válido.")
    candidate = (export_directory / name).resolve()
    if candidate.parent != export_directory or candidate.suffix != ".zip":
        raise ExportError("La ruta de la exportación no es válida.")
    if not candidate.is_file():
        raise ExportError("La exportación solicitada no existe.")
    _validate_export(candidate)
    return candidate
