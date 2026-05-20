"""Template import dialog.

Shows the user template groups available from either:
  - the on-disk templates/ folder (groups that aren't in the current workflow)
  - or, when launched with `from_workflow_path`, the templates of another
    workflow JSON file

User multi-selects which groups to bring into the current workflow. Existing
group names are flagged so the user can choose to skip or overwrite.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QCheckBox, QMessageBox, QFileDialog, QGroupBox,
)

from ...core.workflow import TemplateGroup
from ...persistence.template_io import (
    scan_templates_dir, import_groups_from_workflow_file, variant_image_path,
)


class TemplateImportDialog(QDialog):
    """Returns dict of {group_name: TemplateGroup} for the groups the user chose."""

    def __init__(
        self,
        templates_root: Path,
        existing_group_names: List[str],
        source_label: str,
        groups_to_offer: Dict[str, TemplateGroup],
        parent=None,
    ):
        super().__init__(parent)
        self.templates_root = templates_root
        self.existing_group_names = set(existing_group_names)
        self.source_label = source_label
        self.groups_to_offer = groups_to_offer
        self._build_ui()
        self._populate()

    def _build_ui(self):
        self.setWindowTitle("导入模板组")
        self.resize(560, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"来源: {self.source_label}"))

        self.list = QListWidget()
        self.list.setIconSize(QSize(64, 64))
        layout.addWidget(self.list, 1)

        # Overwrite checkbox
        self.overwrite_check = QCheckBox("对同名组覆盖（默认跳过）")
        layout.addWidget(self.overwrite_check)

        # Buttons
        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton("全不选")
        self.select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(self.select_none_btn)
        btn_row.addStretch(1)
        self.ok_btn = QPushButton("导入选中")
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.ok_btn)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _populate(self):
        self.list.clear()
        for name, group in self.groups_to_offer.items():
            already = name in self.existing_group_names
            label = f"{name}    ({len(group.variants)} 变体)"
            if already:
                label += "    [当前已存在]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if already else Qt.CheckState.Checked)
            # Thumbnail of first variant if it exists on disk
            if group.variants:
                p = variant_image_path(self.templates_root, name, group.variants[0].file)
                if p.exists():
                    pix = QPixmap(str(p))
                    if not pix.isNull():
                        item.setIcon(pix)
            self.list.addItem(item)

    def _select_all(self):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def get_selection(self) -> Tuple[Dict[str, TemplateGroup], bool]:
        """Return (groups_to_import, overwrite_flag)."""
        result: Dict[str, TemplateGroup] = {}
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            name = item.data(Qt.ItemDataRole.UserRole)
            if name in self.groups_to_offer:
                result[name] = self.groups_to_offer[name]
        return result, self.overwrite_check.isChecked()


def offer_disk_import(
    parent,
    templates_root: Path,
    existing_group_names: List[str],
) -> Tuple[Dict[str, TemplateGroup], bool]:
    """Scan templates dir, show dialog, return user's selection.

    Returns ({}, False) if user cancelled or nothing to offer.
    """
    available = scan_templates_dir(templates_root)
    if not available:
        QMessageBox.information(parent, "无可导入模板",
                                f"在 {templates_root} 没有找到任何模板文件夹。")
        return {}, False
    offered = {g.name: g for g in available}
    dlg = TemplateImportDialog(
        templates_root, existing_group_names,
        source_label=f"磁盘目录 {templates_root}",
        groups_to_offer=offered, parent=parent,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return {}, False
    return dlg.get_selection()


def offer_workflow_import(
    parent,
    templates_root: Path,
    existing_group_names: List[str],
    workflow_path: Path,
) -> Tuple[Dict[str, TemplateGroup], bool]:
    """Load another workflow's templates dict and show import dialog."""
    try:
        groups = import_groups_from_workflow_file(workflow_path)
    except Exception as e:
        QMessageBox.critical(parent, "读取失败", f"无法读取 {workflow_path}:\n{e}")
        return {}, False
    if not groups:
        QMessageBox.information(parent, "无模板",
                                f"{workflow_path} 中没有模板组。")
        return {}, False
    dlg = TemplateImportDialog(
        templates_root, existing_group_names,
        source_label=f"工作流文件 {workflow_path.name}",
        groups_to_offer=groups, parent=parent,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return {}, False
    return dlg.get_selection()
