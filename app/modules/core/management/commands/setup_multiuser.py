from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from modules.core.middleware import ADMIN_GROUP, COLLECTOR_GROUP


class Command(BaseCommand):
    help = "Crea roles y usuarios iniciales sin exponer contraseñas en la línea de comandos."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-password-env", default="GESTION_ADMIN_PASSWORD")
        parser.add_argument("--collector-username", default="")
        parser.add_argument("--collector-password-env", default="GESTION_COLLECTOR_PASSWORD")

    def handle(self, *args, **options):
        admin_password = os.environ.get(options["admin_password_env"], "")
        if len(admin_password) < 12:
            raise CommandError(
                f"{options['admin_password_env']} debe contener al menos 12 caracteres."
            )

        admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
        collector_group, _ = Group.objects.get_or_create(name=COLLECTOR_GROUP)
        user_model = get_user_model()

        admin, _ = user_model.objects.get_or_create(username=options["admin_username"])
        admin.is_active = True
        admin.set_password(admin_password)
        admin.save(update_fields=["is_active", "password"])
        admin.groups.set([admin_group])
        self.stdout.write(self.style.SUCCESS(f"Administrador listo: {admin.username}"))

        collector_username = options["collector_username"].strip()
        if collector_username:
            collector_password = os.environ.get(options["collector_password_env"], "")
            if len(collector_password) < 12:
                raise CommandError(
                    f"{options['collector_password_env']} debe contener al menos 12 caracteres."
                )
            collector, _ = user_model.objects.get_or_create(username=collector_username)
            collector.is_active = True
            collector.set_password(collector_password)
            collector.save(update_fields=["is_active", "password"])
            collector.groups.set([collector_group])
            self.stdout.write(self.style.SUCCESS(f"Cobrador listo: {collector.username}"))
