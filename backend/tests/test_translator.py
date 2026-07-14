"""Tests for backend.api.translator.Translator."""

from unittest.mock import patch, MagicMock

from api.translator import Translator, LANG_MAP


class TestLangMap:
    """LANG_MAP must include all four supported languages."""

    def test_ru_present(self):
        assert "ru" in LANG_MAP

    def test_en_present(self):
        assert "en" in LANG_MAP

    def test_de_present(self):
        assert "de" in LANG_MAP

    def test_it_present(self):
        assert "it" in LANG_MAP

    def test_all_map_to_themselves(self):
        for code in ("ru", "en", "de", "it"):
            assert LANG_MAP[code] == code


class TestTranslatorInit:
    def test_cache_starts_empty(self):
        t = Translator()
        assert t._cache == {}

    def test_source_defaults_to_ru(self):
        t = Translator()
        assert t._source == "ru"


class TestTranslate:
    def test_same_language_returns_original(self):
        """When target == source, no API call should be made."""
        t = Translator()
        result = t.translate("привет мир", "ru")
        assert result == "привет мир"

    def test_unknown_language_returns_original(self):
        """A code not in LANG_MAP must return text as-is."""
        t = Translator()
        assert t.translate("hello", "fr") == "hello"

    def test_empty_text(self):
        t = Translator()
        assert t.translate("", "en") == ""

    def test_yandex_called_first(self):
        """Yandex endpoint should be tried before Google."""
        t = Translator()
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"text": ["hello world"]}

        with patch("api.translator.requests") as mock_requests:
            mock_requests.get.return_value = fake_resp
            result = t.translate("привет мир", "en")
            assert result == "hello world"
            # The first call should be to Yandex URL
            first_call = mock_requests.get.call_args_list[0]
            assert "yandex" in first_call[0][0]

    def test_google_fallback_when_yandex_fails(self):
        """If Yandex returns non-200, Google gtx should be the fallback."""
        t = Translator()

        yandex_resp = MagicMock()
        yandex_resp.status_code = 500

        google_resp = MagicMock()
        google_resp.status_code = 200
        # Real Google gtx response shape: [[["translated", "original", null, ...]], ...]
        google_resp.json.return_value = [[["hello world", "привет мир", None, None, 3]], None, "en"]

        call_count = {"n": 0}

        def fake_get(url, **kw):
            call_count["n"] += 1
            if "yandex" in url:
                return yandex_resp
            return google_resp

        with patch("api.translator.requests.get", side_effect=fake_get):
            result = t.translate("привет мир", "en")
            assert result == "hello world"
            assert call_count["n"] == 2  # yandex + google

    def test_fallback_to_original_on_all_failures(self):
        """When both services fail, the original text must be returned."""
        t = Translator()

        fail_resp = MagicMock()
        fail_resp.status_code = 500

        with patch("api.translator.requests") as mock_requests:
            mock_requests.get.side_effect = [fail_resp, fail_resp]
            result = t.translate("привет мир", "en")
            assert result == "привет мир"

    def test_caching(self):
        """Second call with the same args must hit cache, not the network."""
        t = Translator()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"text": ["hello world"]}

        with patch("api.translator.requests.get") as mock_get:
            mock_get.return_value = fake_resp
            t.translate("привет мир", "en")
            t.translate("привет мир", "en")
            # Only one actual network call
            assert mock_get.call_count == 1


class TestTranslateToMultiple:
    def test_includes_original(self):
        t = Translator()
        result = t.translate_to_multiple("тест", ["en"])
        assert result["original"] == "тест"

    def test_includes_source_language(self):
        t = Translator()
        result = t.translate_to_multiple("тест", ["ru", "en"])
        assert result["ru"] == "тест"

    def test_skips_source_language_translation(self):
        """Source language should not be sent to the API."""
        t = Translator()
        with patch.object(t, "translate", wraps=t.translate) as spy:
            t.translate_to_multiple("тест", ["ru", "en"])
            # translate() was called for "en" but NOT for "ru"
            spy.assert_any_call("тест", "en")
