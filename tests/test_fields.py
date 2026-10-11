"""The translating fields, which are where the legacy format stops."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from legacy.fields import CentsDecimalField, LegacyDateField, SimNaoBooleanField


class TestSimNaoBoolean:
    field = SimNaoBooleanField()

    @pytest.mark.parametrize("raw", ["S", "s", "1", "T", "Y", "y"])
    def test_every_spelling_of_yes(self, raw: str) -> None:
        assert self.field.to_python(raw) is True

    @pytest.mark.parametrize("raw", ["N", "n", "0", "", "X"])
    def test_everything_else_is_no(self, raw: str) -> None:
        assert self.field.to_python(raw) is False

    def test_null_is_no_because_the_manual_says_so(self) -> None:
        """A guess the legacy system forces on us, written down once."""
        assert self.field.to_python(None) is False
        assert self.field.from_db_value(None, None, None) is False

    def test_surrounding_whitespace_is_ignored(self) -> None:
        assert self.field.to_python(" S ") is True

    def test_writes_go_back_as_a_flag(self) -> None:
        assert self.field.get_prep_value(True) == "S"
        assert self.field.get_prep_value(False) == "N"

    def test_a_single_character_passes_through_for_queries(self) -> None:
        """Without this, filtering on ['S', 's'] becomes ['S', 'S'].

        Every lowercase row would then be invisible to the query, which is how
        a soft-deleted-row filter silently hid a live customer.
        """
        assert self.field.get_prep_value("s") == "s"
        assert self.field.get_prep_value("N") == "N"


class TestLegacyDate:
    field = LegacyDateField()

    def test_an_ordinary_stored_date(self) -> None:
        assert self.field.from_db_value("20200115", None, None) == date(2020, 1, 15)

    def test_the_sentinel_means_unknown(self) -> None:
        assert self.field.from_db_value("00000000", None, None) is None

    @pytest.mark.parametrize("raw", [None, "", "  ", "notadate", "20201301"])
    def test_unreadable_values_become_none_not_an_error(self, raw: str | None) -> None:
        """One bad column must not hide the seven good fields beside it."""
        assert self.field.from_db_value(raw, None, None) is None

    def test_writes_go_back_in_the_stored_format(self) -> None:
        assert self.field.get_prep_value(date(2024, 3, 7)) == "20240307"

    def test_writing_nothing_stores_the_sentinel(self) -> None:
        assert self.field.get_prep_value(None) == "00000000"

    def test_it_reports_as_text_so_the_backend_keeps_its_hands_off(self) -> None:
        """Load-bearing: the backend's own date converter runs first.

        Reporting DateField let the backend try to read '20200115' as an ISO
        date, fail, and hand this field a None. Every date became null.
        """
        assert self.field.get_internal_type() == "CharField"


class TestCentsDecimal:
    field = CentsDecimalField()

    def test_cents_become_currency(self) -> None:
        assert self.field.from_db_value(125050, None, None) == Decimal("1250.50")

    def test_it_is_a_decimal_never_a_float(self) -> None:
        value = self.field.from_db_value(10, None, None)
        assert isinstance(value, Decimal)
        assert value == Decimal("0.10")

    def test_a_third_of_a_cent_cannot_appear(self) -> None:
        """The reason the legacy column stores integers in the first place."""
        total = self.field.from_db_value(10, None, None) + self.field.from_db_value(
            20, None, None
        )
        assert total == Decimal("0.30")

    def test_null_stays_null(self) -> None:
        assert self.field.from_db_value(None, None, None) is None

    def test_writes_go_back_as_cents(self) -> None:
        assert self.field.get_prep_value(Decimal("1250.50")) == 125050
        assert self.field.get_prep_value("89.90") == 8990

    def test_a_round_trip_keeps_the_amount(self) -> None:
        for cents in (1, 99, 100, 125050, 999999999):
            amount = self.field.from_db_value(cents, None, None)
            assert self.field.get_prep_value(amount) == cents
