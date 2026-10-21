import os

import pytest

# Ensure key present before importing encryption helpers
os.environ.setdefault(
    "SECRET_ENCRYPTION_KEY",
    "afa05d56c675287cb013bb146dcbba88b98477421bef803cfe4a8710b0d2ba7c",
)

from app.core.config import get_settings  # noqa: E402
from app.core.encryption import decrypt_secret_str, encrypt_secret  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_encrypt_roundtrip():
    blob = encrypt_secret("ghn-sandbox-token-xyz")
    assert isinstance(blob, bytes)
    assert decrypt_secret_str(blob) == "ghn-sandbox-token-xyz"
