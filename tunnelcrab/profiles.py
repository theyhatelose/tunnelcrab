from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import urllib.error
import urllib.request
import uuid

from . import subscriptions as subs_api
from .paths import profiles_dir
from .vless_link import VlessLinkError, classify_vless_link, parse_vless_link


class ProfileStoreError(RuntimeError):
    pass


def _store_error(key, message, **params):
    err = ProfileStoreError(message)
    err.key = key
    err.params = params
    return err


DEFAULT_SERVERS = []

_DEFAULT_IDS = {server["profile_id"] for server in DEFAULT_SERVERS}
_LEGACY_DEFAULT_IDS = {
    "default-finland",
    "helsinki-xhttp-reality",
    "helsinki-cf-cloudflare",
    "germany-xhttp-reality",
}
_OLD_DEFAULT_NAMES = {}


@dataclass
class StoredProfile:
    profile_id: str
    name: str
    file_name: str
    update_url: str = ""
    notes: str = ""
    subscription_id: str = ""
    location: str = ""

    @property
    def config_path(self):
        return profiles_dir() / self.file_name


@dataclass
class StoredSubscription:
    subscription_id: str
    name: str
    url: str


def _catalog_path():
    return profiles_dir() / "profiles.json"


def _subscriptions_path():
    return profiles_dir() / "subscriptions.json"


def _removed_defaults_path():
    return profiles_dir() / "removed_defaults.json"


def _load_removed_defaults():
    path = _removed_defaults_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(item) for item in data}
    except (OSError, json.JSONDecodeError):
        return set()


