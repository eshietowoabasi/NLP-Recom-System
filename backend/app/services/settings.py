"""System-wide NLP parameter defaults (spec v2 §1, §9).

Precedence: built-in defaults < DEFAULT_OVERLAP_THRESHOLD / DEFAULT_TOPIC_COUNT from the
environment < values saved by an Administrator. New sessions start from the result.
"""
from flask import current_app

from ..extensions import db
from ..models import SystemSetting
from ..schemas.session_config import DEFAULT_SESSION_CONFIG, build_session_config

NLP_DEFAULTS_KEY = "nlp_defaults"


def _environment_defaults():
    config = dict(DEFAULT_SESSION_CONFIG)
    if current_app.config.get("DEFAULT_OVERLAP_THRESHOLD") is not None:
        config["similarity_threshold"] = float(current_app.config["DEFAULT_OVERLAP_THRESHOLD"])
    if current_app.config.get("DEFAULT_TOPIC_COUNT") is not None:
        config["topic_count"] = int(current_app.config["DEFAULT_TOPIC_COUNT"])
    return config


def get_nlp_defaults() -> dict:
    base = _environment_defaults()
    stored = db.session.get(SystemSetting, NLP_DEFAULTS_KEY)
    if stored and isinstance(stored.value, dict):
        # Ignore keys that no longer exist (settings saved by an older version).
        base.update({k: v for k, v in stored.value.items() if k in DEFAULT_SESSION_CONFIG})
    return base


def set_nlp_defaults(values: dict, user_id: int) -> dict:
    """Validate (same rules as a session's parameter_config) and save."""
    config = build_session_config(values, base=get_nlp_defaults())
    setting = db.session.get(SystemSetting, NLP_DEFAULTS_KEY)
    if setting is None:
        setting = SystemSetting(key=NLP_DEFAULTS_KEY, value=config, updated_by=user_id)
        db.session.add(setting)
    else:
        setting.value = config
        setting.updated_by = user_id
    return config
