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
        """When nothing passes the threshold, the result is EMPTY.

        The old behaviour returned every item with a zero score, which masked
        "nothing was relevant" as "everything is relevant".
        """
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.1):
                items = [{"title": "A"}, {"title": "B"}]
                result = svc.filter_results("q", items, threshold=0.5)
                assert result == []

    def test_empty_result_is_not_masked_as_full_list(self):
        """Regression: a fully-filtered language must not fall back to 'all'."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.05):
                items = [{"title": f"r{i}"} for i in range(10)]
                assert svc.filter_results("q", items, threshold=0.3) == []

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

    def test_item_embedding_failure_skips_item(self):
        """A failure while embedding ONE item must drop that item, not the batch."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        calls = {"n": 0}

        def flaky_encode(text, **kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("chunk too long")
            return MagicMock()

        with patch.object(svc, "_get_embedding", side_effect=flaky_encode):
            with patch.object(svc, "calculate_similarity", return_value=0.9):
                items = [{"title": "A", "highlights": "a"}, {"title": "B", "highlights": "b"}]
                result = svc.filter_results("q", items, threshold=0.0)
        # call 1 = query embedding, call 2 = item "A" -> raises -> "A" is skipped
        assert len(result) == 1
        assert result[0]["title"] == "B"

    def test_uses_highlights_before_title(self):
        """The embedded text is highlights when present, title otherwise."""
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        seen = []

        def capture(text, **kw):
            seen.append(text)
            return MagicMock()

        with patch.object(svc, "_get_embedding", side_effect=capture):
            with patch.object(svc, "calculate_similarity", return_value=0.9):
                svc.filter_results("q", [{"title": "T", "highlights": "H"}], threshold=0.0)
                svc.filter_results("q", [{"title": "T", "highlights": ""}], threshold=0.0)

        assert "H" in seen
        assert "T" in seen


class TestScoringStrategy:
    """The strategy matters more than the threshold — see
    diagnostics/strategy_sweep.py."""

    def _svc(self):
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            return EmbeddingService()

    def test_default_strategy_is_blend(self):
        from config import Config
        assert Config.RELEVANCE_STRATEGY == "blend"

    def test_blend_weights_sum_to_one(self):
        from config import Config
        total = Config.RELEVANCE_TITLE_WEIGHT + Config.RELEVANCE_SNIPPET_WEIGHT
        assert abs(total - 1.0) < 1e-9

    def test_blend_combines_title_and_snippet(self):
        svc = self._svc()
        item = {"title": "TITLE", "highlights": "SNIPPET"}

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", side_effect=[1.0, 0.0]):
                score = svc.score_item(MagicMock(), item, strategy="blend")

        expected = 1.0 * 0.7 + 0.0 * 0.3
        assert abs(score - expected) < 1e-9

    def test_title_strategy_ignores_snippet(self):
        svc = self._svc()
        item = {"title": "TITLE", "highlights": "SNIPPET"}

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.55):
                score = svc.score_item(MagicMock(), item, strategy="title")
        assert abs(score - 0.55) < 1e-9

    def test_blend_without_snippet_falls_back_to_title(self):
        svc = self._svc()
        item = {"title": "TITLE", "highlights": ""}

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.42):
                score = svc.score_item(MagicMock(), item, strategy="blend")
        assert abs(score - 0.42) < 1e-9

    def test_snippet_is_truncated(self):
        """Only the first RELEVANCE_SNIPPET_CHARS characters are embedded."""
        from config import Config
        svc = self._svc()
        long_text = "x" * 5000
        item = {"title": "T", "highlights": long_text}

        seen = []

        def capture(text, **kw):
            seen.append(text)
            return MagicMock()

        with patch.object(svc, "_get_embedding", side_effect=capture):
            with patch.object(svc, "calculate_similarity", return_value=0.5):
                svc.score_item(MagicMock(), item, strategy="blend")

        snippet_part = [t for t in seen if "x" in t]
        assert snippet_part
        assert len(snippet_part[0]) <= Config.RELEVANCE_SNIPPET_CHARS + len("T. ")

    def test_chunk_strategy_takes_max_over_chunks(self):
        svc = self._svc()
        item = {"title": "TITLE", "highlights": "y" * 600}

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", side_effect=[0.2, 0.9, 0.4]):
                score = svc.score_item(MagicMock(), item, strategy="chunk")
        assert abs(score - 0.9) < 1e-9


class TestThresholdSelection:
    def _svc(self):
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            return EmbeddingService()

    def test_explicit_threshold_is_used(self):
        svc = self._svc()
        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.2):
                items = [{"title": "A"}]
                assert svc.filter_results("q", items, threshold=0.5) == []
                assert len(svc.filter_results("q", items, threshold=0.1)) == 1

    def test_batch_filter_uses_per_language_thresholds(self):
        svc = self._svc()
        thresholds = {"ru": 0.9, "en": 0.1}

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.5):
                out = svc.batch_filter("q", {"ru": [{"title": "a"}], "en": [{"title": "b"}]},
                                       thresholds=thresholds)
        assert out["ru"] == []
        assert len(out["en"]) == 1


