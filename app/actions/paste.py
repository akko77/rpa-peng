"""Paste action: copies text to clipboard then presses Ctrl+V.

Preferred over type_text for non-ASCII content (Chinese/Japanese).
"""
import time
from typing import Any, Dict
from .base import ActionBase, ActionResult


class PasteAction(ActionBase):
    type_name = "paste"
    display_name = "粘贴"
    description = "复制文本到剪贴板并粘贴（中文/特殊字符更稳）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"text": "", "delay_after_copy": 0.1}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        import pyautogui
        import pyperclip

        text = params.get("text", "")
        if not isinstance(text, str):
            text = str(text)
        delay = float(params.get("delay_after_copy", 0.1) or 0.1)

        try:
            pyperclip.copy(text)
            if delay > 0:
                time.sleep(delay)
            pyautogui.hotkey("ctrl", "v")
            return ActionResult(True, f"pasted {len(text)} chars")
        except Exception as e:
            return ActionResult(False, f"paste failed: {e}")
