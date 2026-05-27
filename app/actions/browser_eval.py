"""Browser eval action: execute a JavaScript expression."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserEvalAction(ActionBase):
    type_name = "browser_eval"
    display_name = "浏览器-执行JS"
    description = "在浏览器中执行 JavaScript 表达式，结果可存入变量"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"expression": "", "save_as": ""}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        expression = params.get("expression", "")
        if not expression:
            return ActionResult(False, "表达式不能为空")
        save_as = params.get("save_as", "")
        try:
            result = bm.page.evaluate(expression)
            if save_as:
                context.set(save_as, result)
            return ActionResult(True, f"JS 执行结果: {result}")
        except Exception as e:
            return ActionResult(False, f"JS 执行失败: {e}")