def _save_removed_defaults(removed_ids):
    path = _removed_defaults_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(removed_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_slug(text):
    allowed = []
    for char in text.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {" ", "-", "_"}:
            allowed.append("-")

    slug = "".join(allowed).strip("-")
    return slug or "profile"


def _write_catalog(profiles):
    root = profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    _catalog_path().write_text(
        json.dumps([asdict(profile) for profile in profiles], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_server_config(server):
    try:
        config, _ = parse_vless_link(server["link"])
    except VlessLinkError as exc:
        err = ProfileStoreError(f"error.config_rebuild_failed: {exc.key}")
        err.key = "error.config_rebuild_failed"
        err.params = {
            "name": server["name"],
            "reason_key": exc.key,
            "reason_params": exc.params,
        }
        raise err from exc

    root = profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    target = root / server["file_name"]
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _stored_from_server(server):
    return StoredProfile(
        profile_id=server["profile_id"],
        name=server["name"],
        file_name=server["file_name"],
        notes=server.get("notes", ""),
        location=server.get("location", ""),
    )


def _bootstrap_default_catalog():
    profiles = []
    for server in DEFAULT_SERVERS:
        _write_server_config(server)
        profiles.append(_stored_from_server(server))
    _write_catalog(profiles)
    return profiles


def _ensure_default_servers(profiles):
    changed = False

    kept = []
    for profile in profiles:
        if profile.profile_id in _LEGACY_DEFAULT_IDS:
            try:
                profile.config_path.unlink(missing_ok=True)
            except OSError:
                pass
            changed = True
            continue
        kept.append(profile)
    profiles = kept

    servers_by_id = {server["profile_id"]: server for server in DEFAULT_SERVERS}
    for profile in profiles:
        old_name = _OLD_DEFAULT_NAMES.get(profile.profile_id)
        if old_name and profile.name == old_name:
            profile.name = servers_by_id[profile.profile_id]["name"]
            changed = True

    removed = _load_removed_defaults()
    present_ids = {profile.profile_id for profile in profiles}
    for server in DEFAULT_SERVERS:
        if server["profile_id"] in removed:
            continue
        if server["profile_id"] not in present_ids:
            _write_server_config(server)
            profiles.append(_stored_from_server(server))
            changed = True

    return profiles, changed


def load_profiles():
    catalog_path = _catalog_path()
    if not catalog_path.exists():
        return _bootstrap_default_catalog()

    try:
        raw_profiles = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _bootstrap_default_catalog()

    profiles = []
    for item in raw_profiles:
        profile = StoredProfile(
            profile_id=str(item.get("profile_id") or uuid.uuid4().hex),
            name=str(item.get("name") or "Профиль"),
            file_name=str(item.get("file_name") or f"{uuid.uuid4().hex}.json"),
            update_url=str(item.get("update_url") or ""),
            notes=str(item.get("notes") or ""),
            subscription_id=str(item.get("subscription_id") or ""),
            location=str(item.get("location") or ""),
        )
        profiles.append(profile)

    profiles, changed = _ensure_default_servers(profiles)

    if not profiles:
        return _bootstrap_default_catalog()

    root = profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    servers_by_id = {server["profile_id"]: server for server in DEFAULT_SERVERS}
    for profile in profiles:
        if profile.config_path.exists():
            continue
        server = servers_by_id.get(profile.profile_id)
        if server is not None:
            _write_server_config(server)
            changed = True

    if changed:
        _write_catalog(profiles)

    return profiles


def save_profiles(profiles):
    _write_catalog(profiles)


def get_profile(profile_id=None):
    profiles = load_profiles()
    if not profiles:
        return None
    if not profile_id:
        return profiles[0]

    for profile in profiles:
        if profile.profile_id == profile_id:
            return profile

    return profiles[0]


def duplicate_profile(profile_id):
    profiles = load_profiles()
    source = get_profile(profile_id)
    new_id = uuid.uuid4().hex
    file_name = f"{_safe_slug(source.name)}-{new_id[:8]}.json"
    new_profile = StoredProfile(
        profile_id=new_id,
        name=f"{source.name} Copy",
        file_name=file_name,
        update_url=source.update_url,
        notes=source.notes,
    )
    shutil.copyfile(source.config_path, new_profile.config_path)
    profiles.append(new_profile)
    save_profiles(profiles)
    return new_profile


def delete_profile(profile_id):
    profiles = load_profiles()

    target = None
    remaining = []
    for profile in profiles:
        if profile.profile_id == profile_id:
            target = profile
        else:
            remaining.append(profile)

    if target is None:
        raise _store_error("profilestore.server_not_found", "Этот сервер уже не найден")

    try:
        target.config_path.unlink(missing_ok=True)
    except OSError:
        pass

    if profile_id in _DEFAULT_IDS:
        removed = _load_removed_defaults()
        removed.add(profile_id)
        _save_removed_defaults(removed)

    save_profiles(remaining)
    return remaining


def import_profile(profile_path, name=""):
    source = Path(profile_path)
    if not source.exists():
        raise _store_error("profilestore.file_not_found", "Не получилось найти выбранный файл")

    try:
        json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _store_error("profilestore.bad_json", "Этот файл не похож на рабочий JSON-конфиг") from exc

    profiles = load_profiles()
    new_id = uuid.uuid4().hex
    display_name = name.strip() or source.stem
    file_name = f"{_safe_slug(display_name)}-{new_id[:8]}.json"
    target = profiles_dir() / file_name
    shutil.copyfile(source, target)
    new_profile = StoredProfile(
        profile_id=new_id,
        name=display_name,
        file_name=file_name,
    )
    profiles.append(new_profile)
    save_profiles(profiles)
    return new_profile


def save_profile_meta(profile_id, *, name=None, update_url=None, notes=None, location=None):
    profiles = load_profiles()
    changed = False
    for profile in profiles:
        if profile.profile_id != profile_id:
            continue

        if name is not None:
            cleaned_name = name.strip() or profile.name
            profile.name = cleaned_name
            changed = True
        if update_url is not None:
            profile.update_url = update_url.strip()
            changed = True
        if notes is not None:
            profile.notes = notes.strip()
            changed = True
        if location is not None:
            profile.location = location.strip()
            changed = True
        break

    if changed:
        save_profiles(profiles)

    return get_profile(profile_id)


def refresh_profile(profile_id):
    profile = get_profile(profile_id)

    if profile.update_url:
        return update_profile_from_url(profile_id, profile.update_url)

    servers_by_id = {server["profile_id"]: server for server in DEFAULT_SERVERS}
    server = servers_by_id.get(profile.profile_id)
    if server is not None:
        _write_server_config(server)
        return profile

    raise _store_error("profilestore.no_update_url", "У этого сервера пока нет адреса для обновления")


def import_profile_from_link(link, name=""):
    try:
        config, suggested_name = parse_vless_link(link)
    except VlessLinkError as exc:
        err = ProfileStoreError(str(exc))
        err.key = exc.key
        err.params = exc.params
        raise err from exc

    profiles = load_profiles()
    new_id = uuid.uuid4().hex
    display_name = name.strip() or suggested_name or "Импортированный сервер"
    file_name = f"{_safe_slug(display_name)}-{new_id[:8]}.json"
    target = profiles_dir() / file_name
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    new_profile = StoredProfile(
        profile_id=new_id,
        name=display_name,
        file_name=file_name,
    )
    profiles.append(new_profile)
    save_profiles(profiles)
    return new_profile


def update_profile_from_url(profile_id, update_url):
    profile = get_profile(profile_id)
    if not update_url.strip():
        raise _store_error("profilestore.need_update_url", "Нужен адрес, откуда обновлять конфиг")
    if not update_url.strip().lower().startswith(("http://", "https://")):
        raise _store_error("profilestore.url_scheme", "Адрес должен начинаться с http:// или https://")

    request = urllib.request.Request(update_url.strip(), headers={"User-Agent": "TunnelCrab/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise _store_error("profilestore.download_failed", "Не удалось скачать новый конфиг") from exc

    try:
        config_data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _store_error("profilestore.downloaded_bad_json", "Скачанный файл оказался невалидным JSON") from exc

    profile.config_path.write_text(
        json.dumps(config_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_profile_meta(profile_id, update_url=update_url)
    return get_profile(profile_id)


def load_subscriptions():
    path = _subscriptions_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    subs = []
    for item in data:
        subs.append(
            StoredSubscription(
                subscription_id=str(item.get("subscription_id") or uuid.uuid4().hex),
                name=str(item.get("name") or "Подписка"),
                url=str(item.get("url") or ""),
            )
        )
    return [sub for sub in subs if sub.url]


def _save_subscriptions(subs):
    root = profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    _subscriptions_path().write_text(
        json.dumps([asdict(sub) for sub in subs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_subscription(sub_id):
    for sub in load_subscriptions():
        if sub.subscription_id == sub_id:
            return sub
    return None


def _profile_from_link(link, name="", subscription_id=""):
    config, suggested_name = parse_vless_link(link)
    new_id = uuid.uuid4().hex
    display_name = (name or "").strip() or suggested_name or "Сервер из подписки"
    file_name = f"{_safe_slug(display_name)}-{new_id[:8]}.json"
    target = profiles_dir() / file_name
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return StoredProfile(
        profile_id=new_id,
        name=display_name,
        file_name=file_name,
        subscription_id=subscription_id,
    )


def extract_subscription_url(text):
    cleaned = subs_api._clean_text(str(text or "")).strip().strip("`'\"<>")
    if cleaned.lower().startswith("vless://"):
        return ""
    return subs_api.extract_url(text)


def _links_from_subscription(url):
    try:
        links = subs_api.fetch_links(url)
    except subs_api.SubscriptionError as exc:
        raise _store_error("profilestore.subscription_load_failed", str(exc)) from exc
    except Exception as exc:
        raise _store_error("profilestore.subscription_load_failed", "Не удалось загрузить подписку") from exc
    if not links:
        raise _store_error("profilestore.subscription_no_keys", "В подписке не нашлось ни одного ключа vless://")
    return links


def summarize_links(links):
    accept = refuse = unsafe = 0
    reasons = {}
    for link in links:
        bucket, key, _ = classify_vless_link(link)
        if bucket == "ACCEPT":
            accept += 1
        elif bucket == "UNSAFE":
            unsafe += 1
        else:
            refuse += 1
        if key:
            reasons[key] = reasons.get(key, 0) + 1
    total = len(links)
    return {
        "links": total,
        "found": total,
        "accept": accept,
        "accepted": accept,
        "refuse": refuse,
        "refused": refuse,
        "unsafe": unsafe,
        "reasons": reasons,
    }


def _no_usable_keys_message(summary):
    return (
        f"Подписка загружена: найдено ключей — {summary.get('found', 0)}, "
        f"но ни один не подошёл (небезопасных: {summary.get('unsafe', 0)}, "
        f"неподдерживаемых: {summary.get('refuse', 0)}). "
        "TunnelCrab распознал конфиги, но эти режимы транспорта или безопасности пока не поддерживаются."
    )


def diagnose_subscription(url):
    url = (url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise _store_error("profilestore.url_scheme", "Адрес должен начинаться с http:// или https://")
    try:
        raw = subs_api._http_get(url)
    except Exception as exc:
        raise _store_error("profilestore.subscription_load_failed", "Не удалось загрузить подписку") from exc
    body = raw.decode("utf-8", errors="replace")
    summary = summarize_links(subs_api.parse_links(body))
    summary["lines"] = subs_api.count_lines(body)
    return summary


def add_subscription(name, url):
    url = (url or "").strip()
    if not url:
        raise _store_error("profilestore.need_subscription_url", "Нужен адрес подписки")
    if not url.lower().startswith(("http://", "https://")):
        raise _store_error("profilestore.url_scheme", "Адрес должен начинаться с http:// или https://")

    links = _links_from_subscription(url)
    summary = summarize_links(links)
    sub = StoredSubscription(
        subscription_id=uuid.uuid4().hex,
        name=(name or "").strip() or "Подписка",
        url=url,
    )

    profiles = load_profiles()
    added = []
    for link in links:
        try:
            added.append(_profile_from_link(link, "", sub.subscription_id))
        except VlessLinkError:
            continue
    if not added:
        raise _store_error(
            "profilestore.subscription_none_usable",
            _no_usable_keys_message(summary),
            found=summary.get("found", 0),
            unsafe=summary.get("unsafe", 0),
            refuse=summary.get("refuse", 0),
        )

    subs = load_subscriptions()
    subs.append(sub)
    _save_subscriptions(subs)
    save_profiles(profiles + added)
    return sub, summary


def refresh_subscription(sub_id):
    sub = _get_subscription(sub_id)
    if sub is None:
        raise _store_error("profilestore.subscription_not_found", "Эта подписка уже не найдена")

    links = _links_from_subscription(sub.url)
    summary = summarize_links(links)

    fresh = []
    for link in links:
        try:
            fresh.append(_profile_from_link(link, "", sub_id))
        except VlessLinkError:
            continue
    if not fresh:
        raise _store_error(
            "profilestore.subscription_none_usable",
            _no_usable_keys_message(summary),
            found=summary.get("found", 0),
            unsafe=summary.get("unsafe", 0),
            refuse=summary.get("refuse", 0),
        )

    profiles = load_profiles()
    kept = []
    for profile in profiles:
        if profile.subscription_id == sub_id:
            try:
                profile.config_path.unlink(missing_ok=True)
            except OSError:
                pass
        else:
            kept.append(profile)
    save_profiles(kept + fresh)
    return len(fresh), summary


def refresh_all_subscriptions():
    results = []
    for sub in load_subscriptions():
        try:
            count, _ = refresh_subscription(sub.subscription_id)
            results.append((sub.subscription_id, count, None))
        except ProfileStoreError as exc:
            results.append((sub.subscription_id, 0, str(exc)))
    return results


def delete_subscription(sub_id, remove_profiles=True):
    subs = load_subscriptions()
    if not any(sub.subscription_id == sub_id for sub in subs):
        raise _store_error("profilestore.subscription_not_found", "Эта подписка уже не найдена")
    remaining_subs = [sub for sub in subs if sub.subscription_id != sub_id]

    if remove_profiles:
        profiles = load_profiles()
        kept = [p for p in profiles if p.subscription_id != sub_id]
        doomed = [p for p in profiles if p.subscription_id == sub_id]
        for profile in doomed:
            try:
                profile.config_path.unlink(missing_ok=True)
            except OSError:
                pass
        save_profiles(kept)

    _save_subscriptions(remaining_subs)
