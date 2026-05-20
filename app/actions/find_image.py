"""find_image action.

Looks up a template group on the current workflow, runs the matcher, and on
success writes these variables to the execution context:
  - found       : bool
  - match_pos   : (x, y) tuple (center of the best match)
  - match_score : float
  - match_box   : (x, y, w, h) bounding box

Phase 2 supports first_hit and best_score strategies via the TemplateGroup.
"""
from typing import Any, Dict, Optional, Tuple
from .base import ActionBase, ActionResult


class FindImageAction(ActionBase):
    type_name = "find_image"
    display_name = "查找图片"
    description = "在屏幕上查找模板图片；成功后位置写入 ${match_pos}"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "template": "",            # template group name
            "region": None,            # [x,y,w,h] or null = use group default
            "confidence": None,        # override per-variant confidence
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        from ..core.matcher import TemplateMatcher

        group_name = params.get("template", "")
        if not group_name:
            return ActionResult(False, "find_image: 'template' is empty")

        # The executor injects the workflow + templates_dir into context attrs
        workflow = getattr(context, "workflow", None)
        templates_dir = getattr(context, "templates_dir", None)
        if workflow is None or templates_dir is None:
            return ActionResult(False, "find_image: executor did not inject workflow/templates_dir")

        group = workflow.templates.get(group_name)
        if group is None:
            return ActionResult(False, f"find_image: template group '{group_name}' not in workflow")

        region = params.get("region")
        if region is not None:
            try:
                region = tuple(int(v) for v in region)
                if len(region) != 4:
                    raise ValueError
            except (TypeError, ValueError):
                return ActionResult(False, f"find_image: region must be [x,y,w,h]")

        confidence = params.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        matcher = TemplateMatcher(templates_dir)
        try:
            result = matcher.match_group(group, region=region, confidence_override=confidence)
        except Exception as e:
            return ActionResult(False, f"find_image error: {e}")

        if result is None:
            # Write found=False so downstream if-step can check
            context.set("found", False)
            return ActionResult(False, f"not found (group={group_name})")

        context.set("found", True)
        context.set("match_pos", list(result.center))
        context.set("match_score", result.score)
        context.set("match_box", [result.top_left[0], result.top_left[1],
                                  result.width, result.height])
        return ActionResult(
            True,
            f"found at {result.center} score={result.score:.3f} variant={result.variant_file}",
            data={"match_pos": list(result.center), "score": result.score},
        )
