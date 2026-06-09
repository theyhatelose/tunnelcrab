import json
from dataclasses import dataclass
from datetime import datetime
import os
import socket
import threading
import time
import urllib.error
import urllib.request

try:
    import psutil
except ImportError:
    psutil = None

from .coreproc import (
    CoreMissingError,
    CoreProcessManager,
    PrivilegeError,
    RuntimeErrorBase,
    UnsupportedPlatformError,
    is_stale_tunnel_error,
    kill_stray_cores as _kill_stray_cores,
    missing_binaries,
)


class ConnectionCancelled(RuntimeErrorBase):
    pass
from .helper import HelperClient
from .planbuilder import build_plan
from .platform import is_admin, is_windows
from .profile import load_profile
from .sysproxy import disable_system_proxy, enable_system_proxy


_TIMING_MAX_BYTES = 512 * 1024


def _timing_path():
    from .paths import logs_dir, user_data_dir

    folder = logs_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "connect-timing.log"

    legacy = user_data_dir() / "connect-timing.log"
    if legacy.exists():
        try:
            if path.exists():
                legacy.unlink()
            else:
                legacy.replace(path)
        except OSError:
            pass
    return path


def _append_timing(path, text):
    try:
        if path.exists() and path.stat().st_size > _TIMING_MAX_BYTES:
            path.write_text("", encoding="utf-8")
    except OSError:
        pass
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _write_timing(marks):
    if not marks:
        return
    try:
        stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        body = " ".join(f"{name}={ms:.0f}ms" for name, ms in marks)
        _append_timing(_timing_path(), f"{stamp} {body}\n")
    except Exception:
        pass


def log_event(name, detail=""):
    try:
        stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        line = f"{stamp} event {name}" + (f" {detail}" if detail else "")
        _append_timing(_timing_path(), line + "\n")
    except Exception:
        pass


@dataclass
class ConnectionReport:
    before_ip: str | None
    after_ip: str | None
    ping_ms: int | None
    quality: str
    connected_at: float
    profile_name: str
    server: str
    dns_protected: bool = True


@dataclass
class LiveMetrics:
    ping_ms: int | None
    quality: str
    download_rate: float
    upload_rate: float
    downloaded_total: int
    uploaded_total: int
    session_seconds: int
    interface_name: str | None


@dataclass
class SiteCheckResult:
    name: str
    url: str
    ok: bool
    detail: str


@dataclass
class UpdateInfo:
    update_available: bool
    latest_version: str
    download_url: str
    notes: str


@dataclass
class _TrafficPoint:
    downloaded_total: int
    uploaded_total: int
    captured_at: float


class LocalController:
    def __init__(self):
        self.manager = CoreProcessManager()

    def start(self, plan):
        self.manager.start(plan)

    def is_running(self):
        return self.manager.is_running()

    def poll_error(self):
        return self.manager.poll_error()

    def read_log(self):
        return self.manager.read_log()

    def log_tail(self, limit=10):
        return self.manager.log_tail(limit)

    def stop(self):
        self.manager.stop()

    def stop_core(self):
        self.manager.stop()


class RemoteController:
    def __init__(self, client, parent_pid):
        self.client = client
        self.parent_pid = parent_pid

    def start(self, profile_file_name, core, mode, routing):
        self.client.ensure_started(self.parent_pid)
        response = self.client.connect(profile_file_name, core, mode, routing)
        if not response.get("ok"):
            message = response.get("error") or "Не удалось запустить ядро"
            if response.get("kind") == "missing":
                raise CoreMissingError(message)
            raise RuntimeErrorBase(message)

    def is_running(self):
        return bool(self.client.status().get("running"))

    def poll_error(self):
        return self.client.status().get("error")

    def read_log(self):
        return "\n".join(self.client.logtail(50))

    def log_tail(self, limit=10):
        return self.client.logtail(limit)

    def stop(self):
        self.client.disconnect()

    def stop_core(self):
        self.client.stop_core()


