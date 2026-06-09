from __future__ import annotations

import base64
import binascii
import re
import ssl
import urllib.error
import urllib.request

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TunnelCrab/1.0"
_TIMEOUT = 15

_SUPPORTED_SCHEMES = ("vless://",)

_ZERO_WIDTH = dict.fromkeys(
    (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF), None
)
_LINK_RE = re.compile(r"vless://[^\s`'\"<>]+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s`'\"<>]+", re.IGNORECASE)


class SubscriptionError(Exception):
    pass


def _clean_text(text):
    return str(text).translate(_ZERO_WIDTH)


def extract_url(text):
    cleaned = _clean_text(str(text or "")).strip().strip("`'\"<>")
    match = _URL_RE.search(cleaned)
    if match:
        return match.group(0).rstrip(".,;)]}")
    return ""


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise SubscriptionError(f"Сервер подписки ответил ошибкой HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise SubscriptionError(
                "Не удалось проверить TLS-сертификат сервера подписки"
            ) from exc
        if isinstance(reason, ssl.SSLError):
            raise SubscriptionError("Ошибка TLS при подключении к подписке") from exc
        raise SubscriptionError("Не удалось подключиться к серверу подписки") from exc
    except (TimeoutError, OSError) as exc:
        raise SubscriptionError("Сервер подписки не отвечает (таймаут)") from exc


def _maybe_b64decode(text):
    stripped = "".join(text.split())
    if not stripped:
        return text
    if "://" in text:
        return text
    padded = stripped + "=" * (-len(stripped) % 4)
    try:
        decoded = base64.b64decode(padded, validate=False)
        return decoded.decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return text


def parse_links(body):
    text = _clean_text(_maybe_b64decode(body))
    links = []
    for line in text.replace("\r", "\n").split("\n"):
        for match in _LINK_RE.finditer(line):
            links.append(match.group(0).rstrip(".,;)]}"))
    return links


def count_lines(body):
    text = _clean_text(_maybe_b64decode(body))
    return sum(1 for line in text.replace("\r", "\n").split("\n") if line.strip())


def fetch_links(url):
    raw = _http_get(url)
    body = raw.decode("utf-8", errors="replace")
    return parse_links(body)
