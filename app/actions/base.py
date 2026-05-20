"""ActionBase: abstract base for all step types.

Each step type lives in its own module (e.g. actions/click.py).
Modules register themselves into ACTION_REGISTRY via the actions package.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class ActionResult:
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class ActionBase(ABC):
    """Base class for all step actions."""

    # Subclasses override:
    type_name: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, params: Dict[str, Any], context) -> ActionResult:
        """Execute the action. `context` is ExecutionContext."""
        raise NotImplementedError

    def validate(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate params before execution. Return (ok, error_message)."""
        return True, ""

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        """Default params for a newly created step of this type."""
        return {}
