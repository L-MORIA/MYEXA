"""Tests for backend.services.language_detector.LanguageDetector."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.language_detector import LanguageDetector  # noqa: E402


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector()


def _skip_if_unavailable(detector):
    if not detector.available:
        pytest.skip("lingua not installed")


class TestDetection:
    @pytest.mark.parametrize("text,expected", [
        ("Искусственный интеллект в медицине", "ru"),
        ("Регулирование медицинского ИИ в ЕС и США", "ru"),
        ("artificial intelligence in medicine", "en"),
        ("Deep Learning for Early Cancer Detection", "en"),
        ("Künstliche Intelligenz in der Medizin", "de"),
        ("intelligenza artificiale in medicina", "it"),
    ])
    def test_detects_supported_languages(self, detector, text, expected):
        _skip_if_unavailable(detector)
        assert detector.detect(text) == expected

    def test_empty_text_returns_none(self, detector):
        _skip_if_unavailable(detector)
        assert detector.detect("") is None
        assert detector.detect("   ") is None

    def test_never_returns_unsupported_language(self, detector):
        """The detector is restricted to ru/en/de/it."""
        _skip_if_unavailable(detector)
        # A clear French text must NOT be reported as French — the detector may
        # only answer with one of the four supported codes.
        for text in ["Bonjour, comment allez-vous aujourd'hui",
                     "El tiempo es muy bueno hoy en Madrid",
                     "Das ist ein sehr schöner Tag heute"]:
            detected = detector.detect(text)
            assert detected in (None, "ru", "en", "de", "it")

    def test_english_short_query_is_not_italian(self, detector):
        """Regression: low-accuracy mode called this Italian.

        The production detector uses the restricted high-accuracy builder.
        """
        _skip_if_unavailable(detector)
        assert detector.detect("artificial intelligence in medicine") == "en"


class TestMatch:
    def test_matching_language_scores_one(self, detector):
        _skip_if_unavailable(detector)
        assert detector.match("искусственный интеллект в медицине", "ru") == 1.0
        assert detector.match("artificial intelligence in medicine", "en") == 1.0

    def test_other_language_scores_low(self, detector):
        _skip_if_unavailable(detector)
        assert detector.match("artificial intelligence in medicine", "ru") == 0.3

    def test_undetectable_scores_mid(self, detector):
        _skip_if_unavailable(detector)
        assert detector.match("", "ru") == 0.5


class TestAnnotate:
    def test_annotates_every_result(self, detector):
        _skip_if_unavailable(detector)
        results = [
            {"title": "ИИ в медицине", "highlights": "текст на русском"},
            {"title": "AI in medicine", "highlights": "english text"},
        ]
        out = detector.annotate(results, "ru")
        assert out[0]["detected_language"] == "ru"
        assert out[0]["language_match"] == 1.0
        assert out[1]["detected_language"] == "en"
        assert out[1]["language_match"] == 0.3

    def test_missing_fields_do_not_raise(self, detector):
        _skip_if_unavailable(detector)
        out = detector.annotate([{"url": "https://x.com"}], "ru")
        assert "language_match" in out[0]


class TestFilterByLanguage:
    def test_keeps_matching_results_when_majority_matches(self, detector):
        """When at least half of the results are in the target language, only
        those are kept."""
        _skip_if_unavailable(detector)
        results = [
            {"title": "ИИ в медицине", "highlights": "русский текст"},
            {"title": "Нейросети в анализе ЭКГ", "highlights": "русский текст"},
            {"title": "AI in medicine", "highlights": "english text"},
        ]
        detector.annotate(results, "ru")
        kept = detector.filter_by_language(results)
        assert len(kept) == 2
        assert all(k["title"] != "AI in medicine" for k in kept)

    def test_keeps_everything_when_minority_matches(self, detector):
        """Below the half threshold the mismatching results are kept too, so a
        language tab never collapses to nothing."""
        _skip_if_unavailable(detector)
        results = [
            {"title": "ИИ в медицине", "highlights": "русский текст"},
            {"title": "AI in medicine", "highlights": "english text"},
            {"title": "KI in der Medizin", "highlights": "deutscher text"},
        ]
        detector.annotate(results, "ru")
        kept = detector.filter_by_language(results)
        assert len(kept) == 3

    def test_marks_mismatches(self, detector):
        _skip_if_unavailable(detector)
        results = [
            {"title": "ИИ в медицине", "highlights": "русский текст"},
            {"title": "AI in medicine", "highlights": "english text"},
        ]
        detector.annotate(results, "ru")
        detector.filter_by_language(results)
        assert results[0]["language_mismatch"] is False
        assert results[1]["language_mismatch"] is True

    def test_keeps_everything_when_nothing_matches(self, detector):
        """A language tab must not end up empty because the page is in another
        language — the mismatch stays visible instead."""
        _skip_if_unavailable(detector)
        results = [
            {"title": "AI in medicine", "highlights": "english text"},
            {"title": "Deep Learning for cancer", "highlights": "english text"},
        ]
        detector.annotate(results, "ru")
        kept = detector.filter_by_language(results)
        assert len(kept) == 2
        assert all(r["language_mismatch"] for r in kept)

    def test_empty_input(self, detector):
        assert detector.filter_by_language([]) == []
