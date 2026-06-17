from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from alephclient.api import AlephAPI

_TIMEOUT = 300
_MAX_ATTEMPTS = 4
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_BACKOFF_BASE = 1.0  # seconds


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _retry_delay(resp: "requests.Response", attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return _BACKOFF_BASE * (2 ** (attempt - 1))


class ConfigError(Exception):
    pass


class FetchError(Exception):
    pass


def _auth_headers(url: str) -> dict[str, str]:
    api_key = os.environ.get("ALEPHCLIENT_API_KEY")
    host = os.environ.get("ALEPHCLIENT_HOST")
    if api_key and host and urlparse(url).netloc == urlparse(host).netloc:
        return {"Authorization": f"ApiKey {api_key}"}
    return {}


def make_api() -> AlephAPI:
    host = os.environ.get("ALEPHCLIENT_HOST")
    key = os.environ.get("ALEPHCLIENT_API_KEY")
    if not host or not key:
        raise ConfigError(
            "Set ALEPHCLIENT_HOST and ALEPHCLIENT_API_KEY environment variables."
        )
    return AlephAPI(host=host, api_key=key)


def file_url(base_url: str, entity: dict) -> str | None:
    url = entity.get("links", {}).get("file")
    if not url:
        return None
    if not urlparse(url).scheme:
        return urljoin(base_url, url)
    return url


def pick_filename(entity: dict) -> str | None:
    names = entity.get("properties", {}).get("fileName", [])
    if not names:
        return None
    return max(names, key=len)


def http_fetch(url: str, dest: Path) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = _auth_headers(url)
    last_error = "unknown error"
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        sha = hashlib.sha1(usedforsecurity=False)
        total = 0
        try:
            with requests.get(url, headers=headers, stream=True, timeout=_TIMEOUT) as resp:
                if resp.status_code in _RETRY_STATUS:
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < _MAX_ATTEMPTS:
                        time.sleep(_retry_delay(resp, attempt))
                        continue
                    raise FetchError(f"{last_error} after {attempt} attempts")
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=512 * 1024):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        sha.update(chunk)
                        total += len(chunk)
            return total, sha.hexdigest()
        except FetchError:
            _safe_unlink(dest)
            raise
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = str(exc)
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))
                continue
            _safe_unlink(dest)
            raise FetchError(last_error) from exc
        except Exception as exc:  # noqa: BLE001 - non-retryable (e.g. 404); normalize, never abort run
            _safe_unlink(dest)
            raise FetchError(str(exc)) from exc
    _safe_unlink(dest)
    raise FetchError(last_error)
