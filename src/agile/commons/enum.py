from enum import Enum
from typing import TypeVar, Optional

EnumT = TypeVar("EnumT", bound="LabeledStrEnum")


class LabeledStrEnum(str, Enum):
    """
    String enum with a human-readable label for prompt/display usage.
    """

    def __new__(cls, value: str, label: str):
        obj = str.__new__(cls, value)  # type: ignore[arg-type]
        obj._value_ = value
        obj._label = label
        return obj

    @property
    def label(self) -> str:
        return self._label

    def display(self) -> str:
        return f"{self.value} ({self.label})"

    @classmethod
    def get_all(cls) -> list[tuple[str, str]]:
        return [(e.value, e.label) for e in cls]

    @classmethod
    def get_format_instructions(cls, title: Optional[str] = None) -> str:
        body = "\n".join(f"  - {e.value}: {e.label}" for e in cls)
        if title:
            return f"{title}\n{body}"
        return body

    @classmethod
    def from_value(cls: type[EnumT], value: str) -> Optional[EnumT]:
        for e in cls:
            if e.value == value:
                return e
        return None

    @classmethod
    def from_name(cls: type[EnumT], name: str) -> Optional[EnumT]:
        for e in cls:
            if e.name == name:
                return e
        return None