class TestCalculateSimilarity:
    def test_identical_text_scores_one(self):
        """Uses the real pytorch_cos_sim, not a mock."""
        import torch

        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        vec = torch.tensor([1.0, 0.0, 0.0])
        assert abs(svc.calculate_similarity(vec, vec) - 1.0) < 1e-6

    def test_orthogonal_text_scores_zero(self):
        import torch

        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        a = torch.tensor([1.0, 0.0])
        b = torch.tensor([0.0, 1.0])
        assert abs(svc.calculate_similarity(a, b)) < 1e-6


class TestBatchFilter:
    def test_filters_each_language_separately(self):
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        with patch("services.embedding.SentenceTransformer", return_value=mock_model):
            svc = EmbeddingService()

        with patch.object(svc, "_get_embedding", return_value=MagicMock()):
            with patch.object(svc, "calculate_similarity", return_value=0.9):
                out = svc.batch_filter("q", {"ru": [{"title": "a"}], "en": [{"title": "b"}]})
        assert set(out) == {"ru", "en"}


class _FakeModel:
    """A deterministic stand-in for SentenceTransformer.

    The vector of a text depends on its first character, so the similarity
    of two texts is reproducible and differs from text to text.
    """

    def __init__(self, broken_batch: bool = False):
        self.calls = []
        self.broken_batch = broken_batch

    def eval(self):
        return self

    def encode(self, text, convert_to_tensor=True, show_progress_bar=False):
        import torch

        texts = [text] if isinstance(text, str) else list(text)
        self.calls.append(list(texts))
        vectors = []
        for item in texts:
            code = (ord(item[0]) if item else 0) % 97 / 97.0
            vectors.append([code, 1.0 - code, 0.0])
        if self.broken_batch and not isinstance(text, str):
            # Return the wrong number of vectors — the batch must be rejected.
            return torch.tensor(vectors[:-1])
        return torch.tensor(vectors)


class TestBatchedScoring:
    """The filter must embed every text in one model call.

    One forward pass per text made the relevance filter the slowest stage of
    a search: 40 results meant 40 model calls.
    """

    def _svc(self, broken_batch: bool = False):
        with patch("services.embedding.SentenceTransformer",
                   return_value=_FakeModel(broken_batch=broken_batch)):
            return EmbeddingService()

    def test_all_items_are_encoded_in_one_call(self):
        svc = self._svc()
        items = [
            {"title": "Alpha", "highlights": "alpha snippet"},
            {"title": "Beta", "highlights": "beta snippet"},
            {"title": "Gamma", "highlights": "gamma snippet"},
        ]
        svc.filter_results("query", items, threshold=0.0)

        # One call for the query, one call for all item texts.
        assert len(svc.model.calls) == 2
        assert len(svc.model.calls[1]) == 6  # title + snippet per item

    def test_batched_and_per_item_scores_are_identical(self):
        """The fast path must not change a single score."""
        items = [
            {"title": "Alpha", "highlights": "alpha snippet"},
            {"title": "Beta", "highlights": ""},
            {"title": "", "highlights": "gamma snippet"},
        ]

        batched_svc = self._svc()
        batched = batched_svc.filter_results("query", [dict(i) for i in items], threshold=0.0)

        per_item_svc = self._svc(broken_batch=True)
        per_item = per_item_svc.filter_results("query", [dict(i) for i in items], threshold=0.0)

        assert len(batched) == len(per_item) == 3
        for left, right in zip(batched, per_item, strict=True):
            assert abs(left["embedding_score"] - right["embedding_score"]) < 1e-6
            assert left["title"] == right["title"]

    def test_wrong_number_of_vectors_falls_back_to_the_per_item_path(self):
        svc = self._svc(broken_batch=True)
        items = [
            {"title": "Alpha", "highlights": "alpha snippet"},
            {"title": "Beta", "highlights": "beta snippet"},
        ]
        result = svc.filter_results("query", items, threshold=0.0)
        # The batch was rejected, but every item was still scored.
        assert len(result) == 2
        # 1 query + 1 rejected batch + one call per text (title and snippet
        # of each of the two items) — the per-item path.
        assert len(svc.model.calls) == 6

    def test_batch_failure_falls_back_to_the_per_item_path(self):
        svc = self._svc()

        original_encode = svc.model.encode
        state = {"failed": False}

        def flaky(text, convert_to_tensor=True, show_progress_bar=False):
            if isinstance(text, list) and not state["failed"]:
                state["failed"] = True
                raise RuntimeError("batch too long")
            return original_encode(text, convert_to_tensor=convert_to_tensor,
                                   show_progress_bar=show_progress_bar)

        svc.model.encode = flaky
        items = [
            {"title": "Alpha", "highlights": "alpha snippet"},
            {"title": "Beta", "highlights": "beta snippet"},
        ]
        result = svc.filter_results("query", items, threshold=0.0)
        assert len(result) == 2

    def test_items_without_text_are_skipped(self):
        svc = self._svc()
        items = [{"title": "", "highlights": ""}, {"title": "Alpha", "highlights": ""}]
        result = svc.filter_results("query", items, threshold=0.0)
        assert len(result) == 1
        assert result[0]["title"] == "Alpha"

    def test_the_query_is_embedded_separately(self):
        svc = self._svc()
        svc.filter_results("query", [{"title": "Alpha", "highlights": "a"}], threshold=0.0)
        assert svc.model.calls[0] == ["query"]

