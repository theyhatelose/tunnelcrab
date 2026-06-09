from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

from .coreproc import RuntimeErrorBase
from .profile import (
    build_singbox_config,
    build_singbox_tun_bridge_config,
    build_xray_config,
)


def _resolve_via_doh(host):
    for url in (
        f"https://1.1.1.1/dns-query?name={host}&type=A",
        f"https://8.8.8.8/resolve?name={host}&type=A",
    ):
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/dns-json", "User-Agent": "TunnelCrab"},
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
            for answer in data.get("Answer", []):
                if answer.get("type") == 1 and answer.get("data"):
                    return answer["data"]
        except (OSError, urllib.error.URLError, ValueError, TimeoutError):
            continue
    return None


def resolve_server_ip(profile):
    try:
        infos = socket.getaddrinfo(
            profile.server,
            int(profile.server_port or 443),
            type=socket.SOCK_STREAM,
        )
        for family in (socket.AF_INET, socket.AF_INET6):
            for info in infos:
                if info[0] == family:
                    return info[4][0]
        if infos:
            return infos[0][4][0]
    except OSError:
        pass

    doh_ip = _resolve_via_doh(profile.server)
    if doh_ip:
        return doh_ip

    raise RuntimeErrorBase(
        f"Не удалось определить адрес сервера {profile.server}.\n"
        "Похоже, на компьютере барахлит DNS (часто из-за другого включённого VPN).\n"
        "Помогает перезагрузка, либо выбери сервер по IP (Германия / Финляндия · Helsinki)."
    )


def build_plan(profile, core, mode, routing):
    steps = []
    proxy_port = None
    if core == "xray":
        server_ip = resolve_server_ip(profile) if mode == "tun" else None
        steps.append({
            "name": "xray",
            "check": "xray",
            "config_filename": "xray.json",
            "config_json": json.dumps(
                build_xray_config(profile, mode, server_ip, routing=routing),
                ensure_ascii=False,
                indent=2,
            ),
        })
        if mode == "tun":
            steps.append({
                "name": "sing-box",
                "check": "singbox",
                "config_filename": "sing-box-bridge.json",
                "config_json": json.dumps(
                    build_singbox_tun_bridge_config(profile, server_ip, routing=routing),
                    ensure_ascii=False,
                    indent=2,
                ),
            })
        else:
            proxy_port = profile.http_proxy_port
    else:
        steps.append({
            "name": "sing-box",
            "check": "singbox",
            "config_filename": "sing-box.json",
            "config_json": json.dumps(
                build_singbox_config(profile, mode, routing=routing),
                ensure_ascii=False,
                indent=2,
            ),
        })
        if mode == "proxy":
            proxy_port = profile.local_proxy_port
    return {"steps": steps}, proxy_port
