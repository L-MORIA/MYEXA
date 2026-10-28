"""Measure the ranking asymmetry between languages in services/indexing.py.

Feeds the IndexingService two results of *equal topical quality* — one on an
English-leaning domain, one on a Russian news domain — and reports the
relevance_index each receives.

Run: python diagnostics/ranking_asymmetry.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from services.indexing import IndexingService  # noqa: E402


def main():
    svc = IndexingService()
    print("FilteringRules:", svc.rules.model_dump())
    print()

    # Equal embedding score -> the only differentiator is the domain.
    base = {"embedding_score": 0.6, "created_at": None, "highlights": "x"}

    cases = [
        ("EN result on github.com", "https://github.com/torvalds/linux"),
        ("EN result on wikipedia.org", "https://en.wikipedia.org/wiki/AI"),
        ("EN result on medium.com", "https://medium.com/some/article"),
        ("EN result on random https site", "https://someblog.example.org/post"),
        ("RU result on lenta.ru", "https://lenta.ru/news/2026/01/01/x"),
        ("RU result on ria.ru", "https://ria.ru/20260101/x"),
        ("RU result on habr.com", "https://habr.com/ru/articles/1"),
        ("RU result on kommersant.ru", "https://www.kommersant.ru/doc/1"),
        ("RU result on rbc.ru", "https://www.rbc.ru/news/1"),
        ("DE result on spiegel.de", "https://www.spiegel.de/artikel/x"),
        ("IT result on repubblica.it", "https://www.repubblica.it/1"),
    ]

    print(f"{'case':<34} {'domain_auth':>12} {'relevance_index':>16}")
    print("-" * 66)
    for label, url in cases:
        r = {**base, "url": url}
        auth = svc._calculate_domain_authority(url)
        idx = svc.calculate_index(r)
        print(f"{label:<34} {auth:>12} {idx:>16.4f}")

    print()
    print("NOTE: docstring claims 'relevance index (0-100)' and calculate_index")
    print("      ends with min(index, 100.0) — but max reachable value is")
    print(f"      {40/100 + 20/100 + 15/100 + 15/100 + 10/100:.2f}, not 100.")
    print()

    # Same URL, but one has created_at and the other does not -> freshness is
    # always 0.5 because Exa results never carry created_at.
    print("--- freshness is dead weight: Exa results carry no 'created_at' ---")
    r_no_date = {**base, "url": "https://lenta.ru/x"}
    print(f"  no created_at  -> freshness={svc._calculate_freshness(None)}, "
          f"index={svc.calculate_index(r_no_date):.4f}")
    r_date = {**base, "url": "https://lenta.ru/x", "created_at": "2026-10-25T00:00:00+00:00"}
    print(f"  with created_at-> freshness={svc._calculate_freshness(r_date['created_at'])}, "
          f"index={svc.calculate_index(r_date):.4f}")

    print()
    print("--- 'language_match' is hardcoded to 1.0 (no detection at all) ---")
    r_ru = {**base, "url": "https://lenta.ru/x"}
    r_en = {**base, "url": "https://github.com/x"}
    print(f"  ru-domain index={svc.calculate_index(r_ru):.4f}  "
          f"en-domain index={svc.calculate_index(r_en):.4f}  "
          f"(gap is purely domain authority, not language)")

    print()
    print("--- Exa's own relevance signal ('score') is parsed but never ranked ---")
    r = {**base, "url": "https://lenta.ru/x", "score": 0.99}
    print(f"  result has score=0.99, embedding_score=0.6 -> index={svc.calculate_index(r):.4f}")
    r2 = {**base, "url": "https://lenta.ru/x", "score": 0.01}
    print(f"  result has score=0.01, embedding_score=0.6 -> index={svc.calculate_index(r2):.4f}")
    print("  identical -> Exa's native relevance score is ignored by the ranking.")


if __name__ == "__main__":
    main()
