import os
import subprocess
import sys
from pathlib import Path


def is_windows():
    return sys.platform.startswith("win")


def is_admin():
    if is_windows():
        import ctypes

        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except OSError:
            return False

    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid and geteuid() == 0)


def _helper_command(extra_args):
    executable = sys.executable
    base = ["--helper", *extra_args]
    if getattr(sys, "frozen", False):
        return executable, base
    pythonw_path = Path(sys.executable).with_name("pythonw.exe")
    if pythonw_path.exists():
        executable = str(pythonw_path)
    return executable, [os.path.abspath(sys.argv[0]), *base]


def launch_helper_elevated(handshake_path, parent_pid):
    if not is_windows():
        return False

    import ctypes

    executable, args = _helper_command(
        ["--handshake", str(handshake_path), "--parent-pid", str(parent_pid)]
    )
    parameters = subprocess.list2cmdline(args)

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        None,
        0,
    )
    return result > 32


def _hwnd(window):
    if not is_windows():
        return None
    try:
        return int(window.native.Handle.ToInt64())
    except Exception:
        return None


def minimize_window(window):
    try:
        window.minimize()
        return True
    except Exception:
        return False


def work_area_size():
    if not is_windows():
        return None
    import ctypes
    from ctypes import wintypes

    try:
        u = ctypes.windll.user32
        work = wintypes.RECT()
        if u.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):
            w = work.right - work.left
            h = work.bottom - work.top
            if w > 0 and h > 0:
                return (w, h)
        cx = u.GetSystemMetrics(0)
        cy = u.GetSystemMetrics(1)
        if cx > 0 and cy > 0:
            return (cx, cy)
    except Exception:
        return None
    return None


def fit_window_to_workarea(width, height, x, y, work_w, work_h, margin=24, min_w=380, min_h=560):
    if work_w:
        width = max(min_w, min(width, work_w - margin))
    if work_h:
        height = max(min_h, min(height, work_h - margin))
    if x is not None and work_w:
        x = max(0, min(x, max(0, work_w - width)))
    if y is not None and work_h:
        y = max(0, min(y, max(0, work_h - height)))
    return width, height, x, y


def centered_position(width, height, work_w, work_h):
    if not work_w or not work_h:
        return (None, None)
    x = max(0, (work_w - width) // 2)
    y = max(0, (work_h - height) // 2)
    return (x, y)


def center_window(window):
    hwnd = _hwnd(window)
    if hwnd is None:
        return
    import ctypes
    from ctypes import wintypes

    try:
        u = ctypes.windll.user32
        u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
        u.MoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        rect = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        work = wintypes.RECT()
        u.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
        x = work.left + ((work.right - work.left) - w) // 2
        y = work.top + ((work.bottom - work.top) - h) // 2
        u.MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)
    except Exception:
        pass
