"""Tests for utils.py's pure helper functions (no network required)."""
from utils import extract_video_id, format_duration, sanitize_filename


def test_sanitize_filename_strips_invalid_chars():
    assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_filename_collapses_whitespace():
    assert sanitize_filename("Artist   -    Title") == "Artist - Title"


def test_format_duration_under_a_minute():
    assert format_duration(45) == "00:45"


def test_format_duration_under_an_hour():
    assert format_duration(125) == "02:05"


def test_format_duration_over_an_hour():
    assert format_duration(3725) == "01:02:05"


def test_format_duration_none_or_zero():
    assert format_duration(None) == "00:00"
    assert format_duration(0) == "00:00"


def test_format_duration_accepts_float():
    assert format_duration(90.7) == "01:30"


def test_extract_video_id_from_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=jfKfPfyJRdk") == "jfKfPfyJRdk"


def test_extract_video_id_from_short_url():
    assert extract_video_id("https://youtu.be/jfKfPfyJRdk") == "jfKfPfyJRdk"


def test_extract_video_id_from_bare_id():
    assert extract_video_id("jfKfPfyJRdk") == "jfKfPfyJRdk"


def test_extract_video_id_invalid_url_returns_none():
    assert extract_video_id("https://example.com/not-youtube") is None
