"""Browser press action: press a key or key combination."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserPressAction(ActionBase):
    type_name = "browser_press"
    display_name = "浏览器-按键"
    description = "在浏览器中按键或快捷键（可选聚焦到某个元素）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"selector": "", "key": "Enter"}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        selector = params.get("selector", "")
        key = params.get("key", "Enter")
        if not key:
            return ActionResult(False, "按键不能为空")
        try:
            if selector:
                bm.page.press(selector, key)
            else:
                bm.page.keyboard.press(key)
            return ActionResult(True, f"已按键: {key}")
        except Exception as e:
            return ActionResult(False, f"按键失败: {e}")
