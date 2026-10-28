"""Compare lingua detector configurations on the labelled corpus.

The unrestricted detector mislabels short English titles as French, so the
detector must be restricted to the languages MYEXA actually supports.

Run: python diagnostics/detector_probe.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "tests"))

from lingua import Language, LanguageDetectorBuilder  # noqa: E402

from relevance_corpus import CORPUS  # noqa: E402

SUPPORTED = {
    Language.RUSSIAN: "ru",
    Language.ENGLISH: "en",
    Language.GERMAN: "de",
    Language.ITALIAN: "it",
}

VARIANTS = {
    "all languages, high accuracy": LanguageDetectorBuilder.from_all_languages(),
    "all languages, low accuracy": LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode(),
    "restricted to ru/en/de/it, high": LanguageDetectorBuilder.from_languages(*SUPPORTED.keys()),
    "restricted to ru/en/de/it, low": LanguageDetectorBuilder.from_languages(*SUPPORTED.keys()).with_low_accuracy_mode(),
}


def main():
    for name, builder in VARIANTS.items():
        detector = builder.build()
        print("=" * 78)
        print(name)
        print("=" * 78)
        total = correct = 0
        for lang, data in CORPUS.items():
            hits = []
            for item in data["items"]:
                text = f"{item['title']}. {item['highlights'][:400]}"
                detected = detector.detect_language_of(text)
                code = SUPPORTED.get(detected, str(detected).split(".")[-1].lower() if detected else "none")
                ok = code == lang
                total += 1
                correct += ok
                hits.append(("OK " if ok else "BAD") + f" {code:<10} {item['title'][:44]}")
            for h in hits:
                print("   " + h)
        print(f"  --> accuracy on corpus: {correct}/{total} = {correct/total:.0%}")
        print()


if __name__ == "__main__":
    main()
