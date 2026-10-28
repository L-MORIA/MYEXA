"""Strategy sweep for the MYEXA relevance filter.

Picks the scoring strategy + threshold that satisfies the acceptance criteria
from diagnostics/PLAN_multilingual_search.md §5:

  * separation (relevant_mean - irrelevant_mean) >= 0.25 for ru/en/de/it
  * recall (relevant kept / relevant total) >= 0.95 for ru/en/de/it

Run: python diagnostics/strategy_sweep.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sentence_transformers import SentenceTransformer, util  # noqa: E402

from config import Config  # noqa: E402
from embedding_quality import CORPUS, pad  # noqa: E402

SNIPPET = 600
CHUNK = 500


def build_strategies():
    """Return {name: fn(item, query_emb, model) -> score}."""
    def emb(model, text):
        return model.encode(text, convert_to_tensor=True)

    def sim(model, q, t):
        return float(util.pytorch_cos_sim(q, model.encode(t, convert_to_tensor=True))[0][0])

    def s_title(model, q, it):
        return sim(model, q, it["title"])

    def s_title_snippet(model, q, it):
        return sim(model, q, f"{it['title']}. {it['highlights'][:SNIPPET]}")

    def s_title_full(model, q, it):
        return sim(model, q, pad(it["highlights"], 4000))

    def s_title_meanchunk(model, q, it):
        chunks = [it["highlights"][i:i + CHUNK] for i in range(0, len(it["highlights"]), CHUNK)]
        chunks = [c for c in chunks if len(c) >= 80]
        if not chunks:
            return sim(model, q, it["title"])
        vals = [sim(model, q, c) for c in chunks]
        return 0.5 * sim(model, q, it["title"]) + 0.5 * (sum(vals) / len(vals))

    def s_blend_70_30(model, q, it):
        return 0.7 * sim(model, q, it["title"]) + 0.3 * sim(model, q, it["highlights"][:SNIPPET])

    def s_blend_60_40(model, q, it):
        return 0.6 * sim(model, q, it["title"]) + 0.4 * sim(model, q, it["highlights"][:SNIPPET])

    def s_blend_50_50(model, q, it):
        return 0.5 * sim(model, q, it["title"]) + 0.5 * sim(model, q, it["highlights"][:SNIPPET])

    def s_title_maxchunk(model, q, it):
        best = sim(model, q, it["title"])
        for i in range(0, len(it["highlights"]), CHUNK):
            c = it["highlights"][i:i + CHUNK]
            if len(c) >= 80:
                best = max(best, sim(model, q, c))
        return best

    return {
        "title": s_title,
        "title+snippet600": s_title_snippet,
        "title+fullblob (CURRENT)": s_title_full,
        "title+meanchunk": s_title_meanchunk,
        "blend 0.7/0.3": s_blend_70_30,
        "blend 0.6/0.4": s_blend_60_40,
        "blend 0.5/0.5": s_blend_50_50,
        "title+maxchunk": s_title_maxchunk,
    }


def main():
    print("Loading model:", Config.EMBEDDING_MODEL)
    model = SentenceTransformer(Config.EMBEDDING_MODEL)
    model.eval()

    strategies = build_strategies()
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30]

    # per-language scores per strategy
    results = {}
    for lang, data in CORPUS.items():
        q = model.encode(data["query"], convert_to_tensor=True)
        for name, fn in strategies.items():
            scores = [(fn(model, q, it), it["relevant"]) for it in data["items"]]
            results[(lang, name)] = scores

    print()
    print("=" * 100)
    print("STRATEGY / THRESHOLD MATRIX — recall (R) and precision (P) per language")
    print("=" * 100)

    best = []
    for name in strategies:
        for thr in thresholds:
            row = []
            ok = True
            seps = []
            for lang in CORPUS:
                scores = results[(lang, name)]
                kept = [s for s in scores if s[0] >= thr]
                kept_rel = [s for s in kept if s[1]]
                all_rel = [s for s in scores if s[1]]
                rel = [s[0] for s in scores if s[1]]
                irr = [s[0] for s in scores if not s[1]]
                recall = len(kept_rel) / len(all_rel) if all_rel else 0.0
                prec = len(kept_rel) / len(kept) if kept else 0.0
                sep = (sum(rel) / len(rel)) - (sum(irr) / len(irr))
                seps.append(sep)
                if recall < 0.95 or sep < 0.25:
                    ok = False
                row.append(f"{lang}: R{recall:.2f} P{prec:.2f} S{sep:+.3f}")
            flag = "PASS" if ok else "    "
            print(f"{flag} {name:<24} thr={thr:.2f} | " + " | ".join(row))
            if ok:
                best.append((min(seps), name, thr))

    print()
    print("=" * 100)
    print("STRATEGIES MEETING ALL CRITERIA (separation>=0.25, recall>=0.95 in every language)")
    print("=" * 100)
    if not best:
        print("  NONE — criteria are not simultaneously satisfiable with these strategies.")
    else:
        for min_sep, name, thr in sorted(best, reverse=True):
            print(f"  {name:<24} thr={thr:.2f}  worst separation = {min_sep:+.3f}")


if __name__ == "__main__":
    main()
