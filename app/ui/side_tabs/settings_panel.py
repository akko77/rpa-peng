"""Workflow settings panel: retry, pause, failure policy."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QSpinBox, QDoubleSpinBox,
    QComboBox, QLabel, QGroupBox,
)

from ...core.workflow import Workflow


class SettingsTab(QWidget):
    """Right-side tab for editing WorkflowSettings."""
    workflow_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow = None
        self._suspend = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Retry group ---
        retry_box = QGroupBox("失败重试")
        retry_form = QFormLayout(retry_box)

        self.retry_max = QSpinBox()
        self.retry_max.setRange(0, 10)
        self.retry_max.setToolTip("步骤失败后自动重试的次数 (0=不重试)")
        self.retry_max.valueChanged.connect(self._on_changed)
        retry_form.addRow("最大重试次数:", self.retry_max)

        self.retry_delay = QDoubleSpinBox()
        self.retry_delay.setRange(0.1, 60.0)
        self.retry_delay.setSingleStep(0.5)
        self.retry_delay.setDecimals(1)
        self.retry_delay.setSuffix(" 秒")
        self.retry_delay.setToolTip("每次重试前等待的时间 (让遮罩/弹窗消失)")
        self.retry_delay.valueChanged.connect(self._on_changed)
        retry_form.addRow("重试间隔:", self.retry_delay)

        layout.addWidget(retry_box)

        # --- Failure policy ---
        policy_box = QGroupBox("失败策略")
        policy_form = QFormLayout(policy_box)

        self.failure_policy = QComboBox()
        self.failure_policy.addItem("继续执行下一步", "continue")
        self.failure_policy.addItem("终止工作流", "abort")
        self.failure_policy.setToolTip("步骤失败且重试用尽后的行为")
        self.failure_policy.currentIndexChanged.connect(self._on_changed)
        policy_form.addRow("失败时:", self.failure_policy)

        layout.addWidget(policy_box)

        # --- Pause settings ---
        pause_box = QGroupBox("自动休息")
        pause_form = QFormLayout(pause_box)

        self.short_every = QSpinBox()
        self.short_every.setRange(0, 1000)
        self.short_every.setToolTip("每执行 N 个数据项后短休息 (0=禁用)")
        self.short_every.valueChanged.connect(self._on_changed)
        pause_form.addRow("短休息间隔:", self.short_every)

        self.short_sec = QSpinBox()
        self.short_sec.setRange(0, 7200)
        self.short_sec.setSuffix(" 秒")
        self.short_sec.valueChanged.connect(self._on_changed)
        pause_form.addRow("短休息时长:", self.short_sec)

        self.long_every = QSpinBox()
        self.long_every.setRange(0, 10000)
        self.long_every.setToolTip("每执行 N 个数据项后长休息 (0=禁用)")
        self.long_every.valueChanged.connect(self._on_changed)
        pause_form.addRow("长休息间隔:", self.long_every)

        self.long_sec = QSpinBox()
        self.long_sec.setRange(0, 7200)
        self.long_sec.setSuffix(" 秒")
        self.long_sec.valueChanged.connect(self._on_changed)
        pause_form.addRow("长休息时长:", self.long_sec)

        layout.addWidget(pause_box)
        layout.addStretch(1)

    def set_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self._load_settings()

    def _load_settings(self):
        if not self._workflow:
            return
        self._suspend = True
        s = self._workflow.settings
        self.retry_max.setValue(s.retry_max)
        self.retry_delay.setValue(s.retry_delay_sec)
        idx = self.failure_policy.findData(s.failure_policy)
        if idx >= 0:
            self.failure_policy.setCurrentIndex(idx)
        self.short_every.setValue(s.short_pause_every)
        self.short_sec.setValue(s.short_pause_sec)
        self.long_every.setValue(s.long_pause_every)
        self.long_sec.setValue(s.long_pause_sec)
        self._suspend = False

    def _on_changed(self):
        if self._suspend or not self._workflow:
            return
        s = self._workflow.settings
        s.retry_max = self.retry_max.value()
        s.retry_delay_sec = self.retry_delay.value()
        s.failure_policy = self.failure_policy.currentData()
        s.short_pause_every = self.short_every.value()
        s.short_pause_sec = self.short_sec.value()
        s.long_pause_every = self.long_every.value()
        s.long_pause_sec = self.long_sec.value()
        self.workflow_modified.emit()
