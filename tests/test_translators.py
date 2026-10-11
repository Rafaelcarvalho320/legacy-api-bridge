"""The pure translation rules."""

from __future__ import annotations

import pytest

from legacy import translators


class TestOrderStatus:
    @pytest.mark.parametrize(
        ("code", "status"),
        [
            ("A", "open"),
            ("P", "awaiting_payment"),
            ("F", "invoiced"),
            ("C", "cancelled"),
        ],
    )
    def test_the_documented_codes(self, code: str, status: str) -> None:
        assert translators.order_status(code) == status

    def test_lowercase_is_accepted(self) -> None:
        assert translators.order_status("f") == "invoiced"

    @pytest.mark.parametrize("code", ["X", "Z", "", None])
    def test_an_undocumented_code_is_unknown_not_an_error(
        self, code: str | None
    ) -> None:
        """One row with a letter nobody wrote down must not break a listing."""
        assert translators.order_status(code) == "unknown"

    def test_the_mapping_reverses_for_writes(self) -> None:
        assert translators.order_status_code("invoiced") == "F"

    def test_a_status_with_no_legacy_code_reverses_to_none(self) -> None:
        assert translators.order_status_code("unknown") is None


class TestDocuments:
    def test_punctuation_is_irrelevant(self) -> None:
        """Both spellings are in the table, written by two different screens."""
        assert translators.document_digits("123.456.789-00") == "12345678900"
        assert translators.document_digits("12345678900") == "12345678900"

    def test_an_empty_document_is_none(self) -> None:
        assert translators.document_digits(None) is None
        assert translators.document_digits("---") is None

    def test_the_kind_comes_from_the_digits(self) -> None:
        """Harder evidence than TP_PESSOA, which disagrees in real rows."""
        assert translators.document_kind("123.456.789-00") == "cpf"
        assert translators.document_kind("12.345.678/0001-95") == "cnpj"

    @pytest.mark.parametrize("raw", ["123", "1234567890123456789", None])
    def test_an_unrecognised_length_is_unknown(self, raw: str | None) -> None:
        assert translators.document_kind(raw) == "unknown"

    def test_formatting_for_display(self) -> None:
        assert translators.format_document("12345678900") == "123.456.789-00"
        assert translators.format_document("12345678000195") == "12.345.678/0001-95"

    def test_an_odd_length_is_left_as_digits(self) -> None:
        assert translators.format_document("12345") == "12345"


class TestPersonType:
    def test_the_two_documented_values(self) -> None:
        assert translators.person_type("F") == "individual"
        assert translators.person_type("J") == "company"

    def test_anything_else_is_unknown(self) -> None:
        assert translators.person_type(None) == "unknown"
        assert translators.person_type("Q") == "unknown"


class TestTitleize:
    def test_shouting_becomes_readable(self) -> None:
        """Legacy text is uppercase because the terminals were."""
        assert translators.titleize("MARIA SILVA") == "Maria Silva"

    def test_portuguese_connectives_stay_lowercase(self) -> None:
        assert translators.titleize("MARIA DOS SANTOS") == "Maria dos Santos"
        assert translators.titleize("JOSE DA SILVA E SOUZA") == "Jose da Silva e Souza"

    def test_a_connective_at_the_start_is_still_capitalised(self) -> None:
        assert translators.titleize("DOS ANJOS") == "Dos Anjos"

    def test_repeated_spaces_collapse(self) -> None:
        assert translators.titleize("MARIA   SILVA") == "Maria Silva"

    def test_nothing_in_nothing_out(self) -> None:
        assert translators.titleize(None) is None
        assert translators.titleize("   ") is None
