import json
import os
from typing import Literal, Any, Callable

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):

    @classmethod
    def get_env_prefix(cls) -> str:
        """环境变量统一前缀"""
        return ""

    @classmethod
    def get_nested_delimiter(cls) -> str:
        """嵌套配置分隔符"""
        return "__"

    @classmethod
    def get_env_file_list(cls) -> list[str]:
        """默认加载的环境文件"""
        return [".env", ".env.local", ".env.dev", ".env.test", ".env.staging", ".env.prod"]

    @classmethod
    def get_case_sensitive(cls) -> bool:
        """环境变量名大小写策略：True=全大写，False=全小写"""
        return True

    @classmethod
    def get_extra_policy(cls) -> Literal["ignore", "forbid", "allow"]:
        """
        可重写：多余字段处理策略
        ignore: 忽略未知环境变量（默认）
        forbid: 存在未知字段直接抛校验异常
        allow: 保留未知字段到实例
        """
        return "ignore"

    @classmethod
    def build_model_config(cls) -> SettingsConfigDict:
        """配置模型行为"""
        return SettingsConfigDict(
            env_file_encoding="utf-8",
            env_file=cls.get_env_file_list(),
            env_prefix=cls.get_env_prefix(),
            # 始终使用严格大小写匹配，字段名映射由 __init_subclass__ 注入 alias 控制
            case_sensitive=True,
            populate_by_name=True,
            env_nested_delimiter=cls.get_nested_delimiter(),
            extra=cls.get_extra_policy(),
        )

    @staticmethod
    def env_field(
            # 环境变量名称
            alias: str | None = None,
            *,
            # 默认值
            default: Any = ...,
            # 动态默认值工厂（与 default 互斥）
            default_factory: Callable[[], Any] | Callable[[dict[str, Any]], Any] | None = None,
            # 初始化后是否写入系统环境变量（仅当该 key 不存在时）
            os_env: bool = False,
            # 写入系统环境变量时是否覆盖已有值
            os_env_override: bool = False,
            # 其余自定义 Field 参数
            **kwargs,
    ) -> Any:
        """
        环境变量专用 Field 封装
        :param default: 默认值，不传 = ... 代表该环境变量必填
        :param alias: 环境变量名称
        :param default_factory: 无参函数，动态生成默认值，和 default 不能同时使用
        :param os_env: 初始化后是否写入系统环境变量
        :param os_env_override: 写入系统环境变量时是否覆盖已有值
        :param kwargs: 透传其余 Field 原生参数
        """
        # 互斥校验：default 和 default_factory 不能同时提供
        if default is not ... and default_factory is not None:
            raise ValueError("default and default_factory cannot be used together")

        if alias is not None:
            kwargs["alias"] = alias

        # 将自定义行为放到 json_schema_extra，便于在 model_post_init 中读取
        json_schema_extra = kwargs.get("json_schema_extra")
        if json_schema_extra is None:
            json_schema_extra = {}
        json_schema_extra["os_env"] = os_env
        json_schema_extra["os_env_override"] = os_env_override
        kwargs["json_schema_extra"] = json_schema_extra

        if default is not ...:
            kwargs["default"] = default
        if default_factory is not None:
            kwargs["default_factory"] = default_factory

        return Field(**kwargs)

    @staticmethod
    def _to_env_str(value: Any) -> str:
        """将 Python 值序列化为可写入 os.environ 的字符串"""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple, dict, set)):
            normalized = list(value) if isinstance(value, set) else value
            return json.dumps(normalized, ensure_ascii=False)
        return "" if value is None else str(value)

    def model_post_init(self, __context: Any) -> None:
        """将标记了 os_env=True 的字段写入系统环境变量"""
        for field_name, field in self.__class__.model_fields.items():
            extra = field.json_schema_extra or {}
            if not extra.get("os_env"):
                continue

            env_key = field.alias or field_name
            env_value = self._to_env_str(getattr(self, field_name))
            if extra.get("os_env_override"):
                os.environ[str(env_key)] = env_value
            else:
                os.environ.setdefault(str(env_key), env_value)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """子类自动注入 model_config，并按策略生成严格大小写环境变量映射"""
        super().__pydantic_init_subclass__(**kwargs)
        cls.model_config = cls.build_model_config()

        # 严格映射 get_case_sensitive 函数：True -> HOST, False -> host；显式 alias 的字段不做覆盖
        for field_name, field in cls.model_fields.items():
            if field.alias is not None or field.validation_alias is not None:
                continue

            field_part = field_name.upper() if cls.get_case_sensitive() else field_name.lower()
            env_name = f"{cls.get_env_prefix()}{field_part}"
            field.alias = env_name
            field.validation_alias = env_name

        cls.model_rebuild(force=True)

