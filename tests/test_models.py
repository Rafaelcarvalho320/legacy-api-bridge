"""The models, read against the real legacy tables."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from legacy.fields import flag_false, flag_true
from legacy.models import City, Client, Order, OrderItem

pytestmark = pytest.mark.usefixtures("legacy_db")


class TestSoftDelete:
    def test_deleted_rows_are_hidden_by_the_default_manager(self) -> None:
        assert Client.all_objects.count() == 8
        assert Client.objects.count() == 7
        assert not Client.objects.filter(code=5).exists()
        assert Client.all_objects.filter(code=5).exists()

    def test_a_lowercase_flag_does_not_hide_a_live_row(self) -> None:
        """Client 4 has FL_EXCLUI='n'. Comparing to 'N' exactly lost it."""
        assert Client.objects.filter(code=4).exists()

    def test_orders_are_filtered_the_same_way(self) -> None:
        assert Order.all_objects.count() == 8
        assert Order.objects.count() == 7
        assert not Order.objects.filter(code=1006).exists()

    def test_the_escape_hatch_exists_for_reports_that_need_it(self) -> None:
        assert Client.all_objects.get(code=5).name == "CLIENTE REMOVIDO"


class TestFlagQueries:
    def test_active_matches_every_spelling_of_yes(self) -> None:
        codes = set(
            Client.objects.filter(flag_true("active")).values_list("code", flat=True)
        )
        # 4 is 's' lowercase and must be in; 3 is NULL and must not.
        assert 4 in codes
        assert 3 not in codes

    def test_inactive_counts_a_null_flag_as_no(self) -> None:
        """NOT IN against NULL is NULL, so the null branch is load-bearing."""
        codes = set(
            Client.objects.filter(flag_false("active")).values_list("code", flat=True)
        )
        assert codes == {3, 7}

    def test_the_two_sets_partition_the_visible_rows(self) -> None:
        yes = Client.objects.filter(flag_true("active")).count()
        no = Client.objects.filter(flag_false("active")).count()
        assert yes + no == Client.objects.count()


class TestTranslatedReads:
    def test_a_stored_date_arrives_as_a_date(self) -> None:
        assert Client.objects.get(code=1).registered_on == date(2020, 1, 15)

    def test_the_sentinel_date_arrives_as_none(self) -> None:
        assert Client.objects.get(code=6).registered_on is None

    def test_money_arrives_as_an_exact_decimal(self) -> None:
        assert Order.objects.get(code=1001).total == Decimal("1250.50")
        assert Order.objects.get(code=1004).total == Decimal("2300.51")

    def test_a_flag_arrives_as_a_bool(self) -> None:
        assert Client.objects.get(code=1).active is True
        assert Client.objects.get(code=7).active is False

    def test_a_null_flag_arrives_as_false(self) -> None:
        assert Client.objects.get(code=3).active is False

    def test_status_letters_are_translated(self) -> None:
        assert Order.objects.get(code=1002).status == "invoiced"

    def test_an_undocumented_status_does_not_break_the_row(self) -> None:
        order = Order.objects.get(code=1007)
        assert order.status == "unknown"
        assert order.status_code == "X"


class TestRelationsWithoutConstraints:
    def test_a_join_works_even_though_the_database_has_no_foreign_key(
        self,
    ) -> None:
        client = Client.objects.select_related("city").get(code=1)
        assert client.city is not None
        assert client.city.state == "PA"

    def test_an_orphan_row_is_readable(self) -> None:
        """Client 8 points at city 999, which does not exist. No constraint
        ever stopped it, so the API has to cope rather than crash."""
        client = Client.objects.get(code=8)
        assert client.city_id == 999
        with pytest.raises(City.DoesNotExist):
            _ = client.city

    def test_select_related_on_an_orphan_leaves_it_null(self) -> None:
        client = Client.objects.select_related("city").get(code=8)
        assert client.city is None


class TestCompositeKey:
    def test_a_line_is_identified_by_order_and_number(self) -> None:
        item = OrderItem.objects.get(order_id=1001, number=2)
        assert item.description == "PORCA 10MM"

    def test_the_same_line_number_exists_on_different_orders(self) -> None:
        assert OrderItem.objects.filter(number=1).count() > 1

    def test_gaps_in_the_numbering_are_preserved(self) -> None:
        """Line 2 of order 1003 was deleted years ago. 1 and 3 remain."""
        numbers = list(
            OrderItem.objects.filter(order_id=1003)
            .order_by("number")
            .values_list("number", flat=True)
        )
        assert numbers == [1, 3]


class TestDerivedValues:
    def test_a_line_total_is_quantity_times_price(self) -> None:
        item = OrderItem.objects.get(order_id=1001, number=1)
        assert item.unit_price == Decimal("1.50")
        assert item.line_total == Decimal("150.00")

    def test_the_header_total_and_the_lines_can_disagree(self) -> None:
        """A twenty-year-old table has orders that do not add up, and the
        bridge reports both numbers instead of inventing agreement."""
        order = Order.objects.prefetch_related("items").get(code=1001)
        lines = sum(item.line_total for item in order.items.all())
        assert order.total == Decimal("1250.50")
        assert lines == Decimal("350.00")

    def test_names_are_readable(self) -> None:
        assert Client.objects.get(code=3).display_name == "Empresa Abc Ltda"


class TestDjangoDoesNotOwnTheSchema:
    """managed=False is the central promise, so it gets a test of its own."""

    def test_every_legacy_model_is_recorded_as_unmanaged(self) -> None:
        """Asserted against the committed migration state, not a live migrate.

        An unmanaged model still gets a migration; Django records the state and
        emits no DDL for it. Checking the recorded state is what catches a model
        losing its Meta before a deploy offers to create TB_CLI for real on a
        production database.
        """
        from django.db.migrations.loader import MigrationLoader

        state = MigrationLoader(None, ignore_no_migrations=True).project_state()
        legacy_models = [key for key in state.models if key[0] == "legacy"]
        assert len(legacy_models) == 4

        for key in legacy_models:
            options = state.models[key].options
            assert options.get("managed") is False, f"{key[1]} is managed"
            assert options.get("db_table", "").startswith("TB_")

    def test_no_legacy_table_exists_until_the_sql_is_run(self, db: None) -> None:
        """A fresh test database has the Django tables and none of the TB_*."""
        from django.db import connection

        from legacy import schema

        schema.drop_schema()
        present = {
            name.upper()
            for name in connection.introspection.table_names()
            if name.upper().startswith("TB_")
        }
        assert present == set()
