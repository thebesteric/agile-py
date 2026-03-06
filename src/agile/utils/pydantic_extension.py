from abc import ABC

from pydantic import BaseModel, ConfigDict


class BaseModelEnhance(BaseModel, ABC):
    """
    Base model that supports dictionary-like access.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow"
    )

    def __getitem__(self, key: str):
        if key not in self.__class__.model_fields:
            raise KeyError(f"field '{key}' does not exist")
        return getattr(self, key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default
