"""Password hashing: stdlib PBKDF2-HMAC-SHA256, no new dependency.

docs/15 decided against passlib/bcrypt -- consistent with this project's
existing bias toward stdlib over new packages at this scale (see
app/utils.py's validate_download_dir for the same "validate carefully,
write a test for it" standard this module follows).

Stored format is self-describing: "pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>"
so a future iteration-count bump doesn't require a data migration -- old
rows keep verifying against whatever iteration count they were hashed
with, new rows use whatever _ITERATIONS currently is.
"""
import base64
import binascii
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
# OWASP's current (2023+) PBKDF2-SHA256 guidance -- higher than older
# 100k-ish recommendations now that hardware has caught up.
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Hash a password for storage. Returns a self-describing string --
    see module docstring for the format."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"{_ALGORITHM}${_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a stored hash. Never raises -- a malformed
    or corrupted stored_hash (wrong field count, bad base64, unknown
    algorithm) is treated as "doesn't match" rather than a 500, since the
    caller's job (login) is the same either way: reject the attempt."""
    try:
        algorithm, iterations_str, salt_b64, hash_b64 = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError, binascii.Error):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    # compare_digest is timing-safe; it requires equal-length inputs, which
    # a malformed/truncated stored_hash could violate, so that's checked
    # first rather than letting compare_digest raise.
    return len(derived) == len(expected) and hmac.compare_digest(derived, expected)
