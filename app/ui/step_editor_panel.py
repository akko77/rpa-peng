"""Step editor panel: middle column.

Renders a form for the currently selected step's params, switching the form
based on step.type. Includes integration with the position picker (F8) and
common fields (name, on_success, on_failure).
"""
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QLabel, QPushButton, QHBoxLayout, QPlainTextEdit, QCheckBox,
    QGroupBox, QStackedWidget, QSizePolicy, QFrame,
)

from ..core.workflow import Workflow, Step
from .overlays.position_picker import PositionPicker


# ---------------------- Position widget (used by click, scroll) ----------------------

class PositionWidget(QWidget):
    """Compose a position dict {type, x, y} or {type, var}.

    Phase 1 supports types: fixed, variable. (template is Phase 2.)
    """
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.type_combo = QComboBox()
        self.type_combo.addItem("固定坐标", "fixed")
        self.type_combo.addItem("变量", "variable")
        self.type_combo.addItem("模板 (运行时查找)", "template")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        # Fixed: x / y / pick / verify
        self.x_spin = QSpinBox(); self.x_spin.setRange(-99999, 99999)
        self.y_spin = QSpinBox(); self.y_spin.setRange(-99999, 99999)
        self.x_spin.valueChanged.connect(lambda *_: self.changed.emit())
        self.y_spin.valueChanged.connect(lambda *_: self.changed.emit())
        self.pick_btn = QPushButton("拾取 (F8)")
        self.pick_btn.clicked.connect(self._pick_position)
        layout.addWidget(QLabel(" x:"))
        layout.addWidget(self.x_spin)
        layout.addWidget(QLabel(" y:"))
        layout.addWidget(self.y_spin)
        layout.addWidget(self.pick_btn)

        # Variable: var name
        self.var_input = QLineEdit()
        self.var_input.setPlaceholderText("变量名")
        self.var_input.textChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.var_input)

        # Template: template group name
        self.template_input = QComboBox()
        self.template_input.setMinimumWidth(120)
        self.template_input.currentIndexChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.template_input)

        layout.addStretch(1)
        self._on_type_changed()

    def _on_type_changed(self):
        pos_type = self.type_combo.currentData()
        fixed = pos_type == "fixed"
        is_var = pos_type == "variable"
        is_tpl = pos_type == "template"
        self.x_spin.setVisible(fixed)
        self.y_spin.setVisible(fixed)
        self.pick_btn.setVisible(fixed)
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if isinstance(w, QLabel) and w.text().strip() in ("x:", "y:"):
                w.setVisible(fixed)
        self.var_input.setVisible(is_var)
        self.template_input.setVisible(is_tpl)
        self.changed.emit()

    def _pick_position(self):
        picker = PositionPicker()
        pos = picker.pick()
        if pos is not None:
            self.x_spin.setValue(pos[0])
            self.y_spin.setValue(pos[1])

    def set_value(self, value: Optional[Dict[str, Any]]):
        if not isinstance(value, dict):
            value = {"type": "fixed", "x": 0, "y": 0}
        ptype = value.get("type", "fixed")
        idx = self.type_combo.findData(ptype)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.x_spin.setValue(int(value.get("x", 0) or 0))
        self.y_spin.setValue(int(value.get("y", 0) or 0))
        self.var_input.setText(str(value.get("var", "") or ""))
        tpl = str(value.get("template", "") or "")
        idx = self.template_input.findText(tpl)
        if idx >= 0:
            self.template_input.setCurrentIndex(idx)
        elif tpl:
            self.template_input.setCurrentText(tpl)

    def get_value(self) -> Dict[str, Any]:
        ptype = self.type_combo.currentData()
        if ptype == "fixed":
            return {"type": "fixed", "x": self.x_spin.value(), "y": self.y_spin.value()}
        if ptype == "variable":
            return {"type": "variable", "var": self.var_input.text().strip()}
        if ptype == "template":
            return {"type": "template", "template": self.template_input.currentText().strip()}
        return {"type": "fixed", "x": 0, "y": 0}

    def set_template_groups(self, names: List[str]) -> None:
        cur = self.template_input.currentText()
        self.template_input.blockSignals(True)
        self.template_input.clear()
        self.template_input.addItems(names)
        if cur:
            idx = self.template_input.findText(cur)
            if idx >= 0:
                self.template_input.setCurrentIndex(idx)
        self.template_input.blockSignals(False)


# ---------------------- Step-type specific forms ----------------------

class _BaseForm(QWidget):
    """A form that knows how to load params from / write to a Step's params dict."""
    changed = Signal()

    def load(self, params: Dict[str, Any]) -> None:
        raise NotImplementedError

    def write_to(self, params: Dict[str, Any]) -> None:
        raise NotImplementedError

    def set_template_groups(self, names: List[str]) -> None:
        """Update template group dropdown choices. Override in subclasses that need it."""
        pass


class ClickForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.position = PositionWidget()
        self.position.changed.connect(lambda *_: self.changed.emit())
        form.addRow("位置:", self.position)

        self.button_combo = QComboBox()
        self.button_combo.addItems(["left", "right", "middle"])
        self.button_combo.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("按键:", self.button_combo)

        self.clicks_spin = QSpinBox()
        self.clicks_spin.setRange(1, 10)
        self.clicks_spin.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("点击次数:", self.clicks_spin)

    def load(self, p: Dict[str, Any]) -> None:
        self.position.set_value(p.get("position"))
        self.button_combo.setCurrentText(p.get("button", "left"))
        self.clicks_spin.setValue(int(p.get("clicks", 1) or 1))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["position"] = self.position.get_value()
        p["button"] = self.button_combo.currentText()
        p["clicks"] = self.clicks_spin.value()

    def set_template_groups(self, names: List[str]) -> None:
        self.position.set_template_groups(names)


class TypeTextForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("文本，支持 ${var} / ${item.field} 插值")
        self.text.setMaximumHeight(120)
        self.text.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("文本:", self.text)

        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.0, 5.0); self.interval.setSingleStep(0.01); self.interval.setDecimals(3)
        self.interval.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("每键间隔(秒):", self.interval)

    def load(self, p: Dict[str, Any]) -> None:
        self.text.setPlainText(str(p.get("text", "")))
        self.interval.setValue(float(p.get("interval", 0.0) or 0.0))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["text"] = self.text.toPlainText()
        p["interval"] = self.interval.value()


class PasteForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("内容，支持 ${var} 插值。粘贴对中文/特殊字符更稳定")
        self.text.setMaximumHeight(120)
        self.text.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("文本:", self.text)

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.0, 5.0); self.delay.setSingleStep(0.05); self.delay.setDecimals(2)
        self.delay.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("复制后延迟(秒):", self.delay)

    def load(self, p: Dict[str, Any]) -> None:
        self.text.setPlainText(str(p.get("text", "")))
        self.delay.setValue(float(p.get("delay_after_copy", 0.1) or 0.1))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["text"] = self.text.toPlainText()
        p["delay_after_copy"] = self.delay.value()


class HotkeyForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.keys = QLineEdit()
        self.keys.setPlaceholderText("例如: ctrl+a, ctrl+shift+t, alt+f4")
        self.keys.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("组合键:", self.keys)
        hint = QLabel("常用: ctrl / shift / alt / win / 字母 / 数字 / f1-f12 / enter / esc / tab / space")
        hint.setStyleSheet("color: #888;")
        form.addRow("", hint)

    def load(self, p: Dict[str, Any]) -> None:
        self.keys.setText(str(p.get("keys", "")))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["keys"] = self.keys.text().strip()


class WaitForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.mode = QComboBox()
        self.mode.addItem("固定时间", "fixed")
        self.mode.addItem("等待图片出现", "until_image")
        self.mode.currentIndexChanged.connect(lambda *_: self._refresh_visibility())
        self.mode.currentIndexChanged.connect(lambda *_: self.changed.emit())
        form.addRow("模式:", self.mode)

        self.seconds = QDoubleSpinBox()
        self.seconds.setRange(0.0, 3600.0); self.seconds.setSingleStep(0.1); self.seconds.setDecimals(2)
        self.seconds.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("秒数 (fixed):", self.seconds)
        self.seconds_label_row = form.rowCount() - 1

        self.template = QComboBox()
        self.template.setEditable(True)
        self.template.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("模板组 (until_image):", self.template)

        # Region (optional override)
        self.region_check = QCheckBox("自定义搜索区域 (留空=组默认/全屏)")
        self.region_check.toggled.connect(lambda *_: self._toggle_region())
        self.region_check.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.region_check)

        rrow = QHBoxLayout()
        self.rx = QSpinBox(); self.rx.setRange(0, 99999)
        self.ry = QSpinBox(); self.ry.setRange(0, 99999)
        self.rw = QSpinBox(); self.rw.setRange(1, 99999)
        self.rh = QSpinBox(); self.rh.setRange(1, 99999)
        for s in (self.rx, self.ry, self.rw, self.rh):
            s.valueChanged.connect(lambda *_: self.changed.emit())
        rrow.addWidget(QLabel("x:")); rrow.addWidget(self.rx)
        rrow.addWidget(QLabel("y:")); rrow.addWidget(self.ry)
        rrow.addWidget(QLabel("w:")); rrow.addWidget(self.rw)
        rrow.addWidget(QLabel("h:")); rrow.addWidget(self.rh)
        self.pick_region_btn = QPushButton("框选区域")
        self.pick_region_btn.clicked.connect(self._pick_region)
        rrow.addWidget(self.pick_region_btn)
        rw = QWidget(); rw.setLayout(rrow)
        form.addRow("区域:", rw)
        self._region_widgets = [self.rx, self.ry, self.rw, self.rh, self.pick_region_btn]

        # Confidence override
        self.conf_check = QCheckBox("覆盖默认置信度")
        self.conf_check.toggled.connect(lambda *_: self._toggle_conf())
        self.conf_check.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.conf_check)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0); self.confidence.setSingleStep(0.05); self.confidence.setDecimals(2)
        self.confidence.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("置信度:", self.confidence)

        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.5, 3600.0); self.timeout.setSingleStep(0.5); self.timeout.setDecimals(1)
        self.timeout.setValue(10.0)
        self.timeout.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("超时秒数 (until_image):", self.timeout)

        self.poll = QDoubleSpinBox()
        self.poll.setRange(0.05, 10.0); self.poll.setSingleStep(0.05); self.poll.setDecimals(2)
        self.poll.setValue(0.5)
        self.poll.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("轮询间隔 (until_image):", self.poll)

        self._form_layout = form
        self._toggle_region()
        self._toggle_conf()
        self._refresh_visibility()

    def _toggle_region(self):
        on = self.region_check.isChecked()
        for w in self._region_widgets:
            w.setEnabled(on)

    def _toggle_conf(self):
        self.confidence.setEnabled(self.conf_check.isChecked())

    def _pick_region(self):
        from .overlays.region_picker import RegionPicker
        win = self.window()
        win.showMinimized()
        try:
            picker = RegionPicker()
            region = picker.pick()
        finally:
            win.showNormal()
            win.raise_(); win.activateWindow()
        if region:
            self.region_check.setChecked(True)
            self.rx.setValue(region[0]); self.ry.setValue(region[1])
            self.rw.setValue(region[2]); self.rh.setValue(region[3])

    def _refresh_visibility(self):
        is_fixed = self.mode.currentData() == "fixed"
        # Cannot hide rows in QFormLayout reliably; instead disable irrelevant widgets
        self.seconds.setEnabled(is_fixed)
        self.template.setEnabled(not is_fixed)
        self.region_check.setEnabled(not is_fixed)
        for w in self._region_widgets:
            w.setEnabled(not is_fixed and self.region_check.isChecked())
        self.conf_check.setEnabled(not is_fixed)
        self.confidence.setEnabled(not is_fixed and self.conf_check.isChecked())
        self.timeout.setEnabled(not is_fixed)
        self.poll.setEnabled(not is_fixed)

    def load(self, p: Dict[str, Any]) -> None:
        idx = self.mode.findData(p.get("mode", "fixed"))
        if idx >= 0:
            self.mode.setCurrentIndex(idx)
        self.seconds.setValue(float(p.get("seconds", 1.0) or 0.0))
        tpl = str(p.get("template", "") or "")
        idx = self.template.findText(tpl)
        if idx >= 0:
            self.template.setCurrentIndex(idx)
        elif tpl:
            self.template.setCurrentText(tpl)
        region = p.get("region")
        if region and len(region) == 4:
            self.region_check.setChecked(True)
            self.rx.setValue(int(region[0])); self.ry.setValue(int(region[1]))
            self.rw.setValue(int(region[2])); self.rh.setValue(int(region[3]))
        else:
            self.region_check.setChecked(False)
        conf = p.get("confidence")
        if conf is None:
            self.conf_check.setChecked(False)
        else:
            self.conf_check.setChecked(True)
            try:
                self.confidence.setValue(float(conf))
            except (TypeError, ValueError):
                self.confidence.setValue(0.7)
        self.timeout.setValue(float(p.get("timeout", 10.0) or 10.0))
        self.poll.setValue(float(p.get("poll_interval", 0.5) or 0.5))
        self._toggle_region()
        self._toggle_conf()
        self._refresh_visibility()

    def write_to(self, p: Dict[str, Any]) -> None:
        p["mode"] = self.mode.currentData()
        p["seconds"] = self.seconds.value()
        p["template"] = self.template.currentText().strip()
        if self.region_check.isChecked():
            p["region"] = [self.rx.value(), self.ry.value(), self.rw.value(), self.rh.value()]
        else:
            p["region"] = None
        p["confidence"] = self.confidence.value() if self.conf_check.isChecked() else None
        p["timeout"] = self.timeout.value()
        p["poll_interval"] = self.poll.value()

    def set_template_groups(self, names: List[str]) -> None:
        cur = self.template.currentText()
        self.template.blockSignals(True)
        self.template.clear()
        self.template.addItems(names)
        if cur:
            idx = self.template.findText(cur)
            if idx >= 0:
                self.template.setCurrentIndex(idx)
            else:
                self.template.setCurrentText(cur)
        self.template.blockSignals(False)


class ScrollForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)

        self.direction = QComboBox()
        self.direction.addItems(["down", "up"])
        self.direction.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("方向:", self.direction)

        self.amount = QSpinBox(); self.amount.setRange(0, 99999); self.amount.setSingleStep(100)
        self.amount.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("滚轮量:", self.amount)

        # at_position: optional. Reuse PositionWidget, with checkbox to enable.
        self.use_pos = QCheckBox("指定滚动位置")
        self.use_pos.toggled.connect(self._toggle_pos)
        self.use_pos.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.use_pos)

        self.position = PositionWidget()
        self.position.changed.connect(lambda *_: self.changed.emit())
        form.addRow("位置:", self.position)

    def _toggle_pos(self, on: bool):
        self.position.setEnabled(on)

    def load(self, p: Dict[str, Any]) -> None:
        self.direction.setCurrentText(p.get("direction", "down"))
        self.amount.setValue(int(p.get("amount", 0) or 0))
        at_pos = p.get("at_position")
        self.use_pos.setChecked(bool(at_pos))
        self.position.setEnabled(bool(at_pos))
        if at_pos:
            self.position.set_value(at_pos)

    def write_to(self, p: Dict[str, Any]) -> None:
        p["direction"] = self.direction.currentText()
        p["amount"] = self.amount.value()
        p["at_position"] = self.position.get_value() if self.use_pos.isChecked() else None

    def set_template_groups(self, names: List[str]) -> None:
        self.position.set_template_groups(names)


class SetVariableForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.name.setPlaceholderText("变量名 (不含 ${})")
        self.name.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("名字:", self.name)

        self.value = QLineEdit()
        self.value.setPlaceholderText("值 (支持 ${var} 插值)")
        self.value.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("值:", self.value)

    def load(self, p: Dict[str, Any]) -> None:
        self.name.setText(str(p.get("name", "")))
        v = p.get("value", "")
        self.value.setText("" if v is None else str(v))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["name"] = self.name.text().strip()
        p["value"] = self.value.text()


class LogForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.message = QLineEdit()
        self.message.setPlaceholderText("日志内容 (支持 ${var} 插值)")
        self.message.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("消息:", self.message)

        self.level = QComboBox()
        self.level.addItems(["debug", "info", "warning", "error"])
        self.level.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("级别:", self.level)

    def load(self, p: Dict[str, Any]) -> None:
        self.message.setText(str(p.get("message", "")))
        lvl = p.get("level", "info")
        idx = self.level.findText(lvl)
        if idx >= 0:
            self.level.setCurrentIndex(idx)

    def write_to(self, p: Dict[str, Any]) -> None:
        p["message"] = self.message.text()
        p["level"] = self.level.currentText()


class FindImageForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.template = QComboBox()
        self.template.setEditable(True)
        self.template.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("模板组:", self.template)

        # Region (optional override)
        self.region_check = QCheckBox("自定义搜索区域 (留空=组默认/全屏)")
        self.region_check.toggled.connect(lambda *_: self._toggle_region())
        self.region_check.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.region_check)

        rrow = QHBoxLayout()
        self.rx = QSpinBox(); self.rx.setRange(0, 99999)
        self.ry = QSpinBox(); self.ry.setRange(0, 99999)
        self.rw = QSpinBox(); self.rw.setRange(1, 99999)
        self.rh = QSpinBox(); self.rh.setRange(1, 99999)
        for s in (self.rx, self.ry, self.rw, self.rh):
            s.valueChanged.connect(lambda *_: self.changed.emit())
        rrow.addWidget(QLabel("x:")); rrow.addWidget(self.rx)
        rrow.addWidget(QLabel("y:")); rrow.addWidget(self.ry)
        rrow.addWidget(QLabel("w:")); rrow.addWidget(self.rw)
        rrow.addWidget(QLabel("h:")); rrow.addWidget(self.rh)
        self.pick_region_btn = QPushButton("框选区域")
        self.pick_region_btn.clicked.connect(self._pick_region)
        rrow.addWidget(self.pick_region_btn)
        rw = QWidget(); rw.setLayout(rrow)
        form.addRow("区域:", rw)
        self._region_widgets = [self.rx, self.ry, self.rw, self.rh, self.pick_region_btn]

        # Confidence override
        self.conf_check = QCheckBox("覆盖默认置信度")
        self.conf_check.toggled.connect(lambda *_: self._toggle_conf())
        self.conf_check.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.conf_check)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0); self.confidence.setSingleStep(0.05); self.confidence.setDecimals(2)
        self.confidence.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("置信度:", self.confidence)

        info = QLabel("命中后写入: ${found}, ${match_pos}, ${match_score}, ${match_box}")
        info.setStyleSheet("color:#888;")
        form.addRow("", info)

        self._toggle_region()
        self._toggle_conf()

    def _toggle_region(self):
        on = self.region_check.isChecked()
        for w in self._region_widgets:
            w.setEnabled(on)

    def _toggle_conf(self):
        self.confidence.setEnabled(self.conf_check.isChecked())

    def _pick_region(self):
        # Hide top-level window during pick
        from .overlays.region_picker import RegionPicker
        win = self.window()
        win.showMinimized()
        try:
            picker = RegionPicker()
            region = picker.pick()
        finally:
            win.showNormal()
            win.raise_(); win.activateWindow()
        if region:
            self.region_check.setChecked(True)
            self.rx.setValue(region[0]); self.ry.setValue(region[1])
            self.rw.setValue(region[2]); self.rh.setValue(region[3])

    def load(self, p: Dict[str, Any]) -> None:
        tpl = str(p.get("template", "") or "")
        idx = self.template.findText(tpl)
        if idx >= 0:
            self.template.setCurrentIndex(idx)
        elif tpl:
            self.template.setCurrentText(tpl)
        region = p.get("region")
        if region and len(region) == 4:
            self.region_check.setChecked(True)
            self.rx.setValue(int(region[0])); self.ry.setValue(int(region[1]))
            self.rw.setValue(int(region[2])); self.rh.setValue(int(region[3]))
        else:
            self.region_check.setChecked(False)
        conf = p.get("confidence")
        if conf is None:
            self.conf_check.setChecked(False)
        else:
            self.conf_check.setChecked(True)
            try:
                self.confidence.setValue(float(conf))
            except (TypeError, ValueError):
                self.confidence.setValue(0.7)
        self._toggle_region(); self._toggle_conf()

    def write_to(self, p: Dict[str, Any]) -> None:
        p["template"] = self.template.currentText().strip()
        if self.region_check.isChecked():
            p["region"] = [self.rx.value(), self.ry.value(), self.rw.value(), self.rh.value()]
        else:
            p["region"] = None
        p["confidence"] = self.confidence.value() if self.conf_check.isChecked() else None

    def set_template_groups(self, names: List[str]) -> None:
        cur = self.template.currentText()
        self.template.blockSignals(True)
        self.template.clear()
        self.template.addItems(names)
        if cur:
            idx = self.template.findText(cur)
            if idx >= 0:
                self.template.setCurrentIndex(idx)
            else:
                self.template.setCurrentText(cur)
        self.template.blockSignals(False)


class FocusWindowForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.title = QLineEdit()
        self.title.setPlaceholderText("正则表达式 (或精确字符串)")
        self.title.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("窗口标题:", self.title)

        self.exact = QCheckBox("精确匹配 (否则正则搜索)")
        self.exact.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.exact)

        self.class_name = QLineEdit()
        self.class_name.setPlaceholderText("(可选) 限定窗口类名")
        self.class_name.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("类名:", self.class_name)

        info = QLabel("仅 Windows。需要 pywin32。")
        info.setStyleSheet("color:#888;")
        form.addRow("", info)

    def load(self, p: Dict[str, Any]) -> None:
        self.title.setText(str(p.get("title_pattern", "") or ""))
        self.exact.setChecked(bool(p.get("exact", False)))
        self.class_name.setText(str(p.get("class_name", "") or ""))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["title_pattern"] = self.title.text()
        p["exact"] = self.exact.isChecked()
        cls = self.class_name.text().strip()
        p["class_name"] = cls if cls else None


class IfForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.condition = QLineEdit()
        self.condition.setPlaceholderText("Python 表达式, 可用 item / 工作流变量 / found / match_score 等")
        self.condition.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("条件:", self.condition)

        info = QLabel("then / else 分支步骤通过左侧步骤列表点开 if 节点编辑。\n"
                      "示例: item.revenue > 1000  /  found == True  /  'A' in item.tag")
        info.setStyleSheet("color:#888;")
        info.setWordWrap(True)
        form.addRow("", info)

    def load(self, p: Dict[str, Any]) -> None:
        self.condition.setText(str(p.get("condition", "") or ""))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["condition"] = self.condition.text()
        # then/else default to [] if absent
        if "then" not in p:
            p["then"] = []
        if "else" not in p:
            p["else"] = []


class LoopDataForm(_BaseForm):
    """Loop data form: inline a mini DataSource editor (simpler than the side tab)."""
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)

        self.item_var = QLineEdit()
        self.item_var.setPlaceholderText("循环体内引用的变量名，例如 item / row")
        self.item_var.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("循环变量名:", self.item_var)

        self.ds_type = QComboBox()
        self.ds_type.addItem("内联文本 (每行一项)", "inline")
        self.ds_type.addItem("CSV 文件", "csv")
        self.ds_type.addItem("Excel 文件", "xlsx")
        self.ds_type.addItem("JSON 数组", "json")
        self.ds_type.currentIndexChanged.connect(lambda *_: self._refresh())
        self.ds_type.currentIndexChanged.connect(lambda *_: self.changed.emit())
        form.addRow("数据源类型:", self.ds_type)

        self.path = QLineEdit()
        self.path.setPlaceholderText("文件路径")
        self.path.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("路径:", self.path)

        self.column = QLineEdit()
        self.column.setPlaceholderText("(留空=整行)")
        self.column.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("仅取某列:", self.column)

        self.inline = QPlainTextEdit()
        self.inline.setMaximumHeight(120)
        self.inline.setPlaceholderText("内联条目, 每行一项")
        self.inline.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("内联条目:", self.inline)

        self.start = QSpinBox(); self.start.setRange(0, 999999)
        self.start.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("起始 index:", self.start)

        info = QLabel("循环体步骤通过左侧步骤列表点开 loop_data 节点编辑")
        info.setStyleSheet("color:#888;")
        form.addRow("", info)

        self._refresh()

    def _refresh(self):
        t = self.ds_type.currentData()
        self.path.setEnabled(t in ("csv", "xlsx", "json"))
        self.column.setEnabled(t in ("csv", "xlsx"))
        self.inline.setEnabled(t == "inline")

    def load(self, p: Dict[str, Any]) -> None:
        self.item_var.setText(str(p.get("item_var", "item") or "item"))
        src = p.get("source") or {}
        idx = self.ds_type.findData(src.get("type", "inline"))
        if idx >= 0:
            self.ds_type.setCurrentIndex(idx)
        self.path.setText(str(src.get("path", "") or ""))
        self.column.setText(str(src.get("column", "") or ""))
        items = src.get("inline_items") or []
        self.inline.setPlainText("\n".join(str(x) for x in items))
        self.start.setValue(int(src.get("start_index", 0) or 0))
        if "body" not in p:
            p["body"] = []
        self._refresh()

    def write_to(self, p: Dict[str, Any]) -> None:
        p["item_var"] = self.item_var.text().strip() or "item"
        t = self.ds_type.currentData()
        src = p.get("source") or {}
        src["type"] = t
        src["path"] = self.path.text().strip() or None
        src["column"] = self.column.text().strip() or None
        if t == "inline":
            src["inline_items"] = [ln for ln in self.inline.toPlainText().splitlines()]
        else:
            src["inline_items"] = None
        src["start_index"] = self.start.value()
        src.setdefault("end_index", None)
        src.setdefault("skip_empty", True)
        src.setdefault("filter", None)
        p["source"] = src
        if "body" not in p:
            p["body"] = []


