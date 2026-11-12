import unittest
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

from pydantic import AliasChoices, AliasPath, ConfigDict, Field, TypeAdapter, ValidationError, field_validator
from pydantic_core import PydanticCustomError

from agile.commons.biz_error import BizError, ErrorCode
from agile.utils.pydantic_extension import BaseModelEnhance, FieldErrorConfig


class PermissionRequest(BaseModelEnhance):
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def get_empty_str_to_none(cls) -> bool | set[str]:
        return {"id", "parent_id"}

    @classmethod
    def get_field_errors(cls) -> list[FieldErrorConfig]:
        return [
            FieldErrorConfig(field_name="id", error_message="资源 ID 格式不正确"),
            FieldErrorConfig(field_name="resource_name", error_message="资源名称长度必须为 1 到 128 个字符"),
        ]

    id: UUID | None = Field(default=None, validation_alias=AliasChoices("_id", "id"))
    parent_id: UUID | None = None
    resource_name: str = Field(min_length=1, max_length=128)
    resource_value: str = ""


class TestFieldErrorConfig(unittest.TestCase):

    def test_field_name_is_required(self):
        with self.assertRaises(TypeError):
            FieldErrorConfig()

    def test_default_values(self):
        config = FieldErrorConfig(field_name="id")
        self.assertEqual(config.field_name, "id")
        self.assertEqual(config.error_message, "字段校验失败")
        self.assertIsNone(config.func)

    def test_field_name_must_be_a_nonblank_string(self):
        for value in (None, 1, []):
            with self.subTest(value=value), self.assertRaises(TypeError):
                FieldErrorConfig(field_name=value)
        for value in ("", " \t\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                FieldErrorConfig(field_name=value)

    def test_error_message_must_be_a_string(self):
        for value in (None, 1, []):
            with self.subTest(value=value), self.assertRaises(TypeError):
                FieldErrorConfig(field_name="id", error_message=value)

    def test_func_must_be_callable(self):
        for value in ("callback", 1, BizError()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                FieldErrorConfig(field_name="id", func=value)

    def test_message_and_func_can_be_configured_together(self):
        def factory(error):
            return BizError(message=error["msg"])

        config = FieldErrorConfig(field_name="id", error_message="invalid id", func=factory)
        self.assertEqual(config.error_message, "invalid id")
        self.assertIs(config.func, factory)

    def test_configuration_is_immutable(self):
        config = FieldErrorConfig(field_name="id")
        with self.assertRaises(FrozenInstanceError):
            config.field_name = "parent_id"

    def test_unknown_parameters_are_rejected(self):
        with self.assertRaises(TypeError):
            FieldErrorConfig(field_name="id", message="invalid id")


class TestBaseModelEnhance(unittest.TestCase):

    def test_default_field_error_message_is_used(self):
        class Request(BaseModelEnhance):
            id: UUID

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id")]

        for values in ({}, {"id": "bad"}):
            with self.subTest(values=values), self.assertRaises(ValidationError) as raised:
                Request.model_validate(values)
            self.assertEqual(raised.exception.errors()[0]["loc"], ("id",))
            self.assertEqual(raised.exception.errors()[0]["msg"], "字段校验失败")

    def test_func_exception_takes_priority_over_error_message(self):
        observed = []
        exception = BizError(message="exception from func")

        def factory(error):
            observed.append(error)
            return exception

        class Request(BaseModelEnhance):
            id: UUID

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(
                    field_name="id", error_message="ignored error message", func=factory
                )]

        with self.assertRaises(BizError) as raised:
            Request(id="bad")
        self.assertIs(raised.exception, exception)
        self.assertIsInstance(raised.exception.__cause__, ValidationError)
        self.assertEqual(observed[0]["type"], "uuid_parsing")
        self.assertEqual(observed[0]["input"], "bad")
        self.assertNotEqual(observed[0]["msg"], "ignored error message")
        self.assertNotEqual(observed[0]["msg"], "字段校验失败")

    def test_func_must_return_an_exception_instance(self):
        for return_value in (None, "invalid id", RuntimeError):
            with self.subTest(return_value=return_value):
                class Request(BaseModelEnhance):
                    id: UUID

                    @classmethod
                    def get_field_errors(cls) -> list[FieldErrorConfig]:
                        return [FieldErrorConfig(field_name="id", func=lambda error: return_value)]

                with self.assertRaisesRegex(TypeError, "must return an Exception"):
                    Request(id="bad")

    def test_default_configuration_methods_return_independent_values(self):
        self.assertIs(BaseModelEnhance.get_empty_str_to_none(), False)
        errors = BaseModelEnhance.get_field_errors()
        errors.append(FieldErrorConfig(field_name="id", error_message="invalid id"))
        self.assertEqual(BaseModelEnhance.get_field_errors(), [])
        self.assertEqual(BaseModelEnhance.model_fields, {})

    def test_configuration_methods_can_extend_parent_results(self):
        class Request(PermissionRequest):
            owner_id: UUID | None = None

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return {*super().get_empty_str_to_none(), "owner_id"}

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [*super().get_field_errors(), FieldErrorConfig(field_name="owner_id", error_message="invalid owner id")]

        model = Request(id="", parent_id=" ", owner_id="\t", resource_name="menu")
        self.assertIsNone(model.id)
        self.assertIsNone(model.parent_id)
        self.assertIsNone(model.owner_id)
        with self.assertRaises(ValidationError) as raised:
            Request(id="bad", owner_id="bad", resource_name="menu")
        self.assertEqual(raised.exception.errors()[0]["msg"], "资源 ID 格式不正确")
        self.assertEqual(raised.exception.errors()[1]["msg"], "invalid owner id")
        self.assertNotIn("owner_id", PermissionRequest.get_empty_str_to_none())
        self.assertNotIn("owner_id", {config.field_name for config in PermissionRequest.get_field_errors()})

    def test_configuration_methods_receive_the_concrete_subclass(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return {name for name in cls.model_fields if name.endswith("_id")}

            parent_id: UUID | None = None
            text: str = ""

        class ChildRequest(Request):
            owner_id: UUID | None = None

        model = ChildRequest(parent_id="", owner_id=" ")
        self.assertIsNone(model.parent_id)
        self.assertIsNone(model.owner_id)
        self.assertEqual(model.text, "")
        self.assertEqual(Request.get_empty_str_to_none(), {"parent_id"})

    def test_error_configuration_is_read_once_and_only_after_failure(self):
        calls = []

        class Request(BaseModelEnhance):
            first: int
            second: int

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                calls.append(cls)
                return [FieldErrorConfig(field_name="first", error_message="invalid first"), FieldErrorConfig(field_name="second", error_message="invalid second")]

        Request(first=1, second=2)
        self.assertEqual(calls, [])
        with self.assertRaises(ValidationError) as raised:
            Request(first="bad", second="bad")
        self.assertEqual(calls, [Request])
        self.assertEqual(
            [error["msg"] for error in raised.exception.errors()],
            ["invalid first", "invalid second"],
        )

    def test_features_are_opt_in(self):
        class Request(BaseModelEnhance):
            text: str | None
            id: UUID | None = None

        self.assertEqual(Request(text="").text, "")
        self.assertEqual(Request(text="  ").text, "  ")
        with self.assertRaises(ValidationError) as raised:
            Request(text="", id="")
        self.assertEqual(raised.exception.errors()[0]["type"], "uuid_parsing")

    def test_selected_fields_and_alias_choices(self):
        for alias in ("_id", "id"):
            for blank in ("", " ", "\t\n", "\u3000"):
                with self.subTest(alias=alias, blank=blank):
                    model = PermissionRequest.model_validate({
                        alias: blank,
                        "parent_id": blank,
                        "resource_name": "menu",
                    })
                    self.assertIsNone(model.id)
                    self.assertIsNone(model.parent_id)
                    self.assertEqual(model.resource_value, "")

    def test_nonblank_values_and_defaults_are_preserved(self):
        resource_id = uuid4()
        parent_id = uuid4()
        model = PermissionRequest(
            _id=str(resource_id), parent_id=parent_id, resource_name=" menu "
        )
        self.assertEqual(model.id, resource_id)
        self.assertEqual(model.parent_id, parent_id)
        self.assertEqual(model.resource_name, " menu ")
        self.assertIsNone(PermissionRequest(resource_name="menu").id)

    def test_global_conversion_keeps_non_string_values(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return True

            text: str | None
            count: int | None
            flag: bool
            items: list[str]

        model = Request(text="\t", count="", flag=False, items=[""])
        self.assertIsNone(model.text)
        self.assertIsNone(model.count)
        self.assertIs(model.flag, False)
        self.assertEqual(model.items, [""])
        self.assertEqual(Request(text=None, count=0, flag=True, items=[]).count, 0)

    def test_conversion_does_not_make_required_fields_optional(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return True

            text: str

        with self.assertRaises(ValidationError) as raised:
            Request(text="")
        self.assertEqual(raised.exception.errors()[0]["type"], "string_type")

    def test_custom_messages_cover_constraints_and_missing_fields(self):
        cases = (
            ({}, "missing"),
            ({"resource_name": ""}, "string_too_short"),
            ({"resource_name": "a" * 129}, "string_too_long"),
        )
        for values, error_type in cases:
            with self.subTest(error_type=error_type):
                with self.assertRaises(ValidationError) as raised:
                    PermissionRequest(**values)
                error = raised.exception.errors()[0]
                self.assertEqual(error["loc"], ("resource_name",))
                self.assertEqual(error["type"], error_type)
                self.assertEqual(error["msg"], PermissionRequest.get_field_errors()[1].error_message)

    def test_custom_message_uses_python_name_for_aliases(self):
        for alias in ("_id", "id"):
            with self.subTest(alias=alias):
                with self.assertRaises(ValidationError) as raised:
                    PermissionRequest.model_validate({alias: "bad", "resource_name": "menu"})
                error = raised.exception.errors()[0]
                self.assertEqual(error["loc"], (alias,))
                self.assertEqual(error["input"], "bad")
                self.assertEqual(error["msg"], "资源 ID 格式不正确")

    def test_alias_paths_and_location_by_name(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return {"id"}

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", error_message="invalid id")]

            id: UUID | None = Field(validation_alias=AliasPath("payload", 0, "id"))

        self.assertIsNone(Request.model_validate({"payload": [{"id": " "}]}).id)
        for values in ({}, {"payload": [{"id": "bad"}]}):
            with self.assertRaises(ValidationError) as raised:
                Request.model_validate(values)
            self.assertEqual(raised.exception.errors()[0]["msg"], "invalid id")

        class ByNameRequest(Request):
            model_config = ConfigDict(loc_by_alias=False)

        with self.assertRaises(ValidationError) as raised:
            ByNameRequest.model_validate({"payload": [{"id": "bad"}]})
        self.assertEqual(raised.exception.errors()[0]["loc"], ("id",))
        self.assertEqual(raised.exception.errors()[0]["msg"], "invalid id")

    def test_plain_alias_and_missing_alias_choices(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", error_message="invalid id")]

            id: UUID = Field(alias="_id")

        for values in ({}, {"_id": "bad"}):
            with self.assertRaises(ValidationError) as raised:
                Request.model_validate(values)
            self.assertEqual(raised.exception.errors()[0]["loc"], ("_id",))
            self.assertEqual(raised.exception.errors()[0]["msg"], "invalid id")

        class ChoiceRequest(Request):
            id: UUID = Field(validation_alias=AliasChoices("_id", "id"))

        with self.assertRaises(ValidationError) as raised:
            ChoiceRequest()
        self.assertEqual(raised.exception.errors()[0]["msg"], "invalid id")

    def test_business_exception_factory_receives_error_details(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [
                    FieldErrorConfig(field_name="id", func=lambda error: BizError(
                        error_code=ErrorCode.PARAM_VALUE_INVALID,
                        message="资源 ID 格式不正确",
                        data={"field": error["loc"][0], "value": error["input"]},
                    )),
                ]

            id: UUID

        with self.assertRaises(BizError) as raised:
            Request(id="bad")
        self.assertEqual(raised.exception.code, ErrorCode.PARAM_VALUE_INVALID.value)
        self.assertEqual(raised.exception.data, {"field": "id", "value": "bad"})
        self.assertIsInstance(raised.exception.__cause__, ValidationError)

    def test_factory_handles_missing_fields(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", func=lambda error: BizError(message=error["type"]))]

            id: UUID

        with self.assertRaises(BizError) as raised:
            Request()
        self.assertEqual(raised.exception.message, "missing")

    def test_other_errors_are_preserved_when_messages_are_changed(self):
        with self.assertRaises(ValidationError) as raised:
            PermissionRequest(resource_name="", parent_id="bad", extra="forbidden")
        errors = raised.exception.errors()
        self.assertEqual(len(errors), 3)
        by_field = {error["loc"][0]: error for error in errors}
        self.assertEqual(by_field["parent_id"]["type"], "uuid_parsing")
        self.assertIn("uuid_parsing", by_field["parent_id"]["url"])
        self.assertEqual(by_field["extra"]["type"], "extra_forbidden")
        self.assertEqual(by_field["resource_name"]["ctx"], {"min_length": 1})

    def test_unmapped_errors_are_reraised_without_changes(self):
        with self.assertRaises(ValidationError) as raised:
            PermissionRequest(resource_name="menu", parent_id="bad")
        error = raised.exception.errors()[0]
        self.assertEqual(error["type"], "uuid_parsing")
        self.assertIn("url", error)

    def test_subclass_validators_and_custom_error_codes_are_preserved(self):
        class Request(PermissionRequest):
            @field_validator("resource_name")
            @classmethod
            def validate_resource_name(cls, value: str) -> str:
                if not value.strip():
                    raise ValueError("resource_name must not be blank")
                return value.strip()

            @field_validator("resource_value")
            @classmethod
            def validate_resource_value(cls, value: str) -> str:
                if value == "bad":
                    raise PydanticCustomError("invalid_resource", "invalid resource value")
                return value

        with self.assertRaises(ValidationError) as raised:
            Request(resource_name=" ", resource_value="bad")
        errors = raised.exception.errors()
        self.assertEqual(errors[0]["msg"], Request.get_field_errors()[1].error_message)
        self.assertEqual(errors[1]["type"], "invalid_resource")
        self.assertEqual(errors[1]["msg"], "invalid resource value")
        self.assertEqual(Request(resource_name=" menu ").resource_name, "menu")

    def test_config_is_inherited_and_can_be_overridden(self):
        class ChildRequest(PermissionRequest):
            pass

        class DisabledRequest(PermissionRequest):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return False

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return []

        self.assertIsNone(ChildRequest(id="", resource_name="menu").id)
        with self.assertRaises(ValidationError) as raised:
            DisabledRequest(id="", resource_name="menu")
        self.assertEqual(raised.exception.errors()[0]["type"], "uuid_parsing")
        self.assertNotEqual(raised.exception.errors()[0]["msg"], PermissionRequest.get_field_errors()[0].error_message)

    def test_configuration_is_not_a_model_field(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return True
            text: str | None = None

        self.assertEqual(Request(text="").model_dump(), {"text": None})
        self.assertEqual(set(Request.model_json_schema()["properties"]), {"text"})

    def test_dictionary_access_and_extra_allow_are_unchanged(self):
        class Request(BaseModelEnhance):
            text: str = "value"

        model = Request(extra=1)
        self.assertEqual(model["text"], "value")
        self.assertEqual(model.get("text"), "value")
        self.assertEqual(model.get("missing", "fallback"), "fallback")
        with self.assertRaises(KeyError):
            model["extra"]
        self.assertEqual(model.model_dump(), {"text": "value", "extra": 1})

    def test_json_validation_and_type_adapter(self):
        model = PermissionRequest.model_validate_json('{"_id": "", "resource_name": "menu"}')
        self.assertIsNone(model.id)
        with self.assertRaises(ValidationError) as raised:
            PermissionRequest.model_validate_json('{"resource_name": ""}')
        self.assertEqual(raised.exception.errors()[0]["msg"], PermissionRequest.get_field_errors()[1].error_message)
        model = TypeAdapter(PermissionRequest).validate_python({"id": " ", "resource_name": "menu"})
        self.assertIsNone(model.id)

    def test_nested_models_keep_error_locations(self):
        class Request(BaseModelEnhance):
            permission: PermissionRequest

        with self.assertRaises(ValidationError) as raised:
            Request(permission={"resource_name": ""})
        self.assertEqual(raised.exception.errors()[0]["loc"], ("permission", "resource_name"))

    def test_validated_assignment_and_defaults(self):
        class Request(BaseModelEnhance):
            model_config = ConfigDict(validate_assignment=True, validate_default=True)

            @classmethod
            def get_empty_str_to_none(cls) -> bool | set[str]:
                return {"id"}

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", error_message="invalid id")]

            id: UUID | None = ""

        model = Request()
        self.assertIsNone(model.id)
        model.id = " "
        self.assertIsNone(model.id)
        with self.assertRaises(ValidationError) as raised:
            model.id = "bad"
        self.assertEqual(raised.exception.errors()[0]["msg"], "invalid id")

    def test_hide_input_in_errors_is_preserved(self):
        class Request(BaseModelEnhance):
            model_config = ConfigDict(hide_input_in_errors=True)

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", error_message="invalid id")]

            id: UUID

        with self.assertRaises(ValidationError) as raised:
            Request(id="sensitive input")
        self.assertNotIn("sensitive input", str(raised.exception))

    def test_custom_error_with_builtin_code_keeps_its_message(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="name", error_message="invalid name")]

            name: str = Field(min_length=1)
            count: int

            @field_validator("count")
            @classmethod
            def validate_count(cls, value: int) -> int:
                raise PydanticCustomError("int_parsing", "custom count error")

        with self.assertRaises(ValidationError) as raised:
            Request(name="", count=1)
        self.assertEqual(raised.exception.errors()[1]["msg"], "custom count error")

    def test_error_message_can_use_constraint_context(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="name", error_message="at least {min_length} characters")]

            name: str = Field(min_length=2)

        with self.assertRaises(ValidationError) as raised:
            Request(name="a")
        self.assertEqual(raised.exception.errors()[0]["msg"], "at least 2 characters")

    def test_first_factory_exception_stops_error_aggregation(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [
                    FieldErrorConfig(field_name="second", func=lambda error: BizError(message="second")),
                    FieldErrorConfig(field_name="first", func=lambda error: BizError(message="first")),
                ]

            first: int
            second: int

        with self.assertRaises(BizError) as raised:
            Request(first="bad", second="bad")
        self.assertEqual(raised.exception.message, "first")

    def test_factory_value_error_follows_pydantic_behavior(self):
        class Request(BaseModelEnhance):

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", func=lambda error: ValueError("invalid id"))]

            id: UUID

        with self.assertRaises(ValidationError) as raised:
            Request(id="bad")
        self.assertEqual(raised.exception.errors()[0]["type"], "value_error")
        self.assertIn("invalid id", raised.exception.errors()[0]["msg"])

    def test_extra_field_with_same_name_as_aliased_field_is_not_customized(self):
        class Request(BaseModelEnhance):
            model_config = ConfigDict(extra="forbid")

            @classmethod
            def get_field_errors(cls) -> list[FieldErrorConfig]:
                return [FieldErrorConfig(field_name="id", error_message="invalid id")]

            id: UUID = Field(alias="_id")

        with self.assertRaises(ValidationError) as raised:
            Request(_id=uuid4(), id="bad")
        self.assertEqual(raised.exception.errors()[0]["type"], "extra_forbidden")
        self.assertNotEqual(raised.exception.errors()[0]["msg"], "invalid id")


if __name__ == "__main__":
    unittest.main()
