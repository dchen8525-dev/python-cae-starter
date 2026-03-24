from __future__ import annotations

from app.adapters.ansa import AnsaAdapter
from app.adapters.base import BaseCAEAdapter
from app.adapters.dummy_solver import DummySolverAdapter


class AdapterRegistry:
    """Registry for available CAE tool adapters."""

    def __init__(self) -> None:
        ansa = AnsaAdapter()
        dummy = DummySolverAdapter()
        self._adapters: dict[str, BaseCAEAdapter] = {
            ansa.tool_name: ansa,
            dummy.tool_name: dummy,
            # Future extension points:
            # "ansys": AnsysAdapter(),
            # "abaqus": AbaqusAdapter(),
            # "starccm": StarCCMAdapter(),
        }

    def get(self, tool_name: str) -> BaseCAEAdapter | None:
        """Return an adapter by tool name."""

        return self._adapters.get(tool_name)

    def supported_tools(self) -> list[str]:
        """Return the list of supported tool names."""

        return sorted(self._adapters.keys())


adapter_registry = AdapterRegistry()
