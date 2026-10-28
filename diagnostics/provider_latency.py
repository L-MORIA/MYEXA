"""Latency distribution of the SearXNG provider.

The provider was the slowest stage of a search: usually ~1.5 s, but an
occasional query waited for a hanging engine until the timeout. This harness
samples the real distribution so the timeout can be chosen from measurements
instead of a guess.

Run: python diagnostics/provider_latency.py [n]
"""

import os
import statistics
import sys
import time
from urllib.parse import quote

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "backend"))

from config import Config  # noqa: E402
from services.searxng_service import SearxngService  # noqa: E402

QUERIES = {
    "ru": "искусственный интеллект в медицине",
    "en": "artificial intelligence in medicine",
    "de": "Künstliche Intelligenz in der Medizin",
    "it": "intelligenza artificiale in medicina",
}


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    provider = SearxngService()

    print(f"SearXNG: {provider.base_url}")
    print(f"rounds per language: {rounds}")
    print()

    all_times = []
    for lang, query in QUERIES.items():
        times = []
        counts = []
        for _ in range(rounds):
            # A fresh service per round: the response cache would otherwise
            # answer the repeated query instantly and hide the provider.
            provider = SearxngService()
            started = time.perf_counter()
            try:
                results = provider.search(query, num_results=10, language=lang)
            except Exception as e:  # noqa: BLE001
                print(f"[{lang}] FAILED: {e}")
                continue
            times.append(time.perf_counter() - started)
            counts.append(len(results))

        if not times:
            continue
        all_times.extend(times)
        print(f"[{lang}] n={len(times)}  median={statistics.median(times):.2f}s  "
              f"min={min(times):.2f}s  max={max(times):.2f}s  "
              f"mean={statistics.mean(times):.2f}s  results={min(counts)}-{max(counts)}")

    if all_times:
        print()
        print(f"OVERALL n={len(all_times)}  median={statistics.median(all_times):.2f}s  "
              f"p90={sorted(all_times)[int(len(all_times) * 0.9) - 1]:.2f}s  "
              f"max={max(all_times):.2f}s  mean={statistics.mean(all_times):.2f}s")


if __name__ == "__main__":
    main()
