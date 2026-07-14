"""Tests for backend.services.embedding.EmbeddingService."""

from unittest.mock import MagicMock, patch

from services.embedding import EmbeddingService


class TestEmbeddingServiceInit:
    def test_available_on_success(self):
        with patch("services.embedding.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_st.return_value = mock_model
            svc = EmbeddingService()
            assert svc._available is True

    def test_unavailable_on_failure(self):
        with patch("services.embedding.SentenceTransformer", side_effect=RuntimeError("no CUDA")):
            svc = EmbeddingService()
            assert svc._available is False


class TestFilterResults:
    def test_returns_items_when_unavailable(self):
        """If model failed to load, filter should be a pass-through."""
        with patch("services.embedding.SentenceTransformer", side_effect=RuntimeError):
            svc = EmbeddingService()
        items = [{"title": "hello"}]
        assert svc.filter_results("query", items) == items

    def test_returns_items_when_query_embedding_fails(self):
        """If encode() throws on the query, return items as-is."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("OOM")
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()
        items = [{"title": "test"}]
        result = svc.filter_results("q", items)
        assert result == items
        assert svc._available is False  # flagged for future skips

    def test_sorts_by_similarity(self):
        """Results must be sorted by embedding_score descending."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        # encode returns a tensor-like; we mock _get_embedding directly
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        # Mock cosine similarity to return different scores per call
        call_count = {"n": 0}
        scores = [0.8, 0.3, 0.95]

        def fake_sim(q_emb, t_emb):
            val = scores[call_count["n"]]
            call_count["n"] += 1
            # calculate_similarity returns float(sim[0][0])
            return float(val)

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", side_effect=fake_sim):
                items = [
                    {"title": "A"},
                    {"title": "B"},
                    {"title": "C"},
                ]
                result = svc.filter_results("query", items, threshold=0.0)
                # Scores: A=0.8, B=0.3, C=0.95 → sorted: C(0.95), A(0.8), B(0.3)
                assert result[0]["embedding_score"] == 0.95
                assert result[2]["embedding_score"] == 0.3

    def test_fallback_when_all_below_threshold(self):
        """When nothing passes the threshold, return all items with score 0."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.1):
                items = [{"title": "A"}, {"title": "B"}]
                result = svc.filter_results("q", items, threshold=0.5)
                assert len(result) == 2
                # All should have embedding_score set
                for item in result:
                    assert "embedding_score" in item

    def test_skips_items_without_text(self):
        """Items with empty highlights and title should be skipped."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        items = [
            {"title": "", "highlights": ""},
            {"title": "hello"},
        ]
        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.9):
                result = svc.filter_results("q", items, threshold=0.0)
                assert len(result) == 1
                assert result[0]["title"] == "hello"

    def test_threshold_0_3(self):
        """With the new threshold of 0.3, items with score 0.35 pass."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.35):
                items = [{"title": "test"}]
                result = svc.filter_results("q", items, threshold=0.3)
                assert len(result) == 1
