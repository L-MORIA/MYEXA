"""Quality regression tests for the relevance filter.

These are the tests that would have caught the original defect: the filter
compared the query against the full Exa `highlights` blob, which Exa builds by
quoting the query back, so the filter could not tell relevant results from
irrelevant ones — and it failed worst in Russian, the language users
complained about.

They use the REAL multilingual model, so they are skipped when the model
cannot be loaded (no network / not downloaded yet).

Acceptance thresholds come from diagnostics/PLAN_multilingual_search.md §5:
  * separation (relevant_mean - irrelevant_mean) >= 0.25 for every language
  * recall (relevant kept / relevant total) >= 0.95 for every language
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from relevance_corpus import CORPUS  # noqa: E402

SEPARATION_MIN = 0.25
RECALL_MIN = 0.95


@pytest.fixture(scope="module")
def embedding_service():
    """Real EmbeddingService, or skip when the model is unavailable."""
    from services.embedding import EmbeddingService

    try:
        svc = EmbeddingService()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"embedding model unavailable: {exc}")

    if not svc._available:
        pytest.skip("embedding model unavailable (download failed or offline)")
    return svc


def _scores(svc, query, items):
    query_embedding = svc._get_embedding(query)
    return [(svc.score_item(query_embedding, item), item["relevant"]) for item in items]


class TestRelevanceQualityPerLanguage:
    @pytest.mark.parametrize("lang", sorted(CORPUS))
    def test_relevant_outranks_irrelevant(self, embedding_service, lang):
        """Relevant results must score clearly above irrelevant ones."""
        data = CORPUS[lang]
        scores = _scores(embedding_service, data["query"], data["items"])

        relevant = [s for s, rel in scores if rel]
        irrelevant = [s for s, rel in scores if not rel]
        assert relevant and irrelevant, f"{lang}: corpus needs both classes"

        separation = (sum(relevant) / len(relevant)) - (sum(irrelevant) / len(irrelevant))
        assert separation >= SEPARATION_MIN, (
            f"{lang}: separation {separation:+.3f} < {SEPARATION_MIN} "
            f"(relevant mean {sum(relevant)/len(relevant):.3f}, "
            f"irrelevant mean {sum(irrelevant)/len(irrelevant):.3f})"
        )

    @pytest.mark.parametrize("lang", sorted(CORPUS))
    def test_recall_at_default_threshold(self, embedding_service, lang):
        """Relevant results must survive the production threshold."""
        from config import Config

        data = CORPUS[lang]
        threshold = Config.language_threshold(lang)
        scores = _scores(embedding_service, data["query"], data["items"])

        relevant = [s for s, rel in scores if rel]
        kept = [s for s in relevant if s >= threshold]
        recall = len(kept) / len(relevant)
        assert recall >= RECALL_MIN, (
            f"{lang}: recall {recall:.2f} < {RECALL_MIN} at threshold {threshold}"
        )

    @pytest.mark.parametrize("lang", sorted(CORPUS))
    def test_filter_keeps_relevant_results(self, embedding_service, lang):
        """End-to-end: the filter must not drop relevant items."""
        data = CORPUS[lang]
        items = [dict(item) for item in data["items"]]
        kept = embedding_service.filter_results(data["query"], items)

        kept_titles = {k["title"] for k in kept}
        relevant_titles = {i["title"] for i in data["items"] if i["relevant"]}
        missed = relevant_titles - kept_titles
        assert not missed, f"{lang}: filter dropped relevant results: {missed}"

    @pytest.mark.parametrize("lang", sorted(CORPUS))
    def test_russian_is_not_the_weakest_language(self, embedding_service, lang):
        """Regression guard for the reported symptom.

        The old blob-based scoring produced separations of +0.032 (ru),
        +0.096 (en), -0.021 (de), -0.134 (it) — Russian was the weakest and
        German/Italian were inverted. Now every language must clear the bar.
        """
        data = CORPUS[lang]
        scores = _scores(embedding_service, data["query"], data["items"])
        relevant = [s for s, rel in scores if rel]
        irrelevant = [s for s, rel in scores if not rel]
        separation = (sum(relevant) / len(relevant)) - (sum(irrelevant) / len(irrelevant))
        assert separation >= SEPARATION_MIN, f"{lang}: separation {separation:+.3f}"


class TestBlobStrategyIsWorse:
    """Document that the previous strategy was the defect, and keep it that way."""

    @pytest.mark.parametrize("lang", sorted(CORPUS))
    def test_full_blob_scores_worse_than_production_strategy(self, embedding_service, lang):
        data = CORPUS[lang]
        query_embedding = embedding_service._get_embedding(data["query"])

        def sep(strategy):
            scores = []
            for item in data["items"]:
                padded = dict(item)
                padded["highlights"] = (item["highlights"] + " " * 4000)[:4000]
                scores.append((
                    embedding_service.score_item(query_embedding, padded, strategy=strategy),
                    item["relevant"],
                ))
            rel = [s for s, r in scores if r]
            irr = [s for s, r in scores if not r]
            return (sum(rel) / len(rel)) - (sum(irr) / len(irr))

        blob_separation = sep("chunk")
        production_separation = sep("blend")
        assert production_separation > blob_separation, (
            f"{lang}: blend {production_separation:+.3f} must beat blob {blob_separation:+.3f}"
        )


class TestScoringUsesTitleNotQueryEcho:
    def test_irrelevant_item_with_query_in_body_scores_below_relevant(self, embedding_service):
        """A page that merely mentions the topic must rank below one about it."""
        data = CORPUS["ru"]
        scores = _scores(embedding_service, data["query"], data["items"])
        by_title = {item["title"]: score for score, item in
                    zip([s for s, _ in scores], data["items"], strict=True)}

        relevant = [by_title[i["title"]] for i in data["items"] if i["relevant"]]
        irrelevant = [by_title[i["title"]] for i in data["items"] if not i["relevant"]]
        assert min(relevant) > max(irrelevant), (
            "a relevant result must beat every irrelevant one in Russian"
        )
