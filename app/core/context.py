"""Execution context: holds variables, current loop item, etc."""
from typing import Any, Dict, Optional
import threading


class ExecutionContext:
    """Runtime context shared across steps in one execution."""

    def __init__(self, variables: Optional[Dict[str, Any]] = None):
        self._variables: Dict[str, Any] = dict(variables or {})
        self.current_item: Any = None
        self.current_index: int = 0
        self._lock = threading.RLock()

    def get(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self._variables.get(name, default)

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._variables[name] = value

    def update(self, mapping: Dict[str, Any]) -> None:
        with self._lock:
            self._variables.update(mapping)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._variables)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._variables
