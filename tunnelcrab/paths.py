import os
from pathlib import Path
import shutil
import sys


def bundle_root():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


def app_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return bundle_root()


def user_data_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "TunnelCrab"

    return Path.home() / ".tunnelcrab"


def migrate_legacy_data_dir():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return
    new = Path(appdata) / "TunnelCrab"
    old = Path(appdata) / "LoseVPN"
    if new.exists() or not old.exists():
        return
    try:
        old.rename(new)
    except OSError:
        try:
            shutil.copytree(old, new)
        except OSError:
            pass


def branding_path():
    return user_data_dir() / "branding.json"


def branding_seed_path():
    return bundle_root() / "assets" / "branding.seed.json"


def profiles_dir():
    return user_data_dir() / "profiles"


def logs_dir():
    return user_data_dir() / "logs"


def singbox_binary_path():
    executable_name = "sing-box.exe" if sys.platform.startswith("win") else "sing-box"
    return bundle_root() / "core" / executable_name


def xray_binary_path():
    executable_name = "xray.exe" if sys.platform.startswith("win") else "xray"
    return bundle_root() / "core" / executable_name


def core_binary_path():
    return singbox_binary_path()


def webui_dir():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "tunnelcrab" / "webui"
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent / "webui"


def webview_storage_dir():
    return user_data_dir() / "webview"


def icon_path():
    return bundle_root() / "assets" / "tunnelcrab.ico"


def png_icon_path():
    return bundle_root() / "assets" / "tunnelcrab.png"
