from enum import Enum
from typing import Generic, Iterator, Optional, Protocol, Self, TypeVar, cast

ValueT = TypeVar("ValueT")


class _EnumIterableClass(Protocol[ValueT]):
    def __iter__(self) -> Iterator[ValueT]: ...


class LabeledEnumBase(Generic[ValueT]):
    """
    Shared behavior for labeled enums.

    Subclasses provide their own underlying value type (e.g. ``str`` or ``int``)
    and set ``_value_`` / ``_label`` in ``__new__``.
    """

    _label: str
    value: ValueT
    name: str

    @classmethod
    def _iter_members(cls: type[Self]) -> Iterator[Self]:
        return iter(cast(_EnumIterableClass[Self], cast(object, cls)))

    @property
    def label(self) -> str:
        return self._label

    def display(self) -> str:
        return f"{self.value} ({self.label})"

    @classmethod
    def get_all(cls) -> list[tuple[ValueT, str]]:
        return [(e.value, e.label) for e in cls._iter_members()]

    @classmethod
    def get_format_instructions(cls, title: Optional[str] = None) -> str:
        body = "\n".join(f"  - {e.value}: {e.label}" for e in cls._iter_members())
        if title:
            return f"{title}\n{body}"
        return body

    @classmethod
    def from_value(cls: type[Self], value: ValueT) -> Optional[Self]:
        for e in cls._iter_members():
            if e.value == value:
                return e
        return None

    @classmethod
    def from_name(cls: type[Self], name: str) -> Optional[Self]:
        for e in cls._iter_members():
            if e.name == name:
                return e
        return None


class LabeledStrEnum(str, LabeledEnumBase[str], Enum):
    """
    String enum with a human-readable label for prompt/display usage.
    """

    def __new__(cls, value: str, label: str) -> Self:
        obj = str.__new__(cls, value)  # type: ignore[arg-type]
        obj._value_ = value
        obj._label = label
        return cast(Self, obj)


class LabeledIntEnum(int, LabeledEnumBase[int], Enum):
    """
    Integer enum with a human-readable label for prompt/display usage.
    """

    def __new__(cls, value: int, label: str) -> Self:
        obj = int.__new__(cls, value)  # type: ignore[arg-type]
        obj._value_ = value
        obj._label = label
        return cast(Self, obj)


