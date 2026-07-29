import pytest
from django.urls import reverse
from modules.core.models import CollectionAttempt, Payment, Sale

pytestmark = pytest.mark.django_db


def test_financial_choices_describe_the_actual_behavior():
    assert Sale.Frequency.BIWEEKLY.label == "Cada 2 semanas"
    assert Payment.Kind.INITIAL.label == "Pago inicial"
    assert CollectionAttempt.Result.ABSENT.label == "No estaba en el domicilio"


def test_main_pages_use_plain_argentine_spanish(client):
    home = client.get(reverse("core:home")).content.decode()
    agenda = client.get(reverse("core:agenda")).content.decode()
    reports = client.get(reverse("core:reports")).content.decode()
    data = client.get(reverse("core:data_management")).content.decode()

    assert "Datos guardados en este equipo" in home
    assert "Sincronizado localmente" not in home
    assert "Total a cobrar" in agenda
    assert "Total recorrido" not in agenda
    assert "Clientes con pagos atrasados" in reports
    assert "Clientes morosos" not in reports
    assert "Crear copia ZIP" in data
    assert "Crear backup ZIP" not in data
