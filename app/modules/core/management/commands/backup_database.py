from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from modules.core.services.database_backup import DatabaseBackupError, create_deployment_backup


class Command(BaseCommand):
    help = "Crea y verifica un backup SQLite o PostgreSQL en el directorio externo."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--output", default="")
        parser.add_argument("--label", default="scheduled")
        parser.add_argument("--retention", type=int, default=14)

    def handle(self, *args, **options):
        try:
            backup = create_deployment_backup(
                output_directory=Path(options["output"]) if options["output"] else None,
                label=options["label"],
                retention=options["retention"],
            )
        except DatabaseBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Backup verificado: {backup}"))
