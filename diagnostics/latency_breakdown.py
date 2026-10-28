"""Latency breakdown of a multi-language search.

A 4-language query took 11-18 s end to end. This harness measures where the
time goes, so the optimisation targets the real bottleneck instead of a
guessed one.

Run: python diagnostics/latency_breakdown.py
"""

import os
import statistics
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "backend"))
sys.path.insert(0, os.path.join(BASE, "..", "backend", "tests"))

from api.translator import Translator  # noqa: E402
from config import Config  # noqa: E402
from services.embedding import EmbeddingService  # noqa: E402
from services.indexing import IndexingService  # noqa: E402
from services.language_detector import LanguageDetector  # noqa: E402
from services.searxng_service import SearxngService  # noqa: E402

QUERY = "искусственный интеллект в медицине"
LANGUAGES = ["ru", "en", "de", "it"]
NUM_RESULTS = 10


def timed(label, fn):
    started = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - started
    print(f"  {label:<38} {elapsed:6.2f} s")
    return result, elapsed


def main():
    translator = Translator()
    provider = SearxngService()
    embedding = EmbeddingService()
    detector = LanguageDetector()
    indexing = IndexingService()

    print(f"query: {QUERY!r}   languages: {LANGUAGES}")
    print()

    print("Stage timings")
    print("-" * 60)

    translations, t_translate = timed(
        "translate_to_multiple (sequential)",
        lambda: translator.translate_to_multiple(QUERY, LANGUAGES),
    )

    def fetch_all():
        import concurrent.futures

        queries = {lang: translations.get(lang) or QUERY for lang in LANGUAGES}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(LANGUAGES)) as pool:
            futures = {
                lang: pool.submit(provider.search, queries[lang], NUM_RESULTS, lang)
                for lang in LANGUAGES
            }
            return {lang: f.result() for lang, f in futures.items()}

    results, t_fetch = timed("provider fetch (4 languages, parallel)", fetch_all)

    def filter_all():
        out = {}
        for lang in LANGUAGES:
            items = results.get(lang) or []
            out[lang] = embedding.filter_results(
                translations.get(lang) or QUERY, list(items),
                threshold=Config.language_threshold(lang),
            )
        return out

    filtered, t_filter = timed("embedding filter (sequential per item)", filter_all)

    def detect_all():
        out = {}
        for lang in LANGUAGES:
            items = list(filtered.get(lang) or [])
            detector.annotate(items, lang)
            out[lang] = detector.filter_by_language(items)
        return out

    detected, t_detect = timed("language detection", detect_all)

    t_rank_start = time.perf_counter()
    for lang in LANGUAGES:
        indexing.rank_results(list(detected.get(lang) or []), [])
    t_rank = time.perf_counter() - t_rank_start
    print(f"  {'ranking':<38} {t_rank:6.2f} s")

    total = t_translate + t_fetch + t_filter + t_detect + t_rank
    print("-" * 60)
    print(f"  {'TOTAL':<38} {total:6.2f} s")
    print()
    print("Share of the total")
    print("-" * 60)
    for label, value in [
        ("translation", t_translate),
        ("provider fetch", t_fetch),
        ("embedding filter", t_filter),
        ("language detection", t_detect),
        ("ranking", t_rank),
    ]:
        print(f"  {label:<38} {value:6.2f} s  ({value / total:5.1%})")

    # How many single-text forward passes does the filter perform?
    items = sum(len(v) for v in results.values())
    queries = len(LANGUAGES)
    print()
    print(f"Embedding forward passes per search: {items} item texts + {queries} query texts")
    print(f"  (one model call per text today — they can be batched)")


if __name__ == "__main__":
    main()
