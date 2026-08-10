from datetime import date
from decimal import Decimal

from modules.core.models import Customer, Product, Sale


def make_customer(**overrides) -> Customer:
    values = {
        "first_name": "Juan",
        "last_name": "Pérez",
        "phone": "1122334455",
        "address": "San Martín 255",
    }
    values.update(overrides)
    return Customer.objects.create(**values)


def make_product(**overrides) -> Product:
    values = {
        "name": "Smart TV 50",
        "description": "Televisor",
    }
    values.update(overrides)
    return Product.objects.create(**values)


def make_sale(**overrides) -> Sale:
    customer = overrides.pop("customer", None) or make_customer()
    operation_type = overrides.get("operation_type", Sale.OperationType.PRODUCT)
    product = overrides.pop("product", None)
    if product is None and operation_type == Sale.OperationType.PRODUCT:
        product = make_product()
    values = {
        "customer": customer,
        "product": product,
        "operation_type": operation_type,
        "product_description": product.name if product else "Préstamo de dinero",
        "delivery_date": date(2026, 8, 15),
        "cash_price": Decimal("400000.00"),
        "financed_amount": Decimal("480000.00"),
        "frequency": Sale.Frequency.WEEKLY,
        "installment_count": 12,
        "daily_late_fee": Decimal("5000.00"),
        "first_due_date": date(2026, 8, 18),
    }
    values.update(overrides)
    return Sale.objects.create(**values)
