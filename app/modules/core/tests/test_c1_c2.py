from __future__ import annotations

import json
import runpy
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from modules.core import checks, views
from modules.core.middleware import ADMIN_GROUP, COLLECTOR_GROUP
from modules.core.models import AuditEvent, Sale
from modules.core.services import database_backup
from modules.core.services.analytics import build_analytics
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_payment
from modules.core.services.reporting_export import EXPECTED_FILES, create_reporting_export
from modules.core.tests.factories import make_customer, make_sale

pytestmark = pytest.mark.django_db


def _user_with_role(username: str, group_name: str):
    user = get_user_model().objects.create_user(username=username, password="safe-test-pass")
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


@override_settings(GESTION_AUTH_REQUIRED=True, GESTION_DEPLOYMENT_MODE="multiuser")
def test_multiuser_mode_requires_login_and_enforces_role_matrix(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 302
    assert reverse("login") in response.url

    collector = _user_with_role("cobrador", COLLECTOR_GROUP)
    client.force_login(collector)
    assert client.get(reverse("core:analytics")).status_code == 200
    assert client.get(reverse("core:configuration")).status_code == 403

    admin = _user_with_role("administrador", ADMIN_GROUP)
    client.force_login(admin)
    assert client.get(reverse("core:configuration")).status_code == 200
    assert client.get(reverse("core:audit_events")).status_code == 200


@override_settings(GESTION_AUTH_REQUIRED=True, GESTION_DEPLOYMENT_MODE="multiuser")
def test_multiuser_proxy_traffic_uses_login_instead_of_local_mobile_pairing(client):
    response = client.get(reverse("core:home"), REMOTE_ADDR="172.20.0.4")

    assert response.status_code == 302
    assert reverse("login") in response.url
    assert reverse("core:mobile_access") not in response.url


@override_settings(GESTION_AUTH_REQUIRED=True, GESTION_DEPLOYMENT_MODE="multiuser")
def test_successful_mutation_creates_append_only_audit_event(client):
    admin = _user_with_role("admin-audit", ADMIN_GROUP)
    client.force_login(admin)
    response = client.post(
        reverse("core:product_create"),
        {"name": "Producto auditable", "description": "Prueba", "is_active": "on"},
        REMOTE_ADDR="127.0.0.1",
    )

    assert response.status_code == 302
    event = AuditEvent.objects.get(action="core:product_create")
    assert event.actor == admin
    assert event.remote_address == "127.0.0.1"
    assert event.metadata == {"deployment_mode": "multiuser"}

    event.status_code = 201
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()


def test_setup_multiuser_reads_passwords_from_environment(monkeypatch):
    monkeypatch.setenv("TEST_ADMIN_PASSWORD", "admin-password-very-long")
    monkeypatch.setenv("TEST_COLLECTOR_PASSWORD", "collector-password-long")
    call_command(
        "setup_multiuser",
        admin_username="admin-command",
        admin_password_env="TEST_ADMIN_PASSWORD",
        collector_username="collector-command",
        collector_password_env="TEST_COLLECTOR_PASSWORD",
    )

    user_model = get_user_model()
    assert user_model.objects.get(username="admin-command").groups.filter(
        name=ADMIN_GROUP
    ).exists()
    assert user_model.objects.get(username="collector-command").groups.filter(
        name=COLLECTOR_GROUP
    ).exists()


def test_postgresql_and_https_profile_is_built_from_environment(monkeypatch, tmp_path):
    variables = {
        "GESTION_DATA_DIR": str(tmp_path / "data"),
        "GESTION_BACKUP_DIR": str(tmp_path / "backups"),
        "GESTION_EXPORT_DIR": str(tmp_path / "exports"),
        "GESTION_MEDIA_DIR": str(tmp_path / "media"),
        "GESTION_DEPLOYMENT_MODE": "multiuser",
        "GESTION_DATABASE_ENGINE": "postgresql",
        "GESTION_BEHIND_HTTPS_PROXY": "1",
        "DJANGO_DEBUG": "0",
        "DJANGO_SECRET_KEY": "test-secret-key-not-for-production",
        "DJANGO_ALLOWED_HOSTS": "gestion.example.com",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://gestion.example.com",
        "PGDATABASE": "gestion",
        "PGUSER": "gestion_user",
        "PGPASSWORD": "not-logged",
        "PGHOST": "database.internal",
        "PGSSLMODE": "require",
    }
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    project_root = Path(__file__).resolve().parents[4]
    configured = runpy.run_path(str(project_root / "app" / "config" / "settings.py"))

    database = configured["DATABASES"]["default"]
    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert database["ATOMIC_REQUESTS"] is True
    assert database["OPTIONS"]["sslmode"] == "require"
    assert configured["GESTION_AUTH_REQUIRED"] is True
    assert configured["SECURE_SSL_REDIRECT"] is True
    assert configured["SESSION_COOKIE_SECURE"] is True


def test_multiuser_deploy_check_rejects_insecure_profile(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.delenv("DJANGO_ALLOWED_HOSTS", raising=False)
    monkeypatch.setattr(
        checks,
        "settings",
        SimpleNamespace(
            GESTION_DEPLOYMENT_MODE="multiuser",
            GESTION_AUTH_REQUIRED=False,
            DEBUG=True,
            BEHIND_HTTPS_PROXY=False,
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3"}},
            CSRF_TRUSTED_ORIGINS=[],
        ),
    )

    ids = {finding.id for finding in checks.check_multiuser_deployment(None)}

    assert ids == {
        "gestion.E001",
        "gestion.E002",
        "gestion.E003",
        "gestion.E004",
        "gestion.E005",
        "gestion.E006",
        "gestion.E007",
    }


def test_postgresql_backup_uses_safe_arguments_and_verifies_dump(monkeypatch, tmp_path):
    monkeypatch.setattr(database_backup, "connection", SimpleNamespace(vendor="postgresql"))
    monkeypatch.setattr(database_backup.shutil, "which", lambda executable: executable)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[0] == "pg_dump":
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMP-test")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(database_backup.subprocess, "run", fake_run)
    database_settings = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "gestion",
        "USER": "gestion_user",
        "PASSWORD": "secret-not-in-command",
        "HOST": "db",
        "PORT": "5432",
    }
    monkeypatch.setattr(database_backup.settings, "DATABASES", {"default": database_settings})
    backup = database_backup.create_deployment_backup(output_directory=tmp_path)

    assert backup.read_bytes() == b"PGDMP-test"
    assert calls[0][0][0] == "pg_dump"
    assert "secret-not-in-command" not in calls[0][0]
    assert calls[0][1]["env"]["PGPASSWORD"] == "secret-not-in-command"
    assert calls[1][0][0] == "pg_restore"


def test_postgresql_backups_are_listed_without_treating_database_name_as_a_file(
    client, monkeypatch, settings, tmp_path
):
    postgresql_connection = SimpleNamespace(vendor="postgresql")
    monkeypatch.setattr(database_backup, "connection", postgresql_connection)
    monkeypatch.setattr(views, "connection", postgresql_connection)
    settings.BACKUP_DIR = tmp_path
    backup = tmp_path / "gestion_postgresql_manual_2026-08-27_120000.dump"
    backup.write_bytes(b"PGDMP-test")

    response = client.get(reverse("core:data_management"))

    assert response.status_code == 200
    assert response.context["database_engine"] == "PostgreSQL"
    assert response.context["database_size"] is None
    assert response.context["database_exists"] is True
    assert response.context["backup_count"] == 1
    assert response.context["backups"][0]["backup"].label == "manual"
    assert "pg_restore" in response.content.decode()


def test_postgresql_backup_resolver_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(database_backup, "connection", SimpleNamespace(vendor="postgresql"))

    with pytest.raises(database_backup.DatabaseBackupError):
        database_backup.resolve_deployment_backup(
            "../gestion_postgresql_manual_2026-08-27_120000.dump",
            output_directory=tmp_path,
        )


def _analytics_sale():
    as_of = timezone.localdate()
    customer = make_customer(
        first_name="Ana",
        last_name="Analítica",
        dni="99111222",
        phone="1199999999",
        address="Dirección privada 123",
    )
    sale = make_sale(
        customer=customer,
        frequency=Sale.Frequency.MONTHLY,
        delivery_date=as_of - timedelta(days=45),
        first_due_date=as_of - timedelta(days=10),
        cash_price=Decimal("20000.00"),
        financed_amount=Decimal("20000.00"),
        installment_count=2,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    register_payment(
        sale=sale,
        amount=Decimal("10000.00"),
        payment_date=as_of,
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
    )
    return sale, as_of


def test_analytics_reconciles_aging_cohorts_and_payment_allocations():
    _, as_of = _analytics_sale()
    analytics = build_analytics(as_of=as_of)

    assert analytics["principal_originated"] == Decimal("20000.00")
    assert analytics["principal_collected"] == Decimal("10000.00")
    assert analytics["portfolio_total"] == Decimal("10000.00")
    assert analytics["recovery_rate"] == Decimal("50.00")
    assert analytics["reconciliation"]["passed"] is True
    assert sum(row["total_due"] for row in analytics["aging_rows"]) == Decimal("10000.00")
    assert analytics["cohort_rows"][0]["principal_outstanding"] == Decimal("10000.00")


def test_reporting_export_is_power_bi_ready_and_excludes_direct_identifiers(tmp_path):
    _, as_of = _analytics_sale()
    export = create_reporting_export(as_of=as_of, export_directory=tmp_path)

    with ZipFile(export) as archive:
        assert set(archive.namelist()) == EXPECTED_FILES
        manifest = json.loads(archive.read("manifest.json"))
        combined = b"".join(archive.read(name) for name in archive.namelist())
        cohort_content = archive.read("mart_cohortes.csv").decode("utf-8-sig")
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["reconciliation"]["passed"] == "1"
    assert b"99111222" not in combined
    assert b"1199999999" not in combined
    assert b"Direcci\xc3\xb3n privada" not in combined
    assert b"Ana" not in combined
    assert b"Anal\xc3\xadtica" not in combined
    assert "monto_financiado_originado" in cohort_content


def test_analytics_page_and_admin_export_render(client, tmp_path, settings):
    _, as_of = _analytics_sale()
    settings.EXPORT_DIR = tmp_path

    response = client.get(reverse("core:analytics"), {"fecha": as_of.isoformat()})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Analítica financiera" in content
    assert "Cohortes mensuales" in content
    assert "Conciliado" in content

    export_response = client.post(
        reverse("core:reporting_export_create") + f"?fecha={as_of.isoformat()}"
    )
    assert export_response.status_code == 200
    assert export_response["Content-Type"] == "application/zip"


def test_deployment_assets_are_versioned():
    root = Path(__file__).resolve().parents[4]
    compose = (root / "deploy" / "compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (root / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "postgres:17-alpine" in compose
    assert "GESTION_BEHIND_HTTPS_PROXY" in compose
    assert "X-Forwarded-Proto" in compose
    assert "Caddyfile" in compose
    assert "--require-hashes" in dockerfile
    assert "migrate --noinput" in entrypoint
