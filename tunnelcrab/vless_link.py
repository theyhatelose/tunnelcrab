from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, unquote, urlsplit

_ZERO_WIDTH = dict.fromkeys((0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF), None)
_LINK_RE = re.compile(r"vless://[^\s`'\"<>]+", re.IGNORECASE)


def _clean_link(link):
    text = str(link or "").translate(_ZERO_WIDTH).strip().strip("`'\"<>")
    match = _LINK_RE.search(text)
    if match:
        return match.group(0).rstrip(".,;)]}")
    return text


class VlessLinkError(ValueError):
    def __init__(self, key, params=None):
        super().__init__(key)
        self.key = key
        self.params = params or {}


_TRANSPORT_WHITELIST = {"tcp", "xhttp", "splithttp"}

_TRANSPORT_NAMES = {
    "ws": "WebSocket",
    "grpc": "gRPC",
    "httpupgrade": "HTTPUpgrade",
    "h2": "HTTP/2",
    "http": "HTTP/2",
    "quic": "QUIC",
    "kcp": "mKCP",
    "meek": "meek",
}

_TRUTHY = {"1", "true", "yes", "on"}


def _first(query, key, default=""):
    values = query.get(key)
    if not values:
        return default
    return values[0]


def _transport_name(network):
    return _TRANSPORT_NAMES.get(network, network)


def _split_link(link):
    link = _clean_link(link)
    if not link.lower().startswith("vless://"):
        raise VlessLinkError("reason.not_vless")

    try:
        parts = urlsplit(link)
        port = parts.port
    except ValueError as exc:
        raise VlessLinkError("reason.bad_port") from exc

    uuid = unquote(parts.username or "")
    address = parts.hostname or ""
    if not uuid or not address:
        raise VlessLinkError("reason.missing_uuid_or_host")

    query = parse_qs(parts.query, keep_blank_values=True)
    return parts, uuid, address, port or 443, query


def classify_vless_link(link):
    try:
        _, _, _, _, query = _split_link(link)
    except VlessLinkError as exc:
        return "REFUSE", exc.key, exc.params

    security = (_first(query, "security", "none") or "none").lower()
    network = (_first(query, "type", "tcp") or "tcp").lower()
    insecure = _first(query, "allowInsecure") or _first(query, "allowinsecure")

    if insecure.lower() in _TRUTHY:
        return "UNSAFE", "reason.allow_insecure", {}

    if security == "none":
        return "UNSAFE", "reason.no_encryption", {}

    if security == "tls":
        return "REFUSE", "reason.tls_unsupported", {}

    if security != "reality":
        return "REFUSE", "reason.unknown_security", {"security": security}

    if not _first(query, "pbk"):
        return "UNSAFE", "reason.reality_missing_keys", {}

    if network not in _TRANSPORT_WHITELIST:
        return (
            "REFUSE",
            "reason.transport_unsupported",
            {"transport": _transport_name(network)},
        )

    return "ACCEPT", "", {}


def _build_stream_settings(query):
    network = (_first(query, "type", "tcp") or "tcp").lower()
    sni = _first(query, "sni") or _first(query, "host")
    fingerprint = _first(query, "fp", "chrome") or "chrome"

    stream = {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
            "serverName": sni,
            "fingerprint": fingerprint,
            "publicKey": _first(query, "pbk"),
            "shortId": _first(query, "sid"),
            "spiderX": _first(query, "spx", "/") or "/",
        },
    }

    if network in ("xhttp", "splithttp"):
        stream["network"] = "xhttp"
        xhttp = {"path": _first(query, "path", "/") or "/"}
        host = _first(query, "host")
        if host:
            xhttp["host"] = host
        mode = _first(query, "mode")
        if mode:
            xhttp["mode"] = mode
        extra = _parse_extra(query)
        if extra:
            xhttp["extra"] = extra
        stream["xhttpSettings"] = xhttp

    return stream


def _parse_extra(query):
    raw = _first(query, "extra")
    if raw:
        try:
            parsed = json.loads(unquote(raw))
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass

    extra = {}
    padding = _first(query, "x_padding_bytes") or _first(query, "xPaddingBytes")
    if padding:
        extra["xPaddingBytes"] = padding
    return extra


def parse_vless_link(link):
    bucket, key, params = classify_vless_link(link)
    if bucket != "ACCEPT":
        raise VlessLinkError(key, params)

    parts, uuid, address, port, query = _split_link(link)

    user = {"id": uuid, "encryption": _first(query, "encryption", "none") or "none"}
    flow = _first(query, "flow")
    if flow:
        user["flow"] = flow

    outbound = {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": address,
                    "port": int(port),
                    "users": [user],
                }
            ]
        },
        "streamSettings": _build_stream_settings(query),
    }

    config = {
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10808,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
            }
        ],
        "outbounds": [outbound],
    }

    suggested_name = unquote(parts.fragment) if parts.fragment else address
    return config, suggested_name
