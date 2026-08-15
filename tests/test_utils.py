"""Tests for app/utils.py's pure helper functions (no network required)."""
import pytest

from app.utils import (
    extract_video_id,
    format_duration,
    sanitize_filename,
    validate_download_dir,
)


def test_sanitize_filename_strips_invalid_chars():
    assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_filename_collapses_whitespace():
    assert sanitize_filename("Artist   -    Title") == "Artist - Title"


def test_sanitize_filename_strips_control_chars():
    assert sanitize_filename("Title\x00with\x1fcontrol\x07chars") == "Titlewithcontrolchars"


def test_sanitize_filename_all_invalid_chars_falls_back_to_untitled():
    # A title made entirely of stripped characters used to sanitize down to
    # an empty string, producing a bare ".mp3" filename.
    assert sanitize_filename('<>:"/\\|?*') == "untitled"
    assert sanitize_filename("   ") == "untitled"


def test_sanitize_filename_windows_reserved_names():
    assert sanitize_filename("NUL") == "_NUL"
    assert sanitize_filename("con") == "_con"  # case-insensitive
    assert sanitize_filename("COM1") == "_COM1"
    assert sanitize_filename("LPT9") == "_LPT9"
    # Not reserved -- a substring/prefix match shouldn't trigger this.
    assert sanitize_filename("CONcert") == "CONcert"


def test_sanitize_filename_truncates_very_long_names():
    result = sanitize_filename("A" * 300)
    assert len(result) <= 150


def test_validate_download_dir_accepts_normal_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert validate_download_dir("./downloads") == "./downloads"


def test_validate_download_dir_rejects_empty():
    with pytest.raises(ValueError):
        validate_download_dir("")
    with pytest.raises(ValueError):
        validate_download_dir("   ")


def test_validate_download_dir_rejects_drive_root(tmp_path):
    root = str(tmp_path.anchor)
    with pytest.raises(ValueError):
        validate_download_dir(root)


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
