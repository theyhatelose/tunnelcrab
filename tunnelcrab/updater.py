from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request

from .version import APP_VERSION

GITHUB_REPO = "theyhatelose/tunnelcrab"

_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
_USER_AGENT = "TunnelCrab-Updater"
_TIMEOUT = 15


def _repo_configured():
    return bool(GITHUB_REPO) and "/" in GITHUB_REPO and "owner" not in GITHUB_REPO


def _parse_version(text):
    if not text:
        return ()
    nums = re.findall(r"\d+", str(text))
    return tuple(int(n) for n in nums) if nums else ()


def _is_newer(remote, local):
    return _parse_version(remote) > _parse_version(local)


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
        return resp.read()


def _pick_installer_asset(assets):
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe"):
            return asset
    return assets[0] if assets else None


_SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")


def _find_checksum_asset(assets, installer_name):
    target = (installer_name or "").lower()
    sidecar = generic = None
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if target and name == target + ".sha256":
            sidecar = asset
        elif name in ("sha256sums", "sha256sums.txt", "checksums.txt"):
            generic = asset
    return sidecar or generic


def _parse_sha256(text, installer_name):
    target = (installer_name or "").lower()
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if target:
        for ln in lines:
            if target in ln.lower():
                match = _SHA256_RE.search(ln)
                if match:
                    return match.group(0).lower()
    for ln in lines:
        match = _SHA256_RE.search(ln)
        if match:
            return match.group(0).lower()
    return ""


def _expected_sha256(assets, installer_name):
    asset = _find_checksum_asset(assets, installer_name)
    url = asset and asset.get("browser_download_url")
    if not url:
        return ""
    try:
        raw = _http_get(url)
        return _parse_sha256(raw.decode("utf-8", "replace"), installer_name)
    except Exception:
        return ""


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_for_updates():
    if not _repo_configured():
        return {"available": False}
    try:
        raw = _http_get(_API_URL.format(repo=GITHUB_REPO))
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return {"available": False, "error": str(exc)}

    tag = data.get("tag_name") or data.get("name") or ""
    if not _is_newer(tag, APP_VERSION):
        return {"available": False, "version": tag.lstrip("vV")}

    assets = data.get("assets") or []
    asset = _pick_installer_asset(assets)
    if not asset:
        return {"available": False, "version": tag.lstrip("vV")}

    return {
        "available": True,
        "version": tag.lstrip("vV"),
        "notes": data.get("body") or "",
        "url": asset.get("browser_download_url") or "",
        "sha256": _expected_sha256(assets, asset.get("name")),
    }


def download_installer(url, expected_sha256="", progress=None):
    if not url:
        raise ValueError("Нет ссылки на установщик")
    if not expected_sha256:
        raise ValueError(
            "У обновления нет опубликованной контрольной суммы (SHA256) — "
            "автоустановка отменена ради безопасности"
        )
    suffix = ".exe" if url.lower().endswith(".exe") else ""
    fd, path = tempfile.mkstemp(prefix="TunnelCrab-update-", suffix=suffix)
    os.close(fd)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(path, "wb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress and total:
                    try:
                        progress(done, total)
                    except Exception:
                        pass

    actual = _sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        try:
            os.remove(path)
        except OSError:
            pass
        raise ValueError(
            "Контрольная сумма установщика не совпала — файл мог быть "
            "повреждён или подменён, запуск отменён"
        )

    return path


def launch_installer(path):
    if not sys.platform.startswith("win"):
        return False
    try:
        os.startfile(path)
        return True
    except Exception:
        try:
            subprocess.Popen([path], close_fds=True)
            return True
        except Exception:
            return False
