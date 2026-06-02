#!/usr/bin/env python3
"""Shared Garmin Connect authentication for AiCoach.

garmindb 3.8.0 authenticates via the `garminconnect` (curl_cffi) backend. Its
built-in ``secure_password`` mode only reads the macOS Keychain, so on Windows/Linux
we bridge the password from the cross-platform OS credential store (the `keyring`
library) into garmindb's config manager.

Auth strategy (handled by garmindb's adapter):
  1. If a cached token exists (~/.GarminDb/garmin_tokens.json) it is used and
     refreshed automatically -- no password or MFA needed.
  2. Otherwise we log in with the keyring-stored password (prompting for an MFA
     code if 2FA is enabled) and the token is persisted for next time.
"""

import keyring

from garmindb import GarminConnectConfigManager
from garmindb.garmin_connect_auth_adapter import (
    GarminConnectAuthAdapter,
    GarminConnectAuthError,
)

# keyring service name -- must match what setup_config.py stores the password under.
KEYRING_SERVICE = "GarminConnect"


class KeyringConfigManager(GarminConnectConfigManager):
    """garmindb config manager that reads the password from the OS credential store.

    Overrides the macOS-only ``get_secure_password`` so ``secure_password: true`` works
    cross-platform via the `keyring` library (Windows Credential Manager, etc.).
    """

    def get_secure_password(self):
        return keyring.get_password(KEYRING_SERVICE, self.get_user())


def store_password(email: str, password: str) -> None:
    """Save the Garmin password to the OS credential store."""
    keyring.set_password(KEYRING_SERVICE, email, password)


def get_stored_password(email: str):
    """Return the stored Garmin password (or None)."""
    return keyring.get_password(KEYRING_SERVICE, email)


def login(mfa_prompt=None) -> GarminConnectAuthAdapter:
    """Authenticate to Garmin Connect and cache/refresh the session token.

    Uses the cached token first, then the keyring password. ``mfa_prompt`` is an
    optional callable returning the MFA code; if omitted, garmindb prompts on stdin.

    Returns the authenticated adapter (with ``full_name``/``display_name`` set).
    Raises ``GarminConnectAuthError`` on failure.
    """
    config = KeyringConfigManager()
    adapter = GarminConnectAuthAdapter(config, mfa_prompt=mfa_prompt)
    adapter.login()
    return adapter


__all__ = [
    "KeyringConfigManager",
    "GarminConnectAuthError",
    "store_password",
    "get_stored_password",
    "login",
    "KEYRING_SERVICE",
]
