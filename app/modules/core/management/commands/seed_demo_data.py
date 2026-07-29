from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    ZERO,
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
from modules.core.services.balances import get_due_sale_balance
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.money import as_money
from modules.core.services.payments import (
    register_initial_payment,
    register_payment,
    void_payment,
)

SCENARIO_LABELS = {
    0: "finalizada al día",
    1: "finalizada con atraso",
    2: "activa con pago parcial",
    3: "con cuotas atrasadas y sin pagos",
    4: "activa sin cuotas vencidas",
    5: "cancelada",
    6: "con pago anulado",
    7: "activa con pagos mixtos",
}


def _aware_moment(day: date, hour: int = 10) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(hour=hour)))


def _backdate(instance, day: date, *, hour: int = 10) -> None:
    instance.__class__.objects.filter(pk=instance.pk).update(
        created_at=_aware_moment(day, hour),
        updated_at=_aware_moment(day, hour),
    )


def _first_due_date(delivery_date: date, frequency: str) -> date:
    if frequency == Sale.Frequency.WEEKLY:
        return delivery_date + timedelta(days=7)
    if frequency == Sale.Frequency.BIWEEKLY:
        return delivery_date + timedelta(days=14)
    return delivery_date + timedelta(days=21)


class Command(BaseCommand):
    help = "Crea datos ficticios integrales para demostración y QA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-reset",
            action="store_true",
            help="Confirma que se eliminarán los datos comerciales de la base elegida.",
        )
        parser.add_argument(
            "--as-of",
            type=date.fromisoformat,
            default=None,
            help="Fecha de referencia en formato AAAA-MM-DD.",
        )

    def handle(self, *args, **options):
        if not options["confirm_reset"]:
            raise CommandError(
                "Por seguridad debés ejecutar el comando con --confirm-reset."
            )

        as_of: date = options["as_of"] or timezone.localdate()
        if as_of > timezone.localdate():
            raise CommandError("La fecha de referencia no puede estar en el futuro.")

        with transaction.atomic():
            self._clear_business_data()
            settings = self._configure_demo_business()
            products = self._create_products(as_of)
            customers = self._create_customers(as_of)
            sales = self._create_sales(
                as_of=as_of,
                settings=settings,
                products=products,
                customers=customers,
            )
            self._create_collection_attempts(as_of=as_of, sales=sales)
            generate_missing_late_fees(as_of=as_of, settings=settings)

        summary = self._summary()
        self.stdout.write(self.style.SUCCESS("Datos de demostración creados correctamente."))
        for label, value in summary.items():
            self.stdout.write(f"  {label}: {value}")

    def _clear_business_data(self) -> None:
        CollectionAttempt.objects.all().delete()
        PaymentAllocation.objects.all().delete()
        Payment.objects.all().delete()
        LateFee.objects.all().delete()
        Installment.objects.all().delete()
        Sale.objects.all().delete()
        Customer.objects.all().delete()
        Product.objects.all().delete()

    def _configure_demo_business(self) -> BusinessSettings:
        settings = BusinessSettings.get_solo()
        settings.business_name = "Casa Demo — Prueba Integral"
        settings.daily_late_fee = Decimal("2500.00")
        settings.collection_days = [0, 1, 2, 3, 4, 5]
        settings.payment_methods = [
            "Efectivo",
            "Transferencia",
            "Tarjeta",
            "Otro",
        ]
        settings.available_frequencies = [
            Sale.Frequency.WEEKLY,
            Sale.Frequency.BIWEEKLY,
            Sale.Frequency.MONTHLY,
        ]
        settings.max_installments = 60
        settings.charge_sundays = False
        settings.late_fee_after_partial_payment = True
        settings.allow_advance_payments = False
        settings.whatsapp_message = (
            "Hola {nombre}. Demo: tenés pendiente {monto}, "
            "con vencimiento {vencimiento}."
        )
        settings.save()
        return settings

    def _create_products(self, as_of: date) -> list[Product]:
        names = [
            ("Smart TV Demo 50", "Televisor ficticio con control inventado"),
            ("Heladera Demo", "Heladera de prueba con freezer"),
            ("Bicicleta Demo", "Rodado imaginario para recorridos"),
            ("Notebook Demo", "Equipo portátil de laboratorio"),
            ("Celular Demo", "Teléfono creado para QA"),
            ("Cocina Demo", "Cocina inventada de cuatro hornallas"),
            ("Lavarropas Demo", "Carga frontal ficticia"),
            ("Sofá Demo", "Tres cuerpos, color de prueba"),
            ("Mesa Demo", "Mesa extensible de datos"),
            ("Aire Demo", "Equipo frío/calor imaginario"),
            ("Colchón Demo", "Producto de demostración"),
            ("Moto Demo", "Vehículo inexistente para grandes importes"),
            ("Kit Escolar Demo", "Producto de importe bajo"),
            ("Producto Archivado Demo", "No disponible para ventas nuevas"),
        ]
        products = []
        for index, (name, description) in enumerate(names, start=1):
            product = Product.objects.create(
                name=name,
                description=description,
                is_active=index != len(names),
            )
            _backdate(product, as_of - timedelta(days=100 - index))
            products.append(product)
        return products

    def _create_customers(self, as_of: date) -> list[Customer]:
        neighborhoods = [
            "Barrio Norte Inventado",
            "Barrio Sur de Prueba",
            "Centro Ficticio",
            "Zona Oeste Demo",
            "Sin Barrio",
            "Barrio Largo para Probar Diseño",
        ]
        customers = []
        for index in range(1, 49):
            customer = Customer.objects.create(
                first_name=f"Cliente {index:02d}",
                last_name=f"Apellido Inventado {index:02d}",
                dni=None if index % 7 == 0 else f"{31000000 + index:08d}",
                phone="" if index % 9 == 0 else f"11 5555 {index:04d}",
                address=f"Domicilio Inventado {index} — Altura {100 + index}",
                neighborhood=neighborhoods[(index - 1) % len(neighborhoods)],
                address_reference=(
                    ""
                    if index % 4 == 0
                    else f"Referencia ficticia {index}: portón color demo"
                ),
                notes=(
                    "Sin observaciones"
                    if index % 5
                    else "Cliente de prueba con texto largo, símbolos $ % y ñ."
                ),
                is_active=index % 11 != 0,
            )
            # Spread the customer records from roughly three months ago to today.
            days_ago = round((48 - index) * 90 / 47)
            _backdate(customer, as_of - timedelta(days=days_ago))
            customers.append(customer)
        return customers

    def _create_sales(
        self,
        *,
        as_of: date,
        settings: BusinessSettings,
        products: list[Product],
        customers: list[Customer],
    ) -> list[Sale]:
        frequencies = [
            Sale.Frequency.WEEKLY,
            Sale.Frequency.BIWEEKLY,
            Sale.Frequency.MONTHLY,
        ]
        payment_methods = settings.payment_methods
        sales = []

        for index, customer in enumerate(customers, start=1):
            scenario = (index - 1) % len(SCENARIO_LABELS)
            frequency = frequencies[(index - 1) % len(frequencies)]
            age_by_scenario = [90, 88, 65, 52, 10, 45, 38, 78]
            age = max(3, age_by_scenario[scenario] - ((index - 1) // 8))
            delivery_date = as_of - timedelta(days=age)
            installment_count = 3 if scenario in {0, 1} else 6 + (index % 5)
            product = products[(index - 1) % (len(products) - 1)]

            product_price = Decimal(120000 + index * 27500).quantize(
                Decimal("0.01")
            )
            down_payment = (
                as_money(product_price * Decimal("0.20"))
                if index % 3 == 0
                else ZERO
            )
            base_total = as_money(product_price - down_payment)
            adjustment_mode = index % 3
            if adjustment_mode == 1:
                installment_total = as_money(base_total * Decimal("1.10"))
            elif adjustment_mode == 2:
                installment_total = as_money(base_total * Decimal("0.95"))
            else:
                installment_total = base_total

            sale = Sale(
                customer=customer,
                product=product,
                product_description=(
                    f"{product.name} — venta demo {index:02d} "
                    f"({SCENARIO_LABELS[scenario]})"
                ),
                delivery_date=delivery_date,
                cash_price=product_price,
                down_payment=down_payment,
                financed_amount=installment_total,
                frequency=frequency,
                installment_count=installment_count,
                daily_late_fee=(
                    Decimal("0.00")
                    if index % 10 == 0
                    else [Decimal("1500.00"), Decimal("2500.00"), Decimal("5000.00")][
                        index % 3
                    ]
                ),
                first_due_date=_first_due_date(delivery_date, frequency),
                status=Sale.Status.ACTIVE,
            )
            sale.full_clean()
            sale.save()
            _backdate(sale, delivery_date)
            installments = create_installments(sale)
            Installment.objects.filter(pk__in=[item.pk for item in installments]).update(
                created_at=_aware_moment(delivery_date),
                updated_at=_aware_moment(delivery_date),
            )

            if down_payment > ZERO:
                initial = register_initial_payment(
                    sale=sale,
                    payment_method=payment_methods[index % len(payment_methods)],
                    settings=settings,
                )
                _backdate(initial, delivery_date, hour=11)

            self._apply_scenario(
                sale=sale,
                scenario=scenario,
                as_of=as_of,
                settings=settings,
                payment_method=payment_methods[(index + 1) % len(payment_methods)],
            )
            sales.append(sale)

        return sales

    def _register_due_payment(
        self,
        *,
        sale: Sale,
        payment_date: date,
        settings: BusinessSettings,
        payment_method: str,
        fraction: Decimal = Decimal("1.00"),
        notes: str,
    ) -> Payment | None:
        generate_missing_late_fees(
            as_of=payment_date,
            settings=settings,
            sale=sale,
        )
        due = get_due_sale_balance(sale, as_of=payment_date).total_due
        if due <= ZERO:
            return None
        amount = as_money(due * fraction)
        if amount <= ZERO:
            return None
        payment = register_payment(
            sale=sale,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            notes=notes,
            operation_key=uuid.uuid4(),
            settings=settings,
        ).payment
        _backdate(payment, payment_date, hour=16)
        return payment

    def _apply_scenario(
        self,
        *,
        sale: Sale,
        scenario: int,
        as_of: date,
        settings: BusinessSettings,
        payment_method: str,
    ) -> None:
        installments = list(sale.installments.order_by("due_date", "number"))

        if scenario == 0:
            for installment in installments:
                if installment.due_date <= as_of:
                    self._register_due_payment(
                        sale=sale,
                        payment_date=installment.due_date,
                        settings=settings,
                        payment_method=payment_method,
                        notes="Pago completo y puntual de demostración.",
                    )
            return

        if scenario == 1:
            for installment in installments:
                payment_date = min(installment.due_date + timedelta(days=2), as_of)
                if installment.due_date <= as_of:
                    self._register_due_payment(
                        sale=sale,
                        payment_date=payment_date,
                        settings=settings,
                        payment_method=payment_method,
                        notes="Pago completo con dos días de atraso.",
                    )
            return

        if scenario == 2:
            due_installment = next(
                (item for item in installments if item.due_date <= as_of),
                None,
            )
            if due_installment:
                self._register_due_payment(
                    sale=sale,
                    payment_date=min(due_installment.due_date + timedelta(days=1), as_of),
                    settings=settings,
                    payment_method=payment_method,
                    fraction=Decimal("0.40"),
                    notes="Pago parcial: queda saldo para próximas visitas.",
                )
            return

        if scenario == 3:
            return

        if scenario == 4:
            return

        if scenario == 5:
            sale.status = Sale.Status.CANCELLED
            sale.cancelled_on = min(sale.delivery_date + timedelta(days=5), as_of)
            sale.cancellation_reason = (
                "Cancelación ficticia para comprobar estados e historial."
            )
            sale.full_clean()
            sale.save(
                update_fields=[
                    "status",
                    "cancelled_on",
                    "cancellation_reason",
                    "updated_at",
                ]
            )
            return

        if scenario == 6:
            due_installment = next(
                (item for item in installments if item.due_date <= as_of),
                None,
            )
            if due_installment:
                payment = self._register_due_payment(
                    sale=sale,
                    payment_date=due_installment.due_date,
                    settings=settings,
                    payment_method=payment_method,
                    fraction=Decimal("0.50"),
                    notes="Pago que luego será anulado para QA.",
                )
                if payment:
                    void_payment(
                        payment=payment,
                        reason="Anulación ficticia: pago duplicado en la demo.",
                    )
                    Payment.objects.filter(pk=payment.pk).update(
                        voided_at=_aware_moment(payment.payment_date, 18)
                    )
            return

        for paid_count, installment in enumerate(installments):
            if installment.due_date > as_of or paid_count >= 2:
                break
            self._register_due_payment(
                sale=sale,
                payment_date=installment.due_date,
                settings=settings,
                payment_method=payment_method,
                notes="Pago puntual dentro de un historial mixto.",
            )

        sale.refresh_from_db()
        if sale.status == Sale.Status.ACTIVE:
            next_due = next(
                (
                    item
                    for item in sale.installments.order_by("due_date", "number")
                    if item.due_date <= as_of
                ),
                None,
            )
            if next_due:
                self._register_due_payment(
                    sale=sale,
                    payment_date=min(next_due.due_date + timedelta(days=3), as_of),
                    settings=settings,
                    payment_method=payment_method,
                    fraction=Decimal("0.25"),
                    notes="Segundo tramo parcial del historial mixto.",
                )

    def _create_collection_attempts(
        self,
        *,
        as_of: date,
        sales: list[Sale],
    ) -> None:
        results = list(CollectionAttempt.Result.values)
        active_sales = [sale for sale in sales if sale.status == Sale.Status.ACTIVE]
        for index, sale in enumerate(active_sales):
            attempt_date = max(
                sale.delivery_date,
                as_of - timedelta(days=index % 12),
            )
            attempt = CollectionAttempt.objects.create(
                customer=sale.customer,
                sale=sale,
                attempt_date=attempt_date,
                result=results[index % len(results)],
                notes=(
                    f"Visita ficticia {index + 1}: "
                    f"resultado {CollectionAttempt.Result(results[index % len(results)]).label}."
                ),
            )
            _backdate(attempt, attempt_date, hour=17)

    def _summary(self) -> dict[str, int]:
        return {
            "clientes": Customer.objects.count(),
            "clientes archivados": Customer.objects.filter(is_active=False).count(),
            "productos": Product.objects.count(),
            "ventas": Sale.objects.count(),
            "ventas activas": Sale.objects.filter(status=Sale.Status.ACTIVE).count(),
            "ventas finalizadas": Sale.objects.filter(
                status=Sale.Status.COMPLETED
            ).count(),
            "ventas canceladas": Sale.objects.filter(
                status=Sale.Status.CANCELLED
            ).count(),
            "cuotas": Installment.objects.count(),
            "recargos": LateFee.objects.count(),
            "pagos": Payment.objects.count(),
            "pagos anulados": Payment.objects.filter(
                status=Payment.Status.VOIDED
            ).count(),
            "visitas": CollectionAttempt.objects.count(),
        }
