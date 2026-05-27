"""WorkflowExecutor (Phase 2): block-based, data-loop aware."""
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from .workflow import Workflow, Step, DataSource
from .context import ExecutionContext
from .interpolator import interpolate_dict
from .data_source import load_items
from .filter_evaluator import build_filter_fn


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _StopSignal(Exception):
    pass


class ExecutorState:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


TEMPLATES_DIRNAME = "templates"


class WorkflowExecutor(QObject):
    step_started = Signal(str)
    step_finished = Signal(str, bool, str)
    log_emitted = Signal(str, str)
    finished = Signal(bool, str)
    paused_changed = Signal(bool)
    state_changed = Signal(str)

    def __init__(self, workflow: Workflow, project_root: Optional[Path] = None):
        super().__init__()
        self.workflow = workflow
        self.project_root = project_root or Path.cwd()
        self.templates_dir = str(self.project_root / TEMPLATES_DIRNAME)

        self.context = ExecutionContext(workflow.variables)
        self.context.workflow = workflow            # type: ignore[attr-defined]
        self.context.templates_dir = self.templates_dir  # type: ignore[attr-defined]

        from .browser import BrowserManager
        browser_cfg = workflow.settings.browser or {}
        self._browser_manager = BrowserManager(
            headless=browser_cfg.get("headless", False),
            browser_type=browser_cfg.get("browser_type", "chromium"),
            user_data_dir=browser_cfg.get("user_data_dir"),
        )
        self.context.browser_manager = self._browser_manager  # type: ignore[attr-defined]

        self._pause_event = threading.Event(); self._pause_event.set()
        self._stop_event = threading.Event()
        self._single_step_pending = False
        self.state = ExecutorState.IDLE

    # ---------- thread entry ----------
    def run(self) -> None:
        self._set_state(ExecutorState.RUNNING)
        self._log("info", f"开始执行工作流: {self.workflow.name}")
        ok = True
        summary = "完成"
        try:
            if self.workflow.data_source is not None:
                self._run_with_data_source()
            else:
                self._run_block(self.workflow.steps)
            if self._stop_event.is_set():
                ok = False; summary = "用户停止"
        except _StopSignal:
            ok = False; summary = "用户停止"
        except Exception as e:
            ok = False; summary = f"执行器异常: {e}"
            self._log("error", summary)
            self._log("error", traceback.format_exc())
        finally:
            self._browser_manager.close()

        self._set_state(ExecutorState.STOPPED if not ok else ExecutorState.IDLE)
        self._log("info", f"工作流结束: {summary}")
        self.finished.emit(ok, summary)

    # ---------- Top-level data iteration ----------
    def _run_with_data_source(self):
        ds = self.workflow.data_source
        filter_fn = build_filter_fn(ds.filter)
        try:
            items = load_items(ds, filter_fn=filter_fn)
        except Exception as e:
            self._log("error", f"数据源加载失败: {e}")
            return
        self._log("info", f"数据源加载完成, 共 {len(items)} 项 (过滤后)")
        self.context.set("__total__", len(items))
        for idx, item in enumerate(items):
            if self._stop_event.is_set():
                raise _StopSignal()
            self.context.current_item = item
            self.context.current_index = idx
            self.context.set("__index__", idx)
            self._log("info", f"=== 数据项 #{idx + 1}/{len(items)}: {self._brief(item)}")
            try:
                self._run_block(self.workflow.steps)
            except _BreakSignal:
                self._log("info", "顶层 break — 终止数据循环")
                return
            except _ContinueSignal:
                continue
            self._maybe_pause_between_iterations(idx)

    def _maybe_pause_between_iterations(self, idx_done: int):
        s = self.workflow.settings
        n = idx_done + 1
        if s.short_pause_every <= 0:
            return
        if n % s.short_pause_every != 0:
            return
        if s.long_pause_every > 0 and n % s.long_pause_every == 0:
            self._log("info", f"长休息 {s.long_pause_sec}s")
            self._interruptible_sleep(s.long_pause_sec)
        else:
            self._log("info", f"短休息 {s.short_pause_sec}s")
            self._interruptible_sleep(s.short_pause_sec)

    def _interruptible_sleep(self, seconds: float):
        elapsed = 0.0; chunk = 0.5
        while elapsed < seconds:
            if self._stop_event.is_set():
                raise _StopSignal()
            time.sleep(min(chunk, seconds - elapsed))
            elapsed += chunk

    # ---------- Block runner ----------
    def _run_block(self, steps: List[Step], depth: int = 0) -> None:
        from ..actions import get_action, is_control_flow

        if not steps:
            return
        indent = "  " * depth
        id_to_idx = {s.id: i for i, s in enumerate(steps)}
        idx = 0
        while idx < len(steps):
            if self._stop_event.is_set():
                raise _StopSignal()
            step = steps[idx]

            if not step.enabled:
                self._log("info", f"{indent}跳过禁用步骤: [{step.id}] {step.name}")
                idx += 1
                continue

            if step.breakpoint:
                self._log("info", f"{indent}命中断点: [{step.id}] {step.name}")
                self._pause_event.clear()
                self._set_state(ExecutorState.PAUSED)
                self.paused_changed.emit(True)

            self._wait_if_paused()
            self.step_started.emit(step.id)

            if is_control_flow(step.type):
                self._log("info", f"{indent}执行: [{step.id}] {step.name} ({step.type})")
                try:
                    self._run_control_flow(step, depth=depth)
                    self.step_finished.emit(step.id, True, "ok")
                except (_BreakSignal, _ContinueSignal):
                    self.step_finished.emit(step.id, True, "ok")
                    raise
                idx += 1
                self._post_step_pause_if_single_step()
                continue

            self._log("info", f"{indent}执行: [{step.id}] {step.name} ({step.type})")
            action = get_action(step.type)
            if action is None:
                msg = f"未知步骤类型: {step.type}"
                self._log("error", f"{indent}{msg}")
                self.step_finished.emit(step.id, False, msg)
                idx = self._next_after_failure(step, id_to_idx, idx, steps)
                self._post_step_pause_if_single_step()
                continue

            try:
                interpolated = interpolate_dict(step.params or {}, self.context)
            except Exception as e:
                msg = f"参数插值失败: {e}"
                self._log("error", f"{indent}{msg}")
                self.step_finished.emit(step.id, False, msg)
                idx = self._next_after_failure(step, id_to_idx, idx, steps)
                self._post_step_pause_if_single_step()
                continue

            # wait 步骤自带超时机制，不需要重试
            max_retries = 0 if step.type == "wait" else self.workflow.settings.retry_max
            retry_delay = self.workflow.settings.retry_delay_sec
            result = None
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    self._log("info", f"{indent}重试第 {attempt}/{max_retries} 次, 等待 {retry_delay}s ...")
                    self._interruptible_sleep(retry_delay)

                try:
                    result = action.execute(interpolated, self.context)
                except Exception as e:
                    self._log("error", f"{indent}步骤异常: {e}")
                    if attempt < max_retries:
                        continue
                    self._log("error", traceback.format_exc())
                    self.step_finished.emit(step.id, False, str(e))
                    idx = self._next_after_failure(step, id_to_idx, idx, steps)
                    self._post_step_pause_if_single_step()
                    result = None
                    break

                if result.success:
                    break
                if attempt < max_retries:
                    self._log("warning", f"{indent}步骤失败: {result.message}, 准备重试...")

            if result is None:
                continue

            if step.type == "log" and result.data:
                lvl = result.data.get("log_level", "info")
                msg = result.data.get("log_message", "")
                self._log(lvl, f"{indent}{msg}")

            self.step_finished.emit(step.id, result.success, result.message)

            if result.success:
                idx = self._resolve_jump_within_block(step.on_success, id_to_idx, idx + 1)
            else:
                self._log("warning", f"{indent}步骤失败: {result.message}")
                idx = self._next_after_failure(step, id_to_idx, idx, steps)

            self._post_step_pause_if_single_step()

    def _post_step_pause_if_single_step(self):
        if self._single_step_pending:
            self._single_step_pending = False
            self._pause_event.clear()
            self._set_state(ExecutorState.PAUSED)
            self.paused_changed.emit(True)

    # ---------- Control flow ----------
    def _run_control_flow(self, step: Step, depth: int = 0):
        t = step.type
        if t == "loop_data":
            self._run_loop_data(step, depth=depth)
        elif t == "if":
            self._run_if(step, depth=depth)
        elif t == "break":
            raise _BreakSignal()
        elif t == "continue":
            raise _ContinueSignal()

    def _run_loop_data(self, step: Step, depth: int = 0):
        indent = "  " * depth
        item_var = step.params.get("item_var", "item")
        body = step.params.get("body") or []
        src_dict = step.params.get("source") or {}
        try:
            ds = DataSource.from_dict(src_dict)
        except Exception as e:
            self._log("error", f"{indent}loop_data 数据源配置异常: {e}")
            return
        filter_fn = build_filter_fn(ds.filter)
        try:
            items = load_items(ds, filter_fn=filter_fn)
        except Exception as e:
            self._log("error", f"{indent}loop_data 数据源加载失败: {e}")
            return
        self._log("info", f"{indent}loop_data 共 {len(items)} 项 ({step.name})")

        outer_item = self.context.current_item
        outer_index = self.context.current_index
        had_outer_var = item_var in self.context
        outer_var = self.context.get(item_var) if had_outer_var else None

        try:
            for idx, item in enumerate(items):
                if self._stop_event.is_set():
                    raise _StopSignal()
                self.context.current_item = item
                self.context.current_index = idx
                self.context.set(item_var, item)
                self._log("info", f"{indent}loop_data #{idx + 1}/{len(items)}: {self._brief(item)}")
                try:
                    self._run_block(body, depth=depth + 1)
                except _BreakSignal:
                    self._log("info", f"{indent}loop_data: break")
                    break
                except _ContinueSignal:
                    self._log("info", f"{indent}loop_data: continue")
                    continue
        finally:
            self.context.current_item = outer_item
            self.context.current_index = outer_index
            if had_outer_var:
                self.context.set(item_var, outer_var)

    def _run_if(self, step: Step, depth: int = 0):
        indent = "  " * depth
        cond = step.params.get("condition", "")
        then_body = step.params.get("then") or []
        else_body = step.params.get("else") or []
        truthy = self._eval_condition(cond)
        branch_name = "then" if truthy else "else"
        chosen = then_body if truthy else else_body
        self._log(
            "info",
            f"{indent}if 条件 {'真' if truthy else '假'}: {cond!r} → 进入 {branch_name} 分支 "
            f"(共 {len(chosen)} 步)"
        )
        self._run_block(chosen, depth=depth + 1)
        self._log("info", f"{indent}if 结束 (执行了 {branch_name} 分支)")

    def _eval_condition(self, expr: str) -> bool:
        if not expr or not expr.strip():
            return False
        try:
            from simpleeval import SimpleEval, DEFAULT_FUNCTIONS
            se = SimpleEval()
            funcs = dict(DEFAULT_FUNCTIONS)
            funcs.update({"len": len, "str": str, "int": int, "float": float, "bool": bool})
            se.functions = funcs
            se.names = {"item": self.context.current_item, **self.context.snapshot()}
            return bool(se.eval(expr))
        except Exception as e:
            self._log("error", f"if 条件求值失败: {e}")
            return False

    # ---------- Jump helpers ----------
    def _resolve_jump_within_block(self, target_id, id_to_idx, default_idx):
        if target_id is None:
            return default_idx
        if target_id in id_to_idx:
            return id_to_idx[target_id]
        self._log("warning", f"跳转目标 {target_id} 不在当前块内, 按顺序继续")
        return default_idx

    def _next_after_failure(self, step, id_to_idx, idx, steps):
        if step.on_failure:
            return self._resolve_jump_within_block(step.on_failure, id_to_idx, idx + 1)
        policy = self.workflow.settings.failure_policy
        if policy == "abort":
            self._log("error", "failure_policy=abort, 终止当前块")
            raise _StopSignal()
        return idx + 1

    # ---------- Pause helpers ----------
    def _wait_if_paused(self):
        if self._pause_event.is_set():
            return
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                raise _StopSignal()
            time.sleep(0.05)
        if self.state == ExecutorState.PAUSED:
            self._set_state(ExecutorState.RUNNING)
            self.paused_changed.emit(False)

    def _set_state(self, s: str) -> None:
        self.state = s
        self.state_changed.emit(s)

    def _log(self, level: str, message: str) -> None:
        self.log_emitted.emit(level, message)

    @staticmethod
    def _brief(item) -> str:
        s = str(item)
        return s if len(s) <= 80 else s[:77] + "..."

    # ---------- public control ----------
    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def step_once(self) -> None:
        self._single_step_pending = True
        self._pause_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
