from __future__ import annotations

VALID_LANGUAGES = ("ru", "en")
DEFAULT_LANGUAGE = "ru"


TEXT = {
    "ru": {
        "status.idle_ready": "Готов помочь открыть нужные сайты",
        "status.add_server_first": "Сначала добавь сервер",
        "status.connecting": "Крабик ищет безопасный маршрут",
        "status.connected": "Туннель прорыли\nВсё под защитой",
        "status.connection_lost": "Связь оборвалась",
        "status.waiting_internet": "Ждём, пока появится интернет",
        "status.profile_bad": "С этим профилем что-то не так",
        "status.need_admin": "Нужно подтверждение Windows",
        "status.admin_cancelled": "Запуск с правами администратора отменён",
        "status.stumbled": "Крабик споткнулся",
        "status.something_wrong": "Что-то пошло не так",
        "status.reconnecting": "Связь пропала, но мы уже возвращаемся",
        "status.cleanup_running": "Завершаю предыдущий туннель…",

        "helper.add_subscription_hint": "Вставь ссылку на подписку в настройках — и крабик подключится",
        "helper.connecting": "Обычно пара секунд",
        "helper.connected": "Можно спокойно открывать нужные сайты",
        "helper.waiting_internet": "Как только сеть вернётся — крабик подключится сам",
        "helper.need_admin": "Это нужно только для системного VPN",
        "helper.reason": "{reason}",
        "helper.reconnect_again": "{reason}\nЕщё одна попытка примерно через {delay} сек",

        "event.woke_up": "Крабик проснулся и готов помогать",
        "event.autoconnect": "Подключаюсь автоматически при запуске",
        "event.new_version": "Вышла новая версия {version}",
        "event.subs_refreshed": "Обновлены ключи из подписок: {total}",
        "event.no_servers": "Пока нет ни одного сервера — добавь подписку",
        "event.disconnected": "Отключились",
        "event.server_selected": "Выбран сервер «{name}»",
        "event.switching_server": "Меняю сервер — переподключаюсь",
        "event.server_added_link": "Добавлен сервер «{name}» по ссылке",
        "event.subscription_added": "Добавлена подписка «{name}»",
        "event.subscription_refreshed": "Подписка обновлена: {count} ключей",
        "event.subscription_deleted": "Подписка удалена",
        "event.routing_changed": "Сменил режим маршрутизации — переподключаюсь",
        "event.update_launching": "Запускаю установщик обновления",
        "event.connection_lost": "Связь оборвалась",
        "event.no_internet_wait": "Сети сейчас нет, поэтому ждём её спокойно",
        "event.internet_back": "Интернет снова рядом, продолжаем подключение",
        "event.error": "Ошибка: {exc}",
        "event.switched_xray": "Этот сервер работает только на xray-core — переключил ядро",
        "event.connecting_via": "Подключаюсь через «{name}» ({core}/{mode})",
        "event.connected_ip": "Подключились · IP {ip}",
        "event.reconnect_in": "Связь оборвалась, пробуем снова через {delay} сек",

        "notify.connection_lost": "Связь с сервером пропала",
        "notify.connected": "Подключились — можно открывать нужные сайты",
        "notify.hidden_tray": "Крабик спрятался в трей и ждёт тебя",

        "ip.protected": "под защитой",
        "ip.hidden": "скрыт",

        "error.server_not_found": "Этот сервер уже не найден",
        "error.update_unavailable": "Обновление недоступно",
        "error.update_download": "Не удалось скачать обновление: {exc}",
        "error.update_launch": "Не удалось запустить установщик",
        "error.config_rebuild_failed": "Не получилось собрать конфиг для «{name}»: {reason}",

        "profilestore.disconnect_first": "Отключитесь перед удалением этого сервера.",
        "profilestore.server_not_found": "Этот сервер уже не найден.",
        "profilestore.file_not_found": "Не получилось найти выбранный файл.",
        "profilestore.bad_json": "Этот файл не похож на рабочий JSON-конфиг.",
        "profilestore.no_update_url": "У этого сервера пока нет адреса для обновления.",
        "profilestore.need_update_url": "Нужен адрес, откуда обновлять конфиг.",
        "profilestore.url_scheme": "Адрес должен начинаться с http:// или https://.",
        "profilestore.download_failed": "Не удалось скачать новый конфиг.",
        "profilestore.downloaded_bad_json": "Скачанный файл оказался невалидным JSON.",
        "profilestore.subscription_load_failed": "Не удалось загрузить подписку.",
        "profilestore.subscription_no_keys": "В подписке не нашлось ни одного ключа vless://.",
        "profilestore.subscription_none_usable": "Подписка загружена: найдено ключей — {found}, но ни один не подошёл (небезопасных: {unsafe}, неподдерживаемых: {refuse}). TunnelCrab распознал конфиги, но эти режимы транспорта или безопасности пока не поддерживаются.",
        "profilestore.need_subscription_url": "Нужен адрес подписки.",
        "profilestore.subscription_not_found": "Эта подписка уже не найдена.",

        "reason.not_vless": "🦀 Хм, это не похоже на ссылку vless:// — а только их я пока умею открывать.",
        "reason.bad_port": "🦀 Не разберу порт в этой ссылке — кажется, туда закралась опечатка.",
        "reason.missing_uuid_or_host": "🦀 В ссылке не хватает UUID или адреса сервера — без них мне просто некуда стучаться.",
        "reason.allow_insecure": "🦀 Тут выключена проверка сертификата — кто угодно сможет притвориться твоим сервером. Берегу тебя, туда не пойду.",
        "reason.no_encryption": "🦀 Этот сервер без шифрования — твой трафик пойдёт открытым текстом, на виду у всех. Так я тебя не подключу.",
        "reason.reality_missing_keys": "🦀 В этой Reality-ссылке нет публичного ключа (publicKey) — без него защита просто не заработает.",
        "reason.tls_unsupported": "🦀 Обычный TLS я пока не освоил — копаю туннели только через Reality.",
        "reason.unknown_security": "🦀 Незнакомый тип защиты «{security}» — такого я ещё не умею.",
        "reason.transport_unsupported": "🦀 Транспорт {transport} мне пока не по зубам — я хожу через Reality (tcp или xhttp).",

        "friendly.windows_only": "Эта версия работает только в обычной Windows",
        "friendly.no_uac": "Windows не дал нужное подтверждение для подключения",
        "friendly.permission": "Windows не дал доступ к нужному файлу",
        "friendly.config_download": "Не получилось скачать обновлённый конфиг",
        "friendly.partial_tunnel": "Туннель включился не до конца и IP пока не сменился",
        "friendly.timeout": "Сервер сейчас отвечает слишком долго",
        "friendly.keys_outdated": "Похоже, что ключи профиля уже не подходят",
        "friendly.unreachable": "Не удалось достучаться до сервера",
        "friendly.deprecated": "Этому ядру нужна более свежая настройка",
        "friendly.stale_tunnel": "Предыдущий туннель ещё закрывается. Подожди пару секунд и попробуй снова. Если не проходит — перезапусти TunnelCrab или перезагрузи Windows.",
        "friendly.cleanup_running": "Предыдущее подключение ещё закрывается — подожди пару секунд и попробуй снова",

        "diag.title": "TunnelCrab — диагностика",
        "diag.version": "Версия: {v}",
        "diag.core_mode": "Ядро: {core} · режим: {mode}",
        "diag.connected": "Подключено: {running}",
        "diag.profile": "Профиль: {name}",
        "diag.server": "Сервер: {server}",
        "diag.public_ip": "Публичный IP: {ip}",
        "diag.ping": "Пинг: {ping} мс · {quality}",
        "diag.interface": "Интерфейс: {iface}",
        "diag.time": "Время: {time}",
        "diag.last_core_lines": "Последние строки ядра:",
        "diag.empty": "(пусто)",

        "tray.open": "Открыть окошко",
        "tray.connect": "Подключить крабика",
        "tray.disconnect": "Отключить крабика",
        "tray.startup": "Открываться вместе с Windows",
        "tray.autoconnect": "Подключаться автоматически",
        "tray.quiet": "Тихий режим",
        "tray.quit": "Закрыть",

        "dialog.all_files": "Все файлы (*.*)",
        "dialog.json_files": "JSON (*.json)",
    },
    "en": {
        "status.idle_ready": "Ready to help you open the sites you need",
        "status.add_server_first": "Add a server first",
        "status.connecting": "The crab is finding a safe route",
        "status.connected": "Tunnel dug\nYou're protected",
        "status.connection_lost": "The connection dropped",
        "status.waiting_internet": "Waiting for the internet to come back",
        "status.profile_bad": "Something's off with this profile",
        "status.need_admin": "Windows needs your confirmation",
        "status.admin_cancelled": "Run as administrator was cancelled",
        "status.stumbled": "The crab tripped",
        "status.something_wrong": "Something went wrong",
        "status.reconnecting": "Connection dropped, but we're already coming back",
        "status.cleanup_running": "Finishing the previous tunnel…",

        "helper.add_subscription_hint": "Paste a subscription link in settings — and the crab will connect",
        "helper.connecting": "Usually a couple of seconds",
        "helper.connected": "You can safely open the sites you need",
        "helper.waiting_internet": "As soon as the network is back, the crab will connect on its own",
        "helper.need_admin": "This is only needed for the system-wide VPN",
        "helper.reason": "{reason}",
        "helper.reconnect_again": "{reason}\nTrying again in about {delay}s",

        "event.woke_up": "The crab woke up and is ready to help",
        "event.autoconnect": "Connecting automatically on startup",
        "event.new_version": "A new version {version} is out",
        "event.subs_refreshed": "Keys refreshed from subscriptions: {total}",
        "event.no_servers": "No servers yet — add a subscription",
        "event.disconnected": "Disconnected",
        "event.server_selected": "Selected server “{name}”",
        "event.switching_server": "Switching server — reconnecting",
        "event.server_added_link": "Added server “{name}” from a link",
        "event.subscription_added": "Added subscription “{name}”",
        "event.subscription_refreshed": "Subscription refreshed: {count} keys",
        "event.subscription_deleted": "Subscription deleted",
        "event.routing_changed": "Changed routing mode — reconnecting",
        "event.update_launching": "Launching the update installer",
        "event.connection_lost": "The connection dropped",
        "event.no_internet_wait": "No network right now, so we'll wait calmly",
        "event.internet_back": "The internet is back, continuing to connect",
        "event.error": "Error: {exc}",
        "event.switched_xray": "This server only works on xray-core — switched the core",
        "event.connecting_via": "Connecting via “{name}” ({core}/{mode})",
        "event.connected_ip": "Connected · IP {ip}",
        "event.reconnect_in": "Connection dropped, trying again in {delay}s",

        "notify.connection_lost": "Lost the connection to the server",
        "notify.connected": "Connected — you can open the sites you need",
        "notify.hidden_tray": "The crab hid in the tray and is waiting for you",

        "ip.protected": "protected",
        "ip.hidden": "hidden",

        "error.server_not_found": "This server can't be found anymore",
        "error.update_unavailable": "Update unavailable",
        "error.update_download": "Couldn't download the update: {exc}",
        "error.update_launch": "Couldn't launch the installer",
        "error.config_rebuild_failed": "Couldn't build config for \"{name}\": {reason}",

        "profilestore.disconnect_first": "Disconnect before deleting this server.",
        "profilestore.server_not_found": "This server can't be found anymore.",
        "profilestore.file_not_found": "Couldn't find the selected file.",
        "profilestore.bad_json": "This file doesn't look like a valid JSON config.",
        "profilestore.no_update_url": "This server has no update address yet.",
        "profilestore.need_update_url": "An address to update the config from is required.",
        "profilestore.url_scheme": "The address must start with http:// or https://.",
        "profilestore.download_failed": "Couldn't download the new config.",
        "profilestore.downloaded_bad_json": "The downloaded file turned out to be invalid JSON.",
        "profilestore.subscription_load_failed": "Couldn't load the subscription.",
        "profilestore.subscription_no_keys": "No vless:// keys were found in the subscription.",
        "profilestore.subscription_none_usable": "Subscription loaded: {found} keys found, but none worked (unsafe: {unsafe}, unsupported: {refuse}). TunnelCrab recognized the configs, but these transport or security modes aren't supported yet.",
        "profilestore.need_subscription_url": "A subscription address is required.",
        "profilestore.subscription_not_found": "This subscription can't be found anymore.",

        "reason.not_vless": "🦀 Hmm, that doesn't look like a vless:// link — those are the only ones I know how to open.",
        "reason.bad_port": "🦀 I can't make out the port in this link — looks like a typo slipped in.",
        "reason.missing_uuid_or_host": "🦀 This link is missing the UUID or the server address — without them I've got nowhere to knock.",
        "reason.allow_insecure": "🦀 This one turns off certificate checking — anyone could pose as your server. I'm looking out for you, so I'll stay out.",
        "reason.no_encryption": "🦀 This server has no encryption — your traffic would travel in plain sight. I won't hook you up to that.",
        "reason.reality_missing_keys": "🦀 This Reality link has no public key (publicKey) — the protection simply won't work without it.",
        "reason.tls_unsupported": "🦀 I haven't picked up plain TLS yet — I only dig tunnels through Reality.",
        "reason.unknown_security": "🦀 The {security} security type is new to me — I can't handle that one yet.",
        "reason.transport_unsupported": "🦀 The {transport} transport is beyond me for now — I travel over Reality (tcp or xhttp).",

        "friendly.windows_only": "This version only works on regular Windows",
        "friendly.no_uac": "Windows didn't give the confirmation needed to connect",
        "friendly.permission": "Windows denied access to a needed file",
        "friendly.config_download": "Couldn't download the updated config",
        "friendly.partial_tunnel": "The tunnel came up only partway and the IP hasn't changed yet",
        "friendly.timeout": "The server is taking too long to respond",
        "friendly.keys_outdated": "Looks like the profile keys don't fit anymore",
        "friendly.unreachable": "Couldn't reach the server",
        "friendly.deprecated": "This core needs a newer config",
        "friendly.stale_tunnel": "The previous tunnel is still shutting down. Wait a moment and try again. If it persists, restart TunnelCrab or reboot Windows.",
        "friendly.cleanup_running": "The previous connection is still shutting down — wait a moment and try again",

        "diag.title": "TunnelCrab — diagnostics",
        "diag.version": "Version: {v}",
        "diag.core_mode": "Core: {core} · mode: {mode}",
        "diag.connected": "Connected: {running}",
        "diag.profile": "Profile: {name}",
        "diag.server": "Server: {server}",
        "diag.public_ip": "Public IP: {ip}",
        "diag.ping": "Ping: {ping} ms · {quality}",
        "diag.interface": "Interface: {iface}",
        "diag.time": "Time: {time}",
        "diag.last_core_lines": "Last core lines:",
        "diag.empty": "(empty)",

        "tray.open": "Open the window",
        "tray.connect": "Connect the crab",
        "tray.disconnect": "Disconnect the crab",
        "tray.startup": "Launch with Windows",
        "tray.autoconnect": "Connect automatically",
        "tray.quiet": "Quiet mode",
        "tray.quit": "Quit",

        "dialog.all_files": "All files (*.*)",
        "dialog.json_files": "JSON (*.json)",
    },
}


def detect_os_language():
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is not None:
            lang_id = windll.kernel32.GetUserDefaultUILanguage()
            if (lang_id & 0x3FF) == 0x19:
                return "ru"
            return "en"
    except Exception:
        pass
    try:
        import locale

        loc = (locale.getdefaultlocale()[0] or "").lower()
        if loc.startswith("ru"):
            return "ru"
    except Exception:
        pass
    return "en"


def normalize_language(lang):
    return lang if lang in VALID_LANGUAGES else DEFAULT_LANGUAGE


def t(lang, key, **kw):
    table = TEXT.get(lang) or TEXT[DEFAULT_LANGUAGE]
    template = table.get(key)
    if template is None:
        template = TEXT[DEFAULT_LANGUAGE].get(key, key)
    if kw:
        try:
            return template.format(**kw)
        except (KeyError, IndexError, ValueError):
            return template
    return template
