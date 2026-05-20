"""Variable interpolation utility.

Supports ${var}, ${item}, ${item.field}, ${item.field.subfield}.
Used on string fields like type_text.text, paste.text, log.message, etc.
"""
import re
from typing import Any, Dict, List
from .context import ExecutionContext

_PATTERN = re.compile(r'\$\{([^}]+)\}')


def interpolate(text: str, context: ExecutionContext) -> str:
    """Replace ${expr} in text with values from context. Non-string input is returned as-is."""
    if not isinstance(text, str):
        return text

    def replace(match: re.Match) -> str:
        expr = match.group(1).strip()
        value = _resolve(expr, context)
        return "" if value is None else str(value)

    return _PATTERN.sub(replace, text)


def interpolate_dict(d: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
    """Deep-interpolate a dict's string values."""
    return _walk(d, context)  # type: ignore


def _walk(value: Any, context: ExecutionContext) -> Any:
    if isinstance(value, str):
        return interpolate(value, context)
    if isinstance(value, dict):
        return {k: _walk(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, context) for v in value]
    return value


def _resolve(expr: str, context: ExecutionContext) -> Any:
    parts = expr.split('.')
    head = parts[0]

    if head == 'item':
        current: Any = context.current_item
        for part in parts[1:]:
            current = _attr_or_key(current, part)
            if current is None:
                return ""
        return current

    # Plain variable (with optional dotted access)
    current = context.get(head)
    if current is None:
        return ""
    for part in parts[1:]:
        current = _attr_or_key(current, part)
        if current is None:
            return ""
    return current


def _attr_or_key(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    if hasattr(value, key):
        return getattr(value, key)
    return None
