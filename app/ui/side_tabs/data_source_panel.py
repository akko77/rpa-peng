"""Data source side tab.

Configures workflow.data_source: type, path/inline items, slicing options,
and the filter (visual rules + expression modes).
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QFileDialog, QPlainTextEdit,
    QLabel, QTableWidget, QTableWidgetItem, QMessageBox, QTabWidget,
    QHeaderView,
)

from ...core.workflow import Workflow, DataSource, Filter, FilterRule
from ...core.data_source import load_items
from ...core.filter_evaluator import build_filter_fn, visual_to_expression


OPERATORS = ["==", "!=", ">", ">=", "<", "<=", "contains", "startswith", "endswith", "in", "not_in"]


class DataSourceTab(QWidget):
    workflow_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow: Optional[Workflow] = None
        self._suspend_write = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        self.enable_check = QCheckBox("启用顶层数据循环 (遍历每一项执行步骤)")
        self.enable_check.toggled.connect(self._on_enable_toggled)
        outer.addWidget(self.enable_check)

        self.config_box = QGroupBox("数据源配置")
        config_layout = QFormLayout(self.config_box)

        self.type_combo = QComboBox()
        self.type_combo.addItem("CSV", "csv")
        self.type_combo.addItem("Excel (xlsx)", "xlsx")
        self.type_combo.addItem("JSON 数组", "json")
        self.type_combo.addItem("内联文本 (每行一项)", "inline")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        config_layout.addRow("类型:", self.type_combo)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.textChanged.connect(lambda *_: self._write_to_workflow())
        path_row.addWidget(self.path_edit, 1)
        browse = QPushButton("浏览...")
        browse.clicked.connect(self._browse_file)
        path_row.addWidget(browse)
        path_widget = QWidget(); path_widget.setLayout(path_row)
        config_layout.addRow("路径:", path_widget)

        self.sheet_edit = QLineEdit()
        self.sheet_edit.setPlaceholderText("(留空=首个 sheet)")
        self.sheet_edit.textChanged.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("Sheet (xlsx):", self.sheet_edit)

        self.column_edit = QLineEdit()
        self.column_edit.setPlaceholderText("(留空=整行作为 dict)")
        self.column_edit.textChanged.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("仅取某列:", self.column_edit)

        self.inline_edit = QPlainTextEdit()
        self.inline_edit.setMaximumHeight(140)
        self.inline_edit.setPlaceholderText("每行一项")
        self.inline_edit.textChanged.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("内联条目:", self.inline_edit)

        self.start_spin = QSpinBox(); self.start_spin.setRange(0, 999999)
        self.start_spin.valueChanged.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("起始 index:", self.start_spin)

        self.end_spin = QSpinBox(); self.end_spin.setRange(-1, 999999); self.end_spin.setSpecialValueText("(无限)")
        self.end_spin.setValue(-1)
        self.end_spin.valueChanged.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("结束 index (-1 表示无限):", self.end_spin)

        self.skip_empty_check = QCheckBox("跳过空项")
        self.skip_empty_check.setChecked(True)
        self.skip_empty_check.toggled.connect(lambda *_: self._write_to_workflow())
        config_layout.addRow("", self.skip_empty_check)

        outer.addWidget(self.config_box)

        # Filter
        self.filter_box = QGroupBox("过滤器")
        f_layout = QVBoxLayout(self.filter_box)

        self.filter_tabs = QTabWidget()
        # Visual tab
        visual = QWidget()
        v_layout = QVBoxLayout(visual)
        cmb_row = QHBoxLayout()
        cmb_row.addWidget(QLabel("规则组合:"))
        self.combinator_combo = QComboBox()
        self.combinator_combo.addItem("AND (全部满足)", "and")
        self.combinator_combo.addItem("OR (任一满足)", "or")
        self.combinator_combo.currentIndexChanged.connect(lambda *_: self._write_to_workflow())
        cmb_row.addWidget(self.combinator_combo)
        cmb_row.addStretch(1)
        v_layout.addLayout(cmb_row)

        self.rules_table = QTableWidget(0, 3)
        self.rules_table.setHorizontalHeaderLabels(["字段 (留空=item)", "操作符", "值"])
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules_table.itemChanged.connect(self._on_rule_cell_changed)
        v_layout.addWidget(self.rules_table, 1)

        rb = QHBoxLayout()
        b_add = QPushButton("+ 添加规则"); b_add.clicked.connect(self._add_rule); rb.addWidget(b_add)
        b_del = QPushButton("删除选中"); b_del.clicked.connect(self._delete_rule); rb.addWidget(b_del)
        rb.addStretch(1)
        v_layout.addLayout(rb)
        self.filter_tabs.addTab(visual, "可视化")

        # Expression tab
        expr_tab = QWidget()
        e_layout = QVBoxLayout(expr_tab)
        self.expression_edit = QPlainTextEdit()
        self.expression_edit.setPlaceholderText(
            "Python 表达式 (simpleeval 子集)\n例: item.industry == '科技' and item.revenue > 1000"
        )
        self.expression_edit.textChanged.connect(lambda *_: self._write_to_workflow())
        e_layout.addWidget(self.expression_edit, 1)
        hint = QLabel("可用: 比较 / and or not / in / startswith / endswith / contains (用 in) / len() / str() / int() / float()")
        hint.setStyleSheet("color:#888;"); hint.setWordWrap(True)
        e_layout.addWidget(hint)
        self.filter_tabs.addTab(expr_tab, "表达式")

        self.filter_tabs.currentChanged.connect(self._on_filter_mode_changed)
        f_layout.addWidget(self.filter_tabs)

        outer.addWidget(self.filter_box, 1)

        # Preview
        preview_row = QHBoxLayout()
        self.preview_btn = QPushButton("试算 (前 5 项预览过滤结果)")
        self.preview_btn.clicked.connect(self._preview)
        preview_row.addWidget(self.preview_btn)
        preview_row.addStretch(1)
        outer.addLayout(preview_row)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color:#444; background:#fafafa; padding:6px;")
        outer.addWidget(self.preview_label)

        self._refresh_widget_visibility()

    # ---------- public ----------
    def set_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self._load_from_workflow()

    # ---------- enable toggle ----------
    def _on_enable_toggled(self, on: bool):
        if self._suspend_write or self._workflow is None:
            return
        if on:
            if self._workflow.data_source is None:
                self._workflow.data_source = DataSource(type="inline")
            self._load_from_workflow()
        else:
            self._workflow.data_source = None
            self._load_from_workflow()
        self.config_box.setEnabled(on)
        self.filter_box.setEnabled(on)
        self.preview_btn.setEnabled(on)
        self.workflow_modified.emit()

    def _on_type_changed(self):
        self._refresh_widget_visibility()
        self._write_to_workflow()

    def _refresh_widget_visibility(self):
        t = self.type_combo.currentData()
        is_file = t in ("csv", "xlsx", "json")
        self.path_edit.setEnabled(is_file)
        self.sheet_edit.setEnabled(t == "xlsx")
        self.column_edit.setEnabled(t in ("csv", "xlsx"))
        self.inline_edit.setEnabled(t == "inline")

    def _browse_file(self):
        t = self.type_combo.currentData()
        if t == "csv":
            ext = "CSV (*.csv)"
        elif t == "xlsx":
            ext = "Excel (*.xlsx)"
        elif t == "json":
            ext = "JSON (*.json)"
        else:
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", ext)
        if path:
            self.path_edit.setText(path)

    def _load_from_workflow(self):
        if self._workflow is None:
            return
        self._suspend_write = True
        ds = self._workflow.data_source
        enabled = ds is not None
        self.enable_check.setChecked(enabled)
        self.config_box.setEnabled(enabled)
        self.filter_box.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        if not enabled:
            self._suspend_write = False
            return
        idx = self.type_combo.findData(ds.type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.path_edit.setText(ds.path or "")
        self.sheet_edit.setText(ds.sheet or "")
        self.column_edit.setText(ds.column or "")
        if ds.inline_items:
            self.inline_edit.setPlainText("\n".join(str(x) for x in ds.inline_items))
        else:
            self.inline_edit.setPlainText("")
        self.start_spin.setValue(int(ds.start_index or 0))
        self.end_spin.setValue(int(ds.end_index) if ds.end_index is not None else -1)
        self.skip_empty_check.setChecked(bool(ds.skip_empty))

        # Filter
        f = ds.filter
        if f is None:
            self.filter_tabs.setCurrentIndex(0)
            self.combinator_combo.setCurrentIndex(0)
            self.rules_table.setRowCount(0)
            self.expression_edit.setPlainText("")
        else:
            mode_idx = 0 if f.mode == "visual" else 1
            self.filter_tabs.setCurrentIndex(mode_idx)
            idx_cmb = self.combinator_combo.findData(f.combinator)
            if idx_cmb >= 0:
                self.combinator_combo.setCurrentIndex(idx_cmb)
            self.rules_table.setRowCount(0)
            for r in f.rules:
                self._append_rule_row(r.field, r.operator, r.value)
            self.expression_edit.setPlainText(f.expression or "")

        self._refresh_widget_visibility()
        self._suspend_write = False

    def _write_to_workflow(self):
        if self._suspend_write or self._workflow is None or self._workflow.data_source is None:
            return
        ds = self._workflow.data_source
        ds.type = self.type_combo.currentData()
        ds.path = self.path_edit.text().strip() or None
        ds.sheet = self.sheet_edit.text().strip() or None
        ds.column = self.column_edit.text().strip() or None
        if ds.type == "inline":
            lines = [ln for ln in self.inline_edit.toPlainText().splitlines()]
            ds.inline_items = lines
        else:
            ds.inline_items = None
        ds.start_index = self.start_spin.value()
        v = self.end_spin.value()
        ds.end_index = None if v < 0 else v
        ds.skip_empty = self.skip_empty_check.isChecked()
        ds.filter = self._build_filter_from_ui()
        self.workflow_modified.emit()

    def _build_filter_from_ui(self) -> Optional[Filter]:
        mode = "visual" if self.filter_tabs.currentIndex() == 0 else "expression"
        if mode == "visual":
            rules = []
            for row in range(self.rules_table.rowCount()):
                field_item = self.rules_table.item(row, 0)
                op_widget = self.rules_table.cellWidget(row, 1)
                val_item = self.rules_table.item(row, 2)
                field = field_item.text().strip() if field_item else ""
                op = op_widget.currentText() if op_widget else "=="
                raw_value = val_item.text() if val_item else ""
                rules.append(FilterRule(field=field, operator=op, value=self._parse_value(raw_value)))
            if not rules:
                return None
            return Filter(mode="visual",
                          rules=rules,
                          combinator=self.combinator_combo.currentData())
        else:
            expr = self.expression_edit.toPlainText().strip()
            if not expr:
                return None
            return Filter(mode="expression", expression=expr)

    @staticmethod
    def _parse_value(raw: str):
        s = raw.strip()
        if not s:
            return ""
        # Try int / float; otherwise return string
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    # ---------- visual rule row management ----------
    def _add_rule(self):
        self._append_rule_row("", "==", "")
        self._write_to_workflow()

    def _append_rule_row(self, field: str, op: str, value):
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        f_item = QTableWidgetItem(field); self.rules_table.setItem(row, 0, f_item)
        op_combo = QComboBox()
        op_combo.addItems(OPERATORS)
        idx = OPERATORS.index(op) if op in OPERATORS else 0
        op_combo.setCurrentIndex(idx)
        op_combo.currentIndexChanged.connect(lambda *_: self._write_to_workflow())
        self.rules_table.setCellWidget(row, 1, op_combo)
        v_item = QTableWidgetItem(str(value) if value is not None else "")
        self.rules_table.setItem(row, 2, v_item)

    def _delete_rule(self):
        rows = sorted({i.row() for i in self.rules_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.rules_table.removeRow(r)
        self._write_to_workflow()

    def _on_rule_cell_changed(self, _item):
        if self._suspend_write:
            return
        self._write_to_workflow()

    def _on_filter_mode_changed(self, idx):
        # When switching visual -> expression, auto-translate rules into an expression
        if self._suspend_write or self._workflow is None or self._workflow.data_source is None:
            return
        if idx == 1:  # going to expression
            current_filter = self._build_filter_from_ui()
            if current_filter and current_filter.mode == "visual" and current_filter.rules:
                expr = visual_to_expression(current_filter)
                if expr and not self.expression_edit.toPlainText().strip():
                    self._suspend_write = True
                    self.expression_edit.setPlainText(expr)
                    self._suspend_write = False
        self._write_to_workflow()

    # ---------- preview ----------
    def _preview(self):
        if self._workflow is None or self._workflow.data_source is None:
            return
        ds = self._workflow.data_source
        try:
            fn = build_filter_fn(ds.filter)
            items = load_items(ds, filter_fn=fn)
        except Exception as e:
            self.preview_label.setText(f"加载失败: {e}")
            return
        n = len(items)
        head = items[:5]
        text = f"过滤后共 {n} 项。前 5 项:\n"
        for i, it in enumerate(head):
            s = str(it)
            if len(s) > 200:
                s = s[:197] + "..."
            text += f"  [{i}] {s}\n"
        self.preview_label.setText(text)
