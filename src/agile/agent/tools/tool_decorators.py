from collections.abc import Callable
from typing import Any

from pydantic import BaseModel


def structured_tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    args_schema: type[BaseModel] | dict[str, Any] | None = None,
    depends_on: str | tuple[str, ...] | list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]] | Callable[..., Any]:
    """
    Mark a bound method as a StructuredTool entrypoint.

    Supports both ``@structured_tool`` and ``@structured_tool(...)``.
    """

    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        setattr(target, "__structured_tool__", True)
        setattr(target, "__structured_tool_name__", name)
        setattr(target, "__structured_tool_description__", description)
        setattr(target, "__structured_tool_args_schema__", args_schema)
        if depends_on is None:
            normalized_depends_on: tuple[str, ...] | None = None
        elif isinstance(depends_on, str):
            normalized_depends_on = (depends_on,)
        else:
            normalized_depends_on = tuple(depends_on)
        setattr(target, "__structured_tool_depends_on__", normalized_depends_on)
        return target

    if func is not None:
        return decorator(func)
    return decorator

