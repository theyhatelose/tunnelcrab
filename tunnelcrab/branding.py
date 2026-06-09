from __future__ import annotations

import copy
import json
import logging
import shutil
from pathlib import Path

_log = logging.getLogger(__name__)

SEED_ALLOW_ENV = "TUNNELCRAB_ALLOW_BRANDING_SEED"

_LANGS = ("ru", "en")
_FALLBACK_LANG = "ru"


def _localized(ru, en):
    return {"ru": ru, "en": en}


DEFAULT_BRANDING = {
    "app_name": _localized("TunnelCrab", "TunnelCrab"),
    "tagline": _localized(
        "Личный туннель к нужным сайтам",
        "Your personal tunnel to the sites you need",
    ),
    "subtitle": _localized(
        "Крабик, который помогает открывать нужные сайты",
        "A crab that helps you open the sites you need",
    ),
    "about_description": _localized(
        "Крабик, который помогает открывать нужные сайты.",
        "A crab that helps you open the sites you need.",
    ),
    "about_made": _localized("Сделано с заботой 🦀", "Made with care 🦀"),
    "poke_hint": _localized("", ""),
    "secrets": {"ru": [], "en": []},
    "links": [],
}

ALLOWED_FIELDS = frozenset(DEFAULT_BRANDING.keys())

_LOCALIZED_STRING_FIELDS = (
    "app_name",
    "tagline",
    "subtitle",
    "about_description",
    "about_made",
    "poke_hint",
)


def pick(value, lang=_FALLBACK_LANG):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chosen = value.get(lang)
        if isinstance(chosen, str):
            return chosen
        fallback = value.get(_FALLBACK_LANG)
        return fallback if isinstance(fallback, str) else ""
    return ""


def _merge_localized(default_val, override_val):
    if isinstance(override_val, str):
        return {lang: override_val for lang in _LANGS}
    if isinstance(override_val, dict):
        result = dict(default_val)
        for lang in _LANGS:
            candidate = override_val.get(lang)
            if isinstance(candidate, str):
                result[lang] = candidate
        return result
    return None


def _merge_secrets(default_val, override_val):
    def _clean_list(value):
        if not isinstance(value, list):
            return None
        return [str(item) for item in value if isinstance(item, str)]

    if isinstance(override_val, list):
        cleaned = _clean_list(override_val)
        if cleaned is None:
            return None
        return {lang: list(cleaned) for lang in _LANGS}
    if isinstance(override_val, dict):
        result = {lang: list(default_val.get(lang, [])) for lang in _LANGS}
        for lang in _LANGS:
            cleaned = _clean_list(override_val.get(lang))
            if cleaned is not None:
                result[lang] = cleaned
        return result
    return None


def _merge_links(override_val):
    if not isinstance(override_val, list):
        return None
    result = []
    for item in override_val:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        url = item.get("url")
        if not isinstance(label, str) or not isinstance(url, str):
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        result.append({"label": label, "url": url})
    return result


def _merge_field(key, default_val, override_val):
    if key in _LOCALIZED_STRING_FIELDS:
        return _merge_localized(default_val, override_val)
    if key == "secrets":
        return _merge_secrets(default_val, override_val)
    if key == "links":
        return _merge_links(override_val)
    return None


def branding_path():
    from .paths import branding_path as _path

    return _path()


def load_branding(path=None):
    result = copy.deepcopy(DEFAULT_BRANDING)

    if path is None:
        try:
            path = branding_path()
        except Exception:
            return result
    path = Path(path)

    if not path.exists():
        return result

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _log.warning("branding.json could not be read or parsed; using default branding")
        return result

    if not isinstance(raw, dict):
        _log.warning("branding.json is not a JSON object; using default branding")
        return result

    for key, value in raw.items():
        if key not in ALLOWED_FIELDS:
            continue
        merged = _merge_field(key, result[key], value)
        if merged is not None:
            result[key] = merged
        else:
            _log.warning("branding.json field %r has an invalid value; keeping default", key)

    return result


def maybe_seed_branding(target=None, seed=None):
    try:
        if target is None:
            target = branding_path()
        if seed is None:
            from .paths import branding_seed_path

            seed = branding_seed_path()
        target = Path(target)
        seed = Path(seed)

        if target.exists():
            return False
        if not seed.exists():
            return False

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, target)
        _log.info("Seeded branding.json from bundled branding.seed.json")
        return True
    except Exception:
        _log.warning("branding seed step failed; continuing without it", exc_info=True)
        return False


def assert_public_build_clean(seed_path, allow_flag):
    seed_path = Path(seed_path)
    if seed_path.exists() and not allow_flag:
        raise SystemExit(
            "Public build guard tripped.\n"
            f"Found personal branding seed: {seed_path}\n"
            "This file injects personal branding and must NOT ship in a public build.\n"
            "  - For a public build: delete this file before building.\n"
            f"  - For a personal seed build: set {SEED_ALLOW_ENV}=1 to allow it."
        )
