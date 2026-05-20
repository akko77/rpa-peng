"""Type text action."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class TypeTextAction(ActionBase):
    type_name = "type_text"
    display_name = "输入文本"
    description = "通过键盘输入文本（支持 ${var} 插值）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"text": "", "interval": 0.0}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        import pyautogui

        text = params.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        interval = float(params.get("interval", 0.0) or 0.0)

        try:
            pyautogui.typewrite(text, interval=interval)
            return ActionResult(True, f"typed {len(text)} chars")
        except Exception as e:
            return ActionResult(False, f"type_text failed: {e}")
