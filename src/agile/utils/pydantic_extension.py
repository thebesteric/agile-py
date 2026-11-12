from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Self

from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    ModelWrapValidatorHandler,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError


@dataclass(frozen=True, kw_only=True)
class FieldErrorConfig:
    """Configure a field error, preferring an exception factory over a message."""

    field_name: str
    error_message: str = "字段校验失败"
    func: Callable[[ErrorDetails], Exception] | None = None

    def __post_init__(self):
        if not isinstance(self.field_name, str):
            raise TypeError("field_name must be a string")
        if not self.field_name.strip():
            raise ValueError("field_name must not be blank")
        if not isinstance(self.error_message, str):
            raise TypeError("error_message must be a string")
        if self.func is not None and not callable(self.func):
            raise TypeError("func must be callable")


class BaseModelEnhance(BaseModel, ABC):
    """
    Base model with dictionary-like access and configurable field validation.

    Override ``get_empty_str_to_none()`` to return True or a set of field
    names to normalize empty/whitespace-only strings. Override
    ``get_field_errors()`` to return FieldErrorConfig objects with custom
    error messages or factories accepting an ErrorDetails dictionary and
    returning an exception. Both methods use Python field names, not aliases.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow"
    )

    @classmethod
    def get_empty_str_to_none(cls) -> bool | set[str]:
        """Return True for all fields, a set for selected fields, or False."""
        return False

    @classmethod
    def get_field_errors(cls) -> list[FieldErrorConfig]:
        """Return field error configurations; a configured func takes priority."""
        return []

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_empty_string(cls, value: Any, info: ValidationInfo) -> Any:
        fields = cls.get_empty_str_to_none()
        enabled = fields is True or (isinstance(fields, set) and info.field_name in fields)
        if enabled and isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="wrap")
    @classmethod
    def _customize_field_errors(
            cls,
            value: Any,
            handler: ModelWrapValidatorHandler[Self],
            info: ValidationInfo,
    ) -> Self:
        try:
            return handler(value)
        except ValidationError as validation_error:
            field_errors = cls.get_field_errors()
            if not field_errors:
                raise

            errors: list[InitErrorDetails] = []
            changed = False
            for error in validation_error.errors():
                custom_error = cls._get_field_error_config(error, field_errors)
                if custom_error is not None and custom_error.func is not None:
                    exception = custom_error.func(error)
                    if not isinstance(exception, Exception):
                        raise TypeError("FieldErrorConfig.func must return an Exception")
                    raise exception from validation_error
                error_type: str | PydanticCustomError = error["type"]
                if custom_error is not None:
                    error_type = PydanticCustomError(
                        error["type"], custom_error.error_message, error.get("ctx")
                    )
                    changed = True
                elif "url" not in error:
                    error_type = PydanticCustomError(
                        error["type"], error["msg"], error.get("ctx")
                    )
                line_error = InitErrorDetails(
                    type=error_type, loc=error["loc"], input=error["input"]
                )
                if "ctx" in error:
                    line_error["ctx"] = error["ctx"]
                errors.append(line_error)

            if not changed:
                raise
            raise ValidationError.from_exception_data(
                validation_error.title,
                errors,
                input_type=info.mode,
                hide_input=cls.model_config.get("hide_input_in_errors", False),
            ) from validation_error

    @classmethod
    def _get_field_error_config(
            cls,
            error: ErrorDetails,
            field_errors: list[FieldErrorConfig],
    ) -> FieldErrorConfig | None:
        location = error["loc"]
        if not location or (len(location) == 1 and error["type"] == "extra_forbidden"):
            return None

        for custom_error in field_errors:
            field_name = custom_error.field_name
            field = cls.model_fields.get(field_name)
            if field is None:
                continue
            paths: list[tuple[str | int, ...]] = [(field_name,)]
            if cls.model_config.get("loc_by_alias", True):
                alias = field.validation_alias
                if isinstance(alias, str):
                    paths.append((alias,))
                elif isinstance(alias, AliasChoices):
                    paths.extend(tuple(path) for path in alias.convert_to_aliases())
                elif isinstance(alias, AliasPath):
                    paths.append(tuple(alias.convert_to_aliases()))
            if any(location[:len(path)] == path for path in paths):
                return custom_error
        return None

    def __getitem__(self, key: str):
        if key not in self.__class__.model_fields:
            raise KeyError(f"field '{key}' does not exist")
        return getattr(self, key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default
