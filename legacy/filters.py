"""Filters expressed in domain terms, not legacy ones.

A caller filters by ``status=invoiced``, never by ``ST_PEDIDO=F``. Translating
here is what keeps the legacy vocabulary from leaking into every client of the
API — and what lets the codes change without the API changing.
"""

from __future__ import annotations

from decimal import Decimal

import django_filters as filters
from django.db.models import QuerySet

from legacy import translators
from legacy.fields import flag_false, flag_true
from legacy.models import Client, Order


class ClientFilter(filters.FilterSet):
    active = filters.BooleanFilter(method="filter_active")
    state = filters.CharFilter(field_name="city__state", lookup_expr="iexact")
    city = filters.NumberFilter(field_name="city_id")
    document = filters.CharFilter(method="filter_document")
    registered_after = filters.DateFilter(method="filter_registered_after")

    class Meta:
        model = Client
        fields = ["active", "state", "city"]

    def filter_active(
        self, queryset: QuerySet[Client], name: str, value: bool
    ) -> QuerySet[Client]:
        # Through the helpers, which know every spelling the column uses and
        # which count a NULL flag as false.
        return queryset.filter(flag_true("active") if value else flag_false("active"))

    def filter_document(
        self, queryset: QuerySet[Client], name: str, value: str
    ) -> QuerySet[Client]:
        """Match a document however either side chose to punctuate it.

        The column holds both '123.456.789-00' and '12345678900', so a LIKE on
        the raw value finds one and misses the other. Comparing digit strings
        in Python costs a scan and is the only answer that is actually right;
        a generated column would be the fix, and it needs a DBA.
        """
        wanted = translators.document_digits(value)
        if not wanted:
            return queryset.none()
        # values_list rather than only(): the queryset already carries a
        # select_related, and deferring a field that is being traversed is a
        # FieldError. This also drops the model instantiation entirely.
        matching = [
            pk
            for pk, document in queryset.values_list("pk", "document")
            if translators.document_digits(document) == wanted
        ]
        return queryset.filter(pk__in=matching)

    def filter_registered_after(
        self, queryset: QuerySet[Client], name: str, value: object
    ) -> QuerySet[Client]:
        """Compare against the stored 'YYYYMMDD' string.

        That format sorts lexicographically in the same order it sorts
        chronologically, which is the one accidental kindness in this schema.
        The sentinel '00000000' sorts before everything, so unset dates are
        excluded from an "after" filter rather than counted as ancient.
        """
        stamp = value.strftime("%Y%m%d")  # type: ignore[attr-defined]
        return queryset.filter(registered_on__gte=stamp).exclude(
            registered_on="00000000"
        )


class OrderFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        method="filter_status",
        choices=[(label, label) for label in translators.ORDER_STATUS.values()],
    )
    client = filters.NumberFilter(field_name="client_id")
    min_total = filters.NumberFilter(method="filter_min_total")
    issued_after = filters.DateFilter(method="filter_issued_after")

    class Meta:
        model = Order
        fields = ["status", "client"]

    def filter_status(
        self, queryset: QuerySet[Order], name: str, value: str
    ) -> QuerySet[Order]:
        code = translators.order_status_code(value)
        if code is None:
            return queryset.none()
        return queryset.filter(status_code__iexact=code)

    def filter_min_total(
        self, queryset: QuerySet[Order], name: str, value: object
    ) -> QuerySet[Order]:
        """Compared as currency, because the field converts to cents itself.

        Converting here as well multiplied the threshold by a hundred twice
        and the filter quietly matched nothing. Hand the field a domain value
        and let the one place that knows about cents do the arithmetic.
        """
        return queryset.filter(total__gte=Decimal(str(value)))

    def filter_issued_after(
        self, queryset: QuerySet[Order], name: str, value: object
    ) -> QuerySet[Order]:
        stamp = value.strftime("%Y%m%d")  # type: ignore[attr-defined]
        return queryset.filter(issued_on__gte=stamp).exclude(issued_on="00000000")
