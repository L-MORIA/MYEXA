"""Tests for backend.config.Config — language registry and settings."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config  # noqa: E402


class TestLanguageRegistry:
    def test_all_four_languages_registered(self):
        assert set(Config.LANGUAGES) == {"ru", "en", "de", "it"}

    def test_supported_languages_matches_registry(self):
        assert set(Config.SUPPORTED_LANGUAGES) == set(Config.LANGUAGES)

    def test_every_language_has_a_label(self):
        for code in Config.LANGUAGES:
            assert Config.language_label(code)
            assert Config.language_label(code) != code

    def test_default_languages_subset_of_registry(self):
        assert set(Config.DEFAULT_LANGUAGES) <= set(Config.LANGUAGES)

    def test_language_domains_returns_list(self):
        for code in Config.LANGUAGES:
            assert isinstance(Config.language_domains(code), list)

    def test_language_domains_returns_a_copy(self):
        """Mutating the returned list must not corrupt the registry."""
        domains = Config.language_domains("ru")
        domains.append("evil.example")
        assert "evil.example" not in Config.language_domains("ru")

    def test_unknown_language_has_no_domains(self):
        assert Config.language_domains("fr") == []

    def test_unknown_language_label_falls_back_to_code(self):
        assert Config.language_label("fr") == "fr"

    def test_ru_has_no_default_domain_filter(self):
        """Regression: the Russian corpus must not be pinned to a hard allowlist.

        `includeDomains` is a hard constraint in Exa — five domains meant the
        Russian search could only ever see those five sites.
        """
        assert Config.language_domains("ru") == []

    def test_no_language_has_default_domain_filter(self):
        for code in Config.LANGUAGES:
            assert Config.language_domains(code) == [], f"{code} must not hard-filter domains"

    def test_every_language_has_country_code(self):
        for code in Config.LANGUAGES:
            country = Config.language_country(code)
            assert country, f"{code} has no country code"
            assert len(country) == 2 and country.isupper()

    def test_country_codes_are_distinct(self):
        countries = [Config.language_country(c) for c in Config.LANGUAGES]
        assert len(set(countries)) == len(countries)

    def test_unknown_language_has_no_country(self):
        assert Config.language_country("fr") is None

    def test_is_supported(self):
        assert Config.is_supported("ru") is True
        assert Config.is_supported("fr") is False


class TestRelevanceSettings:
    def test_threshold_is_a_float(self):
        assert isinstance(Config.RELEVANCE_THRESHOLD, float)

    def test_threshold_not_higher_than_one(self):
        """Cosine similarity lives in [-1, 1]; a threshold above 1 drops everything."""
        assert Config.RELEVANCE_THRESHOLD <= 1.0

    def test_embedding_model_is_multilingual(self):
        assert "multilingual" in Config.EMBEDDING_MODEL.lower()


class TestPortParsing:
    def test_invalid_port_falls_back_to_3005(self, monkeypatch, capsys):
        """config._parse_port must degrade to 3005 on a non-numeric PORT."""
        import config as config_mod

        monkeypatch.setenv("PORT", "not-a-number")
        assert config_mod._parse_port() == 3005

    def test_valid_port_is_used(self, monkeypatch):
        import config as config_mod

        monkeypatch.setenv("PORT", "8123")
        assert config_mod._parse_port() == 8123

    def test_missing_port_uses_default(self, monkeypatch):
        import config as config_mod

        monkeypatch.delenv("PORT", raising=False)
        assert config_mod._parse_port() == 3005

    def test_empty_port_falls_back(self, monkeypatch):
        import config as config_mod

        monkeypatch.setenv("PORT", "")
        assert config_mod._parse_port() == 3005


class TestDatabasePathResolution:
    def test_relative_path_is_resolved_against_project_root(self, monkeypatch):
        import config as config_mod

        monkeypatch.setenv("DATABASE_PATH", "./database/myexa.db")
        resolved = config_mod._get_db_path()
        assert resolved.endswith("database\\myexa.db") or resolved.endswith("database/myexa.db")
        assert os.path.isabs(resolved)

    def test_absolute_path_is_kept(self, monkeypatch):
        import config as config_mod

        monkeypatch.setenv("DATABASE_PATH", "C:/tmp/x.db")
        assert config_mod._get_db_path() == os.path.normpath("C:/tmp/x.db")
