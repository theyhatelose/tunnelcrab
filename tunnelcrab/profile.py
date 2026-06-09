import copy
from dataclasses import dataclass, field
import ipaddress
import json


class ProfileError(RuntimeError):
    pass


@dataclass
class RealityProfile:
    server: str
    server_port: int
    uuid: str
    flow: str
    network: str
    server_name: str
    public_key: str
    short_id: str
    fingerprint: str
    spider_x: str
    local_proxy_port: int
    security: str = "reality"
    interface_name: str = "TunnelCrab"
    raw_config: dict = field(default_factory=dict)

    @property
    def http_proxy_port(self):
        return self.local_proxy_port + 1


def load_profile(config_path):
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    outbounds = config.get("outbounds") or []
    if not outbounds:
        raise ProfileError("В config.json нет outbound-настроек.")

    outbound = outbounds[0]
    if outbound.get("protocol") != "vless":
        raise ProfileError("Сейчас поддерживается только профиль VLESS + Reality.")

    vnext_items = outbound.get("settings", {}).get("vnext") or []
    if not vnext_items:
        raise ProfileError("В outbound отсутствует vnext.")

    server = vnext_items[0]
    users = server.get("users") or []
    if not users:
        raise ProfileError("В outbound отсутствует пользователь VLESS.")

    stream_settings = outbound.get("streamSettings", {})
    security = (stream_settings.get("security") or "reality").strip()
    reality_settings = stream_settings.get("realitySettings", {})
    tls_settings = stream_settings.get("tlsSettings", {})

    server_name = (
        reality_settings.get("serverName")
        or tls_settings.get("serverName")
        or ""
    ).strip()
    fingerprint = (
        reality_settings.get("fingerprint")
        or tls_settings.get("fingerprint")
        or "chrome"
    ).strip() or "chrome"

    inbound_port = 10808
    for inbound in config.get("inbounds", []):
        if inbound.get("protocol") == "socks":
            inbound_port = inbound.get("port", 10808)
            break

    profile = RealityProfile(
        server=server.get("address", "").strip(),
        server_port=int(server.get("port", 443)),
        uuid=users[0].get("id", "").strip(),
        flow=users[0].get("flow", "").strip(),
        network=stream_settings.get("network", "tcp"),
        server_name=server_name,
        public_key=reality_settings.get("publicKey", "").strip(),
        short_id=reality_settings.get("shortId", "").strip(),
        fingerprint=fingerprint,
        spider_x=reality_settings.get("spiderX", "/").strip() or "/",
        local_proxy_port=int(inbound_port),
        security=security,
        raw_config=config,
    )

    required_fields = {
        "address": profile.server,
        "uuid": profile.uuid,
        "serverName": profile.server_name,
    }
    if security == "reality":
        required_fields["publicKey"] = profile.public_key

    missing_fields = [name for name, value in required_fields.items() if not value]
    if missing_fields:
        raise ProfileError(
            "В конфиге профиля не хватает обязательных полей: "
            + ", ".join(missing_fields)
        )

    return profile


_XRAY_ONLY_NETWORKS = {"xhttp", "splithttp"}


def profile_requires_xray(profile):
    return (profile.network or "tcp").strip().lower() in _XRAY_ONLY_NETWORKS


_RU_TLDS = ["ru", "su", "xn--p1ai"]
_RU_SERVICE_DOMAINS = [
    "yandex.net", "yastatic.net", "ya.ru", "vk.com", "vk.ru", "vkontakte.ru",
    "userapi.com", "vk-cdn.net", "mail.ru", "list.ru", "ok.ru", "mradar.ru",
    "gosuslugi.ru", "sberbank.ru", "sber.ru", "wildberries.ru", "wbbasket.ru",
    "ozon.ru", "ozone.ru", "avito.ru", "avito.st", "kinopoisk.ru", "2gis.ru",
    "rambler.ru", "rbc.ru", "ria.ru", "gismeteo.ru", "hh.ru", "drom.ru",
    "tinkoff.ru", "alfabank.ru", "vtb.ru", "mos.ru", "nalog.ru", "rt.ru",
    "dzen.ru", "rutube.ru", "rustore.ru", "1c.ru",
]

