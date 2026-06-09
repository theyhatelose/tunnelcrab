import subprocess
import sys

from .paths import app_root
from .platform import is_windows

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "TunnelCrab"


def _startup_command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable, "--start-hidden"])

    pythonw = app_root() / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        pythonw = app_root() / ".venv" / "Scripts" / "python.exe"

    app_script = app_root() / "app.pyw"
    return subprocess.list2cmdline([str(pythonw), str(app_script), "--start-hidden"])


def is_startup_enabled():
    if not is_windows():
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def set_startup_enabled(enabled):
    if not is_windows():
        return

    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
