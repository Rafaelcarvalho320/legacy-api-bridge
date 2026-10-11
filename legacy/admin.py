"""Read-only admin screens for browsing the legacy tables.

The reason to have these is investigation. When somebody asks why a customer
disappeared from a report, the fastest answer comes from looking at the rows
with the flags and dates already translated — which is exactly what the admin
gives you for free once the models exist.

Everything is read-only. The legacy application still owns these tables and
enforces rules that are not written down anywhere Django could discover, so an
editable admin would be a way to corrupt data with a single click.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from legacy.models import City, Client, Order, OrderItem


class ReadOnlyAdmin(admin.ModelAdmin[Any]):
    """No add, no change, no delete. Looking only."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(City)
class CityAdmin(ReadOnlyAdmin):
    list_display = ["code", "display_name", "state"]
    list_filter = ["state"]
    search_fields = ["name"]


@admin.register(Client)
class ClientAdmin(ReadOnlyAdmin):
    list_display = [
        "code",
        "display_name",
        "document_kind",
        "active",
        "registered_on",
        "city",
    ]
    search_fields = ["name", "document"]

    # Deliberately the manager that still shows removed rows: the admin is the
    # tool you reach for precisely when you need to see what the API hides.
    def get_queryset(self, request: HttpRequest) -> Any:
        return Client.all_objects.select_related("city")


class OrderItemInline(admin.TabularInline[OrderItem, Order]):
    model = OrderItem
    extra = 0
    can_delete = False
    # Spelled out twice on purpose: django-stubs gives `fields` and
    # `readonly_fields` different declared types, so one shared constant
    # cannot satisfy both without an annotation uglier than the repetition.
    fields = ["number", "display_description", "quantity", "unit_price"]
    readonly_fields = ["number", "display_description", "quantity", "unit_price"]

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ["code", "client", "issued_on", "total", "status"]
    search_fields = ["code", "notes"]
    inlines = [OrderItemInline]

    def get_queryset(self, request: HttpRequest) -> Any:
        return Order.all_objects.select_related("client")
