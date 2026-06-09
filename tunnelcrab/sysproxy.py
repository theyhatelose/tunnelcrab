from __future__ import annotations

import sys

from .paths import user_data_dir

_INTERNET_OPTION_SETTINGS_CHANGED = 39
_INTERNET_OPTION_REFRESH = 37

_INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

_BYPASS = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;192.168.*;<local>"


def _is_windows():
    return sys.platform.startswith("win")


def _proxy_flag_path():
    return user_data_dir() / "proxy_active"


def _mark_proxy_active(active):
    path = _proxy_flag_path()
    try:
        if active:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("1", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    except OSError:
        pass


def _notify_wininet():
    import ctypes

    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(0, _INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    wininet.InternetSetOptionW(0, _INTERNET_OPTION_REFRESH, 0, 0)


def enable_system_proxy(host, port):
    if not _is_windows():
        return False

    import winreg

    proxy_server = f"{host}:{int(port)}"
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        _INTERNET_SETTINGS_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, _BYPASS)

    _mark_proxy_active(True)
    _notify_wininet()
    return True


def disable_system_proxy():
    if not _is_windows():
        return False

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _INTERNET_SETTINGS_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            for value_name in ("ProxyServer", "ProxyOverride"):
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
    except OSError:
        return False

    _mark_proxy_active(False)
    _notify_wininet()
    return True


def cleanup_stale_proxy():
    if not _is_windows():
        return False
    if not _proxy_flag_path().exists():
        return False
    return disable_system_proxy()