class EmptyForm(_BaseForm):
    """Form for break/continue: no params."""
    def __init__(self, info_text: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel(info_text or "该步骤无参数。")
        lbl.setStyleSheet("color:#888;")
        layout.addWidget(lbl)
        layout.addStretch(1)

    def load(self, p): pass
    def write_to(self, p): pass


class BreakForm(EmptyForm):
    def __init__(self):
        super().__init__("跳出当前最近的 loop_data 循环。")


class ContinueForm(EmptyForm):
    def __init__(self):
        super().__init__("跳到当前最近的 loop_data 循环的下一项。")


# ---------------------- Browser action forms ----------------------

class BrowserGotoForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com，支持 ${var} 插值")
        self.url.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("URL:", self.url)

        self.wait_until = QComboBox()
        self.wait_until.addItems(["load", "domcontentloaded", "networkidle"])
        self.wait_until.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("等待方式:", self.wait_until)

    def load(self, p: Dict[str, Any]) -> None:
        self.url.setText(str(p.get("url", "")))
        self.wait_until.setCurrentText(p.get("wait_until", "load"))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["url"] = self.url.text().strip()
        p["wait_until"] = self.wait_until.currentText()


class BrowserClickForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)

        self.position_mode = QComboBox()
        self.position_mode.addItem("CSS 选择器", "selector")
        self.position_mode.addItem("模板图片", "template")
        self.position_mode.currentIndexChanged.connect(lambda *_: self._refresh_mode())
        self.position_mode.currentIndexChanged.connect(lambda *_: self.changed.emit())
        form.addRow("定位方式:", self.position_mode)

        self.selector = QLineEdit()
        self.selector.setPlaceholderText("CSS 选择器，如 #btn, .cls, text=登录")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("选择器:", self.selector)

        self.template = QComboBox()
        self.template.setEditable(True)
        self.template.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("模板组:", self.template)

        self.conf_check = QCheckBox("覆盖默认置信度")
        self.conf_check.toggled.connect(lambda *_: self.confidence.setEnabled(self.conf_check.isChecked()))
        self.conf_check.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.conf_check)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0); self.confidence.setSingleStep(0.05); self.confidence.setDecimals(2)
        self.confidence.setEnabled(False)
        self.confidence.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("置信度:", self.confidence)

        self.button = QComboBox()
        self.button.addItems(["left", "right", "middle"])
        self.button.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("按键:", self.button)

        self.clicks = QSpinBox()
        self.clicks.setRange(1, 10)
        self.clicks.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("点击次数:", self.clicks)

        self.timeout = QSpinBox()
        self.timeout.setRange(1000, 120000)
        self.timeout.setSingleStep(1000)
        self.timeout.setValue(30000)
        self.timeout.setSuffix(" ms")
        self.timeout.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("超时:", self.timeout)

        self._refresh_mode()

    def _refresh_mode(self):
        is_selector = self.position_mode.currentData() == "selector"
        self.selector.setEnabled(is_selector)
        self.template.setEnabled(not is_selector)
        self.conf_check.setEnabled(not is_selector)
        self.confidence.setEnabled(not is_selector and self.conf_check.isChecked())
        self.timeout.setEnabled(is_selector)

    def load(self, p: Dict[str, Any]) -> None:
        mode = p.get("position_mode", "selector")
        idx = self.position_mode.findData(mode)
        if idx >= 0:
            self.position_mode.setCurrentIndex(idx)
        self.selector.setText(str(p.get("selector", "")))
        tpl = str(p.get("template", ""))
        idx = self.template.findText(tpl)
        if idx >= 0:
            self.template.setCurrentIndex(idx)
        elif tpl:
            self.template.setCurrentText(tpl)
        conf = p.get("confidence")
        if conf is not None:
            self.conf_check.setChecked(True)
            self.confidence.setValue(float(conf))
        else:
            self.conf_check.setChecked(False)
        self.button.setCurrentText(p.get("button", "left"))
        self.clicks.setValue(int(p.get("clicks", 1) or 1))
        self.timeout.setValue(int(p.get("timeout", 30000) or 30000))
        self._refresh_mode()

    def write_to(self, p: Dict[str, Any]) -> None:
        p["position_mode"] = self.position_mode.currentData()
        p["selector"] = self.selector.text().strip()
        p["template"] = self.template.currentText().strip()
        p["confidence"] = self.confidence.value() if self.conf_check.isChecked() else None
        p["button"] = self.button.currentText()
        p["clicks"] = self.clicks.value()
        p["timeout"] = self.timeout.value()

    def set_template_groups(self, names: List[str]) -> None:
        cur = self.template.currentText()
        self.template.blockSignals(True)
        self.template.clear()
        self.template.addItems(names)
        if cur:
            idx = self.template.findText(cur)
            if idx >= 0:
                self.template.setCurrentIndex(idx)
            else:
                self.template.setCurrentText(cur)
        self.template.blockSignals(False)


class BrowserFillForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.selector = QLineEdit()
        self.selector.setPlaceholderText("CSS 选择器，如 #kw, input[name='q']")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("选择器:", self.selector)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("要填写的文本，支持 ${var} 插值")
        self.text.setMaximumHeight(120)
        self.text.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("文本:", self.text)

        self.clear_first = QCheckBox("填写前先清空")
        self.clear_first.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.clear_first)

    def load(self, p: Dict[str, Any]) -> None:
        self.selector.setText(str(p.get("selector", "")))
        self.text.setPlainText(str(p.get("text", "")))
        self.clear_first.setChecked(bool(p.get("clear_first", True)))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["selector"] = self.selector.text().strip()
        p["text"] = self.text.toPlainText()
        p["clear_first"] = self.clear_first.isChecked()


class BrowserPressForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.selector = QLineEdit()
        self.selector.setPlaceholderText("(可选) CSS 选择器，留空则全局按键")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("选择器:", self.selector)

        self.key = QLineEdit()
        self.key.setPlaceholderText("Enter / Tab / Escape / Control+a 等 Playwright 键名")
        self.key.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("按键:", self.key)

    def load(self, p: Dict[str, Any]) -> None:
        self.selector.setText(str(p.get("selector", "")))
        self.key.setText(str(p.get("key", "Enter")))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["selector"] = self.selector.text().strip()
        p["key"] = self.key.text().strip()


class BrowserEvalForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.expression = QPlainTextEdit()
        self.expression.setPlaceholderText("JavaScript 表达式，如 document.title")
        self.expression.setMaximumHeight(120)
        self.expression.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("表达式:", self.expression)

        self.save_as = QLineEdit()
        self.save_as.setPlaceholderText("变量名 (不含 ${})")
        self.save_as.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("存为变量:", self.save_as)

    def load(self, p: Dict[str, Any]) -> None:
        self.expression.setPlainText(str(p.get("expression", "")))
        self.save_as.setText(str(p.get("save_as", "")))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["expression"] = self.expression.toPlainText()
        p["save_as"] = self.save_as.text().strip()


class BrowserWaitForForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.selector = QLineEdit()
        self.selector.setPlaceholderText("CSS 选择器")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("选择器:", self.selector)

        self.state = QComboBox()
        self.state.addItems(["visible", "hidden", "attached", "detached"])
        self.state.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("状态:", self.state)

        self.timeout = QSpinBox()
        self.timeout.setRange(1000, 120000)
        self.timeout.setSingleStep(1000)
        self.timeout.setValue(30000)
        self.timeout.setSuffix(" ms")
        self.timeout.valueChanged.connect(lambda *_: self.changed.emit())
        form.addRow("超时:", self.timeout)

    def load(self, p: Dict[str, Any]) -> None:
        self.selector.setText(str(p.get("selector", "")))
        self.state.setCurrentText(p.get("state", "visible"))
        self.timeout.setValue(int(p.get("timeout", 30000) or 30000))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["selector"] = self.selector.text().strip()
        p["state"] = self.state.currentText()
        p["timeout"] = self.timeout.value()


class BrowserScreenshotForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.path = QLineEdit()
        self.path.setPlaceholderText("保存路径，支持 ${var}，如 screenshots/${__index__}.png")
        self.path.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("路径:", self.path)

        self.full_page = QCheckBox("整页截图（含滚动区域）")
        self.full_page.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.full_page)

        self.selector = QLineEdit()
        self.selector.setPlaceholderText("(可选) 仅截取某个元素")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("元素选择器:", self.selector)

    def load(self, p: Dict[str, Any]) -> None:
        self.path.setText(str(p.get("path", "")))
        self.full_page.setChecked(bool(p.get("full_page", False)))
        self.selector.setText(str(p.get("selector", "")))

    def write_to(self, p: Dict[str, Any]) -> None:
        p["path"] = self.path.text().strip()
        p["full_page"] = self.full_page.isChecked()
        p["selector"] = self.selector.text().strip()


class BrowserExtractForm(_BaseForm):
    def __init__(self):
        super().__init__()
        form = QFormLayout(self)
        self.selector = QLineEdit()
        self.selector.setPlaceholderText("CSS 选择器")
        self.selector.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("选择器:", self.selector)

        self.extract = QComboBox()
        self.extract.addItems(["text", "attribute", "inner_html", "value"])
        self.extract.currentIndexChanged.connect(lambda *_: self._refresh_attr())
        self.extract.currentTextChanged.connect(lambda *_: self.changed.emit())
        form.addRow("提取类型:", self.extract)

        self.attribute = QLineEdit()
        self.attribute.setPlaceholderText("extract=attribute 时指定，如 href / src")
        self.attribute.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("属性名:", self.attribute)

        self.save_as = QLineEdit()
        self.save_as.setPlaceholderText("变量名 (不含 ${})")
        self.save_as.textChanged.connect(lambda *_: self.changed.emit())
        form.addRow("存为变量:", self.save_as)

        self.extract_all = QCheckBox("提取所有匹配元素（存为列表）")
        self.extract_all.toggled.connect(lambda *_: self.changed.emit())
        form.addRow("", self.extract_all)

    def _refresh_attr(self):
        self.attribute.setEnabled(self.extract.currentText() == "attribute")

    def load(self, p: Dict[str, Any]) -> None:
        self.selector.setText(str(p.get("selector", "")))
        self.extract.setCurrentText(p.get("extract", "text"))
        self.attribute.setText(str(p.get("attribute", "")))
        self.save_as.setText(str(p.get("save_as", "")))
        self.extract_all.setChecked(bool(p.get("all", False)))
        self._refresh_attr()

    def write_to(self, p: Dict[str, Any]) -> None:
        p["selector"] = self.selector.text().strip()
        p["extract"] = self.extract.currentText()
        p["attribute"] = self.attribute.text().strip()
        p["save_as"] = self.save_as.text().strip()
        p["all"] = self.extract_all.isChecked()


