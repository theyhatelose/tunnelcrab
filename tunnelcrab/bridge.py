from __future__ import annotations

import base64
import io
import threading
import time
import webbrowser
from dataclasses import asdict, is_dataclass

from . import profiles as profiles_api
from . import updater
from .branding import load_branding
from .connection import ConnectionSupervisor
from .crab import render_crab_image
from .i18n import VALID_LANGUAGES, t as _translate
from .platform import is_admin, is_windows, minimize_window
from .profile import ProfileError, load_profile
from .profiles import ProfileStoreError, get_profile, load_profiles
from .runtime import VpnRuntime
from .settings import load_settings, save_settings
from .startup import is_startup_enabled, set_startup_enabled
from .sysproxy import cleanup_stale_proxy
from .themes import THEMES, get_theme, theme_names
from .version import APP_VERSION
from .webtray import WebTray

DEFAULT_SITES = [
    {"name": "YouTube", "url": "https://www.youtube.com"},
    {"name": "Discord", "url": "https://discord.com/app"},
    {"name": "Instagram", "url": "https://www.instagram.com"},
    {"name": "Telegram", "url": "https://web.telegram.org/a/"},
]


_CRAB_PLAN = {
    "idle": [0],
    "connecting": [0, 1],
    "connected": [0, 1],
    "error": [0],
    "easter": [0, 1],
}


def _crab_frames(size=240):
    frames = {}
    for state, indices in _CRAB_PLAN.items():
        urls = []
        for index in indices:
            image = render_crab_image(state=state, frame=index, canvas_size=size)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            urls.append("data:image/png;base64," + encoded)
        frames[state] = urls
    return frames


