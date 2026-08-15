"""Tests for API request validation models (no network/download calls).

Validated directly against the Pydantic models rather than through the full
HTTP stack, so these don't trigger real yt-dlp network calls.
"""
import pytest
from pydantic import ValidationError

from app.api.routes import ConfigUpdate, SearchRequest


def test_search_request_accepts_frontend_default_limit():
    # search.js's searchByName sends limit=60 for pagination (3 pages of 20).
    # Regression test: this was rejected by an overly tight le=50 bound.
    req = SearchRequest(query="test", limit=60)
    assert req.limit == 60


def test_search_request_rejects_excessive_limit():
    with pytest.raises(ValidationError):
        SearchRequest(query="test", limit=1000)


def test_search_request_rejects_zero_or_negative_limit():
    with pytest.raises(ValidationError):
        SearchRequest(query="test", limit=0)


def test_config_update_rejects_invalid_audio_quality():
    with pytest.raises(ValidationError):
        ConfigUpdate(audio_quality="999")


def test_config_update_accepts_valid_audio_quality():
    cfg = ConfigUpdate(audio_quality="256")
    assert cfg.audio_quality == "256"


def test_config_update_rejects_invalid_format():
    with pytest.raises(ValidationError):
        ConfigUpdate(format="wav")
