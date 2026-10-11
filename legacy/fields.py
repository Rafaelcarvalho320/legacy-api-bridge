"""Custom model fields that translate at the ORM boundary.

This is the whole idea of the project. The legacy database stores booleans as
``'S'``/``'N'``, dates as ``'YYYYMMDD'`` strings and money as integer cents.
Those representations could be translated in the serializer, or in the view, or
in whatever piece of code happens to need the value — which is how a legacy
quirk ends up copy-pasted into forty places and one of them gets it wrong.

Putting the translation in the field means the rest of the codebase never sees
it. ``cliente.ativo`` is a ``bool``, ``pedido.emitido_em`` is a ``date``, and
``item.valor_unitario`` is a ``Decimal``, no matter what the column holds.

Each field implements the three hooks Django asks for:

``from_db_value``
    what comes out of a query.
``to_python``
    what comes out of deserialization or of a form.
``get_prep_value``
    what goes back in, so writes stay in the legacy format.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

#: Values a legacy CHAR(1) flag uses for true. Lowercase happens, because
#: nothing in the old system ever stopped it.
TRUE_FLAGS = frozenset({"S", "s", "1", "T", "t", "Y", "y"})

#: The sentinel a VARCHAR(8) date column uses for "we do not know".
NULL_DATE = "00000000"


class SimNaoBooleanField(models.BooleanField[Any, bool]):
    """A ``CHAR(1)`` holding ``'S'`` or ``'N'``, exposed as a ``bool``.

    NULL is read as false, which is what the paper manual says it means. That
    is a guess the legacy system forces on us, and it is written down here
    rather than rediscovered by every caller.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # The column is nullable even when the concept is not, so the field
        # accepts NULL from the database while still handing out a real bool.
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def db_type(self, connection: Any) -> str:
        return "CHAR(1)"

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> bool:
        if value is None:
            return False
        return str(value).strip() in TRUE_FLAGS

    def to_python(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip() in TRUE_FLAGS

    def get_prep_value(self, value: Any) -> str:
        # A single character passes through untouched, so a query can target
        # the raw spellings the column actually contains. Without this escape
        # hatch, filtering on ['S', 's'] would be normalised to ['S', 'S'] and
        # every lowercase row would be silently invisible. Use the Q helpers
        # below rather than writing the letters at call sites.
        if isinstance(value, str) and len(value.strip()) == 1:
            return value.strip()
        return "S" if self.to_python(value) else "N"


class LegacyDateField(models.DateField[Any, date | None]):
    """A ``VARCHAR(8)`` holding ``'YYYYMMDD'``, exposed as a ``date``.

    The sentinel ``'00000000'`` and anything unparseable become ``None``. A row
    whose date column holds garbage is a data problem, not a reason for the API
    to return a 500 — and refusing to read the rest of the record would hide
    seven good fields because of one bad one.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def db_type(self, connection: Any) -> str:
        return "VARCHAR(8)"

    def get_internal_type(self) -> str:
        """Reported as text so no database backend tries to parse the column.

        This is load-bearing. Django picks its own value converters from the
        internal type and runs them *before* ``from_db_value``, so inheriting
        "DateField" means the backend sees ``'20200115'``, fails to read it as
        an ISO date and hands this field a ``None`` it can do nothing with.
        Every stored date silently became null.

        DRF is unaffected: it maps serializer fields by walking the class
        hierarchy, so a DateField subclass still serializes as a date.
        """
        return "CharField"

    def from_db_value(
        self, value: Any, expression: Any, connection: Any
    ) -> date | None:
        return self._parse(value)

    def to_python(self, value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return self._parse(value)

    @staticmethod
    def _parse(value: Any) -> date | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw or raw == NULL_DATE:
            return None
        try:
            return datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            return None

    def get_prep_value(self, value: Any) -> str:
        parsed = self.to_python(value)
        if parsed is None:
            return NULL_DATE
        return parsed.strftime("%Y%m%d")


class CentsDecimalField(models.DecimalField[Any, Decimal | None]):
    """An ``INTEGER`` column of cents, exposed as a ``Decimal`` of currency.

    Integer cents is the one legacy decision here that was right: binary floats
    cannot represent 0.10 exactly, so money in a float column drifts. The field
    keeps the storage and gives callers a Decimal, never a float.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 15)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def db_type(self, connection: Any) -> str:
        return "INTEGER"

    def from_db_value(
        self, value: Any, expression: Any, connection: Any
    ) -> Decimal | None:
        if value is None:
            return None
        return (Decimal(int(value)) / 100).quantize(Decimal("0.01"))

    def to_python(self, value: Any) -> Decimal | None:
        if value is None or isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            # Ambiguous on purpose to resolve: a bare int arriving through a
            # form or a serializer is currency, not cents. Cents only ever
            # come from the database, and that path is from_db_value.
            return Decimal(value).quantize(Decimal("0.01"))
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except ArithmeticError as exc:
            raise ValidationError(f"{value!r} is not a valid amount") from exc

    def get_prep_value(self, value: Any) -> int | None:
        parsed = self.to_python(value)
        if parsed is None:
            return None
        return int((parsed * 100).to_integral_value())


def flag_true(field: str) -> models.Q:
    """Rows whose legacy flag means true, in any spelling the column uses."""
    return models.Q(**{f"{field}__in": sorted(TRUE_FLAGS)})


def flag_false(field: str) -> models.Q:
    """Rows whose legacy flag means false, counting NULL as false.

    The NULL branch is not belt and braces. ``NOT IN ('S', 's', ...)`` against
    a NULL column evaluates to NULL, which SQL treats as not-matched, so a row
    with no flag at all would vanish from a query asking for false — and in
    this schema a NULL flag is exactly how "no" was recorded for years.
    """
    return models.Q(**{f"{field}__isnull": True}) | ~flag_true(field)
