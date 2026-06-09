from __future__ import annotations

from .platform import is_windows

_RUNTIME_KEY = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_RUNTIME_KEY_WOW = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def _pv_present(root, subkey):
    import winreg

    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "pv")
    except OSError:
        return False
    return bool(value) and value != "0.0.0.0"


def is_runtime_present():
    if not is_windows():
        return True
    import winreg

    return (
        _pv_present(winreg.HKEY_LOCAL_MACHINE, _RUNTIME_KEY_WOW)
        or _pv_present(winreg.HKEY_LOCAL_MACHINE, _RUNTIME_KEY)
        or _pv_present(winreg.HKEY_CURRENT_USER, _RUNTIME_KEY)
    )


def show_missing_message():
    if not is_windows():
        return
    import ctypes
    import webbrowser

    from .branding import load_branding, pick

    name = pick(load_branding().get("app_name")) or "TunnelCrab"

    mb_yesno = 0x04
    mb_iconwarning = 0x30
    id_yes = 6
    text = (
        f"{name} requires Microsoft Edge WebView2 Runtime.\n"
        f"Please install it and restart {name}.\n\n"
        f"{name} требует Microsoft Edge WebView2 Runtime.\n"
        f"Установите его и перезапустите {name}.\n\n"
        "Open the download page now? / Открыть страницу загрузки?"
    )
    result = ctypes.windll.user32.MessageBoxW(None, text, name, mb_yesno | mb_iconwarning)
    if result == id_yes:
        try:
            webbrowser.open(DOWNLOAD_URL)
        except Exception:
            pass
