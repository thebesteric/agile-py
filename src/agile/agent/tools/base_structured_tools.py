from abc import ABC
from dataclasses import dataclass
import inspect
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from agile.agent.tools.tool_decorators import structured_tool


@dataclass(frozen=True)
class ToolSpec:
    name: str
    method: Callable[..., Any]
    description: str | None
    args_schema: type[BaseModel] | dict[str, Any] | None


class CompatibleStructuredTool(StructuredTool):
    """StructuredTool compatibility shim for code that expects callable-like naming."""

    @property
    def __name__(self) -> str:
        return self.name


class BaseStructuredTools(ABC):
    """Base class that auto-discovers and registers @structured_tool methods."""

    def __init__(self) -> None:
        self._registered_tools: list[StructuredTool] = []
        self.register_tools()

    def discover_tools(self) -> list[ToolSpec]:
        """Discover tool methods declared on the instance and return their metadata."""
        discovered: list[ToolSpec] = []
        for attr_name, raw_attr in inspect.getmembers(type(self), predicate=callable):
            raw_func = getattr(raw_attr, "__func__", raw_attr)
            if not getattr(raw_func, "__structured_tool__", False):
                continue

            custom_name = getattr(raw_func, "__structured_tool_name__", None)
            description = getattr(raw_func, "__structured_tool_description__", None)
            args_schema = getattr(raw_func, "__structured_tool_args_schema__", None)
            tool_name = custom_name or attr_name
            spec = ToolSpec(
                name=tool_name,
                method=getattr(self, attr_name),
                description=description,
                args_schema=args_schema
            )
            discovered.append(spec)

        return discovered

    def register_tools(self) -> list[StructuredTool]:
        """Build StructuredTool instances for all discovered and ready tools."""
        self._registered_tools = []
        for spec in self.discover_tools():
            structured_tool = CompatibleStructuredTool.from_function(
                func=spec.method,
                name=spec.name,
                description=spec.description,
                args_schema=spec.args_schema,
            )
            setattr(self, spec.name, structured_tool)
            self._registered_tools.append(structured_tool)

        return list(self._registered_tools)

    def _auto_register_tools(self) -> None:
        """Backward-compatible alias for register_tools()."""
        self.register_tools()

    def _get_tool_methods(
            self,
    ) -> list[tuple[str, Callable[..., Any], str | None, type[BaseModel] | dict[str, Any] | None]]:
        """Backward-compatible alias for discover_tools()."""
        return [
            (spec.name, spec.method, spec.description, spec.args_schema)
            for spec in self.discover_tools()
        ]

    def get_tools(self) -> list[StructuredTool]:
        """Return all registered StructuredTool instances."""
        return list(self._registered_tools)
