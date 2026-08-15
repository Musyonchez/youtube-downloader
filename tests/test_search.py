"""Tests for app/services/search.py's pure validate_url logic (no network)."""
from app.services.search import YouTubeSearcher

searcher = YouTubeSearcher()


def test_validate_url_accepts_standard_watch_url():
    assert searcher.validate_url("https://www.youtube.com/watch?v=abc123") == (True, 'video')


def test_validate_url_accepts_short_url():
    assert searcher.validate_url("https://youtu.be/abc123") == (True, 'video')


def test_validate_url_accepts_url_without_scheme():
    assert searcher.validate_url("youtube.com/watch?v=abc123") == (True, 'video')


def test_validate_url_detects_playlist_by_query_param():
    assert searcher.validate_url("https://www.youtube.com/playlist?list=PL123") == (True, 'playlist')


def test_validate_url_rejects_non_youtube_host():
    assert searcher.validate_url("https://example.com/watch?v=abc123") == (False, 'invalid')


def test_validate_url_rejects_host_containing_youtube_as_substring():
    # A raw 'youtube.com' in url substring check would wrongly accept this --
    # the actual host is evil.example, youtube.com is just a query value.
    assert searcher.validate_url("https://evil.example/?x=youtube.com") == (False, 'invalid')


def test_validate_url_rejects_lookalike_subdomain():
    # youtube.com as a prefix of a different real host, not the host itself.
    assert searcher.validate_url("https://youtube.com.evil.com/watch?v=abc123") == (False, 'invalid')


def test_validate_url_rejects_empty_string():
    assert searcher.validate_url("") == (False, 'invalid')
