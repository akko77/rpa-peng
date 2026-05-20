"""Log action: emit a log message during execution."""
from typing import Any, Dict
from .base import ActionBase, ActionResult


class LogAction(ActionBase):
    type_name = "log"
    display_name = "日志"
    description = "输出一条日志（支持 ${var} 插值）"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"message": "", "level": "info"}

    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        message = params.get("message", "")
        level = params.get("level", "info")
        if level not in ("debug", "info", "warning", "error"):
            level = "info"
        # The executor will pick this up via ActionResult.data and emit a log signal.
        return ActionResult(
            True,
            f"[{level}] {message}",
            data={"log_level": level, "log_message": str(message)},
        )