_SINGBOX_RU_DOMAIN_SUFFIXES = ["." + tld for tld in _RU_TLDS] + _RU_SERVICE_DOMAINS

_XRAY_RU_DOMAINS = ["domain:" + d for d in (_RU_TLDS + _RU_SERVICE_DOMAINS)]

_SINGBOX_GEOIP_RU_RULESET = {
    "type": "remote",
    "tag": "geoip-ru",
    "format": "binary",
    "url": "https://raw.githubusercontent.com/SagerNet/sing-geoip/rule-set/geoip-ru.srs",
    "download_detour": "proxy",
    "update_interval": "168h",
}


def _apply_singbox_bypass(route, routing):
    if routing != "bypass_ru":
        return route
    route.setdefault("rules", []).extend(
        [
            {
                "domain_suffix": _SINGBOX_RU_DOMAIN_SUFFIXES,
                "action": "route",
                "outbound": "direct",
            },
            {"rule_set": "geoip-ru", "action": "route", "outbound": "direct"},
        ]
    )
    route["rule_set"] = [_SINGBOX_GEOIP_RU_RULESET]
    return route


def _vless_outbound(profile):
    outbound = {
        "type": "vless",
        "tag": "proxy",
        "server": profile.server,
        "server_port": profile.server_port,
        "uuid": profile.uuid,
        "network": profile.network or "tcp",
        "packet_encoding": "xudp",
        "tls": {
            "enabled": True,
            "server_name": profile.server_name,
            "utls": {
                "enabled": True,
                "fingerprint": profile.fingerprint or "chrome",
            },
            "reality": {
                "enabled": True,
                "public_key": profile.public_key,
                "short_id": profile.short_id,
            },
        },
    }

    if profile.flow:
        outbound["flow"] = profile.flow

    return outbound


def _singbox_tun_inbound(profile):
    return {
        "type": "tun",
        "tag": "tun-in",
        "interface_name": profile.interface_name,
        "address": [
            "172.19.0.1/30",
            "fdfe:dcba:9876::1/126",
        ],
        "mtu": 1500,
        "auto_route": True,
        "strict_route": False,
        "stack": "system",
        "route_exclude_address": [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "127.0.0.0/8",
            "fc00::/7",
            "fe80::/10",
            "::1/128",
        ],
    }


def _singbox_dns_via_proxy():
    return {
        "servers": [
            {
                "type": "https",
                "tag": "remote-dns",
                "server": "1.1.1.1",
                "server_port": 443,
                "path": "/dns-query",
                "tls": {
                    "enabled": True,
                    "server_name": "cloudflare-dns.com",
                },
                "detour": "proxy",
            }
        ],
        "final": "remote-dns",
        "strategy": "prefer_ipv4",
        "independent_cache": True,
    }


def _singbox_tun_route():
    return {
        "rules": [
            {"action": "sniff"},
            {"protocol": "dns", "action": "hijack-dns"},
            {"ip_is_private": True, "action": "route", "outbound": "direct"},
        ],
        "auto_detect_interface": True,
        "final": "proxy",
    }


def _maybe_ip(value):
    try:
        ipaddress.ip_address((value or "").strip())
        return value.strip()
    except ValueError:
        return None


def _singbox_bridge_route(profile, server_ip=None):
    rules = [
        {"action": "sniff"},
        {"protocol": "dns", "action": "hijack-dns"},
        {"process_name": ["xray.exe"], "action": "route", "outbound": "direct"},
    ]

    target_ip = server_ip or _maybe_ip(profile.server)
    if target_ip:
        suffix = "/128" if ":" in target_ip else "/32"
        rules.append(
            {"ip_cidr": [target_ip + suffix], "action": "route", "outbound": "direct"}
        )

    rules.append({"ip_is_private": True, "action": "route", "outbound": "direct"})

    return {
        "rules": rules,
        "auto_detect_interface": True,
        "final": "proxy",
    }


