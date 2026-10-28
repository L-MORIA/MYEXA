"""Offline quality harness for MYEXA multilingual search.

Exa's API host is unreachable from this machine (Cloudflare 403 on both IPv4
and IPv6), so this harness measures the *pipeline* stages that we can measure
locally, using the real multilingual embedding model.

It answers two questions:

1. How does the relevance filter behave when the text it embeds is a long
   Exa `highlights` blob (current code) instead of a compact title+snippet
   (proposed fix)?
2. Does the filter's threshold drop *relevant* results in non-English
   languages more often than in English?

Run: python diagnostics/embedding_quality.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "tests"))

import torch  # noqa: E402
from sentence_transformers import SentenceTransformer, util  # noqa: E402

from config import Config  # noqa: E402
from relevance_corpus import CORPUS  # noqa: E402

# The labelled corpus lives in backend/tests/relevance_corpus.py so that the
# tests and the diagnostics measure exactly the same data.


def pad(text, target_len):
    """Grow a snippet with plausible filler to mimic a long Exa highlights blob."""
    filler = (
        " Дополнительный контекст статьи: эксперты отмечают, что вопрос требует "
        "междисциплинарного подхода и учёта региональной специфики. "
        " Weitere Hinweise: Fachleute betonen die Notwendigkeit, "
        "den Kontext sorgfältig zu prüfen. "
        " Ulteriori precisazioni: gli esperti ricordano l'importanza "
        "di una valutazione attenta e documentata. "
    )
    out = text
    while len(out) < target_len:
        out += filler
    return out


def main():
    print("Loading model:", Config.EMBEDDING_MODEL)
    model = SentenceTransformer(Config.EMBEDDING_MODEL)
    model.eval()

    threshold = Config.RELEVANCE_THRESHOLD
    print(f"Config.RELEVANCE_THRESHOLD = {threshold}\n")

    strategies = {
        "CURRENT: full highlights blob (~4000 chars)": lambda it: pad(it["highlights"], 4000),
        "PROPOSED: title + first 600 chars": lambda it: it["title"] + ". " + it["highlights"][:600],
        "PROPOSED: title only": lambda it: it["title"],
        "PROPOSED: title + chunk max-pool (500 chars)": None,  # handled specially
    }

    def chunk_pool_score(it, q_emb):
        """max(sim(query, title), max over 500-char chunks of the blob)."""
        best = float(util.pytorch_cos_sim(
            q_emb, model.encode(it["title"], convert_to_tensor=True))[0][0])
        blob = it["highlights"]
        for start in range(0, len(blob), 500):
            chunk = blob[start:start + 500]
            if len(chunk) < 80:
                continue
            sim = float(util.pytorch_cos_sim(
                q_emb, model.encode(chunk, convert_to_tensor=True))[0][0])
            best = max(best, sim)
        return best

    for lang, data in CORPUS.items():
        query = data["query"]
        items = data["items"]
        q_emb = model.encode(query, convert_to_tensor=True)

        print("=" * 78)
        print(f"LANGUAGE {lang}   query={query!r}")
        print("=" * 78)

        for sname, fn in strategies.items():
            scores = []
            for it in items:
                if fn is None:
                    sim = chunk_pool_score(it, q_emb)
                else:
                    text = fn(it)
                    t_emb = model.encode(text, convert_to_tensor=True)
                    sim = float(util.pytorch_cos_sim(q_emb, t_emb)[0][0])
                scores.append((sim, it["relevant"]))

            kept = [s for s in scores if s[0] >= threshold]
            kept_rel = [s for s in kept if s[1]]
            all_rel = [s for s in scores if s[1]]
            recall = len(kept_rel) / len(all_rel) if all_rel else 0.0
            precision = len(kept_rel) / len(kept) if kept else 0.0

            rel_scores = [s for s, r in scores if r]
            irr_scores = [s for s, r in scores if not r]
            sep = (sum(rel_scores) / len(rel_scores)) - (sum(irr_scores) / len(irr_scores))
            print(f"\n  {sname}")
            print(f"    kept {len(kept)}/{len(scores)} (threshold {threshold})")
            print(f"    recall(relevant kept) = {recall:.2f}   precision = {precision:.2f}")
            print(f"    separation(rel_mean - irr_mean) = {sep:+.3f}")
            if rel_scores:
                print(f"    relevant scores: min={min(rel_scores):.3f} "
                      f"max={max(rel_scores):.3f} mean={sum(rel_scores)/len(rel_scores):.3f}")
            if irr_scores:
                print(f"    irrelevant scores: min={min(irr_scores):.3f} "
                      f"max={max(irr_scores):.3f} mean={sum(irr_scores)/len(irr_scores):.3f}")
            dropped_rel = [f"{s:.3f}" for s, r in scores if r and s < threshold]
            if dropped_rel:
                print(f"    *** DROPPED RELEVANT: {', '.join(dropped_rel)}")
        print()


if __name__ == "__main__":
    main()
