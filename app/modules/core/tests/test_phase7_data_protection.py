import csv
import sqlite3
import uuid
from contextlib import closing
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from django.urls import reverse
from django.utils import timezone

from launcher.backup import (
    create_backup,
    materialize_backup,
    validate_application_backup,
)
from modules.core.models import CollectionAttempt
from modules.core.services.export_data import (
    EXPECTED_FILES,
    ExportError,
    create_data_export,
    list_exports,
    resolve_export_path,
)
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_payment
from modules.core.services.recovery import refresh_recovery_backup
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def read_csv(archive: ZipFile, name: str) -> list[dict[str, str]]:
    text = archive.read(name).decode("utf-8-sig")
    return list(csv.DictReader(StringIO(text), delimiter=";"))


def create_application_database(path: Path, value: str = "dato") -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table in (
            "django_migrations",
            "core_customer",
            "core_sale",
            "core_payment",
        ):
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", [value])
        connection.commit()


def create_relational_records():
    today = timezone.localdate()
    sale = make_sale(
        customer=None,
        delivery_date=today - timedelta(days=7),
        first_due_date=today,
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("5000.00"),
    )
    sale.customer.first_name = "Ángela"
    sale.customer.notes = "=2+2"
    sale.customer.save()
    create_installments(sale)
    payment = register_payment(
        sale=sale,
        amount=Decimal("10000.00"),
        payment_date=today,
        payment_method="Efectivo",
        notes="Pago parcial",
        operation_key=uuid.uuid4(),
    ).payment
    attempt = CollectionAttempt.objects.create(
        customer=sale.customer,
        sale=sale,
        attempt_date=today,
        result=CollectionAttempt.Result.PROMISED,
        notes="Completa mañana",
    )
    return sale, payment, attempt


def test_export_contains_excel_compatible_relational_csv_files(tmp_path):
    sale, payment, attempt = create_relational_records()

    export = create_data_export(tmp_path)

    with ZipFile(export) as archive:
        assert set(archive.namelist()) == EXPECTED_FILES
        for name in EXPECTED_FILES - {"resumen.txt"}:
            assert archive.read(name).startswith(b"\xef\xbb\xbf")

        customers = read_csv(archive, "clientes.csv")
        sales = read_csv(archive, "ventas.csv")
        installments = read_csv(archive, "cuotas.csv")
        payments = read_csv(archive, "pagos.csv")
        allocations = read_csv(archive, "aplicaciones_pago.csv")
        attempts = read_csv(archive, "intentos_cobranza.csv")

        assert customers[0]["nombre"] == "Ángela"
        assert customers[0]["observaciones"] == "'=2+2"
        assert sales[0]["cliente_id"] == str(sale.customer_id)
        assert sales[0]["precio_producto"] == "400000.00"
        assert sales[0]["entrega_inicial"] == "0.00"
        assert sales[0]["total_en_cuotas"] == "20000.00"
        assert installments[0]["venta_id"] == str(sale.pk)
        assert payments[0]["id"] == str(payment.pk)
        assert payments[0]["tipo"] == "installment"
        assert allocations[0]["pago_id"] == str(payment.pk)
        assert attempts[0]["id"] == str(attempt.pk)
        assert "decimal con punto" in archive.read("resumen.txt").decode("utf-8-sig")


def test_export_catalog_and_safe_path_resolution(tmp_path):
    export = create_data_export(tmp_path)

    listed = list_exports(tmp_path)

    assert [item.path for item in listed] == [export]
    assert resolve_export_path(tmp_path, export.name) == export
    with pytest.raises(ExportError):
        resolve_export_path(tmp_path, "../export_stolen.zip")


def test_data_management_page_explains_backup_export_and_restore(client, settings, tmp_path):
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.EXPORT_DIR = tmp_path / "exports"

    response = client.get(reverse("core:data_management"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Crear backup ZIP" in content
    assert "Descargar ZIP de CSV" in content
    assert "RESTAURAR_DATOS.bat" in content


def test_export_view_generates_download_and_keeps_copy(client, settings, tmp_path):
    create_relational_records()
    settings.EXPORT_DIR = tmp_path / "exports"

    response = client.post(reverse("core:data_export_create"))
    payload = b"".join(response.streaming_content)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert response["Content-Disposition"].startswith("attachment;")
    exports = list(settings.EXPORT_DIR.glob("export_*.zip"))
    assert len(exports) == 1
    assert payload == exports[0].read_bytes()


def test_saved_export_can_be_downloaded_again(client, settings, tmp_path):
    settings.EXPORT_DIR = tmp_path / "exports"
    export = create_data_export(settings.EXPORT_DIR)

    response = client.get(reverse("core:data_export_download", args=[export.name]))

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == export.read_bytes()


def test_missing_export_and_backup_return_not_found(client, settings, tmp_path):
    settings.EXPORT_DIR = tmp_path / "exports"
    settings.BACKUP_DIR = tmp_path / "backups"

    export_response = client.get(
        reverse("core:data_export_download", args=["export_missing.zip"])
    )
    backup_response = client.get(
        reverse("core:backup_download", args=["gestion_missing.sqlite3"])
    )

    assert export_response.status_code == 404
    assert backup_response.status_code == 404


def test_manual_backup_view_creates_valid_sqlite_copy(
    client,
    settings,
    tmp_path,
    monkeypatch,
):
    database = tmp_path / "data" / "gestion_financiera.sqlite3"
    database.parent.mkdir()
    create_application_database(database)
    backup_directory = tmp_path / "backups"
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", database)
    settings.BACKUP_DIR = backup_directory

    response = client.post(reverse("core:backup_create"))

    assert response.status_code == 302
    backups = list(backup_directory.glob("gestion_manual_*.sqlite3.zip"))
    assert len(backups) == 1
    validate_application_backup(backups[0])


def test_backup_can_be_downloaded_from_management_view(client, settings, tmp_path):
    backup_directory = tmp_path / "backups"
    database = tmp_path / "database.sqlite3"
    create_application_database(database)
    backup = create_backup(database, backup_directory, label="manual")
    settings.BACKUP_DIR = backup_directory

    response = client.get(reverse("core:backup_download", args=[backup.name]))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    assert b"".join(response.streaming_content) == backup.read_bytes()


def test_recovery_service_refreshes_fixed_copy(settings, tmp_path, monkeypatch):
    database = tmp_path / "data" / "gestion_financiera.sqlite3"
    database.parent.mkdir()
    create_application_database(database, "estado reciente")
    backup_directory = tmp_path / "backups"
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", database)
    settings.BACKUP_DIR = backup_directory

    recovery = refresh_recovery_backup()

    assert recovery == backup_directory / "gestion_recovery.sqlite3.zip"
    validate_application_backup(recovery)
    with (
        materialize_backup(recovery, working_directory=tmp_path) as extracted,
        closing(sqlite3.connect(extracted)) as connection,
    ):
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "estado reciente",
        )
