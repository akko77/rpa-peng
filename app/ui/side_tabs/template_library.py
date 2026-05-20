"""Template library side tab.

Shows the workflow's template groups, lets the user:
  - Create a new group (and add its first variant by framing a screen region)
  - Add more variants to an existing group
  - Delete variants / groups
  - Edit per-group settings (default_confidence, default_region, match_strategy)
  - Preview variant thumbnails
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QComboBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QFileDialog, QSplitter,
)

from ...core.workflow import Workflow, TemplateGroup, TemplateVariant
from ...persistence.template_io import (
    save_variant_image, today_string, delete_variant, delete_group,
    variant_image_path, sanitize_group_name, write_group_meta,
)
from ..overlays.region_picker import RegionPicker
from ..dialogs.template_import_dialog import offer_disk_import, offer_workflow_import


class TemplateLibraryTab(QWidget):
    workflow_modified = Signal()

    def __init__(self, templates_dir: Path, parent=None):
        super().__init__(parent)
        self.templates_dir = templates_dir
        self._workflow: Optional[Workflow] = None
        self._suspend_write = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        # Top buttons
        top = QHBoxLayout()
        self.btn_new_group = QPushButton("+ 新建组 (框选)")
        self.btn_new_group.clicked.connect(self._new_group_via_picker)
        top.addWidget(self.btn_new_group)
        self.btn_del_group = QPushButton("删除组")
        self.btn_del_group.clicked.connect(self._delete_selected_group)
        top.addWidget(self.btn_del_group)
        top.addStretch(1)
        outer.addLayout(top)

        # Import buttons (second row)
        imp = QHBoxLayout()
        self.btn_import_disk = QPushButton("📁 从磁盘扫描导入")
        self.btn_import_disk.setToolTip("扫描 templates/ 目录, 列出尚未在当前工作流的模板组供导入")
        self.btn_import_disk.clicked.connect(self._import_from_disk)
        imp.addWidget(self.btn_import_disk)
        self.btn_import_wf = QPushButton("📄 从工作流文件导入")
        self.btn_import_wf.setToolTip("从另一个 .awf.json 文件借用模板组定义")
        self.btn_import_wf.clicked.connect(self._import_from_workflow)
        imp.addWidget(self.btn_import_wf)
        imp.addStretch(1)
        outer.addLayout(imp)

        # Splitter: groups list | details
        split = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(split, 1)

        # Groups list
        self.groups_list = QListWidget()
        self.groups_list.currentItemChanged.connect(self._on_group_selected)
        split.addWidget(self.groups_list)

        # Details area
        details = QWidget()
        d_layout = QVBoxLayout(details)
        d_layout.setContentsMargins(0, 0, 0, 0)

        cfg = QGroupBox("组设置")
        cfg_form = QFormLayout(cfg)
        self.lbl_group_name = QLabel("(未选)")
        cfg_form.addRow("名称:", self.lbl_group_name)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0); self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.valueChanged.connect(lambda *_: self._write_group_settings())
        cfg_form.addRow("默认置信度:", self.confidence_spin)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("first_hit (按顺序，命中即返回)", "first_hit")
        self.strategy_combo.addItem("best_score (取最高分)", "best_score")
        self.strategy_combo.currentIndexChanged.connect(lambda *_: self._write_group_settings())
        cfg_form.addRow("匹配策略:", self.strategy_combo)
        self.region_label = QLabel("(无)")
        cfg_form.addRow("默认搜索区域:", self.region_label)
        d_layout.addWidget(cfg)

        # Variants
        v_box = QGroupBox("变体 (variants)")
        v_layout = QVBoxLayout(v_box)
        v_btns = QHBoxLayout()
        self.btn_add_variant = QPushButton("+ 添加变体 (框选)")
        self.btn_add_variant.clicked.connect(self._add_variant_via_picker)
        v_btns.addWidget(self.btn_add_variant)
        self.btn_del_variant = QPushButton("删除变体")
        self.btn_del_variant.clicked.connect(self._delete_selected_variant)
        v_btns.addWidget(self.btn_del_variant)
        v_btns.addStretch(1)
        v_layout.addLayout(v_btns)

        self.variants_list = QListWidget()
        self.variants_list.setIconSize(QSize(96, 96))
        self.variants_list.currentItemChanged.connect(self._on_variant_selected)
        v_layout.addWidget(self.variants_list, 1)

        self.preview = QLabel()
        self.preview.setMinimumHeight(120)
        self.preview.setStyleSheet("background:#222; color:#888;")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setText("(选择变体预览)")
        v_layout.addWidget(self.preview)

        d_layout.addWidget(v_box, 1)
        split.addWidget(details)

        split.setSizes([180, 400])

    # ---------- public ----------
    def set_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self.refresh()

    def refresh(self):
        self.groups_list.clear()
        self.variants_list.clear()
        self.lbl_group_name.setText("(未选)")
        if self._workflow is None:
            return
        for name in sorted(self._workflow.templates.keys()):
            self.groups_list.addItem(name)
        if self.groups_list.count() > 0:
            self.groups_list.setCurrentRow(0)

    # ---------- group handlers ----------
    def _selected_group(self) -> Optional[TemplateGroup]:
        if self._workflow is None:
            return None
        item = self.groups_list.currentItem()
        if item is None:
            return None
        return self._workflow.templates.get(item.text())

    def _on_group_selected(self, *_):
        g = self._selected_group()
        self._suspend_write = True
        if g is None:
            self.lbl_group_name.setText("(未选)")
            self.confidence_spin.setValue(0.7)
            self.strategy_combo.setCurrentIndex(0)
            self.region_label.setText("(无)")
            self.variants_list.clear()
        else:
            self.lbl_group_name.setText(g.name)
            self.confidence_spin.setValue(float(g.default_confidence))
            idx = self.strategy_combo.findData(g.match_strategy)
            if idx >= 0:
                self.strategy_combo.setCurrentIndex(idx)
            self.region_label.setText(str(g.default_region) if g.default_region else "(无 - 全屏)")
            self._populate_variants(g)
        self._suspend_write = False

    def _populate_variants(self, group: TemplateGroup):
        self.variants_list.clear()
        for v in group.variants:
            item = QListWidgetItem(v.file)
            path = variant_image_path(self.templates_dir, group.name, v.file)
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    item.setIcon(pix)
            item.setToolTip(f"confidence={v.confidence}\n{v.note}")
            self.variants_list.addItem(item)

    def _new_group_via_picker(self):
        if self._workflow is None:
            return
        # Hide main window so picker isn't covered
        win = self.window()
        win.showMinimized()
        try:
            picker = RegionPicker()
            region = picker.pick()
        finally:
            win.showNormal()
            win.raise_(); win.activateWindow()

        if not region:
            return

        name, ok = QInputDialog.getText(self, "新建模板组", "名称:")
        if not ok or not name.strip():
            return
        name = sanitize_group_name(name)
        if name in self._workflow.templates:
            QMessageBox.warning(self, "重名", f"模板组 {name!r} 已存在；可在它下面添加变体。")
            return
        # Grab the image
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
        except Exception as e:
            QMessageBox.critical(self, "截图失败", str(e))
            return
        try:
            fn, _ = save_variant_image(self.templates_dir, name, img)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        group = TemplateGroup(
            name=name,
            variants=[TemplateVariant(file=fn, confidence=0.7, added_at=today_string())],
            default_region=list(region),
            default_confidence=0.7,
            match_strategy="first_hit",
        )
        self._workflow.templates[name] = group
        write_group_meta(self.templates_dir, group)
        self.refresh()
        # Select the newly created group
        for i in range(self.groups_list.count()):
            if self.groups_list.item(i).text() == name:
                self.groups_list.setCurrentRow(i)
                break
        self.workflow_modified.emit()

    def _delete_selected_group(self):
        g = self._selected_group()
        if g is None:
            return
        ret = QMessageBox.question(
            self, "确认", f"删除模板组 {g.name!r} 及其全部变体文件？",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_group(self.templates_dir, g.name)
        except Exception as e:
            QMessageBox.warning(self, "文件删除失败", str(e))
        self._workflow.templates.pop(g.name, None)
        self.refresh()
        self.workflow_modified.emit()

    # ---------- variant handlers ----------
    def _add_variant_via_picker(self):
        g = self._selected_group()
        if g is None:
            QMessageBox.information(self, "未选组", "先选中一个模板组")
            return
        win = self.window()
        win.showMinimized()
        try:
            picker = RegionPicker()
            region = picker.pick()
        finally:
            win.showNormal()
            win.raise_(); win.activateWindow()
        if not region:
            return
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
        except Exception as e:
            QMessageBox.critical(self, "截图失败", str(e))
            return
        try:
            fn, _ = save_variant_image(self.templates_dir, g.name, img)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        g.variants.append(TemplateVariant(file=fn, confidence=g.default_confidence,
                                          added_at=today_string()))
        write_group_meta(self.templates_dir, g)
        self._populate_variants(g)
        self.workflow_modified.emit()

    def _delete_selected_variant(self):
        g = self._selected_group()
        if g is None:
            return
        item = self.variants_list.currentItem()
        if item is None:
            return
        fn = item.text()
        ret = QMessageBox.question(self, "确认", f"删除变体文件 {fn}？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        g.variants = [v for v in g.variants if v.file != fn]
        delete_variant(self.templates_dir, g.name, fn)
        write_group_meta(self.templates_dir, g)
        self._populate_variants(g)
        self.workflow_modified.emit()

    def _on_variant_selected(self, *_):
        g = self._selected_group()
        item = self.variants_list.currentItem()
        if g is None or item is None:
            self.preview.clear()
            self.preview.setText("(选择变体预览)")
            return
        path = variant_image_path(self.templates_dir, g.name, item.text())
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaled(
                    self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                return
        self.preview.setText("(图片读取失败)")

    def _write_group_settings(self):
        if self._suspend_write:
            return
        g = self._selected_group()
        if g is None:
            return
        g.default_confidence = self.confidence_spin.value()
        g.match_strategy = self.strategy_combo.currentData()
        write_group_meta(self.templates_dir, g)
        self.workflow_modified.emit()

    # ---------- import ----------
    def _import_from_disk(self):
        if self._workflow is None:
            return
        existing = list(self._workflow.templates.keys())
        selected, overwrite = offer_disk_import(self, self.templates_dir, existing)
        self._commit_import(selected, overwrite)

    def _import_from_workflow(self):
        if self._workflow is None:
            return
        from pathlib import Path
        path_str, _ = QFileDialog.getOpenFileName(
            self, "选择源工作流", str(self.templates_dir.parent / "workflows"),
            "AutoWorkflow files (*.awf.json);;JSON files (*.json);;All files (*)",
        )
        if not path_str:
            return
        existing = list(self._workflow.templates.keys())
        selected, overwrite = offer_workflow_import(
            self, self.templates_dir, existing, Path(path_str)
        )
        self._commit_import(selected, overwrite)

    def _commit_import(self, selected: dict, overwrite: bool):
        if not selected:
            return
        imported = 0
        skipped = 0
        for name, group in selected.items():
            if name in self._workflow.templates and not overwrite:
                skipped += 1
                continue
            self._workflow.templates[name] = group
            # Make sure meta.json exists on disk for this group (so it's visible
            # to future "scan from disk" imports too)
            write_group_meta(self.templates_dir, group)
            imported += 1
        msg = f"已导入 {imported} 组"
        if skipped:
            msg += f", 跳过 {skipped} 个同名组 (勾选「覆盖」以替换)"
        QMessageBox.information(self, "导入完成", msg)
        self.refresh()
        if imported:
            self.workflow_modified.emit()
