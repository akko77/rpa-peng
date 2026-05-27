"""Action registry (Phase 2)."""
from typing import Dict, List, Optional, Type
from .base import ActionBase, ActionResult
from .click import ClickAction
from .type_text import TypeTextAction
from .paste import PasteAction
from .hotkey import HotkeyAction
from .wait import WaitAction
from .scroll import ScrollAction
from .set_variable import SetVariableAction
from .log import LogAction
from .find_image import FindImageAction
from .focus_window import FocusWindowAction
from .control_flow import LoopDataAction, IfAction, BreakAction, ContinueAction
from .browser_goto import BrowserGotoAction
from .browser_click import BrowserClickAction
from .browser_fill import BrowserFillAction
from .browser_press import BrowserPressAction
from .browser_eval import BrowserEvalAction
from .browser_wait_for import BrowserWaitForAction
from .browser_screenshot import BrowserScreenshotAction
from .browser_extract import BrowserExtractAction


_REGISTRY: Dict[str, ActionBase] = {}


def _register(action_cls: Type[ActionBase]) -> None:
    _REGISTRY[action_cls.type_name] = action_cls()


for cls in (
    ClickAction, TypeTextAction, PasteAction, HotkeyAction,
    WaitAction, ScrollAction,
    FindImageAction,
    FocusWindowAction,
    SetVariableAction, LogAction,
    LoopDataAction, IfAction, BreakAction, ContinueAction,
    BrowserGotoAction, BrowserClickAction, BrowserFillAction,
    BrowserPressAction, BrowserEvalAction, BrowserWaitForAction,
    BrowserScreenshotAction, BrowserExtractAction,
):
    _register(cls)


CONTROL_FLOW_TYPES = {"loop_data", "if", "break", "continue"}


def get_action(type_name: str) -> Optional[ActionBase]:
    return _REGISTRY.get(type_name)


def all_action_types() -> List[str]:
    return list(_REGISTRY.keys())


def all_action_classes() -> List[Type[ActionBase]]:
    return [type(a) for a in _REGISTRY.values()]


def default_params(type_name: str) -> Dict:
    action = _REGISTRY.get(type_name)
    if action is None:
        return {}
    return type(action).default_params()


def is_control_flow(type_name: str) -> bool:
    return type_name in CONTROL_FLOW_TYPES


__all__ = [
    "ActionBase", "ActionResult",
    "get_action", "all_action_types", "all_action_classes",
    "default_params", "is_control_flow",
    "CONTROL_FLOW_TYPES",
]
