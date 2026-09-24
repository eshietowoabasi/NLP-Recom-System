"""Analysis-session parameter_config defaults and validation (spec v1 §9-§10; v2 §4, §6)."""
import math

from ..utils.errors import ValidationError

DEFAULT_SESSION_CONFIG = {
    "similarity_threshold": 0.80,
    "ner_weight": 0.40,
    "topic_weight": 0.35,
    "novelty_weight": 0.25,
    "max_recommendations": 20,
    "topic_count": 10,  # spec v2 §4: BERTopic topic count, default 10
}

WEIGHT_KEYS = ("ner_weight", "topic_weight", "novelty_weight")
_FLOAT_KEYS = ("similarity_threshold",) + WEIGHT_KEYS
MAX_RECOMMENDATIONS_CEILING = 100
INT_LIMITS = {"max_recommendations": (1, MAX_RECOMMENDATIONS_CEILING), "topic_count": (2, 100)}


def build_session_config(overrides=None, base=None):
    """Merge user overrides onto the defaults (``base``, else the built-in ones) and validate.

    Raises ValidationError with per-field details on bad input.
    """
    overrides = overrides or {}
    if not isinstance(overrides, dict):
        raise ValidationError("parameter_config must be an object")

    unknown = set(overrides) - set(DEFAULT_SESSION_CONFIG)
    errors = {key: "Unknown parameter" for key in sorted(unknown)}

    config = {**DEFAULT_SESSION_CONFIG, **(base or {})}
    for key in _FLOAT_KEYS:
        if key not in overrides:
            continue
        value = overrides[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors[key] = "Must be a number"
        elif not 0 <= value <= 1:
            errors[key] = "Must be between 0 and 1"
        else:
            config[key] = float(value)

    for key, (low, high) in INT_LIMITS.items():
        if key not in overrides:
            continue
        value = overrides[key]
        if isinstance(value, bool) or not isinstance(value, int):
            errors[key] = "Must be an integer"
        elif not low <= value <= high:
            errors[key] = f"Must be between {low} and {high}"
        else:
            config[key] = value

    if not any(key in errors for key in WEIGHT_KEYS):
        total = sum(config[key] for key in WEIGHT_KEYS)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            errors["weights"] = f"ner_weight + topic_weight + novelty_weight must equal 1.0 (got {total:.4f})"

    if errors:
        raise ValidationError("Invalid parameter_config", details=errors)
    return config