def _dataclass_to_dict(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    return value


class AppController:
    def __init__(self, instance_guard=None):
        self.settings = load_settings()
        self.branding = load_branding()
        self.lang = self.settings.selected_language
        self.runtime = VpnRuntime()
        self.runtime.kill_stray_cores()
        cleanup_stale_proxy()
        self.instance_guard = instance_guard
        self.window = None
        self.tray = WebTray(self)

        self.connect_on_startup = False
        self.start_hidden = False

        self.profiles = load_profiles()
        self.selected = self._pick_initial_profile()

        self.conn = ConnectionSupervisor(self)
        self._closing = False
        self.events = []
        self.update_info = {"available": False}
        self._event(self._t("event.woke_up"))

        self.state = {
            "phase": "idle",
            "status_key": "status.idle_ready",
            "helper_key": "",
            "ip": "",
            "params": {},
        }
        self._crab_cache = None

    def _t(self, key, **kw):
        return _translate(self.lang, key, **kw)

    def _render_profile_error(self, exc):
        key = getattr(exc, "key", "")
        if key == "error.config_rebuild_failed":
            params = getattr(exc, "params", {})
            reason_text = self._t(
                params.get("reason_key", ""), **params.get("reason_params", {})
            )
            return self._t(key, name=params.get("name", ""), reason=reason_text)
        if key:
            return self._t(key, **getattr(exc, "params", {}))
        return str(exc)

    def attach_window(self, window):
        self.window = window
        try:
            window.events.closing += self._on_window_closing
        except Exception:
            pass

    def _on_window_closing(self):
        if self._closing:
            return True
        if self.settings.close_action == "quit" or not self.tray.available:
            self.exit_app()
            return True
        self.hide_to_tray()
        return False

    def debug(self, message):
        try:
            from .paths import logs_dir

            folder = logs_dir()
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "spike.log", "a", encoding="utf-8") as handle:
                handle.write(f"{time.time():.0f} {message}\n")
        except Exception:
            pass
        return {"ok": True}

    def on_loaded(self):
        if self.tray.available:
            self.tray.start()
        if self.connect_on_startup or self.settings.auto_connect_on_launch:
            self._event(self._t("event.autoconnect"))
            self.connect()

        if self.settings.auto_update:
            threading.Thread(target=self._background_update_check, daemon=True).start()
        if self.settings.auto_refresh_subscriptions:
            threading.Thread(target=self._background_refresh_subscriptions, daemon=True).start()
        return

    def _background_update_check(self):
        try:
            info = updater.check_for_updates()
        except Exception:
            return
        self.update_info = info or {"available": False}
        if self.update_info.get("available"):
            self._event(self._t("event.new_version", version=self.update_info.get("version", "")))

    def _background_refresh_subscriptions(self):
        try:
            results = profiles_api.refresh_all_subscriptions()
        except Exception:
            return
        total = sum(count for _sid, count, err in results if not err)
        if total:
            self._reload(self._selected_id())
            self._event(self._t("event.subs_refreshed", total=total))


    def _pick_initial_profile(self):
        wanted = self.settings.selected_profile_id
        if wanted:
            for profile in self.profiles:
                if profile.profile_id == wanted:
                    return profile
        return self.profiles[0] if self.profiles else None

    def _set_state(self, phase, status_key, helper_key="", ip="", **params):
        self.state = {
            "phase": phase,
            "status_key": status_key,
            "helper_key": helper_key,
            "ip": ip,
            "params": params,
        }

    def _render_state(self):
        s = self.state
        params = s.get("params") or {}
        status = self._t(s["status_key"], **params) if s.get("status_key") else ""
        helper = self._t(s["helper_key"], **params) if s.get("helper_key") else ""
        return {"phase": s.get("phase", "idle"), "status": status, "helper": helper, "ip": s.get("ip", "")}

    def _event(self, message):
        self.events.append({"t": time.strftime("%H:%M:%S"), "msg": message})
        if len(self.events) > 80:
            self.events = self.events[-80:]

    def get_events(self):
        return self.events

    def crab_frames(self):
        if self._crab_cache is None:
            self._crab_cache = _crab_frames()
        return self._crab_cache


    def bootstrap(self):
        return {
            "version": APP_VERSION,
            "is_admin": bool(is_admin()),
            "is_windows": bool(is_windows()),
            "themes": THEMES,
            "theme_names": theme_names(),
            "selected_theme": self.settings.selected_theme,
            "selected_core": self.settings.selected_core,
            "connection_mode": self.settings.connection_mode,
            "routing_mode": self.settings.routing_mode,
            "profiles": self._profiles_payload(),
            "subscriptions": self._subscriptions_payload(),
            "selected_profile_id": self.selected.profile_id if self.selected else "",
            "settings": self._settings_payload(),
            "sites": DEFAULT_SITES,
            "crab": self.crab_frames(),
            "state": self._render_state(),
            "selected_language": self.settings.selected_language,
            "branding": self.branding,
        }

    def get_branding(self):
        return self.branding

    def _settings_payload(self):
        return {
            "launch_on_startup": bool(is_startup_enabled()),
            "close_action": self.settings.close_action,
            "auto_reconnect": self.settings.auto_reconnect,
            "auto_connect_on_launch": self.settings.auto_connect_on_launch,
            "connect_when_internet": self.settings.connect_when_internet,
            "quiet_mode": self.settings.quiet_mode,
            "auto_update": self.settings.auto_update,
            "auto_refresh_subscriptions": self.settings.auto_refresh_subscriptions,
        }

    def _profiles_state(self):
        return {
            "profiles": self._profiles_payload(),
            "subscriptions": self._subscriptions_payload(),
            "selected_profile_id": self.selected.profile_id if self.selected else "",
        }

    def _subscriptions_payload(self):
        return [
            {"id": sub.subscription_id, "name": sub.name, "url": sub.url}
            for sub in profiles_api.load_subscriptions()
        ]

    def _selected_id(self):
        return self.selected.profile_id if self.selected else None

    def _reload(self, select_id=None):
        self.profiles = load_profiles()
        if select_id:
            self.selected = get_profile(select_id)
        else:
            self.selected = self._pick_initial_profile()
        if self.selected is not None:
            self.settings.selected_profile_id = self.selected.profile_id
            save_settings(self.settings)

    def _profiles_payload(self):
        items = []
        for profile in self.profiles:
            server = ""
            try:
                parsed = load_profile(profile.config_path)
                server = f"{parsed.server}:{parsed.server_port}"
            except (OSError, ProfileError, ValueError):
                server = ""
            items.append(
                {
                    "id": profile.profile_id,
                    "name": profile.name,
                    "server": server,
                    "notes": profile.notes,
                    "subscription_id": profile.subscription_id,
                    "location": profile.location,
                }
            )
        return items

    def status(self):
        data = self._render_state()
        data["connected"] = self.runtime.is_running()
        return data

    def metrics(self):
        report = self.runtime.live_metrics()
        return _dataclass_to_dict(report)


    def toggle(self):
        if self.state["phase"] in ("connecting", "connected", "waiting"):
            return self.disconnect()
        return self.connect()

    def connect(self):
        if self.selected is None:
            self._set_state(
                "idle",
                "status.add_server_first",
                "helper.add_subscription_hint",
            )
            self._event(self._t("event.no_servers"))
            self._sync_tray()
            return {"ok": False, "error": "no_profile"}
        if self.state["phase"] in ("connecting", "connected", "waiting", "disconnecting"):
            return {"ok": True, "ignored": True}
        self.conn.start()
        return {"ok": True}

    def disconnect(self):
        was = self.state.get("phase") in ("connected", "connecting", "waiting")
        self.conn.stop()
        self._set_state("idle", "status.idle_ready")
        if was:
            self._event(self._t("event.disconnected"))
        self._sync_tray()
        return {"ok": True}


    def select_profile(self, profile_id):
        if self.selected is not None and self.selected.profile_id == profile_id:
            return {"ok": True, "id": profile_id, "ignored": True}
        selected = get_profile(profile_id)
        if selected is None:
            return {"ok": False, "error": self._t("error.server_not_found")}
        self.selected = selected
        self.settings.selected_profile_id = self.selected.profile_id
        save_settings(self.settings)
        self._event(self._t("event.server_selected", name=self.selected.name))
        was_connected = self.state["phase"] == "connected"
        if was_connected:
            self._event(self._t("event.switching_server"))
            self.disconnect()
            self.connect()
        return {"ok": True, "id": self.selected.profile_id}


    def set_theme(self, name):
        if name in THEMES:
            self.settings.selected_theme = name
            save_settings(self.settings)
        return {"ok": True}

    def set_language(self, lang):
        if lang in VALID_LANGUAGES:
            self.settings.selected_language = lang
            self.lang = lang
            save_settings(self.settings)
            self._sync_tray()
        return {"ok": True, "language": self.lang}


    def add_profile_by_link(self, link, name=""):
        sub_url = profiles_api.extract_subscription_url(link or "")
        if sub_url:
            return self.add_subscription(name, sub_url)
        try:
            profile = profiles_api.import_profile_from_link(link, name or "")
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(profile.profile_id)
        self._event(self._t("event.server_added_link", name=profile.name))
        return {"ok": True, **self._profiles_state()}

    def import_profile_file(self):
        if self.window is None:
            return {"ok": False}
        import webview

        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=(self._t("dialog.json_files"), self._t("dialog.all_files")),
        )
        if not paths:
            return {"ok": False, "cancelled": True}
        try:
            profile = profiles_api.import_profile(paths[0])
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(profile.profile_id)
        return {"ok": True, **self._profiles_state()}

    def duplicate_profile(self, profile_id):
        try:
            profile = profiles_api.duplicate_profile(profile_id)
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(profile.profile_id)
        return {"ok": True, **self._profiles_state()}

    def delete_profile(self, profile_id):
        if (
            self.state.get("phase") in ("connected", "connecting", "waiting")
            and self.selected is not None
            and self.selected.profile_id == profile_id
        ):
            return {"ok": False, "error": self._t("profilestore.disconnect_first")}
        try:
            profiles_api.delete_profile(profile_id)
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        keep = None if (self.selected is None or profile_id == self.selected.profile_id) else self.selected.profile_id
        self._reload(keep)
        return {"ok": True, **self._profiles_state()}

    def rename_profile(self, profile_id, name):
        try:
            profiles_api.save_profile_meta(profile_id, name=name)
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(self._selected_id())
        return {"ok": True, **self._profiles_state()}

    def refresh_profile(self, profile_id):
        try:
            profiles_api.refresh_profile(profile_id)
        except (ProfileStoreError, RuntimeError) as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(self._selected_id())
        return {"ok": True, **self._profiles_state()}

    def set_profile_location(self, profile_id, location):
        try:
            profiles_api.save_profile_meta(profile_id, location=location or "")
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(self._selected_id())
        return {"ok": True, **self._profiles_state()}


    def get_settings(self):
        return self._settings_payload()

    _BOOL_SETTINGS = {
        "auto_reconnect",
        "auto_connect_on_launch",
        "connect_when_internet",
        "quiet_mode",
        "auto_update",
        "auto_refresh_subscriptions",
    }

    def set_setting(self, key, value):
        if key == "launch_on_startup":
            value = bool(value)
            try:
                set_startup_enabled(value)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
            self.settings.launch_on_startup = value
        elif key == "close_action":
            if value not in ("ask", "tray", "quit"):
                return {"ok": False, "error": "unknown close action"}
            self.settings.close_action = value
        elif key in self._BOOL_SETTINGS:
            setattr(self.settings, key, bool(value))
        else:
            return {"ok": False, "error": "unknown setting"}
        save_settings(self.settings)
        self._sync_tray()
        return {"ok": True}

    def toggle_setting_from_tray(self, key):
        current = bool(getattr(self.settings, key, False))
        self.set_setting(key, not current)
        return {"ok": True}

    def set_core(self, core):
        if core in ("sing-box", "xray"):
            self.settings.selected_core = core
            save_settings(self.settings)
        return {"ok": True, "core": self.settings.selected_core}

    def set_mode(self, mode):
        if mode in ("tun", "proxy"):
            self.settings.connection_mode = mode
            save_settings(self.settings)
        return {"ok": True, "mode": self.settings.connection_mode}

    def set_routing(self, routing):
        if routing in ("global", "bypass_ru"):
            changed = routing != self.settings.routing_mode
            self.settings.routing_mode = routing
            save_settings(self.settings)
            if changed and self.state["phase"] in ("connected", "connecting", "waiting"):
                self._event(self._t("event.routing_changed"))
                self.disconnect()
                self.connect()
        return {"ok": True, "routing": self.settings.routing_mode}

    def get_engine(self):
        return {
            "core": self.settings.selected_core,
            "mode": self.settings.connection_mode,
            "routing": self.settings.routing_mode,
        }


    def add_subscription(self, name, url):
        try:
            sub, summary = profiles_api.add_subscription(name or "", url or "")
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(self._selected_id())
        self._event(self._t("event.subscription_added", name=sub.name))
        return {"ok": True, "summary": summary, **self._profiles_state()}

    def refresh_subscription(self, subscription_id):
        try:
            count, summary = profiles_api.refresh_subscription(subscription_id)
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(self._selected_id())
        self._event(self._t("event.subscription_refreshed", count=count))
        return {"ok": True, "summary": summary, **self._profiles_state()}

    def delete_subscription(self, subscription_id):
        if (
            self.state.get("phase") in ("connected", "connecting", "waiting")
            and self.selected is not None
            and self.selected.subscription_id == subscription_id
        ):
            return {"ok": False, "error": self._t("profilestore.disconnect_first")}
        try:
            profiles_api.delete_subscription(subscription_id)
        except ProfileStoreError as exc:
            return {"ok": False, "error": self._render_profile_error(exc)}
        self._reload(None if (self.selected is None or self.selected.subscription_id == subscription_id) else self.selected.profile_id)
        self._event(self._t("event.subscription_deleted"))
        return {"ok": True, **self._profiles_state()}


    def get_update_info(self):
        return self.update_info

    def check_for_updates(self):
        try:
            self.update_info = updater.check_for_updates() or {"available": False}
        except Exception as exc:
            return {"available": False, "error": str(exc)}
        return self.update_info

    def install_update(self):
        info = self.update_info or {}
        url = info.get("url")
        if not info.get("available") or not url:
            return {"ok": False, "error": self._t("error.update_unavailable")}
        try:
            path = updater.download_installer(url, expected_sha256=info.get("sha256") or "")
        except Exception as exc:
            return {"ok": False, "error": self._t("error.update_download", exc=exc)}
        if not updater.launch_installer(path):
            return {"ok": False, "error": self._t("error.update_launch")}
        self._event(self._t("event.update_launching"))
        threading.Timer(1.0, self.exit_app).start()
        return {"ok": True}


    def check_sites(self, sites=None):
        items = sites or DEFAULT_SITES
        results = self.runtime.site_checks(items)
        return [_dataclass_to_dict(r) for r in results]

    def diagnostics_text(self):
        snap = self.runtime.diagnostics_snapshot()
        lines = [
            self._t("diag.title"),
            self._t("diag.version", v=APP_VERSION),
            self._t("diag.core_mode", core=snap.get("core"), mode=snap.get("mode")),
            self._t("diag.connected", running=snap.get("running")),
            self._t("diag.profile", name=snap.get("profile_name")),
            self._t("diag.server", server=snap.get("server")),
            self._t("diag.public_ip", ip=snap.get("public_ip")),
            self._t("diag.ping", ping=snap.get("ping_ms"), quality=snap.get("quality")),
            self._t("diag.interface", iface=snap.get("interface_name")),
            self._t("diag.time", time=snap.get("captured_at")),
            "",
            self._t("diag.last_core_lines"),
        ]
        lines.extend(snap.get("log_tail") or [self._t("diag.empty")])
        return "\n".join(lines)

    def open_url(self, url):
        if not str(url or "").lower().startswith(("http://", "https://")):
            return {"ok": False}
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return {"ok": True}

    def read_clipboard(self):
        if not is_windows():
            return ""
        import ctypes
        from ctypes import wintypes

        cf_unicodetext = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        try:
            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(cf_unicodetext)
                if not handle:
                    return ""
                locked = kernel32.GlobalLock(handle)
                if not locked:
                    return ""
                try:
                    return ctypes.wstring_at(locked) or ""
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        except Exception:
            return ""


    def _sync_tray(self):
        try:
            self.tray.update()
        except Exception:
            pass

    def _notify(self, message):
        if self.settings.quiet_mode:
            return
        try:
            self.tray.notify(message)
        except Exception:
            pass

    def minimize(self):
        if self.window is not None:
            if not minimize_window(self.window):
                try:
                    self.window.minimize()
                except Exception:
                    pass
        return {"ok": True}

    def remember_move(self, x, y):
        if x > -10000 and y > -10000:
            self.settings.window_x = int(x)
            self.settings.window_y = int(y)

    def _save_settings_quiet(self):
        try:
            save_settings(self.settings)
        except Exception:
            pass

    def hide_to_tray(self):
        self._save_settings_quiet()
        if self.window is not None:
            try:
                self.window.hide()
            except Exception:
                pass
        self._notify(self._t("notify.hidden_tray"))
        return {"ok": True}

    def restore_window(self):
        if self.window is not None:
            try:
                self.window.show()
                self.window.restore()
            except Exception:
                pass
            try:
                self.window.evaluate_js("document.body && document.body.classList.remove('fading')")
            except Exception:
                pass
        return {"ok": True}

    def request_close(self):
        if not self.tray.available:
            return {"ok": True, "action": "quit"}
        return {"ok": True, "action": self.settings.close_action}

    def quit_app(self):
        self.exit_app()
        return {"ok": True}

    def exit_app(self, relaunched=False):
        if self._closing:
            return
        self._closing = True
        if not relaunched:
            self._save_settings_quiet()
        self.conn.desired = False
        try:
            self.runtime.disconnect()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        if self.instance_guard is not None:
            try:
                self.instance_guard.release()
            except Exception:
                pass
            self.instance_guard = None
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass


