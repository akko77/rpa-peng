"""Step list panel (Phase 2): tree-based to support nested step bodies."""
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMenu, QAbstractItemView, QStyledItemDelegate,
)

from ..core.workflow import Workflow, Step, new_step_id, NESTED_BODY_FIELDS, find_parent
from ..actions import all_action_classes, default_params


_STEP_ID_ROLE = Qt.ItemDataRole.UserRole + 1
_BODY_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
_PARENT_ID_ROLE = Qt.ItemDataRole.UserRole + 3
_CURRENT_ROLE = Qt.ItemDataRole.UserRole + 4
_BREAKPOINT_ROLE = Qt.ItemDataRole.UserRole + 5


class _Delegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        is_current = bool(index.data(_CURRENT_ROLE))
        has_breakpoint = bool(index.data(_BREAKPOINT_ROLE))
        if is_current:
            painter.save()
            painter.fillRect(option.rect, QColor(255, 245, 200))
            painter.restore()
        super().paint(painter, option, index)
        if has_breakpoint:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(180, 30, 30), 1))
            painter.setBrush(QBrush(QColor(220, 60, 60)))
            r = option.rect
            cx = r.right() - 14
            cy = r.center().y()
            painter.drawEllipse(cx - 4, cy - 4, 8, 8)
            painter.restore()


