"""Set variable action.

Phase 1: literal value only. Phase 2 may add expression evaluation.
"""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class SetVariableAction(ActionBase):
    type_name = "set_variable"
    display_name = "设置变量"
    description = "把一个值赋给变量（支持 ${...} 插值）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"name": "", "value": ""}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        name = params.get("name", "")
        if not isinstance(name, str) or not name.strip():
            return ActionResult(False, "variable name is empty")
        value = params.get("value")
        # The executor pre-interpolates strings inside params, so `value` already has
        # any ${var} substituted to a string.
        context.set(name.strip(), value)
        return ActionResult(True, f"set {name} = {value!r}")
