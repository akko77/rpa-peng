"""Browser click action: click by CSS selector or by template image."""
import io
from typing import Any, Dict, Optional, Tuple

from .base import ActionBase, ActionResult


class BrowserClickAction(ActionBase):
    type_name = "browser_click"
    display_name = "浏览器-点击元素"
    description = "通过 CSS 选择器或模板图片点击浏览器中的元素"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "selector": "",
            "position_mode": "selector",  # selector | template
            "template": "",
            "confidence": None,
            "button": "left",
            "clicks": 1,
            "timeout": 30000,
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        bm = getattr(context, "browser_manager", None)
        if bm is None:
            return ActionResult(False, "浏览器未初始化")

        position_mode = params.get("position_mode", "selector")
        button = params.get("button", "left")
        clicks = int(params.get("clicks", 1) or 1)

        if position_mode == "template":
            return self._click_by_template(bm, params, context, button, clicks)
        else:
            return self._click_by_selector(bm, params, button, clicks)

    def _click_by_selector(self, bm, params, button, clicks) -> ActionResult:
        selector = params.get("selector", "")
        if not selector:
            return ActionResult(False, "选择器不能为空")
        timeout = float(params.get("timeout", 30000) or 30000)
        try:
            bm.page.click(selector, button=button, click_count=clicks, timeout=timeout)
            return ActionResult(True, f"已点击: {selector}")
        except Exception as e:
            return ActionResult(False, f"点击失败: {e}")

    def _click_by_template(self, bm, params, context, button, clicks) -> ActionResult:
        template_name = params.get("template", "")
        if not template_name:
            return ActionResult(False, "模板组名不能为空")

        workflow = getattr(context, "workflow", None)
        templates_dir = getattr(context, "templates_dir", None)
        if workflow is None or templates_dir is None:
            return ActionResult(False, "浏览器点击(模板): 缺少工作流上下文")
        group = workflow.templates.get(template_name)
        if group is None:
            return ActionResult(False, f"模板组 '{template_name}' 未找到")

        confidence_override = params.get("confidence")
        try:
            result = self._match_template_on_page(
                bm.page, group, templates_dir, confidence_override
            )
        except Exception as e:
            return ActionResult(False, f"模板匹配失败: {e}")

        if result is None:
            return ActionResult(False, f"模板 '{template_name}' 未在页面中找到")

        cx, cy = result["center"]
        try:
            bm.page.mouse.click(cx, cy, button=button, click_count=clicks)
            return ActionResult(True, f"已点击模板 '{template_name}' 位置 ({cx}, {cy}) 得分={result['score']:.2f}")
        except Exception as e:
            return ActionResult(False, f"点击失败: {e}")

    @staticmethod
    def _match_template_on_page(page, group, templates_dir: str,
                                confidence_override=None) -> Optional[Dict[str, Any]]:
        """Take a Playwright screenshot, match templates using OpenCV, return match info."""
        import cv2
        import numpy as np
        from pathlib import Path

        # Take page screenshot as bytes
        png_bytes = page.screenshot()
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        screenshot_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if screenshot_bgr is None:
            return None

        tpl_dir = Path(templates_dir)
        best_score = -1.0
        best_cx = 0
        best_cy = 0

        from ..core.matcher import DEFAULT_SCALES

        for variant in group.variants:
            tpl_path = tpl_dir / group.name / variant.file
            if not tpl_path.exists():
                continue
            tpl_bgr = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl_bgr is None:
                continue
            threshold = (
                float(confidence_override)
                if confidence_override is not None
                else float(variant.confidence or group.default_confidence)
            )
            for scale in DEFAULT_SCALES:
                if scale == 1.0:
                    tpl = tpl_bgr
                else:
                    new_w = max(1, int(round(tpl_bgr.shape[1] * scale)))
                    new_h = max(1, int(round(tpl_bgr.shape[0] * scale)))
                    tpl = cv2.resize(tpl_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
                th, tw = tpl.shape[:2]
                ss_h, ss_w = screenshot_bgr.shape[:2]
                if th > ss_h or tw > ss_w:
                    continue
                res = cv2.matchTemplate(screenshot_bgr, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = float(max_val)
                    best_cx = max_loc[0] + tw // 2
                    best_cy = max_loc[1] + th // 2

        if best_score < float(confidence_override or group.default_confidence):
            return None
        return {"center": (best_cx, best_cy), "score": best_score}
