from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("agenda/", views.agenda, name="agenda"),
    path("health/", views.health, name="health"),
    path("clientes/", views.customer_list, name="customer_list"),
    path("clientes/nuevo/", views.customer_create, name="customer_create"),
    path("clientes/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("clientes/<int:pk>/editar/", views.customer_edit, name="customer_edit"),
    path("clientes/<int:pk>/estado/", views.customer_toggle, name="customer_toggle"),
    path("productos/", views.product_list, name="product_list"),
    path("productos/nuevo/", views.product_create, name="product_create"),
    path("productos/<int:pk>/editar/", views.product_edit, name="product_edit"),
    path("productos/<int:pk>/estado/", views.product_toggle, name="product_toggle"),
    path("ventas/", views.sale_list, name="sale_list"),
    path("ventas/nueva/", views.sale_create, name="sale_create"),
    path("ventas/<int:pk>/", views.sale_detail, name="sale_detail"),
    path("ventas/<int:pk>/cancelar/", views.sale_cancel, name="sale_cancel"),
    path("cobranza/", views.collection_list, name="collection_list"),
    path(
        "cobranza/ventas/<int:pk>/pagar/",
        views.payment_create,
        name="payment_create",
    ),
    path(
        "cobranza/ventas/<int:pk>/no-pago/",
        views.collection_did_not_pay,
        name="collection_did_not_pay",
    ),
    path(
        "cobranza/ventas/<int:pk>/visita/",
        views.collection_attempt_create,
        name="collection_attempt_create",
    ),
    path(
        "pagos/<int:pk>/anular/",
        views.payment_void,
        name="payment_void",
    ),
]
