"""Scroll action."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class ScrollAction(ActionBase):
    type_name = "scroll"
    display_name = "滚动"
    description = "在指定位置滚动鼠标滚轮"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "direction": "down",
            "amount": 500,
            "at_position": None,  # null = at current cursor
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        import pyautogui

        direction = params.get("direction", "down")
        try:
            amount = int(params.get("amount", 0) or 0)
        except (TypeError, ValueError):
            return ActionResult(False, f"invalid amount: {params.get('amount')}")

        if direction not in ("up", "down"):
            return ActionResult(False, f"direction must be up/down, got: {direction}")

        clicks = amount if direction == "up" else -amount
        at_pos = params.get("at_position")

        try:
            if at_pos and isinstance(at_pos, dict) and at_pos.get("type") == "fixed":
                x = at_pos.get("x")
                y = at_pos.get("y")
                if x is not None and y is not None:
                    pyautogui.moveTo(int(x), int(y))
            pyautogui.scroll(clicks)
            return ActionResult(True, f"scroll {direction} amount={amount}")
        except Exception as e:
            return ActionResult(False, f"scroll failed: {e}")
