"""Read-only API over the legacy tables.

Read-only is a decision, not a limitation. The legacy application is still
running and still writing to these tables; it owns invariants that are not
written down anywhere a second writer could discover. Exposing reads first is
the useful half of a strangler fig, and it cannot corrupt anything.
"""

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import viewsets

from legacy.filters import ClientFilter, OrderFilter
from legacy.models import City, Client, Order
from legacy.serializers import (
    CitySerializer,
    ClientSerializer,
    OrderDetailSerializer,
    OrderSerializer,
)


class ClientViewSet(viewsets.ReadOnlyModelViewSet[Client]):
    serializer_class = ClientSerializer
    filterset_class = ClientFilter
    search_fields = ["name", "document", "email"]
    ordering_fields = ["code", "name", "registered_on"]

    def get_queryset(self) -> QuerySet[Client]:
        # select_related on a db_constraint=False relation works exactly like
        # any other: the constraint is what the database lacks, not the join.
        return Client.objects.select_related("city")


class OrderViewSet(viewsets.ReadOnlyModelViewSet[Order]):
    serializer_class = OrderSerializer
    filterset_class = OrderFilter
    search_fields = ["notes", "client__name"]
    ordering_fields = ["code", "issued_on", "total"]

    def get_queryset(self) -> QuerySet[Order]:
        queryset = Order.objects.select_related("client")
        if self.action == "retrieve":
            return queryset.prefetch_related("items")
        return queryset

    def get_serializer_class(self) -> type[OrderSerializer]:
        if self.action == "retrieve":
            return OrderDetailSerializer
        return OrderSerializer


class CityViewSet(viewsets.ReadOnlyModelViewSet[City]):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    filterset_fields = ["state"]
    search_fields = ["name"]
    ordering_fields = ["name", "state"]
