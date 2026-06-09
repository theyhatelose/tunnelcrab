from __future__ import annotations

import threading

try:
    import pystray
except ImportError:
    pystray = None

from PIL import Image, ImageDraw

from .platform import is_windows


def _tray_image(connected=False):
    image = Image.new("RGBA", (64, 64), (18, 18, 42, 255))
    drawer = ImageDraw.Draw(image)

    body = "#4ecca3" if connected else "#e94560"
    drawer.rounded_rectangle([10, 10, 54, 54], radius=14, fill=body)
    drawer.ellipse([20, 20, 30, 30], fill="white")
    drawer.ellipse([34, 20, 44, 30], fill="white")
    drawer.ellipse([24, 22, 28, 28], fill="#1a1a2e")
    drawer.ellipse([36, 22, 40, 28], fill="#1a1a2e")
    drawer.line([(18, 38), (46, 38)], fill="#1a1a2e", width=3)
    return image


class WebTray:
    def __init__(self, controller):
        self.c = controller
        self.icon = None
        self._thread = None

    @property
    def available(self):
        return bool(is_windows() and pystray is not None)

    def start(self):
        if not self.available or self.icon:
            return
        self.icon = pystray.Icon("TunnelCrab")
        self._sync()
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
            self._thread = None

    def update(self):
        if self.icon:
            self._sync()

    def notify(self, message, title="TunnelCrab"):
        if not self.icon:
            return
        try:
            self.icon.notify(message, title)
        except Exception:
            pass


    def _connected(self):
        return self.c.state.get("phase") in ("connected", "connecting", "waiting")

    def _sync(self):
        if not self.icon:
            return
        connected = self.c.state.get("phase") == "connected"
        self.icon.icon = _tray_image(connected)
        self.icon.title = "TunnelCrab"
        self.icon.menu = pystray.Menu(
            pystray.MenuItem(
                self.c._t("tray.open"),
                lambda icon, item: self.c.restore_window(),
                default=True,
            ),
            pystray.MenuItem(
                lambda item: self.c._t("tray.disconnect") if self._connected() else self.c._t("tray.connect"),
                lambda icon, item: self.c.toggle(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self.c._t("tray.startup"),
                lambda icon, item: self.c.toggle_setting_from_tray("launch_on_startup"),
                checked=lambda item: bool(self.c.settings.launch_on_startup),
            ),
            pystray.MenuItem(
                self.c._t("tray.autoconnect"),
                lambda icon, item: self.c.toggle_setting_from_tray("auto_connect_on_launch"),
                checked=lambda item: bool(self.c.settings.auto_connect_on_launch),
            ),
            pystray.MenuItem(
                self.c._t("tray.quiet"),
                lambda icon, item: self.c.toggle_setting_from_tray("quiet_mode"),
                checked=lambda item: bool(self.c.settings.quiet_mode),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self.c._t("tray.quit"),
                lambda icon, item: self.c.exit_app(),
            ),
        )
        try:
            self.icon.update_menu()
        except Exception:
            pass
