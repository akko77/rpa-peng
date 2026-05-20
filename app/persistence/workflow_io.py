"""Workflow load/save to .awf.json files.

Phase 1: no schema validation beyond basic structure checks. Phase 3 will add jsonschema.
"""
import json
from pathlib import Path
from typing import Union

from ..core.workflow import Workflow


def load_workflow(path: Union[str, Path]) -> Workflow:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"workflow file must contain a JSON object, got {type(data).__name__}")
    return Workflow.from_dict(data)


def save_workflow(workflow: Workflow, path: Union[str, Path]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = workflow.to_dict()
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def workflow_filename_suggestion(workflow: Workflow) -> str:
    """Sanitize workflow.name into a filename stem."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (workflow.name or "untitled"))
    return f"{safe}.awf.json"
