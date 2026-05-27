"""Browser screenshot action: take a screenshot and save to file."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class BrowserScreenshotAction(ActionBase):
    type_name = "browser_screenshot"
    display_name = "浏览器-截图"
    description = "对浏览器页面或指定元素截图并保存"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"path": "", "full_page": False, "selector": ""}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        path = params.get("path", "")
        if not path:
            return ActionResult(False, "保存路径不能为空")
        full_page = params.get("full_page", False)
        selector = params.get("selector", "")
        try:
            if selector:
                el = bm.page.query_selector(selector)
                if el is None:
                    return ActionResult(False, f"元素未找到: {selector}")
                el.screenshot(path=path)
            else:
                bm.page.screenshot(path=path, full_page=full_page)
            return ActionResult(True, f"截图已保存: {path}")
        except Exception as e:
            return ActionResult(False, f"截图失败: {e}")
