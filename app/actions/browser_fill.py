"""Browser fill action: fill text into an input element."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserFillAction(ActionBase):
    type_name = "browser_fill"
    display_name = "浏览器-填写输入框"
    description = "通过 CSS 选择器填写浏览器输入框"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"selector": "", "text": "", "clear_first": True}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        selector = params.get("selector", "")
        if not selector:
            return ActionResult(False, "选择器不能为空")
        text = params.get("text", "")
        clear_first = params.get("clear_first", True)
        try:
            if clear_first:
                bm.page.fill(selector, "")
            bm.page.fill(selector, text)
            return ActionResult(True, f"已填写: {selector}")
        except Exception as e:
            return ActionResult(False, f"填写失败: {e}")