class VpnRuntime:
    def __init__(self):
        self.controller = None
        self.helper = HelperClient()
        self.active_core = "sing-box"
        self.active_mode = "tun"
        self.active_routing = "global"
        self.active_profile_name = ""
        self.active_server = ""
        self.active_server_port = 443
        self.interface_name = "TunnelCrab"
        self.connected_at = None
        self._system_proxy_active = False
        self._traffic_start = None
        self._last_traffic_point = None
        self._last_ping = None
        self._last_ping_at = 0.0
        self._op_lock = threading.RLock()
        self._cancel = threading.Event()

    @staticmethod
    def kill_stray_cores():
        if is_windows():
            _kill_stray_cores()

    def request_cancel(self):
        self._cancel.set()
        log_event("cancel_requested")

    def _check_cancel(self):
        if self._cancel.is_set():
            raise ConnectionCancelled("Подключение отменено")

    def _cancellable_sleep(self, seconds):
        end = time.time() + seconds
        while True:
            remaining = end - time.time()
            if remaining <= 0:
                return
            self._check_cancel()
            time.sleep(min(0.25, remaining))

    @staticmethod
    def _wait_port_free(port, timeout=4.0):
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            try:
                with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
                    pass
            except OSError:
                return (time.perf_counter() - start) * 1000
            time.sleep(0.2)
        return (time.perf_counter() - start) * 1000

    def _make_controller(self, mode):
        if mode == "tun" and not is_admin():
            return RemoteController(self.helper, os.getpid())
        return LocalController()

    def connect(self, profile_path, profile_name="", core="sing-box", mode="tun", routing="global"):
        if not is_windows():
            raise UnsupportedPlatformError(
                "Эта версия живёт только в Windows\n"
                "WSL не умеет переключать трафик обычных Windows-приложений"
            )

        self.active_core = core
        self.active_mode = mode
        self.active_routing = routing

        self._cancel.clear()
        log_event("connect_requested", f"mode={mode} core={core}")

        _t0 = time.perf_counter()
        _marks = []

        def _mark(name):
            _marks.append((name, (time.perf_counter() - _t0) * 1000))

        profile = load_profile(profile_path)
        self.interface_name = profile.interface_name if mode == "tun" else ""

        plan, proxy_port = build_plan(profile, core, mode, routing)
        _mark("build_plan")
        missing = missing_binaries(plan)
        if missing:
            raise CoreMissingError(
                "Не нашёл нужные файлы ядра в папке core:\n" + "\n".join(missing)
            )

        self._check_cancel()
        before_ip = self.probe_public_ip()
        _mark("before_ip")
        controller = self._make_controller(mode)

        self._op_lock.acquire()
        try:
            self._check_cancel()
            if mode == "proxy" and proxy_port:
                _marks.append(("port_wait", self._wait_port_free(proxy_port)))
            if isinstance(controller, RemoteController):
                controller.start(os.path.basename(profile_path), core, mode, routing)
            else:
                controller.start(plan)
            self.controller = controller
            _mark("core_start")
            log_event("core_start", f"mode={mode}")

            after_proxy = None
            if mode == "proxy" and proxy_port:
                enable_system_proxy("127.0.0.1", proxy_port)
                self._system_proxy_active = True
                after_proxy = f"http://127.0.0.1:{proxy_port}"

            _mark("proxy_setup")
            self._cancellable_sleep(2)
            startup_error = controller.poll_error()
            if startup_error:
                raise RuntimeErrorBase(startup_error)

            after_ip = None
            deadline = time.time() + 8
            while True:
                self._check_cancel()
                startup_error = controller.poll_error()
                if startup_error:
                    raise RuntimeErrorBase(startup_error)
                probed = self.probe_public_ip(proxy=after_proxy)
                if probed:
                    after_ip = probed
                    if probed != before_ip:
                        break
                if time.time() >= deadline:
                    break
                self._cancellable_sleep(1.5)

            _mark("ip_ready")
            if before_ip and after_ip and before_ip == after_ip:
                raise RuntimeErrorBase(
                    f"Подключение поднялось не до конца\nIP пока остался таким же: {after_ip}"
                )

            self.active_profile_name = profile_name or "Профиль"
            self.active_server = profile.server
            self.active_server_port = profile.server_port
            self.connected_at = time.time()
            self._traffic_start = self._read_traffic_point()
            self._last_traffic_point = self._traffic_start

            ping_ms = self.measure_ping(profile.server, profile.server_port)
            self._last_ping = ping_ms
            self._last_ping_at = time.time()
            _mark("ping")
            log_event("connected", f"ip={after_ip}")

            return ConnectionReport(
                before_ip=before_ip,
                after_ip=after_ip,
                ping_ms=ping_ms,
                quality=self.classify_quality(ping_ms),
                connected_at=self.connected_at,
                profile_name=self.active_profile_name,
                server=profile.server,
                dns_protected=True,
            )
        except ConnectionCancelled:
            log_event("connect_cancelled")
            self.disconnect(keep_helper=True)
            raise
        except Exception as exc:
            log_event("core_error", "stale_tunnel" if is_stale_tunnel_error(str(exc)) else type(exc).__name__)
            self.disconnect(keep_helper=True)
            raise
        finally:
            self._op_lock.release()
            _write_timing(_marks)

    def disconnect(self, keep_helper=False):
        self._cancel.set()
        log_event("cleanup_start", f"keep_helper={keep_helper}")
        with self._op_lock:
            if self.controller is not None:
                try:
                    if keep_helper:
                        self.controller.stop_core()
                    else:
                        self.controller.stop()
                except Exception:
                    pass
                self.controller = None

            if self._system_proxy_active:
                disable_system_proxy()
                self._system_proxy_active = False

            self.active_profile_name = ""
            self.active_server = ""
            self.active_server_port = 443
            self.connected_at = None
            self._traffic_start = None
            self._last_traffic_point = None
            self._last_ping = None
            self._last_ping_at = 0.0
        log_event("cleanup_finished")

    def is_running(self):
        return self.controller is not None and self.controller.is_running()

    def poll_error(self):
        if self.controller is None:
            return None
        return self.controller.poll_error()

    def read_log(self):
        if self.controller is None:
            return ""
        return self.controller.read_log()

    def log_tail(self, limit=10):
        if self.controller is None:
            return []
        return self.controller.log_tail(limit)

    @staticmethod
    def probe_public_ip(proxy=None):
        try:
            if proxy:
                handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                opener = urllib.request.build_opener(handler)
                with opener.open("https://api.ipify.org", timeout=8) as response:
                    return response.read().decode("utf-8").strip()
            with urllib.request.urlopen("https://api.ipify.org", timeout=8) as response:
                return response.read().decode("utf-8").strip()
        except (OSError, urllib.error.URLError, TimeoutError):
            return None

    @staticmethod
    def internet_available():
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=2).close()
            return True
        except OSError:
            return False

    @staticmethod
    def measure_ping(host, port=443, attempts=2):
        results = []
        for _ in range(attempts):
            started = time.perf_counter()
            try:
                sock = socket.create_connection((host, int(port)), timeout=2.5)
                sock.close()
            except OSError:
                continue
            elapsed = (time.perf_counter() - started) * 1000
            results.append(elapsed)

        if not results:
            return None

        return int(sum(results) / len(results))

    @staticmethod
    def classify_quality(ping_ms):
        if ping_ms is None:
            return "Неизвестно"
        if ping_ms <= 70:
            return "Хорошо"
        if ping_ms <= 150:
            return "Нормально"
        return "Тяжеловато"

    def _read_traffic_point(self):
        if psutil is None:
            return None

        counters = psutil.net_io_counters(pernic=True)
        if not counters:
            return None

        target_name = (self.interface_name or "").lower()
        selected_name = None
        selected_stats = None

        for name, stats in counters.items():
            lowered = name.lower()
            if target_name and target_name in lowered:
                selected_name = name
                selected_stats = stats
                break

        if selected_stats is None:
            for name, stats in counters.items():
                lowered = name.lower()
                if "lose" in lowered or "tun" in lowered or "wintun" in lowered:
                    selected_name = name
                    selected_stats = stats
                    break

        if selected_stats is None:
            return None

        return _TrafficPoint(
            downloaded_total=int(selected_stats.bytes_recv),
            uploaded_total=int(selected_stats.bytes_sent),
            captured_at=time.time(),
        ), selected_name

    def live_metrics(self):
        if not self.connected_at:
            return LiveMetrics(
                ping_ms=None,
                quality="Неизвестно",
                download_rate=0.0,
                upload_rate=0.0,
                downloaded_total=0,
                uploaded_total=0,
                session_seconds=0,
                interface_name=None,
            )

        current = self._read_traffic_point()
        interface_name = None
        downloaded_total = 0
        uploaded_total = 0
        download_rate = 0.0
        upload_rate = 0.0

        if current is not None:
            point, interface_name = current
            baseline = self._traffic_start[0] if self._traffic_start else point
            last_point = self._last_traffic_point[0] if self._last_traffic_point else point
            delta_time = max(point.captured_at - last_point.captured_at, 1e-6)
            download_rate = max(0.0, point.downloaded_total - last_point.downloaded_total) / delta_time
            upload_rate = max(0.0, point.uploaded_total - last_point.uploaded_total) / delta_time
            downloaded_total = max(0, point.downloaded_total - baseline.downloaded_total)
            uploaded_total = max(0, point.uploaded_total - baseline.uploaded_total)
            self._last_traffic_point = current

        if time.time() - self._last_ping_at >= 20 and self.active_server:
            self._last_ping = self.measure_ping(self.active_server, self.active_server_port)
            self._last_ping_at = time.time()

        return LiveMetrics(
            ping_ms=self._last_ping,
            quality=self.classify_quality(self._last_ping),
            download_rate=download_rate,
            upload_rate=upload_rate,
            downloaded_total=downloaded_total,
            uploaded_total=uploaded_total,
            session_seconds=int(time.time() - self.connected_at),
            interface_name=interface_name,
        )

    def site_checks(self, sites):
        results = []
        for item in sites:
            name = item.get("name") or item.get("url") or "Сайт"
            url = item.get("url") or ""
            detail = "Не удалось проверить"
            ok = False
            try:
                request = urllib.request.Request(
                    url,
                    headers={"User-Agent": "TunnelCrab/0.2"},
                )
                with urllib.request.urlopen(request, timeout=8) as response:
                    ok = 200 <= response.status < 400
                    detail = "Открывается" if ok else f"Статус {response.status}"
            except urllib.error.HTTPError as exc:
                ok = False
                detail = f"Ошибка {exc.code}"
            except (OSError, urllib.error.URLError, TimeoutError):
                ok = False
                detail = "Не получилось достучаться"

            results.append(SiteCheckResult(name=name, url=url, ok=ok, detail=detail))

        return results

    def check_for_updates(self, manifest_url, current_version):
        if not manifest_url.strip():
            return UpdateInfo(
                update_available=False,
                latest_version=current_version,
                download_url="",
                notes="Ссылка на update-manifest.json пока не добавлена",
            )

        request = urllib.request.Request(manifest_url.strip(), headers={"User-Agent": "TunnelCrab/0.2"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return UpdateInfo(
                update_available=False,
                latest_version=current_version,
                download_url="",
                notes="Не получилось проверить новую версию",
            )

        latest_version = str(payload.get("version") or current_version)
        download_url = str(payload.get("download_url") or "")
        notes = str(payload.get("notes") or "")
        update_available = self._compare_versions(latest_version, current_version) > 0
        if not notes:
            notes = "Новая версия уже ждёт тебя" if update_available else "Пока всё самое свежее уже у тебя"

        return UpdateInfo(
            update_available=update_available,
            latest_version=latest_version,
            download_url=download_url,
            notes=notes,
        )

    @staticmethod
    def _compare_versions(left, right):
        def parse(version):
            parts = []
            for item in version.split("."):
                try:
                    parts.append(int(item))
                except ValueError:
                    parts.append(0)
            return parts

        left_parts = parse(left)
        right_parts = parse(right)
        length = max(len(left_parts), len(right_parts))
        left_parts.extend([0] * (length - len(left_parts)))
        right_parts.extend([0] * (length - len(right_parts)))
        if left_parts == right_parts:
            return 0
        return 1 if left_parts > right_parts else -1

    def diagnostics_snapshot(self):
        metrics = self.live_metrics()
        return {
            "running": self.is_running(),
            "core": self.active_core,
            "mode": self.active_mode,
            "profile_name": self.active_profile_name or "не выбран",
            "server": self.active_server or "неизвестно",
            "public_ip": self.probe_public_ip() or "не удалось определить",
            "ping_ms": metrics.ping_ms,
            "quality": metrics.quality,
            "download_rate": metrics.download_rate,
            "upload_rate": metrics.upload_rate,
            "downloaded_total": metrics.downloaded_total,
            "uploaded_total": metrics.uploaded_total,
            "session_seconds": metrics.session_seconds,
            "interface_name": metrics.interface_name or "не найден",
            "log_tail": self.log_tail(10),
            "captured_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }


SingBoxWindowsRuntime = VpnRuntime
