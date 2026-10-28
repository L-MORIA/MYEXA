"""Tests for SearchQuery input validation (blank query, languages, num_results)."""

import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.schemas import SearchQuery


class TestQueryValidation:
    def test_valid_query(self):
        q = SearchQuery(query="новости python", languages=["ru", "en"])
        assert q.query == "новости python"
        assert q.num_results == 10

    def test_blank_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchQuery(query="   ")

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            SearchQuery(query="")

    def test_query_is_stripped_not_mangled(self):
        q = SearchQuery(query="  padded query  ")
        assert q.query == "  padded query  "  # only blankness is checked, text kept


class TestLanguagesValidation:
    def test_all_supported_languages_accepted(self):
        q = SearchQuery(query="ok", languages=["ru", "en", "de", "it"])
        assert q.languages == ["ru", "en", "de", "it"]

    def test_unknown_language_rejected_by_the_endpoint(self):
        """The language list is validated by the application, not the schema.

        An unsupported code is a business rule, not a malformed body: the
        endpoint answers 400 and names the offending code. The schema itself
        accepts the list — see test_app_security.py.
        """
        q = SearchQuery(query="ok", languages=["ru", "fr"])
        assert q.languages == ["ru", "fr"]

    def test_empty_languages_list_allowed(self):
        """An empty list is fine — the app falls back to SOURCE_LANGUAGE."""
        q = SearchQuery(query="ok", languages=[])
        assert q.languages == []


class TestNumResultsValidation:
    @pytest.mark.parametrize("value", [0, -1, 101, 1000])
    def test_out_of_range_rejected(self, value):
        with pytest.raises(ValidationError):
            SearchQuery(query="ok", num_results=value)

    @pytest.mark.parametrize("value", [1, 10, 50, 100])
    def test_in_range_accepted(self, value):
        assert SearchQuery(query="ok", num_results=value).num_results == value
