"""Main window: three-column layout with menu/toolbar, log panel, run controls."""
import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QFileDialog,
    QMessageBox, QStatusBar, QLineEdit, QLabel, QInputDialog,
)

from ..core.workflow import Workflow, WorkflowSettings
from ..core.executor import WorkflowExecutor
from ..persistence.workflow_io import load_workflow, save_workflow, workflow_filename_suggestion
from .step_list_panel import StepListPanel
from .step_editor_panel import StepEditorPanel
from .log_panel import LogPanel
from .side_tabs.template_library import TemplateLibraryTab
from .side_tabs.data_source_panel import DataSourceTab
from .side_tabs.settings_panel import SettingsTab


logger = logging.getLogger(__name__)


# Default save location for workflows
DEFAULT_WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "workflows"


class _ExecutorThread(QThread):
    """Run the executor's run() on a dedicated QThread."""
    def __init__(self, executor: WorkflowExecutor, parent=None):
        super().__init__(parent)
        self.executor = executor

    def run(self) -> None:  # noqa: D401 (override)
        self.executor.run()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoWorkflow")
        self.resize(1280, 800)

        self._workflow: Workflow = Workflow(name="未命名工作流")
        self._current_path: Optional[Path] = None
        self._dirty = False

        self._executor: Optional[WorkflowExecutor] = None
        self._executor_thread: Optional[_ExecutorThread] = None

        self._build_ui()
        self._build_menu()
        self._bind_workflow()
        self._update_title()

    # ---------- UI construction ----------
    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Workflow name bar (top thin strip)
        name_bar = QHBoxLayout()
        name_bar.setContentsMargins(8, 6, 8, 6)
        name_bar.addWidget(QLabel("工作流名:"))
        self.name_edit = QLineEdit(self._workflow.name)
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_bar.addWidget(self.name_edit, 1)
        outer.addLayout(name_bar)

        # Main horizontal splitter: list | editor | (placeholder for right tabs)
        self.h_split = QSplitter(Qt.Orientation.Horizontal)

        self.step_list = StepListPanel()
        self.editor = StepEditorPanel()

        # Right side: tabbed (template library, data source)
        from PySide6.QtWidgets import QTabWidget
        self.right_tabs = QTabWidget()
        self.template_tab = TemplateLibraryTab(DEFAULT_WORKFLOW_DIR.parent / "templates")
        self.data_source_tab = DataSourceTab()
        self.settings_tab = SettingsTab()
        self.right_tabs.addTab(self.template_tab, "模板库")
        self.right_tabs.addTab(self.data_source_tab, "数据源")
        self.right_tabs.addTab(self.settings_tab, "设置")

        self.h_split.addWidget(self.step_list)
        self.h_split.addWidget(self.editor)
        self.h_split.addWidget(self.right_tabs)
        self.h_split.setStretchFactor(0, 2)
        self.h_split.setStretchFactor(1, 4)
        self.h_split.setStretchFactor(2, 2)
        self.h_split.setSizes([260, 600, 240])

        # Vertical splitter for log panel at bottom
        self.v_split = QSplitter(Qt.Orientation.Vertical)
        self.v_split.addWidget(self.h_split)
        self.log_panel = LogPanel()
        self.v_split.addWidget(self.log_panel)
        self.v_split.setStretchFactor(0, 4)
        self.v_split.setStretchFactor(1, 1)
        self.v_split.setSizes([600, 200])

        outer.addWidget(self.v_split, 1)
        self.setCentralWidget(central)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

        # Wire signals
        self.step_list.step_selected.connect(self.editor.show_step)
        self.step_list.steps_changed.connect(self._on_steps_changed)
        self.editor.step_modified.connect(self._on_step_modified)
        self.template_tab.workflow_modified.connect(self._on_side_modified)
        self.data_source_tab.workflow_modified.connect(self._on_side_modified)
        self.settings_tab.workflow_modified.connect(self._on_side_modified)

    def _build_menu(self):
        mb = self.menuBar()

        # File
        m_file = mb.addMenu("文件(&F)")
        act_new = QAction("新建", self); act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self.action_new)
        m_file.addAction(act_new)

        act_open = QAction("打开...", self); act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.action_open)
        m_file.addAction(act_open)

        act_save = QAction("保存", self); act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self.action_save)
        m_file.addAction(act_save)

        act_save_as = QAction("另存为...", self); act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(self.action_save_as)
        m_file.addAction(act_save_as)

        m_file.addSeparator()
        act_quit = QAction("退出", self); act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        # Run
        m_run = mb.addMenu("运行(&R)")
        self.act_run = QAction("运行", self); self.act_run.setShortcut("F5")
        self.act_run.triggered.connect(self.action_run)
        m_run.addAction(self.act_run)

        self.act_step = QAction("单步", self); self.act_step.setShortcut("F10")
        self.act_step.triggered.connect(self.action_step)
        m_run.addAction(self.act_step)

        self.act_pause = QAction("暂停/继续", self); self.act_pause.setShortcut("F6")
        self.act_pause.triggered.connect(self.action_pause_toggle)
        m_run.addAction(self.act_pause)

        self.act_stop = QAction("停止", self); self.act_stop.setShortcut("Shift+F5")
        self.act_stop.triggered.connect(self.action_stop)
        m_run.addAction(self.act_stop)

        m_run.addSeparator()
        act_bp = QAction("切换断点", self); act_bp.setShortcut("F9")
        act_bp.triggered.connect(self._toggle_breakpoint_on_selected)
        m_run.addAction(act_bp)

        # Help
        m_help = mb.addMenu("帮助(&H)")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _bind_workflow(self):
        self.step_list.set_workflow(self._workflow)
        self.editor.set_workflow(self._workflow)
        self.template_tab.set_workflow(self._workflow)
        self.data_source_tab.set_workflow(self._workflow)
        self.settings_tab.set_workflow(self._workflow)
        self.name_edit.setText(self._workflow.name)
        self._update_title()

    # ---------- workflow lifecycle ----------
    def _confirm_discard_unsaved(self) -> bool:
        if not self._dirty:
            return True
        ret = QMessageBox.question(
            self, "未保存的更改",
            "当前工作流有未保存的更改，确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

    def action_new(self):
        if not self._confirm_discard_unsaved():
            return
        self._workflow = Workflow(name="未命名工作流", settings=WorkflowSettings())
        self._current_path = None
        self._dirty = False
        self._bind_workflow()
        logger.info("已新建空白工作流")

    def action_open(self):
        if not self._confirm_discard_unsaved():
            return
        DEFAULT_WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        path_str, _ = QFileDialog.getOpenFileName(
            self, "打开工作流", str(DEFAULT_WORKFLOW_DIR),
            "AutoWorkflow files (*.awf.json);;JSON files (*.json);;All files (*)",
        )
        if not path_str:
            return
        try:
            wf = load_workflow(path_str)
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"无法加载工作流:\n{e}")
            logger.error(f"打开工作流失败: {e}")
            return
        self._workflow = wf
        self._current_path = Path(path_str)
        self._dirty = False
        self._bind_workflow()
        logger.info(f"已打开: {path_str}")

    def action_save(self):
        if self._current_path is None:
            self.action_save_as()
            return
        try:
            save_workflow(self._workflow, self._current_path)
            self._dirty = False
            self._update_title()
            self.statusBar().showMessage(f"已保存: {self._current_path}", 3000)
            logger.info(f"已保存: {self._current_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"{e}")
            logger.error(f"保存失败: {e}")

    def action_save_as(self):
        DEFAULT_WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
        default_name = workflow_filename_suggestion(self._workflow)
        default_path = str(DEFAULT_WORKFLOW_DIR / default_name)
        path_str, _ = QFileDialog.getSaveFileName(
            self, "另存为", default_path,
            "AutoWorkflow files (*.awf.json);;JSON files (*.json)",
        )
        if not path_str:
            return
        # Ensure .awf.json suffix
        if not path_str.endswith(".json"):
            path_str += ".awf.json"
        try:
            save_workflow(self._workflow, path_str)
            self._current_path = Path(path_str)
            self._dirty = False
            self._update_title()
            logger.info(f"已另存为: {path_str}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"{e}")

    # ---------- run controls ----------
    def action_run(self):
        if self._executor_thread and self._executor_thread.isRunning():
            QMessageBox.information(self, "正在运行", "工作流已在运行中")
            return
        if not self._workflow.steps:
            QMessageBox.information(self, "无步骤", "工作流没有步骤")
            return
        self._start_executor(single_step_first=False)

    def action_step(self):
        if self._executor_thread and self._executor_thread.isRunning():
            # Already running — just request a single step (resume from pause)
            if self._executor:
                self._executor.step_once()
            return
        if not self._workflow.steps:
            return
        self._start_executor(single_step_first=True)

    def action_pause_toggle(self):
        if not self._executor:
            return
        from ..core.executor import ExecutorState
        if self._executor.state == ExecutorState.PAUSED:
            self._executor.resume()
        else:
            self._executor.pause()

    def action_stop(self):
        if self._executor:
            self._executor.stop()

    def _start_executor(self, single_step_first: bool):
        # project_root: the directory containing the workflows/ and templates/ folders
        project_root = DEFAULT_WORKFLOW_DIR.parent
        self._executor = WorkflowExecutor(self._workflow, project_root=project_root)
        self._executor.step_started.connect(self._on_step_started)
        self._executor.step_finished.connect(self._on_step_finished)
        self._executor.log_emitted.connect(self.log_panel.append_log)
        self._executor.finished.connect(self._on_executor_finished)
        self._executor.state_changed.connect(self._on_state_changed)

        self._executor_thread = _ExecutorThread(self._executor)
        self._executor_thread.start()
        if single_step_first:
            self._executor.step_once()

        self.statusBar().showMessage("运行中...")

    def _on_step_started(self, step_id: str):
        self.step_list.mark_current(step_id)

    def _on_step_finished(self, step_id: str, success: bool, message: str):
        # Keep highlighting until next step starts; nothing to do here for now
        pass

    def _on_executor_finished(self, ok: bool, summary: str):
        self.step_list.mark_current(None)
        self.statusBar().showMessage(summary, 5000)
        if self._executor_thread:
            self._executor_thread.quit()
            self._executor_thread.wait(2000)
            self._executor_thread = None
        self._executor = None

    def _on_state_changed(self, state: str):
        self.statusBar().showMessage(f"状态: {state}")

    # ---------- edit signals ----------
    def _on_name_changed(self, text: str):
        if text != self._workflow.name:
            self._workflow.name = text
            self._mark_dirty()

    def _on_steps_changed(self):
        self.editor.refresh_jump_targets()
        self._mark_dirty()

    def _on_step_modified(self, step_id: str):
        self.step_list.refresh_item(step_id)
        self._mark_dirty()

    def _on_side_modified(self):
        """Called when template library or data source tab modifies the workflow."""
        self._mark_dirty()
        self.editor._propagate_template_groups()

    def _toggle_breakpoint_on_selected(self):
        sid = self.step_list.selected_step_id()
        if sid is None:
            return
        # Reuse step_list's toggle path
        self.step_list._toggle_breakpoint()

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def _update_title(self):
        suffix = " *" if self._dirty else ""
        name = self._current_path.name if self._current_path else "未保存"
        self.setWindowTitle(f"AutoWorkflow — {name}{suffix}")

    # ---------- misc ----------
    def _about(self):
        QMessageBox.information(
            self, "关于 AutoWorkflow",
            "AutoWorkflow Phase 1 MVP\n\n"
            "网页自动化工作流构建器。\n"
            "查看 TECH_DOC.md 了解详细设计。",
        )

    def closeEvent(self, event):
        if not self._confirm_discard_unsaved():
            event.ignore()
            return
        if self._executor:
            self._executor.stop()
        if self._executor_thread:
            self._executor_thread.quit()
            self._executor_thread.wait(2000)
        event.accept()