class Api:

    def __init__(self, controller: AppController):
        self._c = controller

    def get_bootstrap(self):
        return self._c.bootstrap()

    def get_branding(self):
        return self._c.get_branding()

    def debug(self, message):
        return self._c.debug(message)

    def get_status(self):
        return self._c.status()

    def get_metrics(self):
        return self._c.metrics()

    def get_events(self):
        return self._c.get_events()

    def toggle(self):
        return self._c.toggle()

    def connect(self):
        return self._c.connect()

    def disconnect(self):
        return self._c.disconnect()

    def select_profile(self, profile_id):
        return self._c.select_profile(profile_id)

    def set_theme(self, name):
        return self._c.set_theme(name)

    def set_language(self, lang):
        return self._c.set_language(lang)

    def add_profile_by_link(self, link, name=""):
        return self._c.add_profile_by_link(link, name)

    def import_profile_file(self):
        return self._c.import_profile_file()

    def duplicate_profile(self, profile_id):
        return self._c.duplicate_profile(profile_id)

    def delete_profile(self, profile_id):
        return self._c.delete_profile(profile_id)

    def rename_profile(self, profile_id, name):
        return self._c.rename_profile(profile_id, name)

    def refresh_profile(self, profile_id):
        return self._c.refresh_profile(profile_id)

    def set_profile_location(self, profile_id, location):
        return self._c.set_profile_location(profile_id, location)

    def add_subscription(self, name, url):
        return self._c.add_subscription(name, url)

    def refresh_subscription(self, subscription_id):
        return self._c.refresh_subscription(subscription_id)

    def delete_subscription(self, subscription_id):
        return self._c.delete_subscription(subscription_id)

    def get_update_info(self):
        return self._c.get_update_info()

    def check_for_updates(self):
        return self._c.check_for_updates()

    def install_update(self):
        return self._c.install_update()

    def get_settings(self):
        return self._c.get_settings()

    def set_setting(self, key, value):
        return self._c.set_setting(key, value)

    def set_core(self, core):
        return self._c.set_core(core)

    def set_mode(self, mode):
        return self._c.set_mode(mode)

    def set_routing(self, routing):
        return self._c.set_routing(routing)

    def get_engine(self):
        return self._c.get_engine()

    def check_sites(self, sites=None):
        return self._c.check_sites(sites)

    def diagnostics_text(self):
        return self._c.diagnostics_text()

    def open_url(self, url):
        return self._c.open_url(url)

    def read_clipboard(self):
        return self._c.read_clipboard()

    def minimize(self):
        return self._c.minimize()

    def hide_to_tray(self):
        return self._c.hide_to_tray()

    def request_close(self):
        return self._c.request_close()

    def quit_app(self):
        return self._c.quit_app()
