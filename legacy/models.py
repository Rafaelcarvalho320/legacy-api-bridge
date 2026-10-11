"""Django models mapped onto the inherited tables.

Every model here is ``managed = False``. Django did not create these tables and
must never try to: ``makemigrations`` ignores them, and the test suite builds
them from ``legacy/sql/legacy_schema.sql`` instead, which is the same file a
DBA would recognise.

Three habits make the rest of the codebase readable:

* ``db_column`` on every field, so attribute names are words and column names
  stay whatever they have always been.
* Custom fields from :mod:`legacy.fields`, so ``'S'``/``'N'`` and
  ``'YYYYMMDD'`` never leave this module.
* A default manager that hides soft-deleted rows, because the legacy system
  never deletes anything and forgetting that filter once is how a removed
  customer reappears in a report.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from legacy import translators
from legacy.fields import (
    CentsDecimalField,
    LegacyDateField,
    SimNaoBooleanField,
    flag_false,
)


class ClientManager(models.Manager["Client"]):
    """Hides soft-deleted clients.

    Attached as the *default* manager on purpose. Making the safe behaviour the
    one you get without thinking is the only version that survives a hurried
    change; ``all_objects`` is there for the rare report that wants the removed
    rows too.

    Written out per model rather than as one generic manager: the shared part
    is a single expression, and a concrete manager is what types cleanly and
    what the next reader can follow without chasing a type variable.
    """

    def get_queryset(self) -> models.QuerySet[Client]:
        return super().get_queryset().filter(flag_false("excluido"))


class OrderManager(models.Manager["Order"]):
    """Hides soft-deleted orders. See :class:`ClientManager`."""

    def get_queryset(self) -> models.QuerySet[Order]:
        return super().get_queryset().filter(flag_false("excluido"))


class City(models.Model):
    code = models.IntegerField(db_column="CD_CIDADE", primary_key=True)
    name = models.CharField(db_column="NM_CIDADE", max_length=60)
    state = models.CharField(db_column="SG_UF", max_length=2)

    class Meta:
        managed = False
        db_table = "TB_CID"
        ordering = ["name"]
        verbose_name_plural = "cities"

    def __str__(self) -> str:
        return f"{self.display_name}/{self.state}"

    @property
    def display_name(self) -> str | None:
        return translators.titleize(self.name)


class Client(models.Model):
    code = models.IntegerField(db_column="CD_CLI", primary_key=True)
    name = models.CharField(db_column="NM_CLI", max_length=60)
    document = models.CharField(
        db_column="NR_CPFCNPJ", max_length=18, null=True, blank=True
    )
    registered_on = LegacyDateField(db_column="DT_CADAST")
    active = SimNaoBooleanField(db_column="FL_ATIVO")
    excluido = SimNaoBooleanField(db_column="FL_EXCLUI")
    person_type_code = models.CharField(
        db_column="TP_PESSOA", max_length=1, null=True, blank=True
    )
    email = models.CharField(db_column="NM_EMAIL", max_length=80, null=True, blank=True)
    phone = models.CharField(db_column="NR_FONE", max_length=20, null=True, blank=True)
    # No foreign key constraint exists in the database, and the data contains
    # orphans. db_constraint=False declares the relationship for the ORM
    # without asking the database for something it cannot deliver.
    city = models.ForeignKey(
        City,
        db_column="CD_CIDADE",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="clients",
    )

    objects = ClientManager()
    all_objects = models.Manager()

    class Meta:
        managed = False
        db_table = "TB_CLI"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} {self.display_name}"

    @property
    def display_name(self) -> str | None:
        return translators.titleize(self.name)

    @property
    def document_digits(self) -> str | None:
        return translators.document_digits(self.document)

    @property
    def document_kind(self) -> str:
        return translators.document_kind(self.document)

    @property
    def person_type(self) -> str:
        return translators.person_type(self.person_type_code)


class Order(models.Model):
    code = models.IntegerField(db_column="CD_PEDIDO", primary_key=True)
    client = models.ForeignKey(
        Client,
        db_column="CD_CLI",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="orders",
    )
    issued_on = LegacyDateField(db_column="DT_EMISSAO")
    total = CentsDecimalField(db_column="VL_TOTAL")
    status_code = models.CharField(
        db_column="ST_PEDIDO", max_length=1, null=True, blank=True
    )
    excluido = SimNaoBooleanField(db_column="FL_EXCLUI")
    notes = models.CharField(
        db_column="OBS_PEDIDO", max_length=255, null=True, blank=True
    )

    objects = OrderManager()
    all_objects = models.Manager()

    class Meta:
        managed = False
        db_table = "TB_PED"
        ordering = ["-code"]

    def __str__(self) -> str:
        return f"order {self.code}"

    @property
    def status(self) -> str:
        return translators.order_status(self.status_code)


class OrderItem(models.Model):
    # Django 5.2 can express the composite key this table actually has, so the
    # model stops pretending one of the columns is unique on its own.
    # Field names, not column names: the composite key is declared in Django's
    # vocabulary and the db_column on each field is what reaches the database.
    pk = models.CompositePrimaryKey("order", "number")
    order = models.ForeignKey(
        Order,
        db_column="CD_PEDIDO",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="items",
    )
    number = models.IntegerField(db_column="NR_ITEM")
    description = models.CharField(db_column="DS_PRODUTO", max_length=80)
    quantity = models.IntegerField(db_column="QT_ITEM")
    unit_price = CentsDecimalField(db_column="VL_UNIT", null=False)

    class Meta:
        managed = False
        db_table = "TB_PEDITE"
        ordering = ["order", "number"]

    def __str__(self) -> str:
        return f"order {self.order_id} line {self.number}"

    @property
    def line_total(self) -> Decimal:
        """Quantity times unit price.

        VL_UNIT is NOT NULL in the legacy schema, so the None branch should be
        unreachable. It is written out rather than asserted away because an
        assertion that fires in production turns one odd row into a 500, and
        this project's whole posture is that a bad row degrades instead.
        """
        if self.unit_price is None:
            return Decimal("0.00")
        return self.unit_price * self.quantity

    @property
    def display_description(self) -> str | None:
        return translators.titleize(self.description)
