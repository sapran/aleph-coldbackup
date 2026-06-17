import hashlib

import pytest
import requests as _requests

from aleph_coldbackup.client import (
    file_url, http_fetch, pick_filename, FetchError,
)

BASE = "http://localhost:8080/api/2/"


def test_file_url_absolutizes_relative():
    e = {"links": {"file": "/api/2/archive?token=abc"}}
    assert file_url(BASE, e) == "http://localhost:8080/api/2/archive?token=abc"


def test_file_url_keeps_absolute():
    e = {"links": {"file": "https://cdn.example/x?token=abc"}}
    assert file_url(BASE, e) == "https://cdn.example/x?token=abc"


def test_file_url_none_when_missing():
    assert file_url(BASE, {"links": {}}) is None
    assert file_url(BASE, {}) is None


def test_pick_filename_longest_then_none():
    assert pick_filename({"properties": {"fileName": ["a", "abc", "ab"]}}) == "abc"
    assert pick_filename({"properties": {}}) is None


class _Resp:
    def __init__(self, chunks, status_code=200, headers=None):
        self._chunks = chunks
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise _requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_fetch_writes_and_hashes(tmp_path, monkeypatch):
    payload = [b"hello ", b"world"]
    monkeypatch.setattr(
        "aleph_coldbackup.client.requests.get",
        lambda url, headers=None, stream=False, timeout=None: _Resp(payload),
    )
    dest = tmp_path / "sub" / "out.bin"
    n, sha = http_fetch("http://x/file", dest)
    assert dest.read_bytes() == b"hello world"
    assert n == 11
    assert sha == hashlib.sha1(b"hello world").hexdigest()


def test_http_fetch_raises_fetcherror(tmp_path, monkeypatch):
    def boom(url, headers=None, stream=False, timeout=None):
        raise OSError("connection reset")
    monkeypatch.setattr("aleph_coldbackup.client.requests.get", boom)
    with pytest.raises(FetchError):
        http_fetch("http://x/file", tmp_path / "out.bin")


def test_http_fetch_retries_on_429_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr("aleph_coldbackup.client.time.sleep", lambda s: None)
    call_count = 0

    def fake_get(url, headers=None, stream=False, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _Resp([], 429)
        return _Resp([b"ok"], 200)

    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)

    import aleph_coldbackup.client as _mod
    recorded_sleeps = []
    monkeypatch.setattr(_mod.time, "sleep", lambda s: recorded_sleeps.append(s))

    dest = tmp_path / "out.bin"
    n, sha = http_fetch("http://x/file", dest)

    assert dest.read_bytes() == b"ok"
    assert sha == hashlib.sha1(b"ok").hexdigest()
    assert call_count == 2
    assert len(recorded_sleeps) == 1


def test_http_fetch_gives_up_after_max_attempts_on_429(tmp_path, monkeypatch):
    import aleph_coldbackup.client as _mod
    monkeypatch.setattr(_mod.time, "sleep", lambda s: None)
    call_count = 0

    def fake_get(url, headers=None, stream=False, timeout=None):
        nonlocal call_count
        call_count += 1
        return _Resp([], 429)

    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)

    dest = tmp_path / "out.bin"
    with pytest.raises(FetchError):
        http_fetch("http://x/file", dest)

    assert call_count == 4
    assert not dest.exists()


def test_http_fetch_does_not_retry_on_404(tmp_path, monkeypatch):
    import aleph_coldbackup.client as _mod
    monkeypatch.setattr(_mod.time, "sleep", lambda s: None)
    call_count = 0

    def fake_get(url, headers=None, stream=False, timeout=None):
        nonlocal call_count
        call_count += 1
        return _Resp([], 404)

    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)

    dest = tmp_path / "out.bin"
    with pytest.raises(FetchError):
        http_fetch("http://x/file", dest)

    assert call_count == 1
    assert not dest.exists()


def test_http_fetch_retries_on_connection_error(tmp_path, monkeypatch):
    import aleph_coldbackup.client as _mod
    monkeypatch.setattr(_mod.time, "sleep", lambda s: None)
    call_count = 0

    def fake_get(url, headers=None, stream=False, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _requests.ConnectionError("dropped")
        return _Resp([b"x"], 200)

    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)

    dest = tmp_path / "out.bin"
    n, sha = http_fetch("http://x/file", dest)

    assert dest.read_bytes() == b"x"
    assert call_count == 2


def test_http_fetch_honors_retry_after_header(tmp_path, monkeypatch):
    import aleph_coldbackup.client as _mod
    recorded_sleeps = []
    monkeypatch.setattr(_mod.time, "sleep", lambda s: recorded_sleeps.append(s))
    call_count = 0

    def fake_get(url, headers=None, stream=False, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _Resp([], 429, {"Retry-After": "2"})
        return _Resp([b"y"], 200)

    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)

    dest = tmp_path / "out.bin"
    n, sha = http_fetch("http://x/file", dest)

    assert dest.read_bytes() == b"y"
    assert len(recorded_sleeps) == 1
    assert recorded_sleeps[0] == 2.0


def test_http_fetch_omits_api_key_for_foreign_host(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHCLIENT_API_KEY", "secret")
    monkeypatch.setenv("ALEPHCLIENT_HOST", "https://aleph.example")
    captured = {}
    def fake_get(url, headers=None, stream=False, timeout=None):
        captured["headers"] = headers
        return _Resp([b"x"], 200)
    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)
    http_fetch("https://evil.cdn/file?token=abc", tmp_path / "o.bin")
    assert "Authorization" not in (captured["headers"] or {})


def test_http_fetch_sends_api_key_for_aleph_host(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHCLIENT_API_KEY", "secret")
    monkeypatch.setenv("ALEPHCLIENT_HOST", "https://aleph.example")
    captured = {}
    def fake_get(url, headers=None, stream=False, timeout=None):
        captured["headers"] = headers
        return _Resp([b"x"], 200)
    monkeypatch.setattr("aleph_coldbackup.client.requests.get", fake_get)
    http_fetch("https://aleph.example/api/2/archive?token=abc", tmp_path / "o.bin")
    assert captured["headers"].get("Authorization") == "ApiKey secret"
