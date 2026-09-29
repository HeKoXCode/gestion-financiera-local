import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


def _restore_latest():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def _reset_core():
    executor = MigrationExecutor(connection)
    executor.migrate([("core", None)])


@pytest.mark.django_db(transaction=True)
def test_v18_unifies_github_110_history_and_preserves_customer():
    github_target = ("core", "0008_auditevent")
    final_target = ("core", "0015_auditevent")
    _reset_core()
    old_apps = _migrate(github_target)

    try:
        Customer = old_apps.get_model("core", "Customer")
        customer = Customer.objects.create(
            first_name="Cliente",
            last_name="Historia GitHub",
            phone="1111111111",
            address="Domicilio ficticio",
        )

        final_apps = _migrate(final_target)
        FinalCustomer = final_apps.get_model("core", "Customer")
        AuditEvent = final_apps.get_model("core", "AuditEvent")

        migrated = FinalCustomer.objects.get(pk=customer.pk)
        assert (migrated.first_name, migrated.last_name) == (
            "Cliente",
            "Historia GitHub",
        )
        assert migrated.deleted_at is None
        assert AuditEvent.objects.count() == 0
    finally:
        _restore_latest()


@pytest.mark.django_db(transaction=True)
def test_v18_unifies_local_172_history_and_preserves_customer():
    local_target = ("core", "0014_v16_collection_workflow")
    final_target = ("core", "0015_auditevent")
    _reset_core()
    old_apps = _migrate(local_target)

    try:
        Customer = old_apps.get_model("core", "Customer")
        customer = Customer.objects.create(
            first_name="Cliente",
            last_name="Historia Local",
            phone="2222222222",
            address="Domicilio ficticio",
        )

        final_apps = _migrate(final_target)
        FinalCustomer = final_apps.get_model("core", "Customer")
        AuditEvent = final_apps.get_model("core", "AuditEvent")

        migrated = FinalCustomer.objects.get(pk=customer.pk)
        assert (migrated.first_name, migrated.last_name) == (
            "Cliente",
            "Historia Local",
        )
        assert migrated.deleted_at is None
        assert AuditEvent.objects.count() == 0
    finally:
        _restore_latest()