FORM_CLASSES: Dict[str, type] = {
    "click": ClickForm,
    "type_text": TypeTextForm,
    "paste": PasteForm,
    "hotkey": HotkeyForm,
    "wait": WaitForm,
    "scroll": ScrollForm,
    "set_variable": SetVariableForm,
    "log": LogForm,
    "find_image": FindImageForm,
    "focus_window": FocusWindowForm,
    "if": IfForm,
    "loop_data": LoopDataForm,
    "break": BreakForm,
    "continue": ContinueForm,
    "browser_goto": BrowserGotoForm,
    "browser_click": BrowserClickForm,
    "browser_fill": BrowserFillForm,
    "browser_press": BrowserPressForm,
    "browser_eval": BrowserEvalForm,
    "browser_wait_for": BrowserWaitForForm,
    "browser_screenshot": BrowserScreenshotForm,
    "browser_extract": BrowserExtractForm,
}


# ---------------------- The editor panel ----------------------

class StepEditorPanel(QWidget):
    """Middle column: edits the currently selected step."""
    step_modified = Signal(str)  # step_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow: Optional[Workflow] = None
        self._step: Optional[Step] = None
        self._suspend_write = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.empty_label = QLabel("← 在左侧选中一个步骤进行编辑")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; font-size: 13px;")
        outer.addWidget(self.empty_label)

        self.container = QWidget()
        self.container.setVisible(False)
        outer.addWidget(self.container, 1)

        cont = QVBoxLayout(self.container)
        cont.setContentsMargins(0, 0, 0, 0)

        # Header: type label + name + common fields
        header_box = QGroupBox("通用")
        header_form = QFormLayout(header_box)
        self.type_label = QLabel()
        self.type_label.setStyleSheet("font-weight: bold; color: #333;")
        header_form.addRow("类型:", self.type_label)

        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self._on_name_changed)
        header_form.addRow("名称:", self.name_input)

        self.on_success_combo = QComboBox()
        self.on_failure_combo = QComboBox()
        self.on_success_combo.currentIndexChanged.connect(self._on_jump_changed)
        self.on_failure_combo.currentIndexChanged.connect(self._on_jump_changed)
        header_form.addRow("成功跳转:", self.on_success_combo)
        header_form.addRow("失败跳转:", self.on_failure_combo)

        cont.addWidget(header_box)

        # Params group
        params_box = QGroupBox("参数")
        params_layout = QVBoxLayout(params_box)
        self.stack = QStackedWidget()
        self._forms: Dict[str, _BaseForm] = {}
        for type_name, form_cls in FORM_CLASSES.items():
            form = form_cls()
            form.changed.connect(self._on_form_changed)
            self._forms[type_name] = form
            self.stack.addWidget(form)
        params_layout.addWidget(self.stack)
        cont.addWidget(params_box, 1)

    # ---------- public ----------
    def set_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self._refresh_jump_combos()
        self._propagate_template_groups()
        self.show_step(None)

    def _propagate_template_groups(self):
        names = list(self._workflow.templates.keys()) if self._workflow else []
        for form in self._forms.values():
            form.set_template_groups(names)

    def show_step(self, step_id: Optional[str]):
        if not self._workflow or not step_id:
            self._step = None
            self.empty_label.setVisible(True)
            self.container.setVisible(False)
            return
        step = self._workflow.find_step(step_id)
        if step is None:
            return
        self._step = step
        self.empty_label.setVisible(False)
        self.container.setVisible(True)

        self._suspend_write = True
        self.type_label.setText(step.type)
        self.name_input.setText(step.name)

        # Switch param form
        form = self._forms.get(step.type)
        if form is not None:
            self.stack.setCurrentWidget(form)
            form.load(step.params)
        else:
            # Unknown type — should not happen in Phase 1
            pass

        # Jump combos
        self._refresh_jump_combos()
        self._set_combo_value(self.on_success_combo, step.on_success)
        self._set_combo_value(self.on_failure_combo, step.on_failure)
        self._suspend_write = False

    def refresh_jump_targets(self):
        """Called when steps list changes (added/removed/reordered)."""
        if self._step:
            self._suspend_write = True
            self._refresh_jump_combos()
            self._set_combo_value(self.on_success_combo, self._step.on_success)
            self._set_combo_value(self.on_failure_combo, self._step.on_failure)
            self._suspend_write = False

    # ---------- internal ----------
    def _refresh_jump_combos(self):
        for combo in (self.on_success_combo, self.on_failure_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(下一步)", None)
            if self._workflow:
                for s in self._workflow.steps:
                    if self._step is not None and s.id == self._step.id:
                        continue
                    combo.addItem(f"{s.name or '(未命名)'}  [{s.id}]", s.id)
            combo.blockSignals(False)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: Optional[str]):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _on_name_changed(self, _text: str):
        if self._suspend_write or not self._step:
            return
        self._step.name = self.name_input.text()
        self.step_modified.emit(self._step.id)

    def _on_jump_changed(self):
        if self._suspend_write or not self._step:
            return
        self._step.on_success = self.on_success_combo.currentData()
        self._step.on_failure = self.on_failure_combo.currentData()
        self.step_modified.emit(self._step.id)

    def _on_form_changed(self):
        if self._suspend_write or not self._step:
            return
        form = self._forms.get(self._step.type)
        if form is None:
            return
        form.write_to(self._step.params)
        self.step_modified.emit(self._step.id)
