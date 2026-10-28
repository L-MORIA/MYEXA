"""Quality harness for the SearXNG fallback provider.

The Exa API is unreachable from this machine (Cloudflare answers 403 for this
IP range), so the search runs on a local SearXNG instance. This harness
measures what that fallback actually delivers, per language:

1. How many results the provider returns and how many survive the relevance
   filter and the language filter.
2. How pure the language of the results is — the whole point of the whole
   exercise is that the Russian tab must not fill up with English pages.
3. Which engines answered and how long the query took.
4. The ranking spread: a provider that returns ten equally-scored pages is
   not actually ranking anything.

Run: python diagnostics/searxng_quality.py
"""

import os
import statistics
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "backend"))
sys.path.insert(0, os.path.join(BASE, "..", "backend", "tests"))

from config import Config  # noqa: E402
from relevance_corpus import CORPUS  # noqa: E402
from services.embedding import EmbeddingService  # noqa: E402
from services.indexing import IndexingService  # noqa: E402
from services.language_detector import LanguageDetector  # noqa: E402
from services.searxng_service import SearxngService  # noqa: E402
# A second query per language, so the numbers do not depend on a single
# search term.
EXTRA_QUERIES = {
    "ru": "развитие нейросетей в России",
    "en": "neural network research breakthroughs",
    "de": "Entwicklung neuronaler Netze in Deutschland",
    "it": "sviluppo delle reti neurali in Italia",
}


def main():
    provider = SearxngService()
    embedding = EmbeddingService()
    detector = LanguageDetector()
    indexing = IndexingService()

    print("SearXNG base URL:", provider.base_url)
    print("configured:", provider.is_configured())
    print("relevance threshold:", Config.RELEVANCE_THRESHOLD)
    print()

    summary = {}

    for lang, data in CORPUS.items():
        query = data["query"]
        queries = [query, EXTRA_QUERIES.get(lang)]

        for q in queries:
            if not q:
                continue
            started = time.perf_counter()
            try:
                results = provider.search(q, num_results=10, language=lang)
            except Exception as e:  # noqa: BLE001
                print(f"[{lang}] {q!r} -> FAILED: {e}")
                continue
            elapsed = time.perf_counter() - started

            if not results:
                print(f"[{lang}] {q!r} -> no results in {elapsed:.1f}s")
                continue

            filtered = embedding.filter_results(q, results,
                                                threshold=Config.language_threshold(lang))
            detector.annotate(filtered, lang)
            kept = detector.filter_by_language(filtered)

            engines = {}
            for item in results:
                engines[item.get("engine", "?")] = engines.get(item.get("engine", "?"), 0) + 1

            matched = sum(1 for item in kept if not item.get("language_mismatch"))
            for item in kept:
                # calculate_index only returns the value — rank_results is the
                # one that stores it on the item.
                item["relevance_index"] = indexing.calculate_index(item)

            indices = [item.get("relevance_index", 0.0) for item in kept]
            spread = (max(indices) - min(indices)) if len(indices) > 1 else 0.0

            print(f"[{lang}] {q!r}")
            print(f"    fetched={len(results)}  after_filter={len(filtered)}  "
                  f"after_language_filter={len(kept)}  in {elapsed:.1f}s")
            print(f"    language purity: {matched}/{len(kept)} "
                  f"({matched / len(kept) if kept else 0:.0%})")
            print(f"    engines: {', '.join(f'{k}={v}' for k, v in sorted(engines.items()))}")
            if indices:
                print(f"    relevance_index: max={max(indices):.3f} "
                      f"min={min(indices):.3f} spread={spread:.3f} "
                      f"median={statistics.median(indices):.3f}")
            for item in kept[:3]:
                title = item.get("title", "")[:80]
                print(f"      - [{item.get('relevance_index', 0):.3f}] {title}")
            print()

            key = lang
            summary.setdefault(key, []).append({
                "query": q,
                "fetched": len(results),
                "after_filter": len(filtered),
                "after_language_filter": len(kept),
                "purity": matched / len(kept) if kept else 0.0,
                "seconds": elapsed,
                "engines": engines,
                "spread": spread,
            })

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for lang, rows in summary.items():
        fetched = sum(r["fetched"] for r in rows)
        kept = sum(r["after_language_filter"] for r in rows)
        purity = statistics.mean(r["purity"] for r in rows)
        seconds = statistics.mean(r["seconds"] for r in rows)
        spread = statistics.mean(r["spread"] for r in rows)
        print(f"  {lang}: fetched={fetched}  kept={kept}  "
              f"pass_rate={kept / fetched if fetched else 0:.0%}  "
              f"language_purity={purity:.0%}  avg_time={seconds:.1f}s  "
              f"avg_spread={spread:.3f}")


if __name__ == "__main__":
    main()
