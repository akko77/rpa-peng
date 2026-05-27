"""Browser extract action: extract data from elements into variables."""
from typing import Any, Dict, List
from .base import ActionBase, ActionResult


class BrowserExtractAction(ActionBase):
    type_name = "browser_extract"
    display_name = "浏览器-提取数据"
    description = "从浏览器元素中提取文本/属性/HTML/值，存入变量"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "selector": "",
            "extract": "text",
            "attribute": "",
            "save_as": "",
            "all": False,
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")
        selector = params.get("selector", "")
        if not selector:
            return ActionResult(False, "选择器不能为空")
        extract = params.get("extract", "text")
        attribute = params.get("attribute", "")
        save_as = params.get("save_as", "")
        extract_all = params.get("all", False)

        try:
            if extract_all:
                elements = bm.page.query_selector_all(selector)
                values = []
                for el in elements:
                    values.append(self._extract_one(el, extract, attribute))
                result = values
            else:
                el = bm.page.query_selector(selector)
                if el is None:
                    return ActionResult(False, f"元素未找到: {selector}")
                result = self._extract_one(el, extract, attribute)

            if save_as:
                context.set(save_as, result)
            return ActionResult(True, f"提取结果: {result}")
        except Exception as e:
            return ActionResult(False, f"提取失败: {e}")

    @staticmethod
    def _extract_one(element, extract: str, attribute: str = "") -> Any:
        if extract == "text":
            return element.text_content()
        elif extract == "attribute":
            return element.get_attribute(attribute) if attribute else None
        elif extract == "inner_html":
            return element.inner_html()
        elif extract == "value":
            return element.input_value()
        return element.text_content()
