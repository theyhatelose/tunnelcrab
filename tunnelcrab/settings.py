from dataclasses import asdict, dataclass
import json

from .i18n import VALID_LANGUAGES, detect_os_language
from .paths import user_data_dir


def settings_path():
    return user_data_dir() / "settings.json"


VALID_CORES = ("sing-box", "xray")
VALID_MODES = ("tun", "proxy")
VALID_CLOSE_ACTIONS = ("ask", "tray", "quit")
VALID_ROUTING_MODES = ("global", "bypass_ru")


@dataclass
class AppSettings:
    launch_on_startup: bool = False
    close_action: str = "ask"
    auto_reconnect: bool = True
    auto_connect_on_launch: bool = False
    connect_when_internet: bool = True
    quiet_mode: bool = False
    auto_update: bool = True
    auto_refresh_subscriptions: bool = True
    routing_mode: str = "global"
    selected_theme: str = "Dark Crab"
    selected_profile_id: str = ""
    update_manifest_url: str = ""
    selected_core: str = "sing-box"
    connection_mode: str = "proxy"
    selected_language: str = "en"
    window_x: int = -1
    window_y: int = -1
    window_width: int = 0
    window_height: int = 0


def _coerce_close_action(data):
    raw = data.get("close_action")
    if raw in VALID_CLOSE_ACTIONS:
        return raw
    if "close_to_tray" in data:
        return "ask"
    return "ask"


def load_settings():
    path = settings_path()
    if not path.exists():
        return AppSettings(selected_language=detect_os_language())

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    selected_core = str(data.get("selected_core", "sing-box"))
    if selected_core not in VALID_CORES:
        selected_core = "sing-box"

    connection_mode = str(data.get("connection_mode", "tun"))
    if connection_mode not in VALID_MODES:
        connection_mode = "tun"

    routing_mode = str(data.get("routing_mode", "global"))
    if routing_mode not in VALID_ROUTING_MODES:
        routing_mode = "global"

    selected_language = str(data.get("selected_language", "ru"))
    if selected_language not in VALID_LANGUAGES:
        selected_language = "ru"

    return AppSettings(
        launch_on_startup=bool(data.get("launch_on_startup", False)),
        close_action=_coerce_close_action(data),
        auto_reconnect=bool(data.get("auto_reconnect", True)),
        auto_connect_on_launch=bool(data.get("auto_connect_on_launch", False)),
        connect_when_internet=bool(data.get("connect_when_internet", True)),
        quiet_mode=bool(data.get("quiet_mode", False)),
        auto_update=bool(data.get("auto_update", True)),
        auto_refresh_subscriptions=bool(data.get("auto_refresh_subscriptions", True)),
        routing_mode=routing_mode,
        selected_theme=str(data.get("selected_theme", "Dark Crab")),
        selected_profile_id=str(data.get("selected_profile_id", "")),
        update_manifest_url=str(data.get("update_manifest_url", "")),
        selected_core=selected_core,
        connection_mode=connection_mode,
        selected_language=selected_language,
        window_x=int(data.get("window_x", -1)),
        window_y=int(data.get("window_y", -1)),
        window_width=int(data.get("window_width", 0)),
        window_height=int(data.get("window_height", 0)),
    )


def save_settings(settings):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
