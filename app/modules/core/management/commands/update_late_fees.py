from django.core.management.base import BaseCommand

from modules.core.services.late_fees import generate_missing_late_fees


class Command(BaseCommand):
    help = "Genera los recargos diarios faltantes hasta la fecha local actual."

    def handle(self, *args, **options):
        result = generate_missing_late_fees()
        if options["verbosity"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recargos nuevos: {result.created}. "
                    f"Cuotas evaluadas: {result.evaluated_installments}."
                )
            )
