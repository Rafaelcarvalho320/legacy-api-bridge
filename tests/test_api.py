"""The API, which is the only thing callers are meant to see."""

from __future__ import annotations

import pytest
from django.test import Client as HttpClient

pytestmark = pytest.mark.usefixtures("legacy_db")


def get(client: HttpClient, path: str) -> dict:
    response = client.get(path)
    assert response.status_code == 200, response.content
    return response.json()


class TestNoLegacyVocabularyEscapes:
    def test_the_payload_uses_words_not_column_names(self, client: HttpClient) -> None:
        row = get(client, "/api/v1/clients/1/")
        assert set(row) >= {"code", "name", "document", "active", "registered_on"}
        raw = str(row)
        for column in ("CD_CLI", "NM_CLI", "FL_ATIVO", "DT_CADAST", "NR_CPFCNPJ"):
            assert column not in raw

    def test_flags_are_json_booleans(self, client: HttpClient) -> None:
        assert get(client, "/api/v1/clients/1/")["active"] is True
        assert get(client, "/api/v1/clients/7/")["active"] is False

    def test_dates_are_iso(self, client: HttpClient) -> None:
        assert get(client, "/api/v1/clients/1/")["registered_on"] == "2020-01-15"

    def test_an_unknown_date_is_null_not_a_sentinel(self, client: HttpClient) -> None:
        assert get(client, "/api/v1/clients/6/")["registered_on"] is None

    def test_money_is_a_decimal_string_not_cents(self, client: HttpClient) -> None:
        assert get(client, "/api/v1/orders/1001/")["total"] == "1250.50"

    def test_the_status_letter_is_kept_alongside_the_word(
        self, client: HttpClient
    ) -> None:
        """So somebody debugging against the legacy screens can correlate."""
        row = get(client, "/api/v1/orders/1002/")
        assert row["status"] == "invoiced"
        assert row["status_code"] == "F"


class TestListings:
    def test_soft_deleted_rows_never_appear(self, client: HttpClient) -> None:
        codes = [row["code"] for row in get(client, "/api/v1/clients/")["results"]]
        assert 5 not in codes
        assert len(codes) == 7

    def test_a_deleted_row_is_a_404_not_a_500(self, client: HttpClient) -> None:
        assert client.get("/api/v1/clients/5/").status_code == 404

    def test_an_order_whose_client_was_deleted_still_lists(
        self, client: HttpClient
    ) -> None:
        """Order 1008 points at the removed client 5. The listing must hold."""
        row = next(
            r for r in get(client, "/api/v1/orders/")["results"] if r["code"] == 1008
        )
        assert row["client_code"] == 5
        assert row["client_name"] is None

    def test_an_orphan_city_reference_does_not_break_a_client(
        self, client: HttpClient
    ) -> None:
        assert get(client, "/api/v1/clients/8/")["city"] is None

    def test_names_are_rendered_readably_with_the_original_kept(
        self, client: HttpClient
    ) -> None:
        row = get(client, "/api/v1/clients/1/")
        assert row["name"] == "Maria Silva"
        assert row["legacy_name"] == "MARIA SILVA"


class TestFilters:
    def test_filtering_by_active_uses_domain_language(self, client: HttpClient) -> None:
        codes = {
            row["code"]
            for row in get(client, "/api/v1/clients/?active=true")["results"]
        }
        assert 4 in codes  # 's' lowercase
        assert 3 not in codes  # NULL flag

    def test_filtering_by_inactive(self, client: HttpClient) -> None:
        codes = {
            row["code"]
            for row in get(client, "/api/v1/clients/?active=false")["results"]
        }
        assert codes == {3, 7}

    def test_filtering_by_status_word_not_letter(self, client: HttpClient) -> None:
        rows = get(client, "/api/v1/orders/?status=invoiced")["results"]
        assert {row["code"] for row in rows} == {1002, 1008}

    def test_an_unmapped_status_word_returns_nothing_not_an_error(
        self, client: HttpClient
    ) -> None:
        assert client.get("/api/v1/orders/?status=unknown").status_code == 400

    def test_a_document_matches_however_it_was_punctuated(
        self, client: HttpClient
    ) -> None:
        """The table stores both spellings; one query has to find either."""
        punctuated = get(client, "/api/v1/clients/?document=123.456.789-00")
        bare = get(client, "/api/v1/clients/?document=12345678900")
        assert punctuated["count"] == bare["count"] == 1
        assert punctuated["results"][0]["code"] == 1

        other = get(client, "/api/v1/clients/?document=987.654.321-00")
        assert other["results"][0]["code"] == 2

    def test_filtering_by_state_joins_without_a_foreign_key(
        self, client: HttpClient
    ) -> None:
        rows = get(client, "/api/v1/clients/?state=PA")["results"]
        assert {row["code"] for row in rows} == {1, 2}

    def test_a_minimum_total_is_compared_in_cents(self, client: HttpClient) -> None:
        rows = get(client, "/api/v1/orders/?min_total=1000")["results"]
        assert {row["code"] for row in rows} == {1001, 1003, 1004}

    def test_issued_after_excludes_the_sentinel_date(self, client: HttpClient) -> None:
        rows = get(client, "/api/v1/orders/?issued_after=2024-03-01")["results"]
        assert {row["code"] for row in rows} == {1004, 1005, 1007, 1008}

    def test_registered_after_excludes_unknown_dates(self, client: HttpClient) -> None:
        """Client 6 has '00000000'; it is unknown, not ancient."""
        rows = get(client, "/api/v1/clients/?registered_after=2010-01-01")["results"]
        assert 6 not in {row["code"] for row in rows}


class TestOrderDetail:
    def test_the_detail_includes_the_lines(self, client: HttpClient) -> None:
        row = get(client, "/api/v1/orders/1001/")
        assert [item["number"] for item in row["items"]] == [1, 2, 3]
        assert row["items"][0]["description"] == "Parafuso Sextavado 10mm"
        assert row["items"][0]["line_total"] == "150.00"

    def test_both_totals_are_reported_when_they_disagree(
        self, client: HttpClient
    ) -> None:
        """Reconciling them silently would be the API telling a nice lie."""
        row = get(client, "/api/v1/orders/1001/")
        assert row["total"] == "1250.50"
        assert row["items_total"] == "350.00"

    def test_gaps_in_the_line_numbering_show_through(self, client: HttpClient) -> None:
        row = get(client, "/api/v1/orders/1003/")
        assert [item["number"] for item in row["items"]] == [1, 3]


class TestReadOnly:
    @pytest.mark.parametrize("path", ["/api/v1/clients/", "/api/v1/orders/"])
    def test_writing_is_refused(self, client: HttpClient, path: str) -> None:
        """The legacy application still owns these tables and their rules."""
        assert client.post(path, data={}).status_code == 405

    def test_updating_is_refused(self, client: HttpClient) -> None:
        assert client.patch("/api/v1/clients/1/", data={}).status_code == 405
