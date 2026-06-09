import json
import os
from pathlib import Path
import secrets
import threading
import time

from . import ipc
from .coreproc import CoreMissingError, CoreProcessManager, PrivilegeError, RuntimeErrorBase, kill_stray_cores
from .ipc import IpcError, IpcServer
from .paths import profiles_dir, user_data_dir
from .planbuilder import build_plan
from .platform import launch_helper_elevated
from .profile import load_profile


_VALID_CORES = {"sing-box", "xray"}
_VALID_MODES = {"tun", "proxy"}
_VALID_ROUTING = {"global", "bypass_ru"}


def _resolve_profile_path(file_name):
    name = str(file_name or "")
    if not name or name != os.path.basename(name) or name in (".", ".."):
        raise RuntimeErrorBase("Недопустимое имя профиля")
    path = profiles_dir() / name
    if not path.is_file():
        raise RuntimeErrorBase("Профиль для подключения не найден")
    return path


def _plan_from_message(message):
    core = message.get("core")
    mode = message.get("mode")
    routing = message.get("routing")
    if core not in _VALID_CORES or mode not in _VALID_MODES or routing not in _VALID_ROUTING:
        raise RuntimeErrorBase("Недопустимые параметры подключения")
    profile = load_profile(_resolve_profile_path(message.get("profile_file_name")))
    plan, _ = build_plan(profile, core, mode, routing)
    return plan


def _helper_dir():
    folder = user_data_dir() / "helper"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _handshake_path():
    return _helper_dir() / "handshake.json"


def _hlog(message):
    try:
        with open(_helper_dir() / "helper.log", "a", encoding="utf-8") as handle:
            handle.write(f"{time.time():.0f} {message}\n")
    except Exception:
        pass


def _atomic_write_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def _parse_args(argv):
    result = {}
    items = argv[1:]
    for index, item in enumerate(items):
        if item == "--handshake" and index + 1 < len(items):
            result["handshake"] = items[index + 1]
        elif item == "--parent-pid" and index + 1 < len(items):
            result["parent_pid"] = items[index + 1]
    return result


def _parent_alive(pid):
    try:
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        code = wintypes.DWORD()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        if not ok:
            return False
        return code.value == STILL_ACTIVE
    except Exception:
        return True


def run_helper(argv):
    args = _parse_args(argv)
    handshake = Path(args.get("handshake") or _handshake_path())
    parent_pid = args.get("parent_pid")

    try:
        initial = json.loads(handshake.read_text(encoding="utf-8"))
        token = initial["token"]
    except Exception as exc:
        _hlog(f"handshake read failed: {exc}")
        return

    kill_stray_cores()
    manager = CoreProcessManager()
    state = {"connected_at": None}

    def handler(message):
        cmd = message.get("cmd")
        if cmd in ("hello", "ping"):
            return {"ok": True}
        if cmd == "connect":
            try:
                manager.start(_plan_from_message(message))
                state["connected_at"] = time.time()
                _hlog("connect ok")
                return {"ok": True}
            except CoreMissingError as exc:
                _hlog(f"connect missing: {exc}")
                return {"ok": False, "error": str(exc), "kind": "missing"}
            except Exception as exc:
                _hlog(f"connect error: {exc}")
                return {"ok": False, "error": str(exc), "kind": "core"}
        if cmd == "status":
            return {"ok": True, "running": manager.is_running(), "error": manager.poll_error()}
        if cmd == "logtail":
            return {"ok": True, "lines": manager.log_tail(int(message.get("limit", 10)))}
        if cmd == "stopcore":
            _hlog("stopcore received")
            manager.stop()
            return {"ok": True}
        if cmd in ("disconnect", "shutdown"):
            _hlog(f"{cmd} received")
            manager.stop()
            server.stop()
            return {"ok": True}
        return {"ok": False, "error": "unknown_cmd"}

    server = IpcServer(token, handler)
    _atomic_write_json(handshake, {"token": token, "port": server.port, "ready": True})
    _hlog(f"listening on {server.port} parent={parent_pid}")

    def watchdog():
        idle_deadline = time.time() + 120
        while not server._stop.is_set():
            time.sleep(2)
            if parent_pid and not _parent_alive(parent_pid):
                _hlog("parent gone, shutting down")
                break
            if manager.is_running():
                idle_deadline = time.time() + 120
            elif state["connected_at"] is None and time.time() > idle_deadline:
                _hlog("idle without connect, shutting down")
                break
        manager.stop()
        server.stop()

    threading.Thread(target=watchdog, daemon=True).start()

    try:
        server.serve_forever()
    finally:
        manager.stop()
        try:
            handshake.unlink()
        except OSError:
            pass
        _hlog("exited")


class HelperClient:
    def __init__(self):
        self.port = None
        self.token = None

    def is_active(self):
        if self.port is None:
            return False
        try:
            resp = ipc.request(self.port, self.token, {"cmd": "ping"}, timeout=3)
            return bool(resp.get("ok"))
        except IpcError:
            self.port = None
            return False

    def ensure_started(self, parent_pid):
        if self.is_active():
            return

        token = secrets.token_hex(32)
        handshake = _handshake_path()
        _atomic_write_json(handshake, {"token": token})

        if not launch_helper_elevated(handshake, parent_pid):
            raise PrivilegeError(
                "Доступ администратора не выдан\n"
                "Подтверди окно UAC, чтобы поднять общесистемный режим"
            )

        deadline = time.time() + 25
        port = None
        while time.time() < deadline:
            try:
                data = json.loads(handshake.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            if data.get("ready") and data.get("port"):
                port = int(data["port"])
                break
            time.sleep(0.25)

        if port is None:
            raise RuntimeErrorBase("Помощник с правами не запустился вовремя")

        self.port = port
        self.token = token
        resp = ipc.request(port, token, {"cmd": "hello"}, timeout=5)
        if not resp.get("ok"):
            self.port = None
            self.token = None
            raise RuntimeErrorBase("Помощник с правами не ответил")

    def connect(self, profile_file_name, core, mode, routing):
        return ipc.request(
            self.port,
            self.token,
            {
                "cmd": "connect",
                "profile_file_name": profile_file_name,
                "core": core,
                "mode": mode,
                "routing": routing,
            },
            timeout=90,
        )

    def status(self):
        try:
            return ipc.request(self.port, self.token, {"cmd": "status"}, timeout=6)
        except IpcError:
            return {"ok": False, "running": False, "error": None}

    def logtail(self, limit=10):
        try:
            resp = ipc.request(self.port, self.token, {"cmd": "logtail", "limit": limit}, timeout=6)
            return resp.get("lines") or []
        except IpcError:
            return []

    def stop_core(self):
        if self.port is None:
            return
        try:
            ipc.request(self.port, self.token, {"cmd": "stopcore"}, timeout=10)
        except IpcError:
            pass

    def disconnect(self):
        if self.port is None:
            return
        try:
            ipc.request(self.port, self.token, {"cmd": "disconnect"}, timeout=10)
        except IpcError:
            pass
        self.port = None
        self.token = None