class StepListPanel(QWidget):
    step_selected = Signal(str)
    steps_changed = Signal()
    breakpoint_toggled = Signal(str, bool)
    enabled_toggled = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow: Optional[Workflow] = None
        self._suspend = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        tools = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加步骤")
        self.add_btn.clicked.connect(self._show_add_menu)
        tools.addWidget(self.add_btn)
        self.dup_btn = QPushButton("复制"); self.dup_btn.clicked.connect(self._duplicate_selected); tools.addWidget(self.dup_btn)
        self.del_btn = QPushButton("删除"); self.del_btn.clicked.connect(self._delete_selected); tools.addWidget(self.del_btn)
        self.bp_btn = QPushButton("断点"); self.bp_btn.setCheckable(True)
        self.bp_btn.clicked.connect(self._toggle_breakpoint); tools.addWidget(self.bp_btn)
        tools.addStretch(1)
        layout.addLayout(tools)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setItemDelegate(_Delegate(self.tree))
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.tree, 1)

    # ---------- public ----------
    def set_workflow(self, workflow: Workflow):
        self._workflow = workflow
        self.refresh()

    def refresh(self):
        self._suspend = True
        self.tree.clear()
        if self._workflow is not None:
            for s in self._workflow.steps:
                self._add_step_item(self.tree.invisibleRootItem(), s, parent_step=None)
            self.tree.expandAll()
        self._suspend = False

    def selected_step_id(self) -> Optional[str]:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, _STEP_ID_ROLE)

    def select_step(self, step_id: str):
        it = self._find_item_by_step_id(step_id)
        if it is not None:
            self.tree.setCurrentItem(it)

    def mark_current(self, step_id: Optional[str]):
        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                sid = child.data(0, _STEP_ID_ROLE)
                child.setData(0, _CURRENT_ROLE, bool(step_id and sid == step_id))
                walk(child)
        walk(self.tree.invisibleRootItem())
        self.tree.viewport().update()

    def refresh_item(self, step_id: str):
        if self._workflow is None:
            return
        step = self._workflow.find_step(step_id)
        if step is None:
            return
        it = self._find_item_by_step_id(step_id)
        if it is None:
            return
        self._suspend = True
        it.setText(0, self._label(step))
        it.setData(0, _BREAKPOINT_ROLE, step.breakpoint)
        it.setCheckState(0, Qt.CheckState.Checked if step.enabled else Qt.CheckState.Unchecked)
        self._suspend = False
        self.tree.viewport().update()

    # ---------- internal ----------
    def _add_step_item(self, parent_item, step: Step, parent_step: Optional[Step]):
        item = QTreeWidgetItem(parent_item)
        item.setText(0, self._label(step))
        item.setData(0, _STEP_ID_ROLE, step.id)
        item.setData(0, _PARENT_ID_ROLE, parent_step.id if parent_step else None)
        item.setData(0, _BODY_KEY_ROLE, None)
        item.setData(0, _BREAKPOINT_ROLE, step.breakpoint)
        item.setData(0, _CURRENT_ROLE, False)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
        item.setCheckState(0, Qt.CheckState.Checked if step.enabled else Qt.CheckState.Unchecked)

        for body_key in NESTED_BODY_FIELDS.get(step.type, ()):
            header = QTreeWidgetItem(item)
            header.setText(0, f"  ▸ {body_key}")
            header.setData(0, _STEP_ID_ROLE, None)
            header.setData(0, _PARENT_ID_ROLE, step.id)
            header.setData(0, _BODY_KEY_ROLE, body_key)
            header.setFlags((header.flags() & ~Qt.ItemFlag.ItemIsUserCheckable
                             & ~Qt.ItemFlag.ItemIsDragEnabled) | Qt.ItemFlag.ItemIsDropEnabled)
            header.setForeground(0, QBrush(QColor(120, 120, 120)))
            body = step.params.get(body_key) or []
            for child_step in body:
                self._add_step_item(header, child_step, parent_step=step)

    def _find_item_by_step_id(self, step_id: str) -> Optional[QTreeWidgetItem]:
        def walk(item):
            for i in range(item.childCount()):
                ch = item.child(i)
                if ch.data(0, _STEP_ID_ROLE) == step_id:
                    return ch
                found = walk(ch)
                if found:
                    return found
            return None
        return walk(self.tree.invisibleRootItem())

    @staticmethod
    def _label(step: Step) -> str:
        name = step.name or "(未命名)"
        return f"{name}   ·   {step.type}"

    # ---------- add/del/dup ----------
    def _show_add_menu(self):
        if self._workflow is None:
            return
        menu = QMenu(self)
        for cls in all_action_classes():
            act = QAction(f"{cls.display_name}  ({cls.type_name})", menu)
            act.triggered.connect(lambda checked=False, c=cls: self._add_step(c.type_name, c.display_name))
            menu.addAction(act)
        menu.exec(self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))

    def _get_insertion_target(self) -> Tuple[List[Step], int]:
        if self._workflow is None:
            return [], 0
        item = self.tree.currentItem()
        if item is None:
            return self._workflow.steps, len(self._workflow.steps)
        body_key = item.data(0, _BODY_KEY_ROLE)
        if body_key:
            parent_id = item.data(0, _PARENT_ID_ROLE)
            parent_step = self._workflow.find_step(parent_id) if parent_id else None
            if parent_step is None:
                return self._workflow.steps, len(self._workflow.steps)
            body = parent_step.params.setdefault(body_key, [])
            return body, len(body)
        sid = item.data(0, _STEP_ID_ROLE)
        parent_step, body_key, container = find_parent(self._workflow.steps, sid)
        if container is None:
            return self._workflow.steps, len(self._workflow.steps)
        idx = next((i for i, s in enumerate(container) if s.id == sid), len(container))
        return container, idx + 1

    def _add_step(self, type_name: str, display_name: str):
        if self._workflow is None:
            return
        container, idx = self._get_insertion_target()
        step = Step(id=new_step_id(), type=type_name, name=display_name,
                    params=default_params(type_name))
        container.insert(idx, step)
        self.refresh()
        self.select_step(step.id)
        self.steps_changed.emit()

    def _duplicate_selected(self):
        if self._workflow is None:
            return
        sid = self.selected_step_id()
        if sid is None:
            return
        src = self._workflow.find_step(sid)
        if src is None:
            return
        import copy
        clone = copy.deepcopy(src)
        self._reassign_ids(clone)
        clone.name = (src.name or "") + " (copy)"
        parent_step, body_key, container = find_parent(self._workflow.steps, sid)
        if container is None:
            return
        idx = next((i for i, s in enumerate(container) if s.id == sid), len(container))
        container.insert(idx + 1, clone)
        self.refresh()
        self.select_step(clone.id)
        self.steps_changed.emit()

    @staticmethod
    def _reassign_ids(step: Step):
        step.id = new_step_id()
        for k in NESTED_BODY_FIELDS.get(step.type, ()):
            body = step.params.get(k) or []
            for child in body:
                if isinstance(child, Step):
                    StepListPanel._reassign_ids(child)

    def _delete_selected(self):
        if self._workflow is None:
            return
        sid = self.selected_step_id()
        if sid is None:
            return
        parent_step, body_key, container = find_parent(self._workflow.steps, sid)
        if container is None:
            return
        container[:] = [s for s in container if s.id != sid]
        self._purge_jump_refs(self._workflow.steps, sid)
        self.refresh()
        self.steps_changed.emit()

    def _purge_jump_refs(self, steps: List[Step], removed_id: str):
        for s in steps:
            if s.on_success == removed_id:
                s.on_success = None
            if s.on_failure == removed_id:
                s.on_failure = None
            for k in NESTED_BODY_FIELDS.get(s.type, ()):
                body = s.params.get(k) or []
                self._purge_jump_refs(body, removed_id)

    def _toggle_breakpoint(self):
        if self._workflow is None:
            return
        sid = self.selected_step_id()
        if sid is None:
            return
        step = self._workflow.find_step(sid)
        if step is None:
            return
        step.breakpoint = not step.breakpoint
        self.refresh_item(sid)
        self.breakpoint_toggled.emit(sid, step.breakpoint)
        self.steps_changed.emit()

    # ---------- sync ----------
    def _on_item_changed(self, item: QTreeWidgetItem, _col=0):
        if self._suspend or self._workflow is None:
            return
        sid = item.data(0, _STEP_ID_ROLE)
        if sid is None:
            return
        step = self._workflow.find_step(sid)
        if step is None:
            return
        new_enabled = item.checkState(0) == Qt.CheckState.Checked
        if new_enabled != step.enabled:
            step.enabled = new_enabled
            self.enabled_toggled.emit(sid, new_enabled)
            self.steps_changed.emit()

    def _on_selection_changed(self):
        sid = self.selected_step_id()
        if self._workflow and sid:
            step = self._workflow.find_step(sid)
            self.bp_btn.setChecked(bool(step and step.breakpoint))
        else:
            self.bp_btn.setChecked(False)
        self.step_selected.emit(sid or "")

    def _on_rows_moved(self, *args, **kwargs):
        if self._suspend or self._workflow is None:
            return
        # Snapshot ALL step objects (by id) BEFORE any rebuild. We can't query the
        # workflow during rebuild because we're mutating its bodies as we go —
        # find_step() would return None for a step that just got removed from its
        # old container but not yet added to its new one (e.g. cross-branch drag).
        id_map: Dict[str, Step] = {}

        def collect(steps: List[Step]):
            for s in steps:
                id_map[s.id] = s
                for k in NESTED_BODY_FIELDS.get(s.type, ()):
                    body = s.params.get(k) or []
                    if isinstance(body, list):
                        collect(body)

        collect(self._workflow.steps)

        new_top: List[Step] = []
        seen: set = set()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            sid = top.data(0, _STEP_ID_ROLE)
            if sid is None or sid not in id_map:
                continue
            if sid in seen:
                # Defensive: Qt could in theory show the same id twice; skip dupes
                continue
            seen.add(sid)
            step = id_map[sid]
            self._rebuild_step_bodies_from_item(top, step, id_map, seen)
            new_top.append(step)
        if new_top:
            self._workflow.steps = new_top
            self.steps_changed.emit()

    def _rebuild_step_bodies_from_item(self, item: QTreeWidgetItem, step: Step,
                                       id_map: Dict[str, Step], seen: set):
        for i in range(item.childCount()):
            child = item.child(i)
            body_key = child.data(0, _BODY_KEY_ROLE)
            if not body_key:
                continue
            body: List[Step] = []
            for j in range(child.childCount()):
                grand = child.child(j)
                gid = grand.data(0, _STEP_ID_ROLE)
                if gid is None or gid not in id_map:
                    continue
                if gid in seen:
                    continue
                seen.add(gid)
                sub_step = id_map[gid]
                self._rebuild_step_bodies_from_item(grand, sub_step, id_map, seen)
                body.append(sub_step)
            step.params[body_key] = body
