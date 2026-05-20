"""Control-flow actions: loop_data, if, break, continue.

These actions are special: their semantics are implemented in the executor's
block runner, not in `.execute()`. The execute() methods here are placeholders
that should never be called for the control-flow steps themselves — the
executor recognises the type and handles them specially.

This file exists so the registry knows about these types (default_params,
display_name) and the step editor can render forms for them.
"""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class LoopDataAction(ActionBase):
    type_name = "loop_data"
    display_name = "循环 (数据)"
    description = "遍历数据源中的每一项，对每项执行子步骤体（body）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "source": {
                "type": "inline",
                "inline_items": [],
                "start_index": 0,
                "end_index": None,
                "skip_empty": True,
                "filter": None,
            },
            "item_var": "item",
            "body": [],   # list of Step
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        # Should never reach here — executor handles loop_data directly.
        return ActionResult(False, "loop_data must be handled by the executor")


class IfAction(ActionBase):
    type_name = "if"
    display_name = "条件分支"
    description = "条件表达式 (simpleeval) 为真则执行 then 分支，否则 else 分支"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "condition": "",
            "then": [],
            "else": [],
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        return ActionResult(False, "if must be handled by the executor")


class BreakAction(ActionBase):
    type_name = "break"
    display_name = "break"
    description = "跳出当前 loop_data 循环"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        return ActionResult(False, "break must be handled by the executor")


class ContinueAction(ActionBase):
    type_name = "continue"
    display_name = "continue"
    description = "跳到 loop_data 循环的下一项"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        return ActionResult(False, "continue must be handled by the executor")
