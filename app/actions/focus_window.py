"""focus_window action.

Brings a window matching the given title pattern to the foreground.
Windows-only (uses pywin32).
"""
import re
from typing import Any, Dict, Optional
from .base import ActionBase, ActionResult


class FocusWindowAction(ActionBase):
    type_name = "focus_window"
    display_name = "切换窗口"
    description = "按标题匹配把目标窗口切到前台（Windows 专属，比固定坐标点击切换更稳）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "title_pattern": "",
            "exact": False,
            "class_name": None,
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        # Lazy imports so the rest of the app works on non-Windows
        try:
            import win32gui
            import win32con
        except ImportError:
            return ActionResult(False, "pywin32 not installed (Windows-only feature)")

        pattern = params.get("title_pattern", "")
        if not isinstance(pattern, str) or not pattern.strip():
            return ActionResult(False, "focus_window: 'title_pattern' is empty")
        exact = bool(params.get("exact", False))
        class_name = params.get("class_name") or None

        # Compile regex once for non-exact match
        try:
            regex = None if exact else re.compile(pattern)
        except re.error as e:
            return ActionResult(False, f"focus_window: bad regex {pattern!r}: {e}")

        results = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            cls = win32gui.GetClassName(hwnd)
            if class_name and cls != class_name:
                return
            if exact:
                if title == pattern:
                    results.append((hwnd, title, cls))
            else:
                if regex.search(title):
                    results.append((hwnd, title, cls))

        win32gui.EnumWindows(callback, None)
        if not results:
            return ActionResult(False, f"focus_window: no window matches {pattern!r}")

        hwnd, title, cls = results[0]
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            return ActionResult(False, f"focus_window: SetForegroundWindow failed: {e}")

        return ActionResult(True, f"focused: {title!r} (class={cls})",
                            data={"hwnd": hwnd, "title": title, "class_name": cls})
