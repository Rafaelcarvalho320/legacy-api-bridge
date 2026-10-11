"""The shape the outside world sees.

Field names are words, booleans are booleans, dates are ISO dates and money is
a decimal string. Nothing in here exposes a legacy column name, a 'S'/'N' flag
or a status letter — except ``status_code``, which is kept deliberately so that
somebody debugging against the legacy screens can still correlate a record.
"""

from __future__ import annotations

from rest_framework import serializers

from legacy import translators
from legacy.models import City, Client, Order, OrderItem


class CitySerializer(serializers.ModelSerializer[City]):
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = City
        fields = ["code", "name", "state"]


class ClientSerializer(serializers.ModelSerializer[Client]):
    name = serializers.CharField(source="display_name", read_only=True)
    legacy_name = serializers.CharField(source="name", read_only=True)
    document = serializers.CharField(source="document_digits", read_only=True)
    document_formatted = serializers.SerializerMethodField()
    document_kind = serializers.CharField(read_only=True)
    person_type = serializers.CharField(read_only=True)
    phone = serializers.SerializerMethodField()
    city = CitySerializer(read_only=True)

    class Meta:
        model = Client
        fields = [
            "code",
            "name",
            "legacy_name",
            "document",
            "document_formatted",
            "document_kind",
            "person_type",
            "email",
            "phone",
            "active",
            "registered_on",
            "city",
        ]

    def get_document_formatted(self, obj: Client) -> str | None:
        return translators.format_document(obj.document)

    def get_phone(self, obj: Client) -> str | None:
        return translators.phone_digits(obj.phone)


class OrderItemSerializer(serializers.ModelSerializer[OrderItem]):
    description = serializers.CharField(source="display_description", read_only=True)
    line_total = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ["number", "description", "quantity", "unit_price", "line_total"]


class OrderSerializer(serializers.ModelSerializer[Order]):
    status = serializers.CharField(read_only=True)
    client_code = serializers.IntegerField(source="client_id", read_only=True)
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "code",
            "client_code",
            "client_name",
            "issued_on",
            "total",
            "status",
            "status_code",
            "notes",
        ]

    def get_client_name(self, obj: Order) -> str | None:
        """The client's name, or None when there is no client to name.

        Two separate reasons it can be None, both present in the data:

        * the row does not exist at all, because nothing ever constrained
          CD_CLI, and a 500 on a listing is not an acceptable answer to that;
        * the row exists but is soft-deleted. ``select_related`` joins the
          table directly and so bypasses the manager that hides those, which
          would leak a removed customer's name through the orders endpoint.
          The code is still reported, so the reference stays traceable.
        """
        try:
            client = obj.client
        except Client.DoesNotExist:
            return None
        if client is None or client.excluido:
            return None
        return client.display_name


class OrderDetailSerializer(OrderSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    items_total = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = [*OrderSerializer.Meta.fields, "items", "items_total"]

    def get_items_total(self, obj: Order) -> str:
        """The sum of the lines, which does not always equal VL_TOTAL.

        Exposed next to ``total`` on purpose rather than reconciled silently.
        A twenty-year-old table has orders whose header total and line totals
        disagree, and hiding that would be the API telling a comfortable lie.
        """
        total = sum(item.line_total for item in obj.items.all())
        return f"{total:.2f}"
