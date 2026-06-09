from __future__ import annotations

import threading
import time

from .profile import ProfileError, load_profile, profile_requires_xray
from .runtime import (
    ConnectionCancelled,
    CoreMissingError,
    PrivilegeError,
    RuntimeErrorBase,
    UnsupportedPlatformError,
    log_event,
)
from .settings import save_settings


class ConnectionSupervisor:
    def __init__(self, controller):
        self.c = controller
        self._lock = threading.Lock()
        self._worker = None
        self.desired = False
        self.reconnect_attempt = 0
        self._last_error = ""


    def start(self):
        with self._lock:
            log_event("connect_click")
            if not self._stop_worker_locked():
                log_event("connect_ignored", "cleanup_running")
                self.c._set_state(
                    "disconnecting",
                    "status.cleanup_running",
                    "helper.reason",
                    reason=self.c._t("friendly.cleanup_running"),
                )
                self.c._sync_tray()
                return
            self.desired = True
            self.reconnect_attempt = 0
            self._worker = threading.Thread(target=self._supervisor, daemon=True)
            self._worker.start()
            log_event("worker_started")

    def stop(self):
        with self._lock:
            self.desired = False
            self._stop_worker_locked()
            self.reconnect_attempt = 0
            self.c.runtime.disconnect()

    def _stop_worker_locked(self):
        worker = self._worker
        self._worker = None
        if worker and worker.is_alive():
            self.desired = False
            self.c.runtime.request_cancel()
            try:
                self.c.runtime.disconnect()
            except Exception:
                pass
            worker.join(timeout=10)
            if worker.is_alive():
                self._worker = worker
                return False
        return True


    def _supervisor(self):
        c = self.c
        try:
            while self.desired:
                if not self._ensure_internet():
                    break

                outcome = self._attempt_connect()
                if not self.desired or outcome == "fatal":
                    break

                if outcome == "connected":
                    self.reconnect_attempt = 0
                    drop_reason = self._monitor_connection()
                    if not self.desired:
                        break
                    if not c.settings.auto_reconnect:
                        c.runtime.disconnect()
                        c._set_state("error", "status.connection_lost", "helper.reason", reason=self._friendly(drop_reason))
                        c._event(c._t("event.connection_lost"))
                        c._notify(c._t("notify.connection_lost"))
                        c._sync_tray()
                        break
                    if not self._backoff_before_reconnect(drop_reason):
                        break
                    continue

                if not (c.settings.auto_reconnect and self._can_retry(self._last_error)):
                    break
                if not self._backoff_before_reconnect(self._last_error):
                    break
        finally:
            c.runtime.disconnect()
            c._sync_tray()

    def _ensure_internet(self):
        c = self.c
        if not c.settings.connect_when_internet:
            return self.desired
        if c.runtime.internet_available():
            return self.desired

        c._set_state("waiting", "status.waiting_internet", "helper.waiting_internet")
        c._event(c._t("event.no_internet_wait"))
        c._sync_tray()
        while self.desired and not c.runtime.internet_available():
            time.sleep(3)
        if self.desired:
            c._event(c._t("event.internet_back"))
        return self.desired

    def _attempt_connect(self):
        c = self.c
        core = c.settings.selected_core
        mode = c.settings.connection_mode

        try:
            profile = load_profile(c.selected.config_path)
        except (OSError, ProfileError, ValueError) as exc:
            self._last_error = str(exc)
            c._set_state("error", "status.profile_bad", "helper.reason", reason=self._friendly(str(exc)))
            c._event(c._t("event.error", exc=exc))
            self.desired = False
            return "fatal"

        if profile_requires_xray(profile) and core != "xray":
            core = "xray"
            c.settings.selected_core = "xray"
            save_settings(c.settings)
            c._event(c._t("event.switched_xray"))

        c._set_state("connecting", "status.connecting", "helper.connecting")
        c._event(c._t("event.connecting_via", name=c.selected.name, core=core, mode=mode))
        c._sync_tray()
        try:
            report = c.runtime.connect(
                c.selected.config_path,
                c.selected.name,
                core=core,
                mode=mode,
                routing=c.settings.routing_mode,
            )
        except ConnectionCancelled:
            c.runtime.disconnect()
            self.desired = False
            c._set_state("idle", "status.idle_ready")
            return "fatal"
        except (CoreMissingError, PrivilegeError, UnsupportedPlatformError, RuntimeErrorBase, ProfileError) as exc:
            c.runtime.disconnect()
            self._last_error = str(exc)
            c._set_state("error", "status.stumbled", "helper.reason", reason=self._friendly(str(exc)))
            c._event(c._t("event.error", exc=exc))
            return "fatal" if not self._can_retry(str(exc)) else "retry"
        except Exception as exc:
            c.runtime.disconnect()
            self._last_error = str(exc)
            c._set_state("error", "status.something_wrong", "helper.reason", reason=self._friendly(str(exc)))
            c._event(c._t("event.error", exc=exc))
            return "retry"

        if not self.desired:
            c.runtime.disconnect()
            c._set_state("idle", "status.idle_ready")
            return "fatal"

        c._set_state(
            "connected",
            "status.connected",
            "helper.connected",
            ip=report.after_ip or c._t("ip.protected"),
        )
        c._event(c._t("event.connected_ip", ip=report.after_ip or c._t("ip.hidden")))
        c._notify(c._t("notify.connected"))
        c._sync_tray()
        return "connected"

    def _monitor_connection(self):
        c = self.c
        while self.desired:
            time.sleep(1.2)
            if not self.desired:
                return None
            error_message = c.runtime.poll_error()
            if not c.runtime.is_running():
                c.runtime.disconnect(keep_helper=True)
                return error_message or ""
        return None

    def _backoff_before_reconnect(self, reason):
        c = self.c
        self.reconnect_attempt += 1
        delay = min(15, 2 + self.reconnect_attempt * 2)
        c._set_state(
            "connecting",
            "status.reconnecting",
            "helper.reconnect_again",
            reason=self._friendly(reason),
            delay=delay,
        )
        c._event(c._t("event.reconnect_in", delay=delay))
        c._sync_tray()
        waited = 0
        while self.desired and waited < delay:
            time.sleep(1)
            waited += 1
        return self.desired


    def _friendly(self, message):
        raw = " ".join(part.strip() for part in str(message or "").splitlines() if part.strip())
        if not raw:
            return ""
        key = self._friendly_key(raw.lower())
        return self.c._t(key) if key else raw

    def _friendly_key(self, lower):
        if "file already exists" in lower or "configure tun" in lower:
            return "friendly.stale_tunnel"
        if "wsl" in lower and "windows" in lower:
            return "friendly.windows_only"
        if "администратора" in lower or "uac" in lower:
            return "friendly.no_uac"
        if "permission denied" in lower or "отказано в доступе" in lower:
            return "friendly.permission"
        if "не удалось скачать новый конфиг" in lower:
            return "friendly.config_download"
        if "подключение поднялось не до конца" in lower or "ip пока остался" in lower:
            return "friendly.partial_tunnel"
        if "timed out" in lower or "timeout" in lower:
            return "friendly.timeout"
        if "certificate" in lower or "publickey" in lower or "shortid" in lower:
            return "friendly.keys_outdated"
        if "не получилось достучаться" in lower or "не удалось достучаться" in lower:
            return "friendly.unreachable"
        if "deprecated" in lower:
            return "friendly.deprecated"
        return ""

    def _can_retry(self, message):
        lower = str(message or "").lower()
        fatal_markers = [
            "wsl",
            "не найден core",
            "не нашёл sing-box.exe",
            "не нашёл нужные файлы ядра",
            "администратора",
            "отменён",
            "отменено",
            "config.json",
            "обязательных полей",
            "json",
            "поврежд",
            "deprecated",
            "file already exists",
            "configure tun",
        ]
        return not any(marker in lower for marker in fatal_markers)
