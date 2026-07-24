import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_is_available(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "Gestión Financiera" in response.content.decode()


@pytest.mark.django_db
def test_health_checks_sqlite(client):
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
