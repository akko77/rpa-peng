"""Wait action.

Phase 1: only 'fixed' mode (wait a fixed number of seconds).
Phase 2 will add 'until_image' mode that polls find_image until success/timeout.
"""
import time
from typing import Any, Dict
from .base import ActionBase, ActionResult


class WaitAction(ActionBase):
    type_name = "wait"
    display_name = "等待"
    description = "等待固定时间，或等待图片出现（Phase 2）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "mode": "fixed",
            "seconds": 1.0,
            # until_image fields:
            "template": "",
            "region": None,
            "timeout": 10.0,
            "poll_interval": 0.5,
        }

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        mode = params.get("mode", "fixed")

        if mode == "fixed":
            try:
                seconds = float(params.get("seconds", 1.0) or 0.0)
            except (TypeError, ValueError):
                return ActionResult(False, f"invalid seconds: {params.get('seconds')}")
            if seconds < 0:
                return ActionResult(False, "seconds cannot be negative")
            # Sleep in small chunks so a stop request can interrupt promptly.
            elapsed = 0.0
            chunk = 0.1
            while elapsed < seconds:
                time.sleep(min(chunk, seconds - elapsed))
                elapsed += chunk
            return ActionResult(True, f"waited {seconds}s")

        if mode == "until_image":
            template_name = params.get("template", "")
            if not template_name:
                return ActionResult(False, "wait(until_image): 'template' is empty")
            try:
                timeout = float(params.get("timeout", 10.0) or 10.0)
            except (TypeError, ValueError):
                return ActionResult(False, f"invalid timeout: {params.get('timeout')}")
            poll = float(params.get("poll_interval", 0.5) or 0.5)
            region = params.get("region")
            if region is not None:
                try:
                    region = tuple(int(v) for v in region)
                    if len(region) != 4:
                        raise ValueError
                except (TypeError, ValueError):
                    return ActionResult(False, "wait: region must be [x,y,w,h]")

            workflow = getattr(context, "workflow", None)
            templates_dir = getattr(context, "templates_dir", None)
            if workflow is None or templates_dir is None:
                return ActionResult(False, "wait(until_image): executor context missing")
            group = workflow.templates.get(template_name)
            if group is None:
                return ActionResult(False, f"wait(until_image): template '{template_name}' not found")

            from ..core.matcher import TemplateMatcher
            matcher = TemplateMatcher(templates_dir)

            elapsed = 0.0
            while elapsed < timeout:
                try:
                    result = matcher.match_group(group, region=region)
                except Exception as e:
                    return ActionResult(False, f"match error: {e}")
                if result is not None:
                    context.set("found", True)
                    context.set("match_pos", list(result.center))
                    context.set("match_score", result.score)
                    return ActionResult(
                        True,
                        f"image found after {elapsed:.1f}s at {result.center}",
                    )
                time.sleep(poll)
                elapsed += poll
            return ActionResult(False, f"wait(until_image) timeout after {timeout}s")

        return ActionResult(False, f"unknown wait mode: {mode}")
