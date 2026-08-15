"""Tests for app/passwords.py's PBKDF2-based password hashing (docs/15)."""
from app.passwords import hash_password, verify_password


def test_round_trip():
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored) is True


def test_wrong_password_rejected():
    stored = hash_password("correct horse battery staple")
    assert verify_password("wrong password", stored) is False


def test_hash_is_salted_differently_each_time():
    """Two hashes of the same password must differ (random salt per call) --
    otherwise identical passwords would be spottable by comparing stored
    hashes directly."""
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second
    assert verify_password("same password", first) is True
    assert verify_password("same password", second) is True


def test_stored_hash_format():
    stored = hash_password("hunter2")
    parts = stored.split("$")
    assert len(parts) == 4
    assert parts[0] == "pbkdf2_sha256"
    assert parts[1].isdigit()


def test_verify_malformed_hash_does_not_raise():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", "pbkdf2_sha256$notanumber$salt$hash") is False
    assert verify_password("anything", "unknown_algo$260000$c2FsdA==$aGFzaA==") is False
    assert verify_password("anything", "pbkdf2_sha256$260000$not-base64!!$aGFzaA==") is False


def test_verify_empty_password_against_real_hash():
    stored = hash_password("real password")
    assert verify_password("", stored) is False
