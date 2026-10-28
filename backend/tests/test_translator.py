"""Tests for backend.api.translator.Translator."""

from unittest.mock import MagicMock, patch

import requests
from api.translator import LANG_MAP, Translator


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

    def test_yandex_network_error_falls_back_to_google(self):
        """When Yandex keeps failing, the Google fallback must be used."""
        t = Translator()

        google_resp = MagicMock()
        google_resp.status_code = 200
        google_resp.json.return_value = [[["hello world", "привет мир", None, None, 3]], None, "en"]

        def fake_get(url, **kw):
            if "yandex" in url:
                raise requests.ConnectionError("dns fail")
            return google_resp

        with patch("api.translator.requests.get", side_effect=fake_get):
            with patch("api.translator.time.sleep"):
                assert t.translate("привет мир", "en") == "hello world"

    def test_transient_yandex_error_is_recovered_without_google(self):
        """A single throttled request is retried and served by the same provider."""
        t = Translator()

        yandex_resp = MagicMock()
        yandex_resp.status_code = 200
        yandex_resp.json.return_value = {"text": ["hello world"]}

        calls = {"n": 0}

        def fake_get(url, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.ConnectionError("throttled")
            return yandex_resp

        with patch("api.translator.requests.get", side_effect=fake_get):
            with patch("api.translator.time.sleep"):
                assert t.translate("привет мир", "en") == "hello world"
        assert calls["n"] == 2

    def test_google_network_error_returns_original(self):
        """Both transports failing -> the original text is returned."""
        t = Translator()

        with patch("api.translator.requests.get", side_effect=requests.Timeout("timeout")):
            assert t.translate("привет мир", "en") == "привет мир"

    def test_malformed_json_returns_original(self):
        """A non-JSON body from a provider must not raise."""
        t = Translator()

        bad = MagicMock()
        bad.status_code = 200
        bad.json.side_effect = ValueError("not json")

        with patch("api.translator.requests.get", side_effect=[bad, bad]):
            assert t.translate("привет мир", "en") == "привет мир"

    def test_empty_yandex_text_falls_through_to_google(self):
        """Yandex returning an empty text list is not a valid translation."""
        t = Translator()

        yandex_resp = MagicMock()
        yandex_resp.status_code = 200
        yandex_resp.json.return_value = {"text": []}

        google_resp = MagicMock()
        google_resp.status_code = 200
        google_resp.json.return_value = [[["hello", "привет", None, None, 3]], None, "en"]

        with patch("api.translator.requests.get", side_effect=[yandex_resp, google_resp]):
            assert t.translate("привет мир", "en") == "hello"

    def test_google_response_with_empty_parts(self):
        t = Translator()

        yandex_resp = MagicMock()
        yandex_resp.status_code = 500

        google_resp = MagicMock()
        google_resp.status_code = 200
        google_resp.json.return_value = [[], None, "en"]

        with patch("api.translator.requests.get", side_effect=[yandex_resp, google_resp]):
            assert t.translate("привет мир", "en") == "привет мир"


class TestRetryPolicy:
    """Both providers are unofficial endpoints that occasionally throttle."""

    def test_transient_error_is_retried(self):
        t = Translator()

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"text": ["hello world"]}

        calls = {"n": 0}

        def flaky(url, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise requests.ConnectionError("throttled")
            return ok_resp

        with patch("api.translator.requests.get", side_effect=flaky):
            with patch("api.translator.time.sleep"):
                assert t.translate("привет мир", "en") == "hello world"
        assert calls["n"] == 3

    def test_gives_up_after_max_attempts(self):
        t = Translator()

        with patch("api.translator.requests.get",
                   side_effect=requests.ConnectionError("down")) as mock_get:
            with patch("api.translator.time.sleep"):
                result = t.translate("привет мир", "en")

        assert result == "привет мир"
        # Yandex retries, then Google retries.
        assert mock_get.call_count == 2 * 3

    def test_timeout_is_configured(self):
        t = Translator()
        captured = {}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"text": ["hello"]}

        def capture(url, **kw):
            captured["timeout"] = kw.get("timeout")
            return ok_resp

        with patch("api.translator.requests.get", side_effect=capture):
            t.translate("привет", "en")

        assert captured["timeout"] is not None
        assert captured["timeout"] >= 5


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
