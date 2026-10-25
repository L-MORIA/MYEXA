"""Shared fixtures for MYEXA backend tests.

All external services (Exa, Yandex, Google Translate, SentenceTransformer)
are mocked so tests run without network access and without downloading models.
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=False)
def _patch_embedding_model(monkeypatch):
    """Prevent SentenceTransformer from downloading / loading a real model.
    
    NOT autouse — only applies to tests that explicitly request it
    (embedding tests request it directly via fixture name).
    """
    fake_encode = MagicMock(return_value=MagicMock())

    mock_model = MagicMock()
    mock_model.eval.return_value = mock_model
    mock_model.encode.return_value = fake_encode

    with patch("services.embedding.SentenceTransformer", return_value=mock_model):
        yield mock_model


@pytest.fixture()
def tmp_db_path(tmp_path):
    """Return a path to a temporary SQLite database."""
    return str(tmp_path / "test_myexa.db")


@pytest.fixture()
def tmp_config(tmp_db_path, monkeypatch):
    """Patch Config.DATABASE_PATH so Database writes to a temp file."""
    from config import Config

    monkeypatch.setattr(Config, "DATABASE_PATH", tmp_db_path)
    return Config
