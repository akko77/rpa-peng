"""Filter evaluator.

Two modes:
  - 'visual': a list of FilterRule combined with AND/OR
  - 'expression': a Python expression evaluated with simpleeval

Both operate on a single `item` (dict or scalar) and return bool.
"""
from typing import Any, Callable, Optional

from .workflow import Filter, FilterRule


# ---------------------- visual rules ----------------------

def _field_value(item: Any, field: str) -> Any:
    if field == "" or field == "item":
        return item
    if isinstance(item, dict):
        # Support dotted access too
        cur = item
        for part in field.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = None
                break
        return cur
    # Scalar items: only "item" returns the value; others return None
    return None


def _apply_rule(rule: FilterRule, item: Any) -> bool:
    lhs = _field_value(item, rule.field)
    rhs = rule.value
    op = rule.operator

    # Equality always works
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs

    # Numeric comparisons — be forgiving with string numbers
    if op in (">", ">=", "<", "<="):
        try:
            lhs_n = float(lhs) if lhs is not None else float("nan")
            rhs_n = float(rhs)
        except (TypeError, ValueError):
            return False
        if op == ">":  return lhs_n > rhs_n
        if op == ">=": return lhs_n >= rhs_n
        if op == "<":  return lhs_n < rhs_n
        if op == "<=": return lhs_n <= rhs_n

    # String operations
    if op == "contains":
        if lhs is None:
            return False
        return str(rhs) in str(lhs)
    if op == "startswith":
        if lhs is None:
            return False
        return str(lhs).startswith(str(rhs))
    if op == "endswith":
        if lhs is None:
            return False
        return str(lhs).endswith(str(rhs))

    # Membership
    if op == "in":
        if isinstance(rhs, (list, tuple, set, str)):
            return lhs in rhs
        return False
    if op == "not_in":
        if isinstance(rhs, (list, tuple, set, str)):
            return lhs not in rhs
        return False

    return False


def _eval_visual(filt: Filter, item: Any) -> bool:
    if not filt.rules:
        return True
    results = [_apply_rule(r, item) for r in filt.rules]
    if filt.combinator == "or":
        return any(results)
    return all(results)  # default 'and'


# ---------------------- expression ----------------------

def _build_simpleeval():
    """Build a SimpleEval instance with safe string/number helpers.

    simpleeval is imported lazily so test environments without it can still
    import this module for visual-only filtering.
    """
    from simpleeval import SimpleEval, DEFAULT_FUNCTIONS

    se = SimpleEval()
    funcs = dict(DEFAULT_FUNCTIONS)
    funcs.update({
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "lower": lambda s: str(s).lower(),
        "upper": lambda s: str(s).upper(),
        "strip": lambda s: str(s).strip(),
    })
    se.functions = funcs
    return se


def _eval_expression(filt: Filter, item: Any) -> bool:
    if not filt.expression or not filt.expression.strip():
        return True
    se = _build_simpleeval()
    se.names = {"item": item}
    try:
        return bool(se.eval(filt.expression))
    except Exception:
        return False


# ---------------------- public API ----------------------

def build_filter_fn(filt: Optional[Filter]) -> Optional[Callable[[Any], bool]]:
    """Return a predicate item -> bool, or None if filter is empty/None."""
    if filt is None:
        return None
    if filt.mode == "expression":
        if not filt.expression or not filt.expression.strip():
            return None
        return lambda item: _eval_expression(filt, item)
    if filt.mode == "visual":
        if not filt.rules:
            return None
        return lambda item: _eval_visual(filt, item)
    return None


def visual_to_expression(filt: Filter) -> str:
    """Translate a visual filter into an equivalent Python expression.

    Used when the user switches mode visual -> expression in the UI.
    """
    parts = []
    for r in filt.rules:
        lhs = f"item.{r.field}" if r.field and r.field != "item" else "item"
        # Render RHS as a Python literal
        if isinstance(r.value, str):
            rhs = repr(r.value)
        elif isinstance(r.value, (list, tuple)):
            rhs = repr(list(r.value))
        else:
            rhs = repr(r.value)
        op = r.operator
        if op in ("==", "!=", ">", ">=", "<", "<="):
            parts.append(f"({lhs} {op} {rhs})")
        elif op == "contains":
            parts.append(f"({rhs} in str({lhs}))")
        elif op == "startswith":
            parts.append(f"str({lhs}).startswith({rhs})")
        elif op == "endswith":
            parts.append(f"str({lhs}).endswith({rhs})")
        elif op == "in":
            parts.append(f"({lhs} in {rhs})")
        elif op == "not_in":
            parts.append(f"({lhs} not in {rhs})")
        else:
            parts.append("True")
    if not parts:
        return ""
    join = " and " if filt.combinator != "or" else " or "
    return join.join(parts)
