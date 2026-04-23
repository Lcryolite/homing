"""Credential encryption with tiered security strategy.

Priority:
1. Platform keyring (keyring / SecretStorage / KWallet)
2. Fallback: file-based storage with strict permissions

Migration: old flat `.enc_key` files are transparently upgraded on first use.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import cast

from cryptography.fernet import Fernet

from openemail.config import settings

logger = logging.getLogger(__name__)

# --- keyring support (soft dependency) ---
try:
    import keyring
    from keyring.errors import KeyringError

    _kr = keyring.get_keyring()
    _keyring_available = _kr is not None and _kr.__class__.__name__ != "Keyring"
except Exception:
    _keyring_available = False
    keyring = None  # type: ignore[assignment]
    KeyringError = Exception  # type: ignore[misc,assignment]

_APP_NAME = "openemail"
_KEYRING_KEY_ID = "master_encryption_key"
_ENC_FILE = settings.data_dir / ".enc_key_v2"
_LEGACY_ENC_FILE = settings.data_dir / ".enc_key"


def _generate_fernet_key() -> bytes:
    """Generate a fresh URL-safe base64-encoded 32-byte Fernet key."""
    return Fernet.generate_key()


def _store_in_keyring(key: bytes) -> bool:
    """Store the master key in the platform keyring."""
    if not _keyring_available or keyring is None:
        return False
    try:
        keyring.set_password(_APP_NAME, _KEYRING_KEY_ID, base64.urlsafe_b64encode(key).decode())
        logger.info("Master key stored in platform keyring")
        return True
    except Exception as e:
        logger.warning("Failed to store key in keyring: %s", e)
        return False


def _load_from_keyring() -> bytes | None:
    """Load the master key from the platform keyring."""
    if not _keyring_available or keyring is None:
        return None
    try:
        b64 = keyring.get_password(_APP_NAME, _KEYRING_KEY_ID)
        if b64:
            return base64.urlsafe_b64decode(b64.encode())
    except Exception as e:
        logger.warning("Failed to load key from keyring: %s", e)
    return None


def _delete_keyring_entry() -> None:
    """Remove key from keyring (used during migration/cleanup)."""
    if not _keyring_available or keyring is None:
        return
    try:
        keyring.delete_password(_APP_NAME, _KEYRING_KEY_ID)
    except Exception:
        pass


def _store_in_file(key: bytes) -> None:
    """Store the master key in a local file with strict permissions.

    Format (JSON, versioned for future migration):
    {
        "version": 2,
        "key_b64": "<urlsafe_b64encoded_key>"
    }
    """
    payload = json.dumps(
        {"version": 2, "key_b64": base64.urlsafe_b64encode(key).decode()}
    ).encode("utf-8")

    tmp = _ENC_FILE.with_suffix(".tmp")
    tmp.write_bytes(payload)
    tmp.chmod(0o600)
    tmp.replace(_ENC_FILE)
    _ENC_FILE.chmod(0o600)
    logger.info("Master key stored in %s", _ENC_FILE)


def _load_from_file() -> bytes | None:
    """Load master key from local file (v2 format or legacy flat key)."""
    # --- v2 format ---
    if _ENC_FILE.exists():
        try:
            data = json.loads(_ENC_FILE.read_bytes())
            b64 = data.get("key_b64", "")
            if b64:
                return base64.urlsafe_b64decode(b64.encode())
        except Exception as e:
            logger.error("Failed to read v2 key file: %s", e)
        return None

    # --- legacy flat key migration ---
    if _LEGACY_ENC_FILE.exists():
        try:
            raw = _LEGACY_ENC_FILE.read_bytes()
            # Legacy key was already a URL-safe base64 Fernet key (or malformed).
            # Validate it looks like a Fernet key before migration.
            if len(raw) == 44:  # 32 bytes -> 44 chars base64 urlsafe
                _ = Fernet(raw)  # validates format
                logger.warning("Migrating legacy .enc_key to v2 format")
                _store_in_file(raw)
                # Attempt keyring promotion
                _store_in_keyring(raw)
                _LEGACY_ENC_FILE.unlink(missing_ok=True)
                return raw
        except Exception as e:
            logger.error("Legacy key migration failed: %s", e)
        return None

    return None


def _get_or_create_key() -> bytes:
    """Retrieve or create the master Fernet key.

    Order:
    1. Platform keyring
    2. v2 local file
    3. Legacy local file (auto-migrate)
    4. Generate new key, store in keyring + file
    """
    # 1. Try keyring
    key = _load_from_keyring()
    if key is not None:
        return key

    # 2. Try file (v2 or legacy)
    key = _load_from_file()
    if key is not None:
        # Opportunistically promote to keyring if now available
        _store_in_keyring(key)
        return key

    # 3. Generate new key
    logger.warning("No existing encryption key found; generating new master key")
    key = _generate_fernet_key()

    # Store in both keyring (preferred) and file (fallback/backup)
    if not _store_in_keyring(key):
        logger.warning(
            "Platform keyring unavailable; falling back to file-based key storage. "
            "Consider installing a keyring backend (e.g., gnome-keyring, kwallet5, KeePassXC secret service) for better security."
        )
    _store_in_file(key)
    return key


_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(_get_or_create_key())
    return _fernet_instance


def encrypt_password(password: str) -> str:
    """Encrypt a plaintext password (or token) string."""
    if not password:
        return ""
    return _get_fernet().encrypt(password.encode()).decode()


def decrypt_password(token: str) -> str:
    """Decrypt a previously encrypted password (or token) string."""
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()


def rotate_key() -> bool:
    """Re-encrypt all credentials with a fresh key.

    Returns True if rotation succeeded.  This is a no-op if keyring/file
    storage is healthy; it exists for emergency key rotation workflows.
    """
    # NOTE: To fully implement rotation we would need to iterate all
    # encrypted columns in the DB and re-encrypt them.  This is a
    # placeholder for the API surface.
    logger.warning("Key rotation stub called — full implementation requires DB scan")
    return False
