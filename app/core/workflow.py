"""Core data models for workflows.

Phase 2 additions:
- TemplateGroup / TemplateVariant for image template library
- DataSource for top-level data iteration (csv/xlsx/json/inline)
- Filter for data source filtering (visual rules / expression)
- Nested step bodies (loop_data.body, if.then, if.else)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import uuid


def new_step_id() -> str:
    """Short unique id for a step."""
    return "s_" + uuid.uuid4().hex[:8]


# Step types whose params contain nested step lists. Map type -> tuple of param keys.
NESTED_BODY_FIELDS: Dict[str, Tuple[str, ...]] = {
    "loop_data": ("body",),
    "if": ("then", "else"),
}


# ---------------------- Templates ----------------------

@dataclass
class TemplateVariant:
    file: str                  # relative to templates/<group_name>/
    confidence: float = 0.7
    added_at: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"file": self.file, "confidence": self.confidence,
                "added_at": self.added_at, "note": self.note}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TemplateVariant":
        return cls(
            file=d.get("file", ""),
            confidence=float(d.get("confidence", 0.7) or 0.7),
            added_at=d.get("added_at", ""),
            note=d.get("note", ""),
        )


@dataclass
class TemplateGroup:
    name: str
    variants: List[TemplateVariant] = field(default_factory=list)
    default_region: Optional[List[int]] = None  # [x, y, w, h] or None
    default_confidence: float = 0.7
    match_strategy: str = "first_hit"  # first_hit | best_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "variants": [v.to_dict() for v in self.variants],
            "default_region": list(self.default_region) if self.default_region else None,
            "default_confidence": self.default_confidence,
            "match_strategy": self.match_strategy,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TemplateGroup":
        region = d.get("default_region")
        return cls(
            name=d.get("name", ""),
            variants=[TemplateVariant.from_dict(v) for v in d.get("variants", [])],
            default_region=list(region) if region else None,
            default_confidence=float(d.get("default_confidence", 0.7) or 0.7),
            match_strategy=d.get("match_strategy", "first_hit"),
        )


# ---------------------- Filter ----------------------

@dataclass
class FilterRule:
    field: str
    operator: str  # == != > >= < <= contains startswith endswith in not_in
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "operator": self.operator, "value": self.value}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FilterRule":
        return cls(field=d.get("field", ""), operator=d.get("operator", "=="),
                   value=d.get("value"))


@dataclass
class Filter:
    mode: str = "expression"  # visual | expression
    expression: Optional[str] = None
    rules: List[FilterRule] = field(default_factory=list)
    combinator: str = "and"  # for visual mode: and | or

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"mode": self.mode, "combinator": self.combinator}
        if self.expression is not None:
            d["expression"] = self.expression
        d["rules"] = [r.to_dict() for r in self.rules]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Filter":
        return cls(
            mode=d.get("mode", "expression"),
            expression=d.get("expression"),
            rules=[FilterRule.from_dict(r) for r in d.get("rules", [])],
            combinator=d.get("combinator", "and"),
        )


# ---------------------- DataSource ----------------------

@dataclass
class DataSource:
    type: str  # csv | xlsx | json | inline
    path: Optional[str] = None
    sheet: Optional[str] = None  # for xlsx
    column: Optional[str] = None  # if set, items are scalars from this column
    inline_items: Optional[List[Any]] = None
    start_index: int = 0
    end_index: Optional[int] = None
    skip_empty: bool = True
    filter: Optional[Filter] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.type,
            "path": self.path,
            "sheet": self.sheet,
            "column": self.column,
            "inline_items": list(self.inline_items) if self.inline_items else None,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "skip_empty": self.skip_empty,
        }
        if self.filter is not None:
            d["filter"] = self.filter.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataSource":
        return cls(
            type=d.get("type", "inline"),
            path=d.get("path"),
            sheet=d.get("sheet"),
            column=d.get("column"),
            inline_items=list(d.get("inline_items", []) or []) if d.get("inline_items") else None,
            start_index=int(d.get("start_index", 0) or 0),
            end_index=d.get("end_index"),
            skip_empty=bool(d.get("skip_empty", True)),
            filter=Filter.from_dict(d["filter"]) if d.get("filter") else None,
        )


# ---------------------- WorkflowSettings (unchanged) ----------------------

@dataclass
class WorkflowSettings:
    short_pause_sec: int = 360
    short_pause_every: int = 5
    long_pause_sec: int = 1800
    long_pause_every: int = 15
    default_step_timeout: float = 10.0
    failure_policy: str = "continue"
    retry_max: int = 2
    record_merge_threshold_sec: float = 1.5
    record_idle_to_wait_sec: float = 1.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "short_pause_sec": self.short_pause_sec,
            "short_pause_every": self.short_pause_every,
            "long_pause_sec": self.long_pause_sec,
            "long_pause_every": self.long_pause_every,
            "default_step_timeout": self.default_step_timeout,
            "failure_policy": self.failure_policy,
            "retry_max": self.retry_max,
            "record_merge_threshold_sec": self.record_merge_threshold_sec,
            "record_idle_to_wait_sec": self.record_idle_to_wait_sec,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowSettings":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------- Step ----------------------

@dataclass
class Step:
    id: str
    type: str
    name: str = ""
    enabled: bool = True
    breakpoint: bool = False
    params: Dict[str, Any] = field(default_factory=dict)
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    timeout: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        out_params = _serialize_nested(self.type, self.params)
        d: Dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "enabled": self.enabled,
            "breakpoint": self.breakpoint,
            "params": out_params,
        }
        if self.on_success is not None:
            d["on_success"] = self.on_success
        if self.on_failure is not None:
            d["on_failure"] = self.on_failure
        if self.timeout is not None:
            d["timeout"] = self.timeout
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Step":
        params = dict(data.get("params", {}))
        params = _deserialize_nested(data.get("type", ""), params)
        return cls(
            id=data["id"],
            type=data["type"],
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            breakpoint=data.get("breakpoint", False),
            params=params,
            on_success=data.get("on_success"),
            on_failure=data.get("on_failure"),
            timeout=data.get("timeout"),
        )

    def get_body(self, key: str = "body") -> List["Step"]:
        return self.params.get(key) or []

    def set_body(self, body: List["Step"], key: str = "body") -> None:
        self.params[key] = body


def _serialize_nested(step_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    fields = NESTED_BODY_FIELDS.get(step_type, ())
    if not fields:
        return dict(params)
    out = dict(params)
    for f in fields:
        body = out.get(f)
        if body is None:
            continue
        if isinstance(body, list):
            out[f] = [s.to_dict() if isinstance(s, Step) else dict(s) for s in body]
    return out


def _deserialize_nested(step_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    fields = NESTED_BODY_FIELDS.get(step_type, ())
    if not fields:
        return params
    for f in fields:
        body = params.get(f)
        if body is None:
            continue
        if isinstance(body, list):
            params[f] = [Step.from_dict(s) if isinstance(s, dict) else s for s in body]
    return params


# ---------------------- Workflow ----------------------

@dataclass
class Workflow:
    name: str
    description: str = ""
    version: str = "0.2"
    variables: Dict[str, Any] = field(default_factory=dict)
    settings: WorkflowSettings = field(default_factory=WorkflowSettings)
    steps: List[Step] = field(default_factory=list)
    templates: Dict[str, TemplateGroup] = field(default_factory=dict)
    data_source: Optional[DataSource] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "variables": dict(self.variables),
            "settings": self.settings.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "templates": {k: v.to_dict() for k, v in self.templates.items()},
            "data_source": self.data_source.to_dict() if self.data_source else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        ds_data = data.get("data_source")
        templates_data = data.get("templates") or {}
        return cls(
            name=data.get("name", "Untitled"),
            description=data.get("description", ""),
            version=data.get("version", "0.2"),
            variables=dict(data.get("variables", {})),
            settings=WorkflowSettings.from_dict(data.get("settings", {})),
            steps=[Step.from_dict(s) for s in data.get("steps", [])],
            templates={k: TemplateGroup.from_dict(v) for k, v in templates_data.items()},
            data_source=DataSource.from_dict(ds_data) if ds_data else None,
        )

    def find_step(self, step_id: str) -> Optional[Step]:
        """Find a step anywhere in the tree (top-level or nested in bodies)."""
        return _find_step_recursive(self.steps, step_id)

    def index_of(self, step_id: str) -> int:
        """Index in top-level steps; -1 if not at top level."""
        for i, s in enumerate(self.steps):
            if s.id == step_id:
                return i
        return -1


def _find_step_recursive(steps: List[Step], step_id: str) -> Optional[Step]:
    for s in steps:
        if s.id == step_id:
            return s
        for body_key in NESTED_BODY_FIELDS.get(s.type, ()):
            body = s.params.get(body_key)
            if isinstance(body, list):
                found = _find_step_recursive(body, step_id)
                if found:
                    return found
    return None


def find_parent(steps: List[Step], step_id: str) -> Tuple[Optional[Step], Optional[str], Optional[List[Step]]]:
    """Find a step's parent container: returns (parent_step_or_None, body_key_or_None, container_list).

    For top-level steps, returns (None, None, steps).
    """
    for s in steps:
        if s.id == step_id:
            return None, None, steps
    for s in steps:
        for body_key in NESTED_BODY_FIELDS.get(s.type, ()):
            body = s.params.get(body_key)
            if isinstance(body, list):
                if any(child.id == step_id for child in body):
                    return s, body_key, body
                deeper = find_parent(body, step_id)
                if deeper[2] is not None:
                    return deeper
    return None, None, None
