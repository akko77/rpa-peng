"""Browser goto action: navigate to a URL."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserGotoAction(ActionBase):
    type_name = "browser_goto"
    display_name = "浏览器-打开URL"
    description = "导航浏览器到指定 URL"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"url": "", "wait_until": "load"}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        url = params.get("url", "")
        if not url:
            return ActionResult(False, "URL 不能为空")
        # Auto-prepend https:// if no scheme is provided
        if not url.startswith(("http://", "https://", "file://", "about:", "data:")):
            url = "https://" + url
        wait_until = params.get("wait_until", "load")
        try:
            bm.page.goto(url, wait_until=wait_until)
            return ActionResult(True, f"已打开: {url}")
        except Exception as e:
            return ActionResult(False, f"导航失败: {e}")
