"""Live diagnostic probe for MYEXA search quality.

Runs the real Translator / ExaService against the live APIs and reports
per-language counts and content, so we can see *where* the Russian path
degrades compared to English.

Usage:  python diagnostics/live_probe.py [query]
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from api.translator import Translator  # noqa: E402
from config import Config  # noqa: E402
from services.exa_service import ExaService  # noqa: E402

QUERY = sys.argv[1] if len(sys.argv) > 1 else "искусственный интеллект в медицине"
LANGS = ["ru", "en", "de", "it"]


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    print(f"EXA key present: {bool(Config.EXA_API_KEY)} (len={len(Config.EXA_API_KEY)})")
    print(f"Source language: {Config.SOURCE_LANGUAGE}")
    print(f"Query: {QUERY!r}")

    translator = Translator()
    exa = ExaService()

    section("1) TRANSLATION QUALITY (live)")
    translations = translator.translate_to_multiple(QUERY, LANGS)
    for lang in LANGS:
        value = translations.get(lang)
        same_as_source = value == QUERY
        print(f"  {lang}: {value!r}   [identical_to_source={same_as_source}]")

    section("2) EXA SEARCH: with vs without includeDomains")
    for lang in LANGS:
        domains = Config.language_domains(lang)
        search_query = translations.get(lang) or QUERY

        unrestricted = exa.search(search_query, 10, lang, include_domains=[])
        restricted = (
            exa.search(search_query, 10, lang, include_domains=domains)
            if domains
            else unrestricted
        )

        print(f"\n--- {lang} ---  query={search_query!r}")
        print(f"  includeDomains = {domains or '(none)'}")
        print(f"  unrestricted: {len(unrestricted)} results | restricted: {len(restricted)} results")
        for i, r in enumerate(unrestricted[:5]):
            print(f"    [{i}] {r['url'][:88]}")
            print(f"        title: {r['title'][:90]}")
        if domains:
            for i, r in enumerate(restricted[:5]):
                print(f"    RESTRICTED[{i}] {r['url'][:88]}")
                print(f"        title: {r['title'][:90]}")

    section("3) RAW EXA PAYLOAD INSPECTION (ru, no domain filter)")
    raw = exa._request("/search", {
        "query": translations.get("ru", QUERY),
        "numResults": 3,
        "type": "auto",
        "contents": {"highlights": {"maxCharacters": 4000}},
    })
    print(json.dumps(raw, ensure_ascii=False, indent=2)[:2500])


if __name__ == "__main__":
    main()