def build_singbox_config(profile, mode="tun", routing="global"):
    if mode == "proxy":
        proxy_route = {
            "rules": [
                {"action": "sniff"},
                {"ip_is_private": True, "action": "route", "outbound": "direct"},
            ],
            "auto_detect_interface": True,
            "final": "proxy",
        }
        return {
            "log": {"level": "info", "timestamp": True},
            "dns": _singbox_dns_via_proxy(),
            "inbounds": [
                {
                    "type": "mixed",
                    "tag": "mixed-in",
                    "listen": "127.0.0.1",
                    "listen_port": profile.local_proxy_port,
                    "set_system_proxy": False,
                }
            ],
            "outbounds": [
                _vless_outbound(profile),
                {"type": "direct", "tag": "direct"},
            ],
            "route": _apply_singbox_bypass(proxy_route, routing),
        }

    return {
        "log": {"level": "info", "timestamp": True},
        "dns": _singbox_dns_via_proxy(),
        "inbounds": [
            _singbox_tun_inbound(profile),
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": profile.local_proxy_port,
                "set_system_proxy": False,
            },
        ],
        "outbounds": [
            _vless_outbound(profile),
            {"type": "direct", "tag": "direct"},
        ],
        "route": _apply_singbox_bypass(_singbox_tun_route(), routing),
    }


def build_singbox_tun_bridge_config(profile, server_ip=None, routing="global"):
    return {
        "log": {"level": "warn", "timestamp": True},
        "dns": _singbox_dns_via_proxy(),
        "inbounds": [_singbox_tun_inbound(profile)],
        "outbounds": [
            {
                "type": "socks",
                "tag": "proxy",
                "server": "127.0.0.1",
                "server_port": profile.local_proxy_port,
                "version": "5",
            },
            {"type": "direct", "tag": "direct"},
        ],
        "route": _apply_singbox_bypass(_singbox_bridge_route(profile, server_ip), routing),
    }


def _pin_outbound_address(outbound, server_ip):
    if not server_ip:
        return
    try:
        vnext = outbound["settings"]["vnext"]
        if vnext:
            vnext[0]["address"] = server_ip
    except (KeyError, TypeError, IndexError):
        pass


def _xray_proxy_outbound(profile, server_ip=None):
    raw_outbounds = (profile.raw_config or {}).get("outbounds") or []
    if raw_outbounds:
        outbound = copy.deepcopy(raw_outbounds[0])
        outbound["tag"] = "proxy"
        _pin_outbound_address(outbound, server_ip)
        return outbound

    return {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": server_ip or profile.server,
                    "port": profile.server_port,
                    "users": [
                        {
                            "id": profile.uuid,
                            "encryption": "none",
                            "flow": profile.flow,
                        }
                    ],
                }
            ]
        },
        "streamSettings": {
            "network": profile.network or "tcp",
            "security": "reality",
            "realitySettings": {
                "fingerprint": profile.fingerprint or "chrome",
                "serverName": profile.server_name,
                "publicKey": profile.public_key,
                "shortId": profile.short_id,
                "spiderX": profile.spider_x or "/",
            },
        },
    }


def build_xray_config(profile, mode="tun", server_ip=None, routing="global"):
    inbounds = [
        {
            "tag": "socks-in",
            "listen": "127.0.0.1",
            "port": profile.local_proxy_port,
            "protocol": "socks",
            "settings": {"auth": "noauth", "udp": True, "ip": "127.0.0.1"},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        }
    ]

    if mode == "proxy":
        inbounds.append(
            {
                "tag": "http-in",
                "listen": "127.0.0.1",
                "port": profile.http_proxy_port,
                "protocol": "http",
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
            }
        )

    rules = [
        {
            "type": "field",
            "ip": [
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
                "127.0.0.0/8",
                "169.254.0.0/16",
                "::1/128",
                "fc00::/7",
                "fe80::/10",
            ],
            "outboundTag": "direct",
        },
    ]
    if routing == "bypass_ru":
        rules.insert(
            0,
            {"type": "field", "domain": _XRAY_RU_DOMAINS, "outboundTag": "direct"},
        )

    return {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
        "outbounds": [
            _xray_proxy_outbound(profile, server_ip),
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": rules,
        },
    }
