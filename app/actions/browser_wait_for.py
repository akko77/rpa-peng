"""Browser wait_for action: wait for an element to reach a given state."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserWaitForAction(ActionBase):
    type_name = "browser_wait_for"
    display_name = "浏览器-等待元素"
    description = "等待浏览器中的元素达到指定状态（可见/隐藏/附加/分离）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"selector": "", "state": "visible", "timeout": 30000}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        selector = params.get("selector", "")
        if not selector:
            return ActionResult(False, "选择器不能为空")
        state = params.get("state", "visible")
        timeout = float(params.get("timeout", 30000) or 30000)
        try:
            bm.page.wait_for_selector(selector, state=state, timeout=timeout)
            return ActionResult(True, f"元素已{state}: {selector}")
        except Exception as e:
            return ActionResult(False, f"等待元素失败: {e}")
