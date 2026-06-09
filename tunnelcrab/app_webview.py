from __future__ import annotations

import sys

import webview

from .branding import maybe_seed_branding, pick
from .bridge import Api, AppController
from .paths import icon_path, migrate_legacy_data_dir, webui_dir, webview_storage_dir
from .platform import centered_position, fit_window_to_workarea, work_area_size
from .single_instance import SingleInstance, show_already_running_message

INSTANCE_NAME = "TunnelCrabDesktopClient"


def _has_flag(name):
    return name in sys.argv[1:]


def main():
    if _has_flag("--helper"):
        from .helper import run_helper

        run_helper(sys.argv)
        return

    from .webview2 import is_runtime_present, show_missing_message

    if not is_runtime_present():
        show_missing_message()
        return

    migrate_legacy_data_dir()
    maybe_seed_branding()
    guard = SingleInstance(INSTANCE_NAME)
    if not guard.acquire():
        show_already_running_message()
        return

    controller = AppController(instance_guard=guard)
    controller.start_hidden = _has_flag("--start-hidden")
    api = Api(controller)

    index = webui_dir() / "index.html"

    storage = webview_storage_dir()
    try:
        storage.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    start_hidden = controller.start_hidden and controller.tray.available

    s = controller.settings
    work = work_area_size()
    work_w, work_h = work if work else (None, None)
    saved_x = s.window_x if s.window_x >= 0 else None
    saved_y = s.window_y if s.window_y >= 0 else None
    width, height, fit_x, fit_y = fit_window_to_workarea(440, 820, saved_x, saved_y, work_w, work_h)
    if saved_x is None or saved_y is None:
        fit_x, fit_y = centered_position(width, height, work_w, work_h)
    geom = {"width": width, "height": height}
    if fit_x is not None and fit_y is not None:
        geom["x"] = fit_x
        geom["y"] = fit_y

    window_title = pick(controller.branding.get("app_name"), s.selected_language) or "TunnelCrab"

    window = webview.create_window(
        window_title,
        url=str(index),
        js_api=api,
        min_size=(380, 560),
        frameless=True,
        easy_drag=False,
        hidden=start_hidden,
        background_color="#1b1020",
        **geom,
    )
    controller.attach_window(window)

    window.events.moved += lambda x, y: controller.remember_move(x, y)

    webview.start(
        controller.on_loaded,
        icon=str(icon_path()),
        http_server=True,
        storage_path=str(storage),
        private_mode=True,
    )


if __name__ == "__main__":
    main()
