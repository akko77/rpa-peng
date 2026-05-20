"""Hotkey action: press a key combination like 'ctrl+a' or 'ctrl+shift+t'."""
from typing import Any, Dict, List
from .base import ActionBase, ActionResult


class HotkeyAction(ActionBase):
    type_name = "hotkey"
    display_name = "组合键"
    description = "按下组合键，例如 ctrl+a / ctrl+shift+t"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"keys": "ctrl+a"}

    @staticmethod
    def _parse_keys(spec: str) -> List[str]:
        return [k.strip().lower() for k in spec.split("+") if k.strip()]

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        import pyautogui

        keys_spec = params.get("keys", "")
        if not isinstance(keys_spec, str) or not keys_spec.strip():
            return ActionResult(False, "hotkey 'keys' is empty")

        parts = self._parse_keys(keys_spec)
        if not parts:
            return ActionResult(False, f"unable to parse keys: {keys_spec}")

        try:
            pyautogui.hotkey(*parts)
            return ActionResult(True, f"hotkey {'+'.join(parts)}")
        except Exception as e:
            return ActionResult(False, f"hotkey failed: {e}")
