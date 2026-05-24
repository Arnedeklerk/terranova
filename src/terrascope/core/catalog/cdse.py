"""Copernicus Data Space Ecosystem OAuth helpers (device-code flow).

CDSE uses Keycloak as its identity provider.  The device-code flow is the
right shape for a desktop plugin: we open a URL in the user's browser, they
sign in, and the plugin polls for a token.  We persist the refresh token in
the user's platform-specific cache directory so subsequent sessions skip the
browser step entirely.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass

CDSE_AUTH_BASE = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
DEVICE_AUTH_URL = f"{CDSE_AUTH_BASE}/protocol/openid-connect/auth/device"
TOKEN_URL = f"{CDSE_AUTH_BASE}/protocol/openid-connect/token"
CLIENT_ID = "cdse-public"  # public client; no secret required for device flow

# Per RFC 8628 the standard polling backoff is "slow_down".
SLOW_DOWN_INCREMENT = 5


@dataclass(slots=True, frozen=True)
class DeviceFlowChallenge:
    """The blob returned by the device-authorisation endpoint."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    interval: int      # seconds between polls
    expires_in: int    # seconds


@dataclass(slots=True)
class CDSEToken:
    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds

    def is_expired(self, *, skew: int = 30) -> bool:
        return time.time() > (self.expires_at - skew)


# --------------------------------------------------------------------------- #
# Token cache                                                                 #
# --------------------------------------------------------------------------- #
def token_cache_path() -> Path:
    """Per-user cache for the CDSE refresh token."""
    try:
        import platformdirs

        return Path(platformdirs.user_cache_dir("terrascope")) / "cdse_token.json"
    except ImportError:  # pragma: no cover
        return Path.home() / ".cache" / "terrascope" / "cdse_token.json"


def load_cached_token() -> CDSEToken | None:
    p = token_cache_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return CDSEToken(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def save_token(token: CDSEToken) -> None:
    p = token_cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(token)), encoding="utf-8")
    try:
        # Best-effort: restrict file to current user only.
        import stat

        p.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover — Windows
        pass


def forget_token() -> None:
    """Wipe the cached token (sign-out)."""
    p = token_cache_path()
    p.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Device-code flow                                                            #
# --------------------------------------------------------------------------- #
def begin_device_flow() -> DeviceFlowChallenge:
    """POST to the device-authorisation endpoint.  Returns the challenge blob."""
    import requests

    resp = requests.post(
        DEVICE_AUTH_URL,
        data={"client_id": CLIENT_ID, "scope": "openid"},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()
    return DeviceFlowChallenge(
        device_code=payload["device_code"],
        user_code=payload["user_code"],
        verification_uri=payload["verification_uri"],
        verification_uri_complete=payload.get(
            "verification_uri_complete", payload["verification_uri"]
        ),
        interval=int(payload.get("interval", 5)),
        expires_in=int(payload["expires_in"]),
    )


class DeviceFlowError(RuntimeError):
    """Raised when a CDSE device flow fails (expired / declined / etc.)."""


def poll_for_token(
    challenge: DeviceFlowChallenge,
    *,
    on_pending: callable | None = None,  # type: ignore[type-arg]
) -> CDSEToken:
    """Block until the user signs in, or the challenge expires.

    ``on_pending`` is called once per poll with the elapsed seconds, useful for
    surfacing "waiting for browser sign-in..." progress in the UI.
    """
    import requests

    started = time.time()
    interval = challenge.interval
    while True:
        elapsed = time.time() - started
        if elapsed > challenge.expires_in:
            raise DeviceFlowError("device-code challenge expired; restart sign-in")

        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": challenge.device_code,
                "client_id": CLIENT_ID,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            payload = resp.json()
            return _token_from_payload(payload)

        err = resp.json().get("error")
        if err == "authorization_pending":
            if on_pending is not None:
                on_pending(elapsed)
            time.sleep(interval)
            continue
        if err == "slow_down":
            interval += SLOW_DOWN_INCREMENT
            time.sleep(interval)
            continue
        if err in {"expired_token", "access_denied"}:
            raise DeviceFlowError(f"sign-in failed: {err}")
        raise DeviceFlowError(f"unexpected response from CDSE: {resp.status_code} {resp.text}")


def refresh(token: CDSEToken) -> CDSEToken:
    """Exchange the refresh token for a fresh access token."""
    import requests

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": CLIENT_ID,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return _token_from_payload(resp.json())


def get_token() -> CDSEToken:
    """Return a valid access token, refreshing or re-authing as needed."""
    cached = load_cached_token()
    if cached is not None and not cached.is_expired():
        return cached
    if cached is not None:
        try:
            fresh = refresh(cached)
            save_token(fresh)
            return fresh
        except Exception:
            forget_token()

    challenge = begin_device_flow()
    print(
        f"[TerraScope CDSE] Open {challenge.verification_uri_complete} "
        f"and enter code {challenge.user_code}"
    )
    token = poll_for_token(challenge)
    save_token(token)
    return token


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _token_from_payload(payload: dict) -> CDSEToken:
    return CDSEToken(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_at=time.time() + int(payload["expires_in"]),
    )
