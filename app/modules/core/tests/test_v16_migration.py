from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_v16_migration_recovers_latest_active_collector_as_habitual():
    old_target = [("core", "0013_collector_safe_archive")]
    new_target = [("core", "0014_v16_collection_workflow")]
    executor = MigrationExecutor(connection)
    executor.migrate(old_target)
    old_apps = executor.loader.project_state(old_target).apps

    try:
        Customer = old_apps.get_model("core", "Customer")
        Collector = old_apps.get_model("core", "Collector")
        CollectionRoute = old_apps.get_model("core", "CollectionRoute")
        CollectionAssignment = old_apps.get_model("core", "CollectionAssignment")

        customer = Customer.objects.create(
            first_name="Cliente",
            last_name="Migración 1.6",
            phone="1111111111",
            address="Domicilio de prueba",
        )
        older_collector = Collector.objects.create(name="Cobrador anterior")
        current_collector = Collector.objects.create(name="Cobrador actual")
        archived_collector = Collector.objects.create(
            name="Cobrador archivado",
            is_active=False,
            archived_at=datetime(2026, 9, 15, 12, tzinfo=UTC),
        )
        routes = [
            CollectionRoute.objects.create(
                collection_date=date(2026, 9, 1),
                collector=older_collector,
            ),
            CollectionRoute.objects.create(
                collection_date=date(2026, 9, 10),
                collector=current_collector,
            ),
            CollectionRoute.objects.create(
                collection_date=date(2026, 9, 15),
                collector=archived_collector,
            ),
        ]
        for route in routes:
            CollectionAssignment.objects.create(
                route=route,
                customer=customer,
                assigned_date=route.collection_date,
                expected_amount=Decimal("10000.00"),
                snapshot={},
            )

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        migrated_apps = executor.loader.project_state(new_target).apps
        CustomerCollectorLink = migrated_apps.get_model(
            "core", "CustomerCollectorLink"
        )
        link = CustomerCollectorLink.objects.get(customer_id=customer.pk)

        assert link.collector_id == current_collector.pk
        assert link.started_at == date(2026, 9, 10)
        assert link.source_route_id == routes[1].pk
        assert "recuperada" in link.reason
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
