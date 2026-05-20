"""Click action."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class ClickAction(ActionBase):
    type_name = "click"
    display_name = "点击"
    description = "在指定位置点击鼠标"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "position": {"type": "fixed", "x": 0, "y": 0},
            "button": "left",
            "clicks": 1,
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        import pyautogui  # imported lazily so headless tests can import the class

        position = params.get("position", {}) or {}
        pos_type = position.get("type", "fixed")
        button = params.get("button", "left")
        clicks = int(params.get("clicks", 1) or 1)

        if pos_type == "fixed":
            x = position.get("x")
            y = position.get("y")
            if x is None or y is None:
                return ActionResult(False, "fixed position missing x or y")
            try:
                x, y = int(x), int(y)
            except (TypeError, ValueError):
                return ActionResult(False, f"invalid coordinate: ({x}, {y})")
        elif pos_type == "variable":
            var_name = position.get("var")
            if not var_name:
                return ActionResult(False, "variable position missing 'var'")
            value = context.get(var_name)
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                return ActionResult(False, f"variable {var_name} is not a 2-element coordinate")
            x, y = int(value[0]), int(value[1])
        elif pos_type == "template":
            # Find the template now and click its center.
            from ..core.matcher import TemplateMatcher

            template_name = position.get("template", "")
            if not template_name:
                return ActionResult(False, "template position missing 'template'")

            workflow = getattr(context, "workflow", None)
            templates_dir = getattr(context, "templates_dir", None)
            if workflow is None or templates_dir is None:
                return ActionResult(False, "click(template): executor did not inject workflow context")
            group = workflow.templates.get(template_name)
            if group is None:
                return ActionResult(False, f"click(template): group '{template_name}' not found")

            matcher = TemplateMatcher(templates_dir)
            try:
                result = matcher.match_group(group)
            except Exception as e:
                return ActionResult(False, f"click(template) match failed: {e}")
            if result is None:
                return ActionResult(False, f"click(template): '{template_name}' not found on screen")
            x, y = result.center
        else:
            return ActionResult(False, f"unknown position.type: {pos_type}")

        try:
            pyautogui.click(x=x, y=y, clicks=clicks, button=button)
            return ActionResult(True, f"clicked ({x}, {y}) button={button} clicks={clicks}")
        except Exception as e:
            return ActionResult(False, f"click failed: {e}")
